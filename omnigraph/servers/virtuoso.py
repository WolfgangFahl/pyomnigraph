"""
Created on 2025-06-03

OpenLink Virtuoso SPARQL support

@author: wf
"""

from dataclasses import dataclass

from omnigraph.server_config import ServerLifecycleState, ServerStatus
from omnigraph.sparql_server import ServerConfig, ServerEnv, SparqlServer,\
    ShellResult


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
        self.status_url = f"{self.base_url}/sparql"
        self.sparql_url = f"{self.base_url}/sparql"
        self.update_url = f"{self.base_url}/sparql"
        self.upload_url = f"{self.base_url}/sparql-graph-crud"
        self.web_url = f"{self.base_url}/sparql"

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
            f"docker run {env} -d --name {self.container_name} "
            f"-p {self.port}:8890 "
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
        args = f"isql 1111 dba {self.config.auth_password or 'dba'} \"EXEC='{cmd}'\""
        shell_result = self.run_docker_cmd("exec", args=args)
        return shell_result

    def setup_permissions(self) -> bool:
        """
        Grant necessary permissions to SPARQL user.
        """
        # Grant general SPARQL update capability
        success=True
        grants = [
            "GRANT SPARQL_UPDATE TO \"SPARQL\";",
            # workaround of 2023-01 as per https://community.openlinksw.com/t/sparul-insert-access-denied-even-after-granting-update-permission/3448/7
            "DB.DBA.RDF_DEFAULT_USER_PERMS_SET ('nobody', 7);"
        ]
        for sql in grants:
            shell_result = self.run_isql_cmd(sql)
            success=success and shell_result.success

        return success

    def status(self) -> ServerStatus:
        """
        Get server status information.

        Returns:
            ServerStatus object with status information
        """
        server_status = super().status()
        logs = server_status.logs

        if logs and "Server online at" in logs and "HTTP/WebDAV server online at" in logs:
            server_status.at = ServerLifecycleState.READY

        return server_status

    def get_clear_query(self)->str:
        """
        the clear query to be used
        overrides the default query
        """
        clear_query="""DELETE WHERE {
  GRAPH <urn:virtuoso:default> { ?s ?p ?o }
}"""
        return clear_query


    def get_web_url(self) -> str:
        web_url = self.config.web_url
        if self.config.auth_user and self.config.auth_password:
            proto, rest = web_url.split("://", 1)
            auth=f"{self.config.auth_user}:{self.config.auth_password}@"
            web_url=f"{proto}://{auth}{rest}"
        return web_url