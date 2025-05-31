"""
Created on 31.05.2025

@author: wf
"""

from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
import webbrowser

from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.version import Version


class BaseCmd:
    """
    Base class for Omnigraph-related command line interfaces.
    """

    def __init__(self, description: str = None):
        """
        Initialize CLI base.
        """
        self.ogp = OmnigraphPaths()
        self.version = Version()
        self.program_version_message = f"{self.version.name} {self.version.version}"
        if description is None:
            description = self.version.description
        self.parser=None
        self.debug=False
        self.quiet=False

    def get_arg_parser(self, description: str, version_msg: str) -> ArgumentParser:
        """
        Setup argument parser.

        Args:
            description: CLI description
            version_msg: Version string

        Returns:
            Configured argument parser
        """
        parser = ArgumentParser(description=description, formatter_class=RawDescriptionHelpFormatter)
        parser.add_argument(
            "-a",
            "--about",
            help="show about info [default: %(default)s]",
            action="store_true",
        )
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
            help="force actions that would modify existing data [default: %(default)s]",
        )
        parser.add_argument(
            "-q",
            "--quiet",
            action="store_true",
            help="avoid any output [default: %(default)s]",
        )

        parser.add_argument("-V", "--version", action="version", version=version_msg)
        return parser

    def about(self):
        """
        show about info
        """
        print(self.program_version_message)
        print(f"see {self.version.doc_url}")
        webbrowser.open(self.version.doc_url)

    def handle_args(self, args: Namespace):
        """
        Must be implemented in subclass.
        """
        self.args = args
        self.debug=args.debug
        self.quiet=args.quiet

    def parse_args(self)->Namespace:
        if not self.parser:
            self.parser = self.get_arg_parser(self.version.description, self.program_version_message)
        args = self.parser.parse_args()
        return args

    def run(self):
        """
        Parse arguments and dispatch to handler.
        """
        args=self.parse_args()
        self.handle_args(args)


    @classmethod
    def main(cls):
        """
        Entry point for CLI.
        """
        instance = cls()
        args=instance.parse_args()
        instance.handle_args(args)
