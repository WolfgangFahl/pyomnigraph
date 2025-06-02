"""
Created on 2025-05-30

Ontotext GraphDB SPARQL support

@author: wf
"""

from dataclasses import dataclass
from typing import Any, Dict

from omnigraph.sparql_server import ServerConfig, ServerEnv, SparqlServer


@dataclass
class GraphDBConfig(ServerConfig):
    """
    GraphDB configuration
    """

    def __post_init__(self):
        """
        configure the configuration
        """
        super().__post_init__()

        # Clean URLs without credentials
        graphdb_repo = f"{self.base_url}/repositories/{self.dataset}"
        self.status_url = f"{self.base_url}/rest/info"
        self.sparql_url = f"{graphdb_repo}"
        self.update_url = f"{graphdb_repo}/statements"
        self.upload_url = f"{graphdb_repo}/statements"
        self.web_url = f"{self.base_url}/sparql"


    def get_docker_run_command(self, data_dir) -> str:
        """
        Generate docker run command with bind mount for data directory.

        Args:
            data_dir: Host directory path to bind mount to container

        Returns:
            Complete docker run command string
        """
        env = ""
        if self.auth_password:
            env = f"-e GDB_JAVA_OPTS='-Dgraphdb.auth.token.secret={self.auth_password}'"

        docker_run_command = (
            f"docker run {env}-d --name {self.container_name} "
            f"-p 127.0.0.1:{self.port}:7200 "
            f"-v {data_dir}:/opt/graphdb/home "
            f"{self.image}"
        )
        return docker_run_command


class GraphDB(SparqlServer):
    """
    Dockerized Ontotext GraphDB SPARQL server
    """

    def __init__(self, config: ServerConfig, env: ServerEnv):
        """
        Initialize the GraphDB manager.

        Args:
            config: Server configuration
            env: Server environment (includes log, shell, debug, verbose)
        """
        super().__init__(config=config, env=env)

    def status(self) -> Dict[str, Any]:
        """
        Check GraphDB server status from container logs.

        Returns:
            Dict containing status information
        """
        logs = self.shell.run(f"docker logs {self.config.container_name}", tee=False).stdout
        if "GraphDB Workbench is running" in logs and "Started GraphDB" in logs:
            status = {
                "status": "ready",
            }
        else:
            status = {"status": "starting"}
        return status
