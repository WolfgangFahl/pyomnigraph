"""
Created on 2025-05-28

@author: wf
"""
import webbrowser
from pathlib import Path

from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.omniserver import OmniServer
from omnigraph.version import Version
from argparse import ArgumentParser, RawDescriptionHelpFormatter

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

        parser = ArgumentParser(
            description=description, formatter_class=RawDescriptionHelpFormatter
        )
        parser.add_argument(
            "-a",
            "--about",
            help="show about info [default: %(default)s]",
            action="store_true",
        )
        parser.add_argument(
            "-c","--config",
            type=str,
            default=str(self.default_yaml_path),
            help="Path to server configuration YAML file [default: %(default)s]"
        )
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            help="show debug info [default: %(default)s]",
        )
        parser.add_argument(
            "-l",
            "--list-servers",
            action="store_true",
            help="List available servers [default: %(default)s]"
        )
        parser.add_argument(
            "--status",
            type=str,
            help="Check status of specific server"
        )
        parser.add_argument("-V", "--version", action="version", version=version_msg)
        return parser

    def handle_args(self) -> bool:
        """
        Handle command line arguments.

        Returns:
            bool: True if arguments were handled, False otherwise
        """
        handled = False
        self.servers={}
        if Path(self.args.config).exists():
            servers = OmniServer.servers(self.args.config)
        else:
            print(f"Config file not found: {self.args.config}")

        if self.args.about:
            print(self.program_version_message)
            print(f"{len(servers)} servers configured")
            print(f"see {self.version.doc_url}")
            webbrowser.open(self.version.doc_url)
            handled = True

        if self.args.list_servers:
            print("Available servers:")
            for name, server in servers.items():
                print(f"  {name}: {server.config.server}")
            handled = True

        if self.args.status:
            if self.args.status in servers:
                status = servers[self.args.status].status()
                print(f"{self.args.status}: {status}")
            else:
                print(f"Server '{self.args.status}' not found")
            handled = True
        return handled


def main():
    """
    Main entry point for command line interface.
    """
    cmd = OmnigraphCmd()
    cmd.args = cmd.parser.parse_args()
    cmd.handle_args()


if __name__ == "__main__":
    main()