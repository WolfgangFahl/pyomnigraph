"""
Created on 2026-11-07

Tentris SPARQL support - see issue #66
https://docs.tentris.io/
https://docs.tentris.io/running_with_docker.html
https://docs.tentris.io/sparql_endpoints.html

@author: wf
"""

from dataclasses import dataclass
from pathlib import Path

from omnigraph.server_config import ServerLifecycleState, ServerStatus
from omnigraph.sparql_server import ServerConfig, ServerEnv, SparqlServer


@dataclass
class TentrisConfig(ServerConfig):
    """
    Tentris configuration
    """

    def __post_init__(self):
        """
        configure the configuration
        """
        super().__post_init__()
        # an ASK query answers 200 only once the store is serving queries
        self.status_url = f"{self.base_url}/sparql?query=ASK%7B%7D"
        self.sparql_url = f"{self.base_url}/sparql"
        self.update_url = f"{self.base_url}/update"
        # SPARQL 1.1 Graph Store HTTP Protocol - POST adds to the default graph
        self.upload_url = f"{self.base_url}/graph-store?default"
        self.web_url = f"{self.base_url}/ui"

    def get_docker_run_command(self, data_dir) -> str:
        """
        Generate docker run command with bind mount for data directory.

        The image entrypoint initializes /data only when it is empty, so the
        dataset directory - not the base data directory holding it - is the store.
        Without a mounted /config/tentris-license.toml the image runs under
        the Tentris non-commercial license.

        Args:
            data_dir: Host base data directory holding the dataset directories

        Returns:
            Complete docker run command string
        """
        store_dir = Path(data_dir) / self.dataset
        docker_run_command = (
            f"docker run {self.docker_options_flag}{self.docker_user_flag} -d --name {self.container_name} "
            f"-p {self.docker_bind}:{self.port}:9080 "
            f"-v {store_dir}:/data "
            f"{self.image}"
        )
        return docker_run_command


class Tentris(SparqlServer):
    """
    Dockerized Tentris SPARQL server
    """

    def __init__(self, config: ServerConfig, env: ServerEnv):
        """
        Initialize the Tentris manager.

        Args:
            config: Server configuration
            env: Server environment (includes log, shell, debug, verbose)
        """
        super().__init__(config=config, env=env)

    def pre_create(self):
        """
        Create the dataset store directory private to the user.

        Tentris refuses a datastore other local users can reach, and a container
        started with --user skips the chmod of the image entrypoint.
        """
        store_dir = Path(self.config.base_data_dir) / self.config.dataset
        store_dir.mkdir(parents=True, exist_ok=True)
        store_dir.chmod(0o700)

    def status(self) -> ServerStatus:
        """
        Get server status information.

        Returns:
            ServerStatus object with status information
        """
        server_status = super().status()
        if server_status.running and self.endpoint_answers():
            response = self.make_request("GET", self.config.status_url)
            if response.success:
                server_status.at = ServerLifecycleState.READY
                self.add_triple_count2_server_status(server_status)
        return server_status

    def execute_update_query(self, update_query: str) -> tuple[any, Exception]:
        """
        Execute SPARQL UPDATE query using the Tentris update endpoint
        with the application/sparql-update content type.

        Args:
            update_query: SPARQL UPDATE query string

        Returns:
            Tuple of (response, exception)
        """
        result, error = self.execute_update_query_with_post(update_query)
        return result, error
