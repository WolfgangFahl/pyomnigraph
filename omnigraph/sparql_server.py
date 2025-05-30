"""
Created on 2025-05-27

@author: wf
"""

import time
import traceback
import webbrowser
from pathlib import Path

import requests
from lodstorage.sparql import SPARQL
from tqdm import tqdm

from omnigraph.server_config import ServerConfig, ServerEnv
from omnigraph.software import SoftwareList


class Response:
    """
    wrapper for responses including errors
    """

    @property
    def success(self) -> bool:
        if self.error is not None:
            return False
        if self.response is not None:
            return self.response.status_code in [200, 204]
        return False

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error


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
            is_fuseki = self.config.server == "jena"
            self.sparql = SPARQL(self.config.sparql_url, isFuseki=is_fuseki)
            if (
                hasattr(self.config, "auth_password")
                and self.config.auth_password
                and hasattr(self.config, "auth_user")
                and self.config.auth_user
            ):
                self.sparql.addAuthentication(self.config.auth_user, self.config.auth_password)

    @property
    def full_name(self):
        full_name = f"{self.name} {self.config.container_name}"
        return full_name

    def handle_exception(self, context: str, ex: Exception):
        """
        handle the given exception
        """
        container_name = self.config.container_name
        self.log.log("❌", container_name, f"Exception {context}: {ex}")
        if self.debug:
            traceback.print_exc()

    def make_request(self, method: str, url: str, **kwargs) -> Response:
        """
        Helper function for making HTTP requests with consistent error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments for requests

        Returns:
            Response
        """
        try:
            #  add auth if we have auth_password and auth_user
            if (
                hasattr(self.config, "auth_password")
                and self.config.auth_password
                and hasattr(self.config, "auth_user")
                and self.config.auth_user
            ):
                kwargs.setdefault("auth", (self.config.auth_user, self.config.auth_password))
            # for Jena Fuseki we do this via url
            # Only set timeout if not already provided
            kwargs.setdefault("timeout", self.config.timeout)
            response = requests.request(method, url, **kwargs)
            response = Response(response)
        except Exception as ex:
            self.handle_exception(f"request {url}", ex)
            response = Response(None, ex)
        return response

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
        except Exception as ex:
            self.handle_exception(f"command '{command}'", ex)
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
        except Exception as ex:
            self.handle_exception(f"starting {server_name}", ex)
            start_success = False
        return start_success

    def count_triples(self) -> int:
        """
        Count total triples in the SPARQL server.

        Returns:
            Number of triples
        """
        count_query = "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
        try:
            result = self.sparql.getValue(count_query, "count")
            triple_count = int(result) if result else 0
        except Exception as ex:
            self.handle_exception("count_triples", ex)
            triple_count = -1
        return triple_count

    def wait_until_ready(self, show_progress: bool = False) -> bool:
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
        timeout = self.config.ready_timeout

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

    def docker_cmd(self, cmd: str, options: str = "", args: str = "") -> str:
        """
        run the given docker commmand with the given options
        """
        container_name = self.config.container_name
        if options:
            options = f" {options}"
        if args:
            args = f" {args}"
        full_cmd = f"docker {cmd}{options} {container_name}{args}"
        return full_cmd

    def run_docker_cmd(self, cmd: str, options: str = "", args: str = "") -> bool:
        container_name = self.config.container_name
        full_cmd = self.docker_cmd(cmd, options, args)
        success = self.run_shell_command(
            full_cmd,
            success_msg=f"{cmd} container {container_name}",
            error_msg=f"Failed to {cmd} container {container_name}",
        )
        return success

    def logs(self) -> bool:
        """show the logs of the container"""
        logs_success = self.run_docker_cmd("logs")
        return logs_success

    def stop(self) -> bool:
        """stop the server container"""
        stop_success = self.run_docker_cmd("stop")
        return stop_success

    def rm(self) -> bool:
        """remove the server container."""
        rm_success = self.run_docker_cmd("rm")
        return rm_success

    def bash(self) -> bool:
        """bash into the server container."""
        bash_cmd = self.docker_cmd("exec", "-it", "/bin/bash")
        print(bash_cmd)
        return True

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
            try:
                self.sparql.insert(clear_query)
                new_count = self.count_triples()
                if new_count == 0:
                    self.log.log("✅", container_name, f"deleted {count_triples} triples")
                else:
                    self.log.log("❌", container_name, f"delete failed: {new_count} triples remain")
                count_triples = new_count
            except Exception as ex:
                self.handle_exception("clear triples", ex)
        return count_triples

    def upload_request(self, file_content: bytes) -> Response:
        """Default upload request for Blazegraph-style servers."""
        response = self.make_request(
            "POST",
            self.config.upload_url,
            headers={"Content-Type": "text/turtle"},
            data=file_content,
            timeout=self.config.upload_timeout,
        )
        return response

    def load_file(self, filepath: str, upload_request=None) -> bool:
        """
        Load a single RDF file into the RDF server.
        """
        container_name = self.config.container_name
        load_success = False

        if upload_request is None:
            upload_request_callback = self.upload_request
        else:
            upload_request_callback = upload_request

        try:
            with open(filepath, "rb") as f:
                file_content = f.read()

            response = upload_request_callback(file_content)

            if response.success:  # Changed from result["success"]
                self.log.log("✅", container_name, f"Loaded {filepath}")
                load_success = True
            else:
                if response.error:
                    error_msg = str(response.error)
                else:
                    status_code = response.response.status_code
                    content = response.response.text
                    error_msg = f"HTTP {status_code} → {content}"
                self.log.log("❌", container_name, f"Failed to load {filepath}: {error_msg}")
                load_success = False

        except Exception as ex:
            self.handle_exception(f"loading {filepath}", ex)
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

    def check_needed_software(self) -> int:
        """
        Check if needed software for this server configuration is installed
        """
        container_name = self.config.container_name
        if self.config.needed_software is None:
            return
        software_list = SoftwareList.from_dict2(self.config.needed_software)  # @UndefinedVariable
        missing = software_list.check_installed(self.log, self.shell, verbose=True)
        if missing > 0:
            self.log.log("❌", container_name, "Please install the missing commands before running this script.")
        return missing
