"""
Created on 2025-05-28

@author: wf
"""

from dataclasses import asdict
from pathlib import Path
from typing import Dict

from omnigraph.blazegraph import Blazegraph, BlazegraphConfig
from omnigraph.jena import Jena, JenaConfig
from omnigraph.qlever import QLever, QLeverConfig
from omnigraph.sparql_server import ServerEnv,ServerConfig, ServerConfigs, SparqlServer


class OmniServer:
    """
    Factory class for creating and managing SPARQL server instances.
    """

    def __init__(self,env:ServerEnv):
        """
        constructor
        """
        self.env=env

    def server4Config(self, config: ServerConfig) -> SparqlServer:
        """
        Create a SparqlServer instance based on server type in config.

        Args:
            config: ServerConfig with server type and settings

        Returns:
            SparqlServer instance of appropriate type
        """
        server_instance = None
        config_dict = asdict(config)

        if config.server == "blazegraph":
            blazegraph_config = BlazegraphConfig(**config_dict)
            server_instance = Blazegraph(config=blazegraph_config,env=self.env)
        elif config.server == "qlever":
            qlever_config = QLeverConfig(**config_dict)
            server_instance = QLever(config=qlever_config,env=self.env)
        elif config.server == "jena":
            jena_config = JenaConfig(**config_dict)
            server_instance = Jena(config=jena_config,env=self.env)

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
