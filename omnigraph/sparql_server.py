"""
Created on 2025-05-27

@author: wf
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Optional

import requests
from lodstorage.sparql import SPARQL
from tqdm import tqdm

from omnigraph.persistent_log import Log
from omnigraph.shell import Shell
from omnigraph.yamlable import lod_storable


@dataclass
class ServerConfig:
    server: str
    name: str
    container_name: str
    image: str
    port: int
    active: bool = True
    protocol: str = "http"
    host: str = "localhost"
    # fields to be configured by post_init
    base_url: Optional[str] = field(default=None)
    status_url: Optional[str] = field(default=None)
    sparql_url: Optional[str] = field(default=None)
    data_dir: Optional[str] = field(default=None)
    dump_dir: Optional[str] = field(default=None)
    docker_run_command: Optional[str] = field(default=None)

    def __post_init__(self):
        if self.base_url is None:
            self.base_url = f"{self.protocol}://{self.host}:{self.port}"


@lod_storable
class ServerConfigs:
    """Collection of server configurations loaded from YAML."""

    servers: Dict[str, ServerConfig] = field(default_factory=dict)

    @classmethod
    def ofYaml(cls, yaml_path: str) -> "ServerConfigs":
        """Load server configurations from YAML file."""
        server_configs = cls.load_from_yaml_file(yaml_path)
        return server_configs


class SparqlServer:
    """
    Base class for dockerized SPARQL servers
    """

    def __init__(
        self,
        config: ServerConfig,
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
        self.config = config
        self.name = self.config.name
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
            self.log.log("❌", container_name, f"Exception running command '{command}': {e}")
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
            pbar = tqdm(total=timeout, desc=f"Waiting for {server_name}", unit="s")

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
        stop_cmd = f"docker stop {self.container_name}"
        stop_success = self._run_shell_command(
            stop_cmd,
            success_msg=f"Stopped container {self.container_name}",
            error_msg=f"Failed to stop container {self.container_name}",
        )
        return stop_success
