"""
Created on 2025-06-03

Stardog SPARQL support

@author: wf
"""

from dataclasses import dataclass

from omnigraph.server_config import ServerLifecycleState, ServerStatus
from omnigraph.sparql_server import ServerConfig, ServerEnv, SparqlServer


@dataclass
class StardogConfig(ServerConfig):
    """
    Stardog configuration
    """

    def __post_init__(self):
        """
        configure the configuration
        """
        super().__post_init__()

        # Clean URLs without credentials
        stardog_base = f"{self.base_url}/{self.dataset}"
        self.status_url = f"{self.base_url}/admin/status"
        self.sparql_url = f"{stardog_base}/query"
        self.update_url = f"{stardog_base}/update"
        self.upload_url = f"{stardog_base}/add"
        self.web_url = f"{self.base_url}/"

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
            env = f"-e STARDOG_SERVER_JAVA_ARGS='-Dstardog.default.cli.server=http://localhost:5820'"

        docker_run_command = (
            f"docker run {self.docker_user_flag} {env} -d --name {self.container_name} "
            f"-p {self.port}:5820 "
            f"-v {data_dir}:/var/opt/stardog "
            f"{self.image}"
        )
        return docker_run_command


class Stardog(SparqlServer):
    """
    Dockerized Stardog SPARQL server
    """

    def __init__(self, config: ServerConfig, env: ServerEnv):
        """
        Initialize the Stardog manager.

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

        if logs and "Stardog server started" in logs and "Server is ready" in logs:
            server_status.at = ServerLifecycleState.READY
        else:
            server_status.at = ServerLifecycleState.STARTING

        return server_status