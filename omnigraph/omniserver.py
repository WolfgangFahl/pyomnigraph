"""
Created on 2025-05-28

@author: wf
"""

from dataclasses import asdict
from pathlib import Path
from typing import Callable, Dict

from tabulate import tabulate

from omnigraph.ominigraph_paths import OmnigraphPaths
from lodstorage.prefix_config import PrefixConfigs
from omnigraph.server_config import ServerCmd, ServerConfig, ServerConfigs, ServerEnv
from omnigraph.servers.blazegraph import Blazegraph, BlazegraphConfig
from omnigraph.servers.graphdb import GraphDB, GraphDBConfig
from omnigraph.servers.jena import Jena, JenaConfig
from omnigraph.servers.oxigraph import Oxigraph, OxigraphConfig
from omnigraph.servers.qlever import QLever, QLeverConfig
from omnigraph.servers.stardog import Stardog, StardogConfig
from omnigraph.servers.virtuoso import Virtuoso, VirtuosoConfig
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
            "bash": lambda s: ServerCmd(title("bash into", s), s.bash),
            "clear": lambda s: ServerCmd(title("clear", s), s.clear),
            "count": lambda s: ServerCmd(title("triple count", s), s.count_triples),
            "info": lambda s: ServerCmd(title("info", s), s.docker_info),
            "load": lambda s: ServerCmd(title("load dumps", s), s.load_dump_files),
            "logs": lambda s: ServerCmd(title("logs of", s), s.logs),
            "needed": lambda s: ServerCmd(title("check needed software for", s), s.check_needed_software),
            "rm": lambda s: ServerCmd(title("remove", s), s.rm),
            "start": lambda s: ServerCmd(title("start", s), s.start),
            "status": lambda s: ServerCmd(title("status", s), s.status_info),
            "stop": lambda s: ServerCmd(title("stop", s), s.stop),
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
        if self.patch_config:
            self.patch_config(config)
        config_dict = asdict(config)

        server_mappings = {
            "blazegraph": (BlazegraphConfig, Blazegraph),
            "graphdb": (GraphDBConfig, GraphDB),
            "jena": (JenaConfig, Jena),
            "oxigraph": (OxigraphConfig, Oxigraph),
            "qlever": (QLeverConfig, QLever),
            "stardog": (StardogConfig, Stardog),
            "virtuoso": (VirtuosoConfig, Virtuoso),
        }

        if config.server not in server_mappings:
            raise ValueError(f"Knowledge Graph Server {config.server} not supported yet")

        config_class, server_class = server_mappings[config.server]
        server_config = config_class(**config_dict)
        server_instance = server_class(config=server_config, env=self.env)

        return server_instance

    def servers(self, yaml_path: Path, filter_active: bool = True) -> Dict[str, SparqlServer]:
        """
        Load active servers from YAML configuration.

        Args:
            yaml_path: Path to YAML configuration file
            filter_active: if true filter active servers

        Returns:
            Dictionary mapping server names to SparqlServer instances
        """
        server_configs = ServerConfigs.ofYaml(yaml_path)
        servers_dict = {}

        for server_name, config in server_configs.servers.items():
            if config.active or not filter_active:
                server_instance = self.server4Config(config)
                if server_instance:
                    servers_dict[server_name] = server_instance

        return servers_dict

    def list_servers(self, servers: Dict[str, SparqlServer], table_format: str, host: str = "localhost") -> str:
        """
        Generate formatted table of servers.

        Args:
            servers: Dictionary of server instances
            table_format: Table format for tabulate
            host: Host for server links (default: localhost)

        Returns:
            str: Formatted table markup
        """
        headers = ["Active", "Name", "Container Name", "Wikidata", "Image", "Port", "Test Port", "Dataset", "User"]
        table_data = []

        def format_link(text: str, url: str, format_type: str) -> str:
            """Format link based on table format."""
            if format_type == "plain" or format_type == "simple":
                return text
            elif format_type == "html":
                return f'<a href="{url}">{text}</a>'
            elif format_type == "mediawiki":
                return f"[{url} {text}]"
            elif format_type == "rst":
                return f"`{text} <{url}>`_"
            elif format_type == "github":
                return f"[{text}]({url})"
            else:
                return text

        for server in servers.values():
            active_str = server.flag

            wikidata_id = getattr(server.config, "wikidata_id", "")
            wikidata_link = (
                format_link(wikidata_id, f"https://www.wikidata.org/wiki/{wikidata_id}", table_format)
                if wikidata_id
                else ""
            )

            server_host = getattr(server.config, "host", host)
            if server_host == "localhost" and host != "localhost":
                server_host = host
            server_port = getattr(server.config, "port", "")
            server_url = f"http://{server_host}:{server_port}" if server_port else ""
            server_name_link = format_link(server.name, server_url, table_format) if server_url else server.name
            image = getattr(server.config, "image", "")
            image_link = image
            if image:
                # Remove tag (everything after :) and create Docker Hub link
                image_name = image.split(":")[0]
                docker_url = f"https://hub.docker.com/r/{image_name}"
                image_link = format_link(image, docker_url, table_format)

            table_data.append(
                [
                    active_str,
                    server_name_link,
                    server.config.container_name,
                    wikidata_link,
                    image_link,
                    server_port,
                    getattr(server.config, "test_port", ""),
                    getattr(server.config, "dataset", ""),
                    getattr(server.config, "auth_user", ""),
                ]
            )

        markup = tabulate(table_data, headers=headers, tablefmt=table_format)
        return markup

    def generate_endpoints_yaml(
        self, servers: Dict[str, SparqlServer], prefix_configs: PrefixConfigs, output_path: str = None
    ) -> str:
        """
        Generate endpoints.yaml from server configurations.
        """
        yaml_entries = []

        for server in servers.values():
            if server.config.active:
                prefix_sets = getattr(server.config, "prefix_sets", ["rdf"])
                prefixes_text = prefix_configs.get_selected_declarations(prefix_sets)
                # optional elements
                auth = "\n  auth: BASIC" if server.config.auth_user else ""
                user = f"\n  user: {server.config.auth_user}" if server.config.auth_user else ""
                passwd = f"\n  passwd: {server.config.auth_password}" if server.config.auth_password else ""
                # Indent prefixes for literal block scalar (4 spaces)
                indented_prefixes = "\n".join(f"    {line}" for line in prefixes_text.split("\n") if line.strip())

                entry = f"""{server.name}:
  method: {getattr(server.config, 'method', 'POST')}
  lang: sparql
  name: {server.name}
  endpoint: {server.config.sparql_url}
  website: {server.config.base_url}
  database: {server.config.server}{auth}{user}{passwd}
  prefixes: |
{indented_prefixes}"""

                yaml_entries.append(entry)

        yaml_header = "# SPARQL endpoints for snapquery, sparqlquery and omnigraph tools\n"
        yaml_header += server.config.generator_header() + "\n"
        yaml_content = yaml_header + "\n".join(yaml_entries)

        if output_path:
            with open(output_path, "w") as f:
                f.write(yaml_content)

        return yaml_content
