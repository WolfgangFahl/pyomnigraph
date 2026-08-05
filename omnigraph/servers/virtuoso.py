"""
Created on 2025-06-03

OpenLink Virtuoso SPARQL support

@author: wf
"""

from dataclasses import dataclass
from typing import Any, Optional

from requests.auth import HTTPDigestAuth

from omnigraph.server_config import ServerLifecycleState, ServerStatus
from omnigraph.sparql_server import Response, ServerConfig, ServerEnv, SparqlServer, ShellResult


@dataclass
class VirtuosoConfig(ServerConfig):
    """
    Virtuoso configuration
    """

    def __post_init__(self):
        """
        configure the configuration
        """
        super().__post_init__()

        # Clean URLs without credentials
        # /sparql is read only by design - the SPARQL_SELECT role of user SPARQL applies there
        # writes go to /sparql-auth which authenticates a user holding the SPARQL_UPDATE role
        # see https://community.openlinksw.com/t/trying-to-get-pyomnigraph-working-with-virtuoso/5037/2
        self.status_url = f"{self.base_url}/sparql"
        self.sparql_url = f"{self.base_url}/sparql"
        self.update_url = f"{self.base_url}/sparql-auth"
        self.upload_url = f"{self.base_url}/sparql-graph-crud"
        self.web_url = f"{self.base_url}/sparql"
        # Virtuoso has no per dataset endpoint and its unqualified default graph is the
        # union of all graphs including the system graphs, so the dataset name is
        # materialised as a named graph - the way other servers materialise it as a
        # namespace, repository or database, see #43
        self.graph_uri = f"urn:omnigraph:{self.dataset}" if self.dataset else "urn:virtuoso:default"

    def get_docker_run_command(self, data_dir) -> str:
        """
        Generate docker run command with bind mount for data directory.

        Args:
            data_dir: Host directory path to bind mount to container

        Returns:
            Complete docker run command string
        """
        # Docker command setup
        env = "-e SPARQL_UPDATE=true"
        if self.auth_password:
            env += f" -e DBA_PASSWORD={self.auth_password}"

        # run as root - no user flag
        docker_run_command = (
            f"docker run {self.docker_options_flag}{env} -d --name {self.container_name} "
            f"-p {self.docker_bind}:{self.port}:8890 "
            f"-v {data_dir}:/database "
            f"{self.image}"
        )
        return docker_run_command


class Virtuoso(SparqlServer):
    """
    Dockerized OpenLink Virtuoso SPARQL server
    """

    def __init__(self, config: ServerConfig, env: ServerEnv):
        """
        Initialize the Virtuoso manager.

        Args:
            config: Server configuration
            env: Server environment (includes log, shell, debug, verbose)
        """
        super().__init__(config=config, env=env)

    def post_create(self):
        """
        Setup permissions after container creation.
        """
        super().post_create()
        self.setup_permissions()

    def run_isql_cmd(self, cmd: str) -> ShellResult:
        """
        Run SQL command via isql.
        """
        # Escape double quotes in the SQL command for proper shell handling
        escaped_cmd = cmd.replace('"', '\\"')
        args = (
            f'isql 1111 dba {self.config.auth_password or "dba"} "EXEC={escaped_cmd}"'
        )
        shell_result = self.run_docker_cmd("exec", args=args)
        return shell_result

    def setup_permissions(self) -> bool:
        """
        Grant necessary permissions to SPARQL user.
        """
        # Grant general SPARQL update capability
        success = True
        grants = [
            'GRANT SPARQL_UPDATE TO "SPARQL";',
            # workaround of 2023-01 as per https://community.openlinksw.com/t/sparul-insert-access-denied-even-after-granting-update-permission/3448/7
            "DB.DBA.RDF_DEFAULT_USER_PERMS_SET ('nobody', 7);",
            # Grant write permissions on default graph for SPARQL user
            "DB.DBA.RDF_DEFAULT_USER_PERMS_SET ('SPARQL', 7);",
        ]
        for sql in grants:
            shell_result = self.run_isql_cmd(sql)
            success = success and shell_result.success

        return success

    def status(self) -> ServerStatus:
        """
        Get server status information.

        Returns:
            ServerStatus object with status information
        """
        server_status = super().status()
        logs = server_status.logs

        # the log lines survive a restart, so they only qualify the container -
        # readiness is decided by the endpoint answering, as for jena and graphdb
        if logs and "Server online at" in logs and "HTTP/WebDAV server online at" in logs:
            if self.endpoint_answers():
                server_status.at = ServerLifecycleState.READY

        return server_status

    def ensure_permissions(self):
        """
        Ensure permissions are set (can be called even if server is already running).
        """
        status = self.status()
        if status.running:
            self.setup_permissions()

    @property
    def supports_datasets(self) -> bool:
        # the dataset name is materialised as a named graph, which needs no creation
        return True

    def get_digest_auth(self) -> Optional[HTTPDigestAuth]:
        """
        Get the digest authentication for the /sparql-auth endpoint.

        Returns:
            HTTPDigestAuth for the configured user or None if unconfigured
        """
        digest_auth = None
        if self.config.auth_user and self.config.auth_password:
            digest_auth = HTTPDigestAuth(self.config.auth_user, self.config.auth_password)
        return digest_auth

    def execute_update_query(self, update_query: str) -> tuple[Optional[Any], Optional[Exception]]:
        """
        Execute SPARQL UPDATE query via the authenticated /sparql-auth endpoint.

        Args:
            update_query: SPARQL UPDATE query string

        Returns:
            Tuple of (response, exception)
        """
        kwargs = {}
        digest_auth = self.get_digest_auth()
        if digest_auth:
            kwargs["auth"] = digest_auth
        result, error = self.execute_update_query_with_post(update_query, **kwargs)
        return result, error

    def count_triples(self) -> int:
        """
        Count the triples of my graph.

        An unrestricted pattern would count the union of all graphs including
        the system graphs Virtuoso ships with.

        Returns:
            Number of triples in the configured graph
        """
        count_query = f"SELECT (COUNT(*) AS ?count) WHERE {{ GRAPH <{self.config.graph_uri}> {{ ?s ?p ?o }} }}"
        try:
            result = self.sparql.getValue(count_query, "count")
            triple_count = int(result) if result else 0
        except Exception as ex:
            self.handle_exception("count_triples", ex)
            triple_count = -1
        return triple_count

    def upload_request(self, file_content: bytes) -> Response:
        """
        Upload via the graph store protocol into my graph.

        Without a graph parameter Virtuoso answers 200 with an HTML page and stores nothing.

        Args:
            file_content: the RDF payload to upload

        Returns:
            Response of the upload request
        """
        response = self.make_request(
            "POST",
            f"{self.config.upload_url}?graph-uri={self.config.graph_uri}",
            headers={"Content-Type": self.rdf_format.mime_type},
            data=file_content,
            timeout=self.config.upload_timeout,
            auth=self.get_digest_auth(),
        )
        return response

    def get_clear_query(self) -> str:
        """
        the clear query to be used
        overrides the default query
        """
        # Ensure permissions are set before clearing
        self.ensure_permissions()

        # Use CLEAR GRAPH instead of DELETE for better Virtuoso compatibility
        # This requires fewer permissions than DELETE
        clear_query = f"CLEAR GRAPH <{self.config.graph_uri}>"
        return clear_query

    def get_web_url(self) -> str:
        web_url = self.config.web_url
        if self.config.auth_user and self.config.auth_password:
            proto, rest = web_url.split("://", 1)
            auth = f"{self.config.auth_user}:{self.config.auth_password}@"
            web_url = f"{proto}://{auth}{rest}"
        return web_url
