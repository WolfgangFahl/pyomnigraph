"""
Created on 2025-06-03

Stardog SPARQL support

@author: wf
"""

from dataclasses import dataclass

from omnigraph.server_config import ServerLifecycleState, ServerStatus
from omnigraph.sparql_server import ServerConfig, ServerEnv, SparqlServer


@dataclass
class StardogConfig(ServerConfig):
    """
    Stardog configuration
    """

    def __post_init__(self):
        """
        configure the configuration
        """
        super().__post_init__()

        # Clean URLs without credentials
        stardog_base = f"{self.base_url}/{self.dataset}"
        self.status_url = f"{self.base_url}/admin/status"
        self.sparql_url = f"{stardog_base}/query"
        self.update_url = f"{stardog_base}/update"
        self.upload_url = f"{stardog_base}/add"
        self.web_url = f"{self.base_url}/"

    def get_docker_run_command(self, data_dir) -> str:
        """
        Generate docker run command with bind mount for data directory.
        Handles the special case of swapping to the free image (Github/Zazuko)
        where the license key must NOT be injected.

        Args:
            data_dir: Host directory path to bind mount to container

        Returns:
            Complete docker run command string
        """
        # 1. Determine which image to use (Enterprise vs Free/Github) based on license existence
        target_image = self.effective_image

        # 2. Build Environment Variables
        env_parts = []
        if self.auth_password:
            env_parts.append("-e STARDOG_SERVER_JAVA_ARGS='-Dstardog.default.cli.server=http://localhost:5820'")

        # 3. Only inject the License Key if we are using the Enterprise image.
        # The free (Github) image does not require (and may not support) the license env var.
        if target_image == self.image and self.license_env_var:
            env_parts.append(f"-e {self.license_env_var}")

        env_str = " " + " ".join(env_parts) if env_parts else ""

        # 4. Construct Command using target_image
        docker_run_command = (
            f"docker run {self.docker_user_flag}{env_str} -d --name {self.container_name} "
            f"-p {self.docker_bind}:{self.port}:5820 "
            f"-v {data_dir}:/var/opt/stardog "
            f"{target_image}"
        )
        return docker_run_command


class Stardog(SparqlServer):
    """
    Dockerized Stardog SPARQL server
    """

    def __init__(self, config: ServerConfig, env: ServerEnv):
        """
        Initialize the Stardog manager.

        Args:
            config: Server configuration
            env: Server environment (includes log, shell, debug, verbose)
        """
        super().__init__(config=config, env=env)

    def pre_create(self):
        """Build Stardog image if needed."""
        if not self.config.has_license:
            return

        target = self.effective_image

        # Check if image exists
        result = self.shell.run(f"docker images -q {target}")
        if result.stdout.strip():
            self.msg(f"Image {target} already exists")
            return

        # Build image
        self.msg(f"Building {target}...")
        dockerfile_path = self.config_path / "Dockerfile"
        result = self.shell.run(
            f"docker build -t {target} -f {dockerfile_path} {self.config_path}",
            tee=True
        )
        if result.returncode == 0:
            self.msg(f"✅ Built {target}")
        else:
            raise RuntimeError(f"Failed to build {target}")

    def status(self) -> ServerStatus:
        """
        Get server status information.

        Returns:
            ServerStatus object with status information
        """
        server_status = super().status()
        logs = server_status.logs

        if logs and "Stardog server started" in logs and "Server is ready" in logs:
            server_status.at = ServerLifecycleState.READY
        return server_status