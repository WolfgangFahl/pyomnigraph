"""
Created on 31.05.2025

@author: wf
"""

import webbrowser
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from typing import Dict

from lodstorage.rdf_format import RdfFormat

from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.rdf_dataset import RdfDataset, RdfDatasets
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
        self.parser = None
        self.debug = False
        self.quiet = False
        self.force = False
        self.default_datasets_path = self.ogp.examples_dir / "datasets.yaml"

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
            "-ds",
            "--datasets",
            nargs="+",
            default=["wikidata_triplestores"],
            help="datasets to work with - all is an alias for all datasets [default: %(default)s]",
        )
        parser.add_argument(
            "-dc",
            "--datasets-config",
            type=str,
            default=str(self.default_datasets_path),
            help="Path to datasets configuration YAML file [default: %(default)s]",
        )

        parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="force actions that would modify existing data [default: %(default)s]",
        )
        rdf_format_choices = [fmt.label for fmt in RdfFormat]

        parser.add_argument(
            "-r",
            "--rdf_format",
            type=str,
            default="turtle",
            choices=rdf_format_choices,
            help="RDF format to use [default: %(default)s]",
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
        should be extended by specialized subclass.
        """
        self.args = args
        self.debug = args.debug
        self.quiet = args.quiet
        self.force = args.force
        self.datasets = self.getDatasets(yaml_path=args.datasets_config)
        self.rdf_format = RdfFormat.by_label(args.rdf_format)

    def parse_args(self) -> Namespace:
        if not self.parser:
            self.parser = self.get_arg_parser(self.version.description, self.program_version_message)
        args = self.parser.parse_args()
        return args

    def run(self):
        """
        Parse arguments and dispatch to handler.
        """
        args = self.parse_args()
        self.handle_args(args)

    def getDatasets(self, yaml_path: str) -> Dict[str, RdfDataset]:
        """
        Resolve and select datasets to download.

        Args:
            yaml_path: Path to datasets configuration YAML file

        Returns:
            Dict[str, RdfDataset]: selected datasets by name
        """
        datasets = {}
        self.all_datasets = RdfDatasets.ofYaml(yaml_path)
        dataset_names = self.args.datasets
        if "all" in dataset_names:
            dataset_names = list(self.all_datasets.datasets.keys())
        for dataset_name in dataset_names:
            dataset = self.all_datasets.datasets.get(dataset_name)
            if dataset:
                datasets[dataset_name] = dataset
        return datasets

    @classmethod
    def main(cls):
        """
        Entry point for CLI.
        """
        instance = cls()
        args = instance.parse_args()
        instance.handle_args(args)
