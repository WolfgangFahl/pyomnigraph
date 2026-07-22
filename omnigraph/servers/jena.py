"""
Created on 2025-05-28

Apache Jena SPARQL support

@author: wf
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List

from omnigraph.server_config import ServerLifecycleState, ServerStatus
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

    def get_docker_run_command(self, data_dir) -> str:
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
            f"docker run {self.docker_user_flag} {env} -d --name {self.container_name} "
            f"-p {self.docker_bind}:{self.port}:3030 "
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

    def status(self) -> ServerStatus:
        """
        Get server status information.

        Returns:
        ServerStatus object with status information
        """
        server_status = super().status()
        logs = server_status.logs
        if logs and "Creating dataset" in logs and "Fuseki is available :-)" in logs:
            server_status.at = ServerLifecycleState.READY

        return server_status

    def execute_update_query(self, update_query: str) -> tuple[any, Exception]:
        """
        Execute SPARQL UPDATE query using Jena's update endpoint.

        Jena Fuseki requires application/sparql-update content type for UPDATE operations.

        Args:
            update_query: SPARQL UPDATE query string

        Returns:
            Tuple of (response, exception)
        """
        result, error = self.execute_update_query_with_post(update_query)
        return result, error

    def get_tdbloader_command(self, files: List[Path]) -> str:
        """
        Build the tdb2.tdbloader docker command for the given dump files.

        The loader classes ship inside fuseki-server.jar, so the server's own
        image is reused with an overridden entrypoint. The TDB2 dataset is
        single-writer - the server must be stopped while the loader runs.

        Args:
            files: dump files to load (from the dumps directory)

        Returns:
            the docker run command string
        """
        loc = f"/fuseki/databases/{self.config.dataset}"
        dumps_dir = Path(self.config.dumps_dir)
        file_args = " ".join(f"/dumps/{file.name}" for file in files)
        command = (
            f"docker run --rm {self.config.docker_user_flag} --entrypoint java "
            f"-v {self.config.base_data_dir}:/fuseki "
            f"-v {dumps_dir}:/dumps "
            f"{self.config.image} "
            f"-cp /jena-fuseki/fuseki-server.jar tdb2.tdbloader "
            f"--loc {loc} {file_args}"
        )
        return command

    def upload_dump_files(self, file_pattern: str = None) -> int:
        """
        Bulk-load dump files with tdb2.tdbloader directly into the TDB2
        database files - the native path for the file-backed store, avoiding
        the HTTP single-POST transaction that faults the mmap'd node table
        (issue #25).

        Args:
            file_pattern: Glob pattern for dump files

        Returns:
            Number of files loaded successfully
        """
        container_name = self.config.container_name
        files = self.get_dump_files(file_pattern)
        loaded_count = 0
        if not files:
            self.log.log("⚠️", container_name, f"No dump files found for pattern: {file_pattern}")
        else:
            self.stop()
            loader_cmd = self.get_tdbloader_command(files)
            shell_result = self.run_shell_command(
                loader_cmd,
                success_msg=f"tdb2.tdbloader loaded {len(files)} file(s)",
                error_msg="tdb2.tdbloader failed",
            )
            if shell_result.success:
                loaded_count = len(files)
            self.start()
        return loaded_count


