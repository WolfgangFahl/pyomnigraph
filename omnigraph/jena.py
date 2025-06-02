"""
Created on 2025-05-28

Apache Jena SPARQL support

@author: wf
"""

from dataclasses import dataclass
from typing import Any, Dict

from omnigraph.sparql_server import ServerConfig, ServerEnv, SparqlServer


@dataclass
class JenaConfig(ServerConfig):
    """
    Jena Fuseki configuration
    """

    def __post_init__(self):
        """
        configure the configuration
        """
        super().__post_init__()

        # Clean URLs without credentials
        jena_base = f"{self.base_url}/ds"
        self.status_url = f"{self.base_url}/$/ping"
        self.sparql_url = f"{jena_base}/sparql"
        self.update_url = f"{jena_base}/update"
        self.upload_url = f"{jena_base}/data"
        self.web_url = f"{self.base_url}/#/dataset/ds/query"


    def get_docker_run_command(self,data_dir)->str:
        """
        Generate docker run command with bind mount for data directory.

        Args:
            data_dir: Host directory path to bind mount to container

        Returns:
            Complete docker run command string
        """
        # Docker command setup
        env = "-e FUSEKI_DATASET_1=ds"
        if self.auth_password:
            env = f"{env} -e ADMIN_PASSWORD={self.auth_password}"
        docker_run_command = (
            f"docker run {env} -d --name {self.container_name} "
            f"-p {self.port}:3030 "
            f"-v {data_dir}:/fuseki "
            f"{self.image}"
        )
        return docker_run_command


class Jena(SparqlServer):
    """
    Dockerized Jena Fuseki SPARQL server
    """

    def __init__(self, config: ServerConfig, env: ServerEnv):
        """
        Initialize the Jena Fuseki manager.

        Args:
            config: Server configuration
            env: Server environment (includes log, shell, debug, verbose)
        """
        super().__init__(config=config, env=env)

    def status(self) -> Dict[str, Any]:
        logs = self.shell.run(f"docker logs {self.config.container_name}", tee=False).stdout
        if "Creating dataset" in logs and "Fuseki is available :-)" in logs:
            status = {
                "status": "ready",
            }
        else:
            status = {"status": "starting"}
        return status
