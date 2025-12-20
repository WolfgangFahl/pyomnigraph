"""
Created on 2025-05-28

@author: wf
"""

import os
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, Optional

from basemkit.yamlable import lod_storable

from basemkit.persistent_log import Log
from basemkit.shell import Shell
from omnigraph.software import SoftwareList
from omnigraph.version import Version

class SupportStatus(Enum):
    """
    Determines if and how a server can run based on environment/licenses.
    """
    SUPPORTED = "supported ✅"
    LIMITED = "limited ⚠️"
    MISSING_LICENSE = "no_license 🛑"
    MISSING_SOFTWARE = "no_software 🛑"
    MANUAL_DISABLED = "disabled ⛔"

    def can_start(self) -> bool:
        """Check if server can be started with this status."""
        return self in (SupportStatus.SUPPORTED, SupportStatus.LIMITED)

    def is_blocking(self) -> bool:
        """Check if this status blocks server operations."""
        return not self.can_start()

    def log_status(self, log: Log, container_name: str, config: 'ServerConfig') -> None:
        """Log appropriate message for this status."""
        if self == SupportStatus.MANUAL_DISABLED:
            log.log("🛑", container_name, "Server is manually disabled in configuration")

        elif self == SupportStatus.MISSING_SOFTWARE:
            log.log("🛑", container_name, "Required software missing - cannot start")

        elif self == SupportStatus.MISSING_LICENSE:
            log.log("🛑", container_name,
                   f"License required (set {config.license_env_var}) and no free fallback available")

        elif self == SupportStatus.LIMITED:
            log.log("⚠️", container_name,
                   f"Using free/community image: {config.effective_image}")

        elif self == SupportStatus.SUPPORTED:
            log.log("✅", container_name, "Server fully supported")

class ServerLifecycleState(Enum):
    """
    a state in the servers lifecycle
    """
    READY = "ready ✅"
    UP = "up 🟢"
    ERROR = "error ❌"
    UNKNOWN = "unknown ❓"
    STARTING = "starting 🔄"
    STOPPED = "stopped ⏹️"


@dataclass
class ServerStatus:
    """
    Server status
    """

    at: ServerLifecycleState
    running: bool = False
    exists: bool = False
    error: Optional[Exception] = None
    http_status_code: Optional[int] = None
    docker_status: Optional[str] = None
    docker_exit_code: Optional[int] = None
    # fields to be initialized by post_init
    logs: str = field(default=None)
    triple_count: int = field(default=None)
    timestamp: datetime = field(default=None)
    status_dict: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.timestamp = datetime.now()

    def get_summary(self, debug: bool) -> str:
        """
        get a summary of the Server Status
        """
        summary = f"@ {self.timestamp.strftime('%H:%M:%S')}"
        if self.http_status_code:
            summary += f" (HTTP {self.http_status_code})"
        if self.triple_count:
            summary += f"{self.triple_count} triples"
        if self.error:
            debug_msg = f" - {type(self.error).__name__}"
            if debug:
                debug_msg = "".join(traceback.format_exception(type(self.error), self.error, self.error.__traceback__))
            summary += debug_msg
        return summary


class ServerEnv:
    """
    Server environment configuration.
    """

    def __init__(self, log: Log = None, shell: Shell = None, force:bool=False, debug: bool = False, verbose: bool = False):
        """
        Initialize server environment.

        Args:
            log: Log instance for logging
            shell: Shell instance for command execution
            force: if True enable actions that are otherwise protected e.g. deletion of data
            debug: Enable debug mode
            verbose: Enable verbose output
        """
        if log is None:
            log = Log()
            log.do_print = debug and verbose
        self.log = log
        if shell is None:
            shell = Shell()
        self.shell = shell
        self.force=force
        self.debug = debug
        self.verbose = verbose


@dataclass
class ServerConfig:
    """
    a server configuration for a Knowledge Graph endpoint
    potentially provided by a docker container and often
    implemented as a SPARQL endpoint
    """
    server: str
    name: str
    wikidata_id: str
    container_name: str
    port: int
    test_port: int
    image: str
    free_image: Optional[str] = None       # Fallback image if license is missing
    license_env_var: Optional[str] = None  # Name of EnvVar holding the key
    active: bool = True
    has_license: bool=False
    protocol: str = "http"
    host: str = "localhost"
    rdf_format: str = "turtle"
    auth_user: Optional[str] = None
    auth_password: Optional[str] = None
    dataset: Optional[str] = None
    prefix_sets: Optional[list] = field(default_factory=lambda: ["rdf"])
    timeout: int = 30
    ready_timeout: int = 20
    proxy_timeout: int = 5400  # e.g. apache server
    upload_timeout: int = 300
    unforced_clear_limit = 100000  # maximumn number of triples that can be cleared without force option
    # fields to be configured by post_init
    base_url: Optional[str] = field(default=None)
    status_url: Optional[str] = field(default=None)
    web_url: Optional[str] = field(default=None)
    sparql_url: Optional[str] = field(default=None)
    upload_url: Optional[str] = field(default=None)
    base_data_dir: Optional[str] = field(default=None)  # base data directory available as bind mount
    data_dir: Optional[str] = field(default=None)  # default data directory
    dumps_dir: Optional[str] = field(default=None)
    needed_software: Optional[SoftwareList] = field(default=None)

    def __post_init__(self):
        if self.base_url is None:
            self.base_url = f"{self.protocol}://{self.host}:{self.port}"
        # Check if we have a license available
        self.has_license = self.license_env_var and os.environ.get(self.license_env_var)

    @property
    def support_status(self) -> SupportStatus:
        """
        Determine support status based on configuration and environment.

        Returns:
            SupportStatus enum indicating if/how server can run
        """
        status = SupportStatus.SUPPORTED

        # Check if manually disabled
        if not self.active:
            status = SupportStatus.MANUAL_DISABLED
        elif self.license_env_var:
            # Check license requirements
            if self.has_license:
                status = SupportStatus.SUPPORTED
            elif self.free_image:
                status = SupportStatus.LIMITED
            else:
                status = SupportStatus.MISSING_LICENSE

        return status

    @property
    def effective_image(self) -> str:
        # Default to the main image
        target_image = self.image

        # Downgrade to free image ONLY if we have no license AND a free alternative exists
        if self.free_image and not self.has_license:
            target_image = self.free_image
            if target_image.startswith("https://github.com/"):
                target_image=target_image.split('/')[-1].replace('.git', '') + ":local"
        return target_image

    @property
    def docker_user_flag(self) -> str:
        try:
            uid = os.getuid()
            gid = os.getgid()
            user_flag = f"-u {uid}:{gid}"
        except AttributeError:
            # e.g. on Windows
            user_flag = ""
        return user_flag

    def generator_header(self, version=None) -> str:
        """
        generate a standard header with timestamp and optional version information

        Args:
            version: optional version info, defaults to Version.version

        Returns:
            str: a header string suitable for generated files
        """
        iso_timestamp = datetime.now().isoformat()
        version_info = ""
        if version is None:
            version = Version
        if version:
            version_info = f"""{version.name} Version {version.version} of {version.updated} ({version.description})"""

        header = f"""# Generated by omnigraph at {iso_timestamp}
# {version_info}"""
        return header

    def to_apache_config(self, domain: str, version: None) -> str:
        """
        Generate Apache configuration based for this server.

        Args:
            domain(str): the base domain to use
            version: the omnigraph Version info to use
        Returns:
            str: The Apache configuration as a string.
        """
        server_name = f"{self.name}.{domain}"
        admin_email = f"webmaster@{domain}"
        header = self.generator_header(version)
        header_comment = f"""# Apache Configuration for {server_name}
# {header}
# http Port: {self.port}
# SSL Port: 443
# timeout: {self.proxy_timeout}
"""

        template = """<VirtualHost *:{port}>
    ServerName {server_name}
    ServerAdmin {admin_email}

    {ssl_config_part}
    ErrorLog ${{APACHE_LOG_DIR}}/{short_name}_error{log_suffix}.log
    CustomLog ${{APACHE_LOG_DIR}}/{short_name}{log_suffix}.log combined

    ProxyPreserveHost On
    ProxyTimeout {proxy_timeout}

    ProxyPass / http://localhost:{default_port}/
    ProxyPassReverse / http://localhost:{default_port}/
</VirtualHost>
"""

        # For SSL Configuration
        ssl_config = template.format(
            port=443,
            server_name=server_name,
            admin_email=admin_email,
            short_name=self.name,
            log_suffix="_ssl",
            default_port=self.port,
            proxy_timeout=self.proxy_timeout,
            ssl_config_part="Include ssl.conf",
        )

        # For Non-SSL Configuration
        http_config = template.format(
            port=80,
            server_name=server_name,
            admin_email=admin_email,
            short_name=self.name,
            log_suffix="",
            default_port=self.port,
            proxy_timeout=self.proxy_timeout,
            ssl_config_part="",
        )

        apache_config = header_comment + ssl_config + http_config
        return apache_config


@lod_storable
class ServerConfigs:
    """Collection of server configurations loaded from YAML."""

    servers: Dict[str, ServerConfig] = field(default_factory=dict)

    @classmethod
    def ofYaml(cls, yaml_path: str) -> "ServerConfigs":
        """Load server configurations from YAML file."""
        server_configs = cls.load_from_yaml_file(yaml_path)
        return server_configs


@dataclass
class ServerCmd:
    """
    Command wrapper for server operations.
    """

    def __init__(self, title: str, func: Callable):
        """
        Initialize server command.

        Args:
            title: Description of the command
            func: Function to execute
        """
        self.title = title
        self.func = func

    def run(self, verbose: bool = True) -> any:
        """
        Execute the server command.

        Args:
            verbose: Whether to print result

        Returns:
            Result from function execution
        """
        if verbose:
            print(f"{self.title} ...")
        result = self.func()
        if verbose:
            print(f"{self.title}: {result}")
        return result
