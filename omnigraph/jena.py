"""
Created on 2025-05-28

Apache Jena SPARQL support

@author: wf
"""

from dataclasses import dataclass

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
        jena_base = f"{self.base_url}/ds"
        self.status_url = f"{self.base_url}/$/ping"
        self.sparql_url = f"{jena_base}/sparql"
        self.update_url = f"{jena_base}/update"
        self.web_url = f"{self.base_url}/#/dataset/ds/query"
        self.upload_url = f"{jena_base}/data"
        env=""
        if self.admin_password:
            env=f"-e ADMIN_PASSWORD={self.admin_password}"
        self.docker_run_command = f"docker run {env} -d --name {self.container_name} -p {self.port}:3030 {self.image}"


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
