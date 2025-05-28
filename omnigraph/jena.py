"""
Created on 2025-05-28

Apache Jena SPARQL support

@author: wf
"""

from dataclasses import dataclass

from omnigraph.persistent_log import Log
from omnigraph.shell import Shell
from omnigraph.sparql_server import ServerConfig


@dataclass
class JenaConfig(ServerConfig):
    """
    Jena Fuseki configuration
    """

    dataset: str = "ds"

    def __post_init__(self):
        super().__post_init__()
        self.status_url = f"{self.base_url}/$/ping"
        self.sparql_url = f"{self.base_url}/{self.dataset}/sparql"
        self.update_url = f"{self.base_url}/{self.dataset}/update"
        self.upload_url = f"{self.base_url}/{self.dataset}/data"
        self.docker_run_command = (
            f"docker run -d --name {self.container_name} -p {self.port}:3030 -e ADMIN_PASSWORD=admin {self.image}"
        )


def __init__(
    self,
    config: ServerConfig,
    log: Log = None,
    shell: Shell = None,
    debug: bool = False,
):
    """
    Initialize the Jena Fuseki manager.

    Args:
        config: Jena server configuration
        log: Log instance for logging
        shell: Shell instance for Docker commands
        debug: Enable debug output
    """
    super().__init__(config=config, log=log, shell=shell, debug=debug)
    self.dataset = getattr(config, "dataset", "ds")
    self.update_url = f"{self.config.base_url}/{self.dataset}/update"
    self.upload_url = f"{self.config.base_url}/{self.dataset}/data"


from omnigraph.sparql_server import SparqlServer


class Jena(SparqlServer):
    """
    Dockerized Apache Jena Fuseki SPARQL server
    """

    def __init__(
        self,
        config: ServerConfig,
        log: Log = None,
        shell: Shell = None,
        debug: bool = False,
    ):
        """
        Initialize the Jena Fuseki manager.

        Args:
            config: Jena server configuration
            log: Log instance for logging
            shell: Shell instance for Docker commands
            debug: Enable debug output
        """
        super().__init__(config=config, log=log, shell=shell, debug=debug)
        self.dataset = getattr(config, "dataset", "ds")
        self.update_url = f"{self.config.base_url}/{self.dataset}/update"
        self.upload_url = f"{self.config.base_url}/{self.dataset}/data"

    def status(self) -> dict:
        """
        Get Jena Fuseki status information.

        Returns:
            Dictionary with status information, empty dict if error
        """
        result = self._make_request("GET", self.config.status_url, timeout=2)

        if result["success"]:
            status = {"status": "ready"}
        else:
            error_msg = result.get("error", f"status_code: {result['status_code']}")
            status = {"status": f"error: {error_msg}"}
        return status
