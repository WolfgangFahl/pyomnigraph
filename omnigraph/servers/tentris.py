"""
Created on 2026-11-07

Tentris SPARQL support - see issues #66 and #67
https://docs.tentris.io/
https://docs.tentris.io/running_with_docker.html
https://docs.tentris.io/sparql_endpoints.html
https://docs.tentris.io/additional_endpoints.html#health-endpoints

@author: wf
"""

import re
import shlex
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from basemkit.shell import ShellResult

from omnigraph.server_config import LoadPath, ServerLifecycleState, ServerStatus
from omnigraph.sparql_server import ServerConfig, ServerEnv, SparqlServer


@dataclass
class TentrisConfig(ServerConfig):
    """
    Tentris configuration
    """

    # names of the dump files in dumps_dir to load on the first initialization
    # via TENTRIS_RDF_FILE - set only while the store is built, see issue #67
    build_files: Optional[List[str]] = field(default=None)

    def __post_init__(self):
        """
        configure the configuration
        """
        super().__post_init__()
        # 503 during startup and the initial load, 200 once requests are accepted
        self.status_url = f"{self.base_url}/health/ready"
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
        the Tentris non-commercial license. With build_files set the dumps
        directory is mounted read only as /dumps and TENTRIS_RDF_FILE names the
        files to load on the first initialization.

        Args:
            data_dir: Host base data directory holding the dataset directories

        Returns:
            Complete docker run command string
        """
        store_dir = Path(data_dir) / self.dataset
        build_flags = ""
        if self.build_files:
            rdf_files = " ".join(f"/dumps/{name}" for name in self.build_files)
            dumps_dir = Path(self.dumps_dir).resolve()
            build_flags = f"-v {dumps_dir}:/dumps:ro -e TENTRIS_RDF_FILE={shlex.quote(rdf_files)} "
        docker_run_command = (
            f"docker run {self.docker_options_flag}{self.docker_user_flag} -d --name {self.container_name} "
            f"-p {self.docker_bind}:{self.port}:9080 "
            f"-v {store_dir}:/data "
            f"{build_flags}"
            f"{self.image}"
        )
        return docker_run_command


class Tentris(SparqlServer):
    """
    Dockerized Tentris SPARQL server
    """

    # seconds docker stop waits before killing - https://docs.tentris.io/running_with_docker.html
    STOP_TIMEOUT = 120

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
        if server_status.running:
            response = self.make_request("GET", self.config.status_url)
            if response.success:
                server_status.at = ServerLifecycleState.READY
                self.add_triple_count2_server_status(server_status)
        return server_status

    def stop(self) -> ShellResult:
        """
        Stop the container with the 120s grace period the Tentris docs advise -
        a shorter kill timeout may kill Tentris before it shut down gracefully,
        especially during the initial load of TENTRIS_RDF_FILE.

        Returns:
            the result of the docker stop command
        """
        container_name = self.config.container_name
        stop_result = self.run_shell_command(
            f"docker stop -t {self.STOP_TIMEOUT} {container_name}",
            success_msg=f"stop container {container_name}",
            error_msg=f"Failed to stop container {container_name}",
        )
        return stop_result

    @property
    def load_paths(self) -> List[LoadPath]:
        """
        TENTRIS_RDF_FILE first - more efficient than the graph store protocol
        per the Tentris answer on issue #66.

        Returns:
            list of supported LoadPath values
        """
        paths = [LoadPath.BUILD, LoadPath.LIVELOAD]
        return paths

    def build_from_dump_files(self, file_pattern: str = None) -> int:
        """
        Build the store from the dump files via TENTRIS_RDF_FILE.

        Tentris loads TENTRIS_RDF_FILE only on the first initialization of an
        empty /data, so the container is removed, the store directory emptied
        and the container recreated with the dumps mounted.

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
        elif any(re.search(r"\s", file.name) for file in files):
            # TENTRIS_RDF_FILE separates its paths by spaces
            self.log.log("❌", container_name, "TENTRIS_RDF_FILE can not name dump files containing whitespace")
        else:
            self.stop()
            self.rm()
            store_dir = Path(self.config.base_data_dir) / self.config.dataset
            # the container runs as the invoking user, so the store is removable here
            shutil.rmtree(store_dir, ignore_errors=True)
            self.config.build_files = [file.name for file in files]
            try:
                started = self.start()
            finally:
                self.config.build_files = None
            if started:
                loaded_count = len(files)
                self.log.log("✅", container_name, f"built from {loaded_count} files via TENTRIS_RDF_FILE")
        return loaded_count

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
