
"""
Created on 2025-05-30

@author: wf

Command line interface for RDF dump downloading.
"""

from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from omnigraph.rdfdump import RdfDumpDownloader
from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.rdf_dataset import RdfDataset, RdfDatasets
from omnigraph.version import Version
from typing import Dict

class RdfDumpCmd:
    """
    Command line interface for RDF dump downloading.
    """

    def __init__(self):
        """
        Initialize command line interface.
        """
        self.ogp = OmnigraphPaths()
        self.default_datasets_path = self.ogp.examples_dir / "datasets.yaml"
        self.version = Version()
        self.program_version_message = f"{self.version.name} RDF Dump Downloader {self.version.version}"
        self.parser = self.getArgParser()

    def getArgParser(self, description: str = None, version_msg=None) -> ArgumentParser:
        """
        Setup command line argument parser.
        """
        if description is None:
            description = "Download RDF dump from SPARQL endpoint via paginated CONSTRUCT queries"
        if version_msg is None:
            version_msg = self.program_version_message

        parser = ArgumentParser(description=description, formatter_class=RawDescriptionHelpFormatter)
        parser.add_argument(
            "-c",
            "--config",
            type=str,
            default=str(self.default_datasets_path),
            help="Path to datasets configuration YAML file [default: %(default)s]",
        )
        parser.add_argument(
            "-d",
            "--datasets",
            nargs="+",
            default=["all"],
            help="datasets to download - all is an alias for all datasets [default: %(default)s]",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=10000,
            help="Number of triples per request [default: %(default)s]",
        )
        parser.add_argument(
            "-l", "--list", action="store_true", help="List available datasets [default: %(default)s]"
        )
        parser.add_argument(
            "--max-triples",
            type=int,
            default=None,
            help="Maximum number of triples to download (uses dataset expected_triples if not specified)",
        )
        parser.add_argument("--no-progress", action="store_true", help="Disable progress bar")
        parser.add_argument("--output-path", default=".", help="Path for dump files")
        parser.add_argument("-V", "--version", action="version", version=version_msg)
        return parser

    def getDatasets(self) -> Dict[str, RdfDataset]:
        """
        Get the datasets to work with.
        """
        datasets = {}
        all_datasets = RdfDatasets.ofYaml(self.args.config)
        dataset_names = self.args.datasets
        if "all" in dataset_names:
            dataset_names = list(all_datasets.datasets.keys())
        for dataset_name in dataset_names:
            dataset = all_datasets.datasets.get(dataset_name)
            if dataset:
                datasets[dataset_name] = dataset
        return datasets

    def download_dataset(self, dataset_name: str, dataset: RdfDataset):
        """
        Download a single dataset.
        """
        print(f"Starting download for dataset: {dataset_name}")

        downloader = RdfDumpDownloader(
            dataset=dataset,
            output_path=self.args.output_path,
            limit=self.args.limit,
            max_triples=self.args.max_triples,
            show_progress=not self.args.no_progress,
        )

        chunk_count = downloader.download()
        print(f"Dataset {dataset_name}: Downloaded {chunk_count} chunks.")

    def handle_args(self, args: Namespace):
        """
        Handle command line arguments.
        """
        self.args = args
        datasets = self.getDatasets()
        if self.args.list:
            print("Available datasets:")
            for dataset_name, dataset in datasets.items():
                print(f"  {dataset_name}: {dataset.name}")
            return

        for dataset_name, dataset in datasets.items():
            self.download_dataset(dataset_name, dataset)


def main():
    """
    Main entry point for command line interface.
    """
    cmd = RdfDumpCmd()
    args = cmd.parser.parse_args()
    cmd.handle_args(args)