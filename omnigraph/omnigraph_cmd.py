"""
Created on 2025-05-28

@author: wf
"""

import webbrowser
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from pathlib import Path
from typing import Dict, List

from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.omniserver import OmniServer
from omnigraph.sparql_server import ServerEnv, SparqlServer
from omnigraph.version import Version


class OmnigraphCmd:
    """
    Command line interface for omnigraph.
    """

    def __init__(self):
        """
        Initialize command line interface.
        """
        self.ogp = OmnigraphPaths()
        self.default_yaml_path = self.ogp.examples_dir / "servers.yaml"
        self.version = Version()
        self.program_version_message = f"{self.version.name} {self.version.version}"
        # Prepare an environment to extract commands
        self.env = ServerEnv()
        self.omni_server = OmniServer(env=self.env)
        self.server_cmds = self.omni_server.get_server_commands()
        available_cmds_keys = list(self.server_cmds.keys())
        self.available_cmds = ", ".join(available_cmds_keys)
        self.parser = self.getArgParser()

    def getArgParser(self, description: str = None, version_msg=None) -> ArgumentParser:
        """
        Setup command line argument parser

        Args:
            description(str): the description
            version_msg(str): the version message

        Returns:
            ArgumentParser: the argument parser
        """
        if description is None:
            description = self.version.description
        if version_msg is None:
            version_msg = self.program_version_message

        parser = ArgumentParser(description=description, formatter_class=RawDescriptionHelpFormatter)
        parser.add_argument(
            "-a",
            "--about",
            help="show about info [default: %(default)s]",
            action="store_true",
        )
        parser.add_argument(
            "-c",
            "--config",
            type=str,
            default=str(self.default_yaml_path),
            help="Path to server configuration YAML file [default: %(default)s]",
        )
        parser.add_argument("--cmd", nargs="+", help=f"commands to execute on servers: {self.available_cmds}")
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            help="show debug info [default: %(default)s]",
        )
        parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="force action e.g. for clear command [default: %(default)s]",
        )
        parser.add_argument(
            "-l", "--list-servers", action="store_true", help="List available servers [default: %(default)s]"
        )
        parser.add_argument(
            "--test",
            action="store_true",
            help="use test environment [default: %(default)s]",
        )
        parser.add_argument(
            "-q",
            "--quiet",
            action="store_true",
            help="avoid any output [default: %(default)s]",
        )
        parser.add_argument(
            "-s",
            "--servers",
            nargs="+",
            default=["blazegraph"],
            help="servers: servers to work with - all is an alias for all servers [default: %(default)s]",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="show verbose output [default: %(default)s]",
        )
        parser.add_argument("-V", "--version", action="version", version=version_msg)
        return parser

    def getServers(self) -> Dict[str, SparqlServer]:
        """
        Get the servers to work with.

        Returns:
            Dictionary of active servers
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
                    server.config.data_dir = self.ogp.omnigraph_dir / f"{server.name}" / f"{server.config.dataset}"
                    server.config.data_dir.mkdir(parents=True, exist_ok=True)
                servers[server_name] = server
        return servers

    def run_cmds(self, server: SparqlServer, cmds: List[str]) -> bool:
        """
        Run commands on a server.

        Args:
            server: Server instance
            cmds: List of commands to execute

        Returns:
            True if any commands were handled
        """
        handled = False
        if cmds:
            for cmd in cmds:
                s_cmd_factory = self.server_cmds.get(cmd)
                s_cmd = s_cmd_factory(server)
                if s_cmd:
                    s_cmd.run(verbose=not self.args.quiet)
                    handled = True
                else:
                    print(f"unsupported command {cmd}")
        return handled

    def handle_args(self, args: Namespace) -> bool:
        """
        Handle command line arguments.

        Returns:
            bool: True if arguments were handled, False otherwise
            args: Namespace
        """
        self.args = args
        handled = False
        self.all_servers = {}
        if Path(self.args.config).exists():
            env = ServerEnv(debug=args.debug, verbose=args.verbose)
            patch_config = None
            if args.test:
                patch_config = lambda config: OmniServer.patch_test_config(config, self.ogp)
            omni_server = OmniServer(env=env, patch_config=patch_config)
            self.all_servers = omni_server.servers(args.config)
        else:
            print(f"Config file not found: {args.config}")
        self.servers = self.getServers()

        if args.about:
            print(self.program_version_message)
            print(f"{len(self.all_servers)} servers configured - {len(self.servers)} active")
            for name, server in self.servers.items():
                print(f"  {server.full_name}")
            print(f"see {self.version.doc_url}")
            webbrowser.open(self.version.doc_url)
            handled = True

        if self.args.list_servers:
            print("Available servers:")
            for server in self.all_servers.value():
                print(f"  {server.full_name}")
            handled = True
        cmds = list(args.cmd)
        for server in self.servers.values():
            if not self.args.quiet:
                print(f"  {server.full_name}:")
            try:
                cmds_handled = self.run_cmds(server, cmds=cmds)
                handled = handled or cmds_handled
            except Exception as ex:
                server.handle_exception(f"{args.cmd}", ex)

        return handled


def main():
    """
    Main entry point for command line interface.
    """
    cmd = OmnigraphCmd()
    args = cmd.parser.parse_args()
    cmd.handle_args(args)


if __name__ == "__main__":
    main()
