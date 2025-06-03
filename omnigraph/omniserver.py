"""
Created on 2025-05-28

@author: wf
"""

from dataclasses import asdict
from pathlib import Path
from typing import Callable, Dict

from omnigraph.blazegraph import Blazegraph, BlazegraphConfig
from omnigraph.graphdb import GraphDB, GraphDBConfig
from omnigraph.jena import Jena, JenaConfig
from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.qlever import QLever, QLeverConfig
from omnigraph.server_config import ServerCmd, ServerConfig, ServerConfigs, ServerEnv
from omnigraph.sparql_server import SparqlServer


class OmniServer:
    """
    Factory class for creating and managing SPARQL server instances.
    """

    def __init__(self, env: ServerEnv, patch_config: Callable = None):
        """
        constructor
        """
        self.env = env
        self.patch_config = patch_config

    @staticmethod
    def patch_test_config(config: ServerConfig, ogp: OmnigraphPaths):
        config.base_data_dir = ogp.omnigraph_dir / "test" / config.name / "data"
        config.data_dir = config.base_data_dir / config.dataset
        config.data_dir.mkdir(parents=True, exist_ok=True)
        config.container_name = f"{config.container_name}-test"
        config.port = config.test_port
        # make sure the port is reconfigured for test
        config.base_url = None
        pass

    def get_server_commands(self) -> Dict[str, Callable[[SparqlServer], ServerCmd]]:
        """
        Get available server commands as factory functions.

        Returns:
            Dictionary mapping command names to ServerCmd factories
        """

        def title(action, s):
            return f"{action} {s.name} ({s.config.container_name})"

        server_cmds = {
            "start": lambda s: ServerCmd(title("start", s), s.start),
            "stop": lambda s: ServerCmd(title("stop", s), s.stop),
            "rm": lambda s: ServerCmd(title("remove", s), s.rm),
            "bash": lambda s: ServerCmd(title("bash into", s), s.bash),
            "logs": lambda s: ServerCmd(title("logs of", s), s.logs),
            "status": lambda s: ServerCmd(title("status", s), s.status),
            "clear": lambda s: ServerCmd(title("clear", s), s.clear),
            "needed": lambda s: ServerCmd(title("check needed software for", s), s.check_needed_software),
            "count": lambda s: ServerCmd(title("triple count", s), s.count_triples),
            "load": lambda s: ServerCmd(title("load dumps", s), s.load_dump_files),
            "webui": lambda s: ServerCmd(title("webui", s), s.webui),
        }
        return server_cmds

    def server4Config(self, config: ServerConfig) -> SparqlServer:
        """
        Create a SparqlServer instance based on server type in config.

        Args:
            config: ServerConfig with server type and settings

        Returns:
            SparqlServer instance of appropriate type
        """
        server_instance = None
        if self.patch_config:
            self.patch_config(config)
        config_dict = asdict(config)

        if config.server == "blazegraph":
            blazegraph_config = BlazegraphConfig(**config_dict)
            server_instance = Blazegraph(config=blazegraph_config, env=self.env)
        elif config.server == "graphdb":
            graphdb_config = GraphDBConfig(**config_dict)
            server_instance = GraphDB(config=graphdb_config, env=self.env)
        elif config.server == "jena":
            jena_config = JenaConfig(**config_dict)
            server_instance = Jena(config=jena_config, env=self.env)
        elif config.server == "qlever":
            qlever_config = QLeverConfig(**config_dict)
            server_instance = QLever(config=qlever_config, env=self.env)
        else:
            raise ValueError(f"Knowledge Graph Server {config.server} not supported yet")

        return server_instance

    def servers(self, yaml_path: Path) -> Dict[str, SparqlServer]:
        """
        Load active servers from YAML configuration.

        Args:
            yaml_path: Path to YAML configuration file

        Returns:
            Dictionary mapping server names to SparqlServer instances
        """
        server_configs = ServerConfigs.ofYaml(yaml_path)
        servers_dict = {}

        for server_name, config in server_configs.servers.items():
            if config.active:
                server_instance = self.server4Config(config)
                if server_instance:
                    servers_dict[server_name] = server_instance

        return servers_dict
