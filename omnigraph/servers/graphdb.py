"""
Created on 2025-05-30

Ontotext GraphDB SPARQL support

@author: wf
"""

from dataclasses import dataclass
from omnigraph.server_config import ServerLifecycleState, ServerStatus
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
        Handles image swapping (effective_image) and conditional license injection.

        Args:
            data_dir: Host directory path to bind mount to container

        Returns:
            Complete docker run command string
        """
        # 1. Determine which image to use (Enterprise vs Free/Community)
        target_image = self.effective_image

        # 2. Build Environment Variables
        env_parts = []
        if self.auth_password:
            env_parts.append(f"-e GDB_JAVA_OPTS='-Dgraphdb.auth.token.secret={self.auth_password}'")

        # 3. Only inject the License Key if we are using the Enterprise image.
        # This prevents sending the license env var to the free/free-edition image if swapped.
        if target_image == self.image and self.license_env_var:
            env_parts.append(f"-e {self.license_env_var}")

        env_str = " " + " ".join(env_parts) if env_parts else ""

        # 4. Construct Command
        docker_run_command = (
            f"docker run {env_str} -d --name {self.container_name} "
            f"-p {self.docker_bind}:{self.port}:7200 "
            f"-v {data_dir}:/opt/graphdb/home "
            f"{target_image}"
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
        self.repo_created=False

    def post_start(self, first_start:bool):
        """Create repository after container starts.

        References:
            - https://graphdb.ontotext.com/documentation/11.2/manage-repos-with-restapi.html
        """
        if not first_start:
            return
        config = f"""@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>.
    @prefix rep: <http://www.openrdf.org/config/repository#>.
    @prefix sr: <http://www.openrdf.org/config/repository/sail#>.
    @prefix sail: <http://www.openrdf.org/config/sail#>.
    @prefix graphdb: <http://www.ontotext.com/config/graphdb#>.

    [] a rep:Repository ;
        rep:repositoryID "{self.config.dataset}" ;
        rdfs:label "{self.config.dataset}" ;
        rep:repositoryImpl [
            rep:repositoryType "graphdb:SailRepository" ;
            sr:sailImpl [
                sail:sailType "graphdb:Sail" ;
                graphdb:read-only "false" ;
                graphdb:ruleset "rdfsplus-optimized" ;
                graphdb:disable-sameAs "true" ;
                graphdb:check-for-inconsistencies "false" ;
                graphdb:entity-id-size "32" ;
                graphdb:enable-context-index "false" ;
                graphdb:enablePredicateList "true" ;
                graphdb:enable-fts-index "false" ;
                graphdb:query-timeout "0" ;
                graphdb:throw-QueryEvaluationException-on-timeout "false" ;
                graphdb:query-limit-results "0" ;
                graphdb:base-URL "http://example.org/owlim#" ;
                graphdb:defaultNS "" ;
                graphdb:imports "" ;
                graphdb:repository-type "file-repository" ;
                graphdb:storage-folder "storage" ;
                graphdb:entity-index-size "10000000" ;
                graphdb:in-memory-literal-properties "true" ;
                graphdb:enable-literal-index "true" ;
            ]
        ] ."""

        files = {'config': ('repo-config.ttl', config, 'application/x-turtle')}

        response=self.make_request(
            "POST",
            f"{self.config.base_url}/rest/repositories",
            files=files
        )
        if not response.success:
            raise Exception(f"Failed to create repository: {response.error}")
        else:
            self.repo_created=True


    def status(self) -> ServerStatus:
        """
        Check GraphDB server status from container logs.

        Returns:
        ServerStatus object with status information
        """
        server_status = super().status()
        logs = server_status.logs
        if logs:
            if "Started GraphDB" in logs:
                lifecycle = ServerLifecycleState.READY
                server_status.at = lifecycle

        if server_status.at == ServerLifecycleState.READY:
            if self.repo_created:
                self.add_triple_count2_server_status(server_status)
        return server_status
