"""
Created on 2025-05-28

@author: wf
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from lodstorage.yamlable import lod_storable

from omnigraph.persistent_log import Log
from omnigraph.shell import Shell
from omnigraph.software import SoftwareList


class ServerEnv:
    """
    Server environment configuration.
    """

    def __init__(self, log: Log = None, shell: Shell = None, debug: bool = False, verbose: bool = False):
        """
        Initialize server environment.

        Args:
            log: Log instance for logging
            shell: Shell instance for command execution
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
        self.debug = debug
        self.verbose = verbose


@dataclass
class ServerConfig:
    server: str
    name: str
    wikidata_id: str
    container_name: str
    image: str
    port: int
    test_port: int
    active: bool = True
    protocol: str = "http"
    host: str = "localhost"
    auth_user: Optional[str] = None
    auth_password: Optional[str] = None
    dataset: Optional[str] = None
    timeout: int = 30
    ready_timeout: int = 20
    upload_timeout: int = 300
    unforced_clear_limit = 100000  # maximumn number of triples that can be cleared without force option
    # fields to be configured by post_init
    base_url: Optional[str] = field(default=None)
    status_url: Optional[str] = field(default=None)
    web_url: Optional[str] = field(default=None)
    sparql_url: Optional[str] = field(default=None)
    upload_url: Optional[str] = field(default=None)
    data_dir: Optional[str] = field(default=None)
    dumps_dir: Optional[str] = field(default=None)
    docker_run_command: Optional[str] = field(default=None)
    needed_software: Optional[SoftwareList] = field(default=None)

    def __post_init__(self):
        if self.base_url is None:
            self.base_url = f"{self.protocol}://{self.host}:{self.port}"


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
