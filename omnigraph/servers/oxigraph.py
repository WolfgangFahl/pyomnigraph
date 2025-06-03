"""
Created on 2025-06-03

Oxigraph SPARQL support

@author: wf
"""

from dataclasses import dataclass

from omnigraph.server_config import ServerLifecycleState, ServerStatus
from omnigraph.sparql_server import ServerConfig, ServerEnv, SparqlServer


@dataclass
class OxigraphConfig(ServerConfig):
    """
    Oxigraph configuration
    """

    def __post_init__(self):
        """
        configure the configuration
        """
        super().__post_init__()

        # Clean URLs without credentials
        self.status_url = f"{self.base_url}/"
        self.sparql_url = f"{self.base_url}/query"
        self.update_url = f"{self.base_url}/update"
        self.upload_url = f"{self.base_url}/store"
        self.web_url = f"{self.base_url}/"

    def get_docker_run_command(self, data_dir) -> str:
        """
        Generate docker run command with bind mount for data directory.

        Args:
            data_dir: Host directory path to bind mount to container

        Returns:
            Complete docker run command string
        """
        docker_run_command = (
            f"docker run {self.docker_user_flag} -d --name {self.container_name} "
            f"-p {self.port}:7878 "
            f"-v {data_dir}:/data "
            f"{self.image} --bind 0.0.0.0:7878 /data"
        )
        return docker_run_command


class Oxigraph(SparqlServer):
    """
    Dockerized Oxigraph SPARQL server
    """

    def __init__(self, config: ServerConfig, env: ServerEnv):
        """
        Initialize the Oxigraph manager.

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

        if logs and "Listening for requests at" in logs:
            server_status.at = ServerLifecycleState.READY
        else:
            server_status.at = ServerLifecycleState.STARTING

        return server_status