"""
Created on 2026-08-05

Franz AllegroGraph SPARQL support

@author: wf
"""

from dataclasses import dataclass

from omnigraph.server_config import ServerLifecycleState, ServerStatus
from omnigraph.sparql_server import Response, ServerConfig, ServerEnv, SparqlServer


@dataclass
class AllegroGraphConfig(ServerConfig):
    """
    AllegroGraph configuration
    """

    def __post_init__(self):
        """
        configure the configuration
        """
        super().__post_init__()

        # AllegroGraph exposes the Sesame/RDF4J style repository API
        agraph_repo = f"{self.base_url}/repositories/{self.dataset}"
        self.status_url = f"{self.base_url}/version"
        self.sparql_url = agraph_repo
        # SPARQL UPDATE is taken as an update form parameter on the repository endpoint,
        # the statements endpoint rejects application/sparql-update with 400
        self.update_url = agraph_repo
        self.upload_url = f"{agraph_repo}/statements"
        self.web_url = f"{self.base_url}/"

    def get_docker_run_command(self, data_dir) -> str:
        """
        Generate docker run command with bind mount for data directory.

        Args:
            data_dir: Host directory path to bind mount to container

        Returns:
            Complete docker run command string
        """
        env_parts = []
        if self.auth_user:
            env_parts.append(f"-e AGRAPH_SUPER_USER={self.auth_user}")
        if self.auth_password:
            env_parts.append(f"-e AGRAPH_SUPER_PASSWORD={self.auth_password}")
        env_str = " " + " ".join(env_parts) if env_parts else ""

        docker_run_command = (
            f"docker run{env_str} -d --name {self.container_name} "
            # demanded by the image - the linux docker default of 64m shared
            # memory makes the container exit at boot with exactly this advice
            f"--shm-size 1g "
            f"-p {self.docker_bind}:{self.port}:10035 "
            f"-v {data_dir}:/agraph/data "
            f"{self.image}"
        )
        return docker_run_command


class AllegroGraph(SparqlServer):
    """
    Dockerized Franz AllegroGraph SPARQL server
    """

    def __init__(self, config: ServerConfig, env: ServerEnv):
        """
        Initialize the AllegroGraph manager.

        Args:
            config: Server configuration
            env: Server environment (includes log, shell, debug, verbose)
        """
        super().__init__(config=config, env=env)
        self.repo_created = False

    def post_start(self, first_start: bool):
        """
        Create the repository after the container starts.

        Args:
            first_start: True if the container was created by this start
        """
        if not first_start:
            return
        response = self.make_request("PUT", f"{self.config.base_url}/repositories/{self.config.dataset}")
        if not response.success:
            raise Exception(f"Failed to create repository: {response.error}")
        self.repo_created = True

    @property
    def supports_datasets(self) -> bool:
        # the dataset name is materialised as a repository
        return True

    def ensure_dataset(self) -> bool:
        """
        Create the repository if it does not exist yet.

        A PUT on an existing repository recreates it empty, so its existence is
        checked first - see issue #44.

        Returns:
            True if the repository is available
        """
        repo_url = f"{self.config.base_url}/repositories/{self.config.dataset}"
        exists = self.make_request("GET", f"{repo_url}/size").success
        available = exists
        if not exists:
            available = self.make_request("PUT", repo_url).success
        if available:
            self.repo_created = True
        return available

    def status(self) -> ServerStatus:
        """
        Get server status information.

        Returns:
            ServerStatus object with status information
        """
        server_status = super().status()
        logs = server_status.logs
        if logs and "scheduler process started" in logs and self.endpoint_answers():
            server_status.at = ServerLifecycleState.READY
        if server_status.at == ServerLifecycleState.READY and self.repo_created:
            self.add_triple_count2_server_status(server_status)
        return server_status

    def execute_update_query(self, update_query: str) -> tuple:
        """
        Execute SPARQL UPDATE query as an update form parameter.

        Args:
            update_query: SPARQL UPDATE query string

        Returns:
            Tuple of (response, exception)
        """
        result = None
        error = None
        try:
            resp = self.make_request(
                "POST",
                self.config.update_url,
                data={"update": update_query},
                timeout=self.config.upload_timeout,
            )
            result = resp.response
            if not resp.success:
                status = resp.response.status_code if resp.response else "unknown"
                error = resp.error or Exception(f"HTTP {status}")
        except Exception as ex:
            error = ex
        return result, error

    def upload_request(self, file_content: bytes) -> Response:
        """
        Upload RDF via the statements endpoint of the repository.

        Args:
            file_content: the RDF payload to upload

        Returns:
            Response of the upload request
        """
        response = self.make_request(
            "POST",
            self.config.upload_url,
            headers={"Content-Type": self.rdf_format.mime_type},
            data=file_content,
            timeout=self.config.upload_timeout,
        )
        return response
