"""
Created on 2025-05-27

@author: wf
"""
from dataclasses import dataclass
import glob
import re
import time
from pathlib import Path

import requests
from lodstorage.sparql import SPARQL
from ngwidgets.persistent_log import Log
from ngwidgets.shell import Shell
from tqdm import tqdm

@dataclass
class ServerConfig:
    name: str
    container_name: str
    image: str
    port: int
    protocol: str = "http"
    host:str="localhost"
    base_url: str = None
    status_url: str = ""
    sparql_url: str = ""
    data_dir: str = ""
    dump_dir: str = ""
    docker_run_command: str = ""

    def __post_init__(self):
        if self.base_url is None:
            self.base_url = f"{self.protocol}://{self.host}:{self.port}"

class SparqlServer:
    """
    Base class for dockerized SPARQL servers
    """

    def __init__(
        self,
        config:ServerConfig,
        log: Log = None,
        shell: Shell = None,
        debug: bool = False,

    ):
        """
        Initialize the SPARQL server manager.

        """
        if log is None:
            log = Log()
        self.log = log
        self.config=config
        self.name=self.config.name
        self.debug = debug

        if shell is None:
            shell = Shell()
        self.shell = shell

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

    def run_shell_command(
        self, command: str, success_msg: str = None, error_msg: str = None
    ) -> bool:
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
            result = self.shell.run(command, debug=self.debug)
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
            self.log.log(
                "❌", container_name, f"Exception running command '{command}': {e}"
            )
            command_success = False
        return command_success

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
            pbar = tqdm(
                total=timeout, desc=f"Waiting for {server_name}", unit="s"
            )

        ready_status = False
        for i in range(timeout):
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
        running_cmd = (
            f'docker ps --filter "name={self.config.container_name}" --format "{{{{.Names}}}}"'
        )
        result = self.shell.run(running_cmd, debug=self.debug)
        is_container_running = self.config.container_name in result.stdout
        return is_container_running

    def exists(self) -> bool:
        """
        Check if container exists (running or stopped).

        Returns:
            True if container exists
        """
        container_name=self.config.container_name
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
        stop_cmd = f"docker stop {self.container_name}"
        stop_success = self._run_shell_command(
            stop_cmd,
            success_msg=f"Stopped container {self.container_name}",
            error_msg=f"Failed to stop container {self.container_name}",
        )
        return stop_success

@dataclass
class BlazegraphConfig(ServerConfig):
    """
    Blazegraph configuration
    """
    def __post_init__(self):
        super().__post_init__()
        blazegraph_base = f"{self.base_url}/bigdata"
        self.status_url = f"{blazegraph_base}/status"
        self.sparql_url = f"{blazegraph_base}/namespace/kb/sparql"
        self.dataloader_url = f"{blazegraph_base}/dataloader"
        self.docker_run_command = f"docker run -d --name {self.container_name} -p {self.port}:8080 {self.image}"

class Blazegraph(SparqlServer):
    """
    Dockerized Blazegraph SPARQL server
    """

    def __init__(
        self,
        config:ServerConfig,
        log: Log = None,
        shell: Shell = None,
        debug: bool = False,
    ):
        """
        Initialize the Blazegraph manager.

        Args:
            log: Log instance for logging
            shell: Shell instance for Docker commands
            debug: Enable debug output
        """
        super().__init__(config=config, log=log, shell=shell, debug=debug)
        self.dataloader_url = f"{self.config.base_url}/dataloader"

    def status(self) -> dict:
        """
        Get Blazegraph status information.

        Returns:
            Dictionary with status information, empty dict if error
        """
        status_dict = {}

        result = self._make_request("GET", self.config.status_url, timeout=2)

        if result["success"]:
            status_dict["status"] = "ready"
            html_content = result["content"]
            name_value_pattern = r'(?:<span id="(?P<name1>[^"]+)">(?P<value1>[^<]+)</span[^>]*>|&#47;(?P<name2>[^=]+)=(?P<value2>[^\s&#]+))'
            matches = re.finditer(name_value_pattern, html_content, re.DOTALL)

            for match in matches:
                for name_group, value_group in {
                    "name1": "value1",
                    "name2": "value2",
                }.items():
                    name = match.group(name_group)
                    if name:
                        value = match.group(value_group)
                        sanitized_value = value.replace("</p", "").replace("&#47;", "/")
                        sanitized_name = name.replace("-", "_").replace("/", "_")
                        sanitized_name = sanitized_name.replace("&#47;", "/")
                        if not sanitized_name.startswith("/"):
                            status_dict[sanitized_name] = sanitized_value
                        break
        else:
            if result.get("error"):
                status_dict["status"] = f"error: {result['error']}"
            else:
                status_dict["status"] = f"status_code: {result['status_code']}"

        return status_dict

    def load_file(self, filepath: str) -> bool:
        """
        Load a single RDF file into Blazegraph.

        Args:
            filepath: Path to RDF file

        Returns:
            True if loaded successfully
        """
        load_success = False
        try:
            with open(filepath, "rb") as f:
                result = self._make_request(
                    "POST",
                    self.config.sparql_url,
                    headers={"Content-Type": "text/turtle"},
                    data=f.read(),
                    timeout=300,
                )

            if result["success"]:
                self.log.log("✅", self.name, f"Loaded {filepath}")
                load_success = True
            else:
                error_msg = result.get("error", f"HTTP {result['status_code']}")
                self.log.log(
                    "❌", self.name, f"Failed to load {filepath}: {error_msg}"
                )
                load_success = False

        except Exception as e:
            self.log.log(
                "❌", self.name, f"Exception loading {filepath}: {e}"
            )
            load_success = False

        return load_success

    def load_files_bulk(self, file_list: list) -> bool:
        """
        Load multiple files using Blazegraph's bulk loader REST API.

        Args:
            file_list: List of file paths to load

        Returns:
            True if loaded successfully
        """
        bulk_load_success = False

        if not file_list:
            bulk_load_success = False
        else:
            # Convert to absolute paths
            abs_paths = [str(Path(f).absolute()) for f in file_list]

            properties = f"""<?xml version="1.0" encoding="UTF-8"?>
            <properties>
                <entry key="format">turtle</entry>
                <entry key="quiet">false</entry>
                <entry key="verbose">1</entry>
                <entry key="namespace">kb</entry>
                <entry key="fileOrDirs">{','.join(abs_paths)}</entry>
            </properties>"""

            result = self._make_request(
                "POST",
                self.dataloader_url,
                headers={"Content-Type": "application/xml"},
                data=properties,
                timeout=3600,
            )

            if result["success"]:
                self.log.log(
                    "✅", self.container_name, f"Bulk loaded {len(file_list)} files"
                )
                bulk_load_success = True
            else:
                error_msg = result.get("error", f"HTTP {result['status_code']}")
                self.log.log(
                    "❌", self.container_name, f"Bulk load failed: {error_msg}"
                )
                bulk_load_success = False

        return bulk_load_success

    def load_dump_files(
        self, file_pattern: str = "dump_*.ttl", use_bulk: bool = True
    ) -> int:
        """
        Load all dump files matching pattern.

        Args:
            file_pattern: Glob pattern for dump files
            use_bulk: Use bulk loader if True, individual files if False

        Returns:
            Number of files loaded successfully
        """
        files = sorted(glob.glob(file_pattern))
        loaded_count = 0

        if not files:
            self.log.log(
                "⚠️",
                self.container_name,
                f"No files found matching pattern: {file_pattern}",
            )
            loaded_count = 0
        else:
            self.log.log("✅", self.container_name, f"Found {len(files)} files to load")

            if use_bulk:
                bulk_result = self.load_files_bulk(files)
                loaded_count = len(files) if bulk_result else 0
            else:
                loaded_count = 0
                for filepath in tqdm(files, desc="Loading files"):
                    file_result = self.load_file(filepath)
                    if file_result:
                        loaded_count += 1
                    else:
                        self.log.log(
                            "❌", self.container_name, f"Failed to load: {filepath}"
                        )

        return loaded_count

    def test_geosparql(self) -> bool:
        """
        Test if GeoSPARQL functions work.

        Returns:
            True if GeoSPARQL is available
        """
        test_query = """
        PREFIX geo: <http://www.opengis.net/ont/geosparql#>
        PREFIX geof: <http://www.opengis.net/def/function/geosparql/>

        SELECT * WHERE {
            BIND(geof:distance("POINT(0 0)"^^geo:wktLiteral, "POINT(1 1)"^^geo:wktLiteral) AS ?dist)
        } LIMIT 1
        """

        result = self._make_request(
            "POST",
            self.sparql_url,
            data={"query": test_query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=10,
        )

        geosparql_available = result["success"]
        return geosparql_available

@dataclass
class QLeverConfig(ServerConfig):
    def __post_init__(self):
        super().__post_init__()
        self.status_url = f"{self.base_url}/status"
        self.sparql_url = f"{self.base_url}/api/sparql"
        self.docker_run_command = f"docker run -d --name {self.container_name} -e UID=$(id -u) -e GID=$(id -g) -v {self.data_dir}:/data -w /data -p {self.port}:7001 {self.image}"

class QLever(SparqlServer):
    """
    Dockerized QLever SPARQL server
    """

    def __init__(
        self,
        container_name: str = "qlever",
        image: str = "adfreiburg/qlever",
        data_dir: str = None,
        dataset: str = "olympics",
        port: int = 7001,
        log: Log = None,
        shell: Shell = None,
        debug: bool = False,
    ):
        """
        Initialize the QLever manager.

        Args:
            container_name: Docker container name
            image: Docker image to use
            port: Port for QLever web interface
            data_dir: where to keep the data
            dataset(str): a default dataset to be loaded
            log: Log instance for logging
            shell: Shell instance for Docker commands
            debug: Enable debug output
        """
        if not data_dir:
            raise ValueError("Data directory needs to be specified")
        self.data_dir = data_dir
        self.dataset = dataset
        super().__init__(container_name, image, port, log, shell, debug)

    def start(self, show_progress: bool = True) -> bool:
        """
        Start QLever using proper workflow.
        """
        # Use base class start to get container running
        started = super().start(show_progress=show_progress)
        if started and self.dataset:
            # Run QLever setup workflow
            setup_cmd = (
                f"docker exec {self.container_name} qlever setup-config {self.dataset}"
            )
            self._run_shell_command(setup_cmd)

            get_data_cmd = f"docker exec {self.container_name} qlever get-data"
            self._run_shell_command(get_data_cmd)

            index_cmd = f"docker exec {self.container_name} qlever index"
            self._run_shell_command(index_cmd)

            start_cmd = f"docker exec {self.container_name} qlever start"
            self._run_shell_command(start_cmd)

        return started

    def status(self) -> dict:
        """
        Get QLever status information.

        Returns:
            Dictionary with status information, empty dict if error
        """
        status_dict = {}
        result = self._make_request("GET", self.status_url, timeout=2)

        if result["success"]:
            status_dict["status"] = "ready"
            try:
                import json

                status_data = json.loads(result["content"])
                status_dict.update(status_data)
            except json.JSONDecodeError:
                status_dict["raw_content"] = result["content"]
        else:
            if result.get("error"):
                status_dict["status"] = f"error: {result['error']}"
            else:
                status_dict["status"] = f"status_code: {result['status_code']}"

        return status_dict

    def load_file(self, filepath: str) -> bool:
        """
        Load a single RDF file into QLever.

        Args:
            filepath: Path to RDF file

        Returns:
            True if loaded successfully
        """
        load_success = False
        try:
            with open(filepath, "rb") as f:
                result = self._make_request(
                    "POST",
                    f"{self.base_url}/api/upload",
                    files={"file": f},
                    timeout=300,
                )

            if result["success"]:
                self.log.log("✅", self.container_name, f"Loaded {filepath}")
                load_success = True
            else:
                error_msg = result.get("error", f"HTTP {result['status_code']}")
                self.log.log(
                    "❌", self.container_name, f"Failed to load {filepath}: {error_msg}"
                )
                load_success = False

        except Exception as e:
            self.log.log(
                "❌", self.container_name, f"Exception loading {filepath}: {e}"
            )
            load_success = False

        return load_success

    def load_dump_files(
        self, file_pattern: str = "dump_*.ttl", use_bulk: bool = True
    ) -> int:
        """
        Load all dump files matching pattern.

        Args:
            file_pattern: Glob pattern for dump files
            use_bulk: Use bulk loader if True, individual files if False

        Returns:
            Number of files loaded successfully
        """
        files = sorted(glob.glob(file_pattern))
        loaded_count = 0

        if not files:
            self.log.log(
                "⚠️",
                self.container_name,
                f"No files found matching pattern: {file_pattern}",
            )
            loaded_count = 0
        else:
            self.log.log("✅", self.container_name, f"Found {len(files)} files to load")

            # QLever typically loads files individually
            loaded_count = 0
            for filepath in tqdm(files, desc="Loading files"):
                file_result = self.load_file(filepath)
                if file_result:
                    loaded_count += 1
                else:
                    self.log.log(
                        "❌", self.container_name, f"Failed to load: {filepath}"
                    )

        return loaded_count
