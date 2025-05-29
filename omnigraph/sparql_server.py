"""
Created on 2025-05-27

@author: wf
"""

from pathlib import Path
import time
import webbrowser

from lodstorage.sparql import SPARQL
from omnigraph.server_config import ServerConfig, ServerEnv
import requests
from tqdm import tqdm
from omnigraph.software import SoftwareList


class SparqlServer:
    """
    Base class for dockerized SPARQL servers
    """

    def __init__(self, config: ServerConfig, env: ServerEnv):
        """
        Initialize the SPARQL server manager.

        """
        self.log = env.log
        self.config = config
        self.name = self.config.name
        self.debug = env.debug
        self.verbose = env.verbose
        self.shell = env.shell

        # Subclasses must set these URLs
        if self.config.sparql_url:
            self.sparql = SPARQL(self.config.sparql_url)

    def _make_request(self, method: str, url: str, timeout: int = 30, **kwargs) -> dict:
        """
        Helper function for making HTTP requests with consistent error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            timeout: Request timeout in seconds
            **kwargs: Additional arguments for requests

        Returns:
            Dictionary with 'success', 'status_code', 'content', and optional 'error'
        """
        request_result = {}
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
            request_result = {
                "success": response.status_code in [200, 204],
                "status_code": response.status_code,
                "content": response.text,
                "response": response,
            }
        except Exception as e:
            request_result = {
                "success": False,
                "status_code": None,
                "content": None,
                "error": str(e),
            }
        return request_result

    def run_shell_command(self, command: str, success_msg: str = None, error_msg: str = None) -> bool:
        """
        Helper function for running shell commands with consistent error handling.

        Args:
            command: Shell command to run
            success_msg: Message to log on success
            error_msg: Message to log on error

        Returns:
            True if command succeeded (returncode 0)
        """
        container_name = self.config.container_name
        command_success = False
        try:
            result = self.shell.run(command, debug=self.debug, tee=self.verbose)
            if result.returncode == 0:
                if success_msg:
                    self.log.log("✅", container_name, success_msg)
                command_success = True
            else:
                error_detail = error_msg or f"Command failed: {command}"
                if result.stderr:
                    error_detail += f" - {result.stderr}"
                self.log.log("❌", container_name, error_detail)
                command_success = False
        except Exception as e:
            self.log.log("❌", container_name, f"Exception running command '{command}': {e}")
            command_success = False
        return command_success

    def webui(self):
        """
        open my webui
        """
        webbrowser.open(self.config.web_url)

    def status(self) -> dict:
        """
        Get status information via SPARQL triple count.

        Returns:
            Dictionary with status info or error details.
        """
        status_dict = {}
        try:
            triple_count = self.count_triples()
            status_dict["status"] = "ready"
            status_dict["triples"] = triple_count
        except Exception as e:
            status_dict["status"] = "error"
            status_dict["error"] = str(e)
        return status_dict

    def start(self, show_progress: bool = True) -> bool:
        """
        Start SPARQL server in Docker container.

        Args:
            show_progress: Show progress bar while waiting

        Returns:
            True if started successfully
        """
        container_name = self.config.container_name
        server_name = self.config.name
        start_success = False
        try:
            if self.is_running():
                self.log.log(
                    "✅",
                    container_name,
                    f"Container {container_name} is already running",
                )
                start_success = self.wait_until_ready(show_progress=show_progress)
            elif self.exists():
                self.log.log(
                    "✅",
                    container_name,
                    f"Container {container_name} exists, starting...",
                )
                start_cmd = f"docker start {container_name}"
                start_result = self.run_shell_command(
                    start_cmd,
                    error_msg=f"Failed to start container {container_name}",
                )
                if start_result:
                    start_success = self.wait_until_ready(show_progress=show_progress)
                else:
                    start_success = False
            else:
                self.log.log(
                    "✅",
                    container_name,
                    f"Creating new {server_name} container {container_name}...",
                )
                create_cmd = self.config.docker_run_command
                create_result = self.run_shell_command(
                    create_cmd,
                    error_msg=f"Failed to create container {container_name}",
                )
                if create_result:
                    start_success = self.wait_until_ready(show_progress=show_progress)
                else:
                    start_success = False
        except Exception as e:
            self.log.log(
                "❌",
                container_name,
                f"Error starting {server_name}: {e}",
            )
            start_success = False
        return start_success

    def count_triples(self) -> int:
        """
        Count total triples in the SPARQL server.

        Returns:
            Number of triples
        """
        count_query = "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
        result = self.sparql.getValue(count_query, "count")
        triple_count = int(result) if result else 0
        return triple_count

    def wait_until_ready(self, timeout: int = 30, show_progress: bool = False) -> bool:
        """
        Wait for server to be ready.

        Args:
            timeout: Maximum seconds to wait
            show_progress: Show progress bar while waiting

        Returns:
            True if ready within timeout
        """
        container_name = self.config.container_name
        server_name = self.config.name
        status_url = self.config.status_url
        base_url = self.config.base_url

        self.log.log(
            "✅",
            container_name,
            f"Waiting for {server_name} to start ... {status_url}",
        )

        pbar = None
        if show_progress:
            pbar = tqdm(total=timeout, desc=f"Waiting for {server_name}", unit="s")

        ready_status = False
        for _i in range(timeout):
            status_dict = self.status()
            if status_dict.get("status") == "ready":
                if show_progress and pbar:
                    pbar.close()
                self.log.log(
                    "✅",
                    container_name,
                    f"{server_name} ready at {base_url}",
                )
                ready_status = True
                break

            if show_progress and pbar:
                pbar.update(1)
            time.sleep(1)

        if not ready_status:
            if show_progress and pbar:
                pbar.close()
            self.log.log(
                "⚠️",
                container_name,
                f"Timeout waiting for {server_name} to start after {timeout}s",
            )

        return ready_status

    def is_running(self) -> bool:
        """
        Check if container is currently running.

        Returns:
            True if container is running
        """
        running_cmd = f'docker ps --filter "name={self.config.container_name}" --format "{{{{.Names}}}}"'
        result = self.shell.run(running_cmd, debug=self.debug)
        is_container_running = self.config.container_name in result.stdout
        return is_container_running

    def exists(self) -> bool:
        """
        Check if container exists (running or stopped).

        Returns:
            True if container exists
        """
        container_name = self.config.container_name
        check_cmd = f'docker ps -a --filter "name={container_name}" --format "{{{{.Names}}}}"'
        result = self.shell.run(check_cmd, debug=self.debug)
        if result.stderr:
            self.log.log("❌", container_name, result.stderr)
        container_exists = container_name in result.stdout
        return container_exists

    def stop(self) -> bool:
        """
        Stop the server container.

        Returns:
            True if stopped successfully
        """
        container_name = self.config.container_name
        stop_cmd = f"docker stop {container_name}"
        stop_success = self.run_shell_command(
            stop_cmd,
            success_msg=f"Stopped container {container_name}",
            error_msg=f"Failed to stop container {container_name}",
        )
        return stop_success

    def clear(self) -> int:
        """
        delete all triples
        """
        container_name = self.config.container_name
        count_triples = self.count_triples()
        msg = f"deleting {count_triples} triples ..."
        if count_triples >= self.config.unforced_clear_limit:
            self.log.log("❌", container_name, f"{msg} needs force option")
        else:
            clear_query = "DELETE { ?s ?p ?o } WHERE { ?s ?p ?o }"
            self.sparql.insert(clear_query)
            count_triples = self.count_triples()
            self.log.log("✅", container_name, f"{msg}")
        return count_triples

    def upload_request(self, file_content: bytes) -> dict:
        """Default upload request for Blazegraph-style servers."""
        response= self._make_request(
            "POST",
            self.config.sparql_url,
            headers={"Content-Type": "text/turtle"},
            data=file_content,
            timeout=self.config.upload_timeout,
        )
        return response

    def load_file(self, filepath: str, upload_request=None) -> bool:
        """
        Load a single RDF file into the RDF server.

        Args:
            filepath: Path to RDF file
            upload_request_callback: Function that performs the upload request

        Returns:
            True if loaded successfully
        """
        container_name = self.config.container_name
        load_success = False

        if upload_request is None:
            upload_request_callback = self.upload_request

        try:
            with open(filepath, "rb") as f:
                file_content = f.read()

            result = upload_request_callback(file_content)

            if result["success"]:
                self.log.log("✅", container_name, f"Loaded {filepath}")
                load_success = True
            else:
                status_code = result['status_code']
                content = result['content']
                error_msg = result.get("error", f"HTTP {status_code} → {content}")
                self.log.log("❌", container_name, f"Failed to load {filepath}: {error_msg}")
                load_success = False

        except Exception as e:
            self.log.log("❌", container_name, f"Exception loading {filepath}: {e}")
            load_success = False

        return load_success

    def load_dump_files(self, file_pattern: str = "*.ttl") -> int:
        """
        Load all dump files matching pattern.

        Args:
            file_pattern: Glob pattern for dump files
            use_bulk: Use bulk loader if True, individual files if False

        Returns:
            Number of files loaded successfully
        """
        dump_path: Path = Path(self.config.dumps_dir)
        files = sorted(dump_path.glob(file_pattern))
        loaded_count = 0
        container_name = self.config.container_name

        if not files:
            self.log.log("⚠️", container_name, f"No files found matching pattern: {file_pattern}")
        else:
            self.log.log("✅", container_name, f"Found {len(files)} files to load")
            for filepath in tqdm(files, desc="Loading files"):
                file_result = self.load_file(filepath)
                if file_result:
                    loaded_count += 1
                else:
                    self.log.log("❌", container_name, f"Failed to load: {filepath}")

        return loaded_count

    def check_needed_software(self)->int:
        """
        Check if needed software for this server configuration is installed
        """
        container_name=self.config.container_name
        if self.config.needed_software is None:
            return
        software_list = SoftwareList.from_dict2(self.config.needed_software) # @UndefinedVariable
        missing=software_list.check_installed(self.log, self.shell, verbose=True)
        if missing>0:
            self.log.log("❌",container_name,"Please install the missing commands before running this script.")
        return missing