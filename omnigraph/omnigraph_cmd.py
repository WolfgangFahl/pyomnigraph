"""
Created on 2025-05-28

@author: wf
"""
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Dict, List

from omnigraph.basecmd import BaseCmd
from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.omniserver import OmniServer
from omnigraph.sparql_server import ServerEnv, SparqlServer

class OmnigraphCmd(BaseCmd):
    """
    Command line interface for omnigraph.
    """

    def __init__(self):
        """
        Initialize command line interface.
        """
        self.ogp = OmnigraphPaths()
        self.default_yaml_path = self.ogp.examples_dir / "servers.yaml"
        self.env = ServerEnv()
        self.omni_server = OmniServer(env=self.env)
        self.server_cmds = self.omni_server.get_server_commands()
        self.available_cmds = ", ".join(self.server_cmds.keys())
        super().__init__(description="Manage SPARQL server configurations and command execution")

    def get_arg_parser(self, description: str, version_msg: str) -> ArgumentParser:
        """
        Extend base parser with Omnigraph-specific arguments.
        """
        parser = super().get_arg_parser(description, version_msg)
        parser.add_argument(
            "-c",
            "--config",
            type=str,
            default=str(self.default_yaml_path),
            help="Path to server configuration YAML file [default: %(default)s]",
        )
        parser.add_argument("--cmd", nargs="+", help=f"commands to execute on servers: {self.available_cmds}")
        parser.add_argument(
            "-l", "--list-servers", action="store_true", help="List available servers [default: %(default)s]"
        )
        parser.add_argument(
            "--test",
            action="store_true",
            help="use test environment [default: %(default)s]",
        )
        parser.add_argument(
            "-s",
            "--servers",
            nargs="+",
            default=["blazegraph"],
            help="servers to work with - 'all' selects all configured servers [default: %(default)s]",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="show verbose output [default: %(default)s]",
        )
        return parser

    def getServers(self) -> Dict[str, SparqlServer]:
        """
        Get the active servers from configuration.
        """
        servers = {}
        server_names = self.args.servers
        if "all" in server_names:
            server_names = list(self.all_servers.keys())
        for server_name in server_names:
            server = self.all_servers.get(server_name)
            if server:
                if server.config.dumps_dir is None:
                    server.config.dumps_dir = self.ogp.examples_dir
                    server.config.data_dir = self.ogp.omnigraph_dir / server.name / server.config.dataset
                    server.config.data_dir.mkdir(parents=True, exist_ok=True)
                servers[server_name] = server
        return servers

    def run_cmds(self, server: SparqlServer, cmds: List[str]) -> bool:
        """
        Run commands on a specific server.

        Args:
            server: Server instance
            cmds: List of command names to run

        Returns:
            bool: True if any commands were successfully run
        """
        handled = False
        if cmds:
            for cmd in cmds:
                s_cmd_factory = self.server_cmds.get(cmd)
                s_cmd = s_cmd_factory(server) if s_cmd_factory else None
                if s_cmd:
                    s_cmd.run(verbose=not self.quiet)
                    handled = True
                else:
                    print(f"unsupported command {cmd}")
        return handled

    def handle_args(self, args: Namespace):
        """
        Handle parsed CLI arguments.

        Args:
            args: parsed argument namespace
        """
        super().handle_args(args)
        self.all_servers = {}
        if Path(self.args.config).exists():
            env = ServerEnv(debug=self.debug, verbose=self.args.verbose)
            patch_config = None
            if self.args.test:
                patch_config = lambda config: OmniServer.patch_test_config(config, self.ogp)
            omni_server = OmniServer(env=env, patch_config=patch_config)
            self.all_servers = omni_server.servers(self.args.config)
        else:
            print(f"Config file not found: {self.args.config}")
        self.servers = self.getServers()

        if self.args.about:
            self.about()
            print(f"{len(self.all_servers)} servers configured - {len(self.servers)} active")
            for _name, server in self.servers.items():
                print(f"  {server.full_name}")

        if self.args.list_servers:
            print("Available servers:")
            for server in self.all_servers.values():
                print(f"  {server.full_name}")

        cmds = list(self.args.cmd or [])
        for server in self.servers.values():
            if not self.quiet:
                print(f"  {server.full_name}:")
            try:
                self.run_cmds(server, cmds=cmds)
            except Exception as ex:
                server.handle_exception(str(self.args.cmd), ex)

def main():
    OmnigraphCmd.main()

if __name__ == "__main__":
    main()
