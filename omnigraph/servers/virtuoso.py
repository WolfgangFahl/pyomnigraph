"""
Created on 2025-06-03

OpenLink Virtuoso SPARQL support

@author: wf
"""

from dataclasses import dataclass

from omnigraph.server_config import ServerLifecycleState, ServerStatus
from omnigraph.sparql_server import ServerConfig, ServerEnv, SparqlServer


@dataclass
class VirtuosoConfig(ServerConfig):
    """
    Virtuoso configuration
    """

    def __post_init__(self):
        """
        configure the configuration
        """
        super().__post_init__()

        # Clean URLs without credentials
        self.status_url = f"{self.base_url}/sparql"
        self.sparql_url = f"{self.base_url}/sparql"
        self.update_url = f"{self.base_url}/sparql"
        self.upload_url = f"{self.base_url}/sparql-graph-crud"
        self.web_url = f"{self.base_url}/conductor"

    def get_docker_run_command(self, data_dir) -> str:
        """
        Generate docker run command with bind mount for data directory.

        Args:
            data_dir: Host directory path to bind mount to container

        Returns:
            Complete docker run command string
        """
        # Docker command setup
        env = ""
        if self.auth_password:
            env = f"-e DBA_PASSWORD={self.auth_password}"

        docker_run_command = (
            f"docker run {self.docker_user_flag} {env} -d --name {self.container_name} "
            f"-p {self.port}:8890 "
            f"-v {data_dir}:/database "
            f"{self.image}"
        )
        return docker_run_command


class Virtuoso(SparqlServer):
    """
    Dockerized OpenLink Virtuoso SPARQL server
    """

    def __init__(self, config: ServerConfig, env: ServerEnv):
        """
        Initialize the Virtuoso manager.

        Args:
            config: Server configuration
            env: Server environment (includes log, shell, debug, verbose)
        """
        super().__init__(config=config, env=env)

    def status(self) -> ServerStatus:
        """
        Get server status information.

        Returns:
            ServerStatus object with status information
        """
        server_status = super().status()
        logs = server_status.logs

        if logs and "Server online at" in logs and "HTTP/WebDAV server online at" in logs:
            server_status.at = ServerLifecycleState.READY
        else:
            server_status.at = ServerLifecycleState.STARTING

        return server_status
