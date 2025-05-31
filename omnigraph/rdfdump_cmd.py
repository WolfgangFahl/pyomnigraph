"""
Created on 2025-05-30

@author: wf

Command line interface for RDF dump downloading.
"""

from argparse import ArgumentParser, Namespace
import os
from typing import Dict

from omnigraph.basecmd import BaseCmd
from omnigraph.rdf_dataset import RdfDataset, RdfDatasets
from omnigraph.rdfdump import RdfDumpDownloader

class RdfDumpCmd(BaseCmd):
    """
    Command line interface for RDF dump downloading.
    """

    def __init__(self):
        """
        Initialize command line interface.
        """
        super().__init__(
            description="Download RDF dump from SPARQL endpoint via paginated CONSTRUCT queries"
        )
        self.default_datasets_path = self.ogp.examples_dir / "datasets.yaml"

    def get_arg_parser(self, description: str, version_msg: str) -> ArgumentParser:
        """
        Extend base parser with RDF-specific arguments.

        Args:
            description: CLI description string
            version_msg: version display string

        Returns:
            ArgumentParser: extended argument parser
        """
        parser = super().get_arg_parser(description, version_msg)
        parser.add_argument(
            "-c",
            "--config",
            type=str,
            default=str(self.default_datasets_path),
            help="Path to datasets configuration YAML file [default: %(default)s]",
        )
        parser.add_argument(
            "-ds",
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
        parser.add_argument("-l", "--list", action="store_true", help="List available datasets [default: %(default)s]")
        parser.add_argument(
            "-4o",
            "--for-omnigraph",
            action="store_true",
            help="store dump at default omnigraph location [default: %(default)s]",
        )
        parser.add_argument(
            "--max-triples",
            type=int,
            default=None,
            help="Maximum number of triples to download (uses dataset expected_triples if not specified)",
        )
        parser.add_argument("--no-progress", action="store_true", help="Disable progress bar")
        parser.add_argument("--output-path", default=".", help="Path for dump files")
        return parser

    def getDatasets(self) -> Dict[str, RdfDataset]:
        """
        Resolve and select datasets to download.

        Returns:
            Dict[str, RdfDataset]: selected datasets by name
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

    def download_dataset(self, dataset_name: str, dataset: RdfDataset, output_path: str):
        """
        Download the specified dataset to a subdirectory.

        Args:
            dataset_name: name of dataset
            dataset: RDF dataset definition
            output_path: base output directory
        """
        dataset_dir = os.path.join(output_path, dataset_name)
        os.makedirs(dataset_dir, exist_ok=True)
        if not self.quiet:
            print(f"Starting download for dataset: {dataset_name} to {dataset_dir} ...")

        downloader = RdfDumpDownloader(
            dataset=dataset,
            output_path=dataset_dir,
            limit=self.args.limit,
            max_triples=self.args.max_triples,
            show_progress=not self.args.no_progress,
        )

        chunk_count = downloader.download()
        print(f"Dataset {dataset_name}: Downloaded {chunk_count} chunks.")

    def handle_args(self, args: Namespace):
        """
        Handle parsed CLI arguments.

        Args:
            args: parsed namespace
        """
        super().handle_args(args)
        if self.args.about:
            self.about()
        datasets = self.getDatasets()
        if self.args.list:
            print("Available datasets:")
            for dataset_name, dataset in datasets.items():
                print(f"  {dataset_name}: {dataset.name}")
            return

        output_path = self.args.output_path
        if self.args.for_omnigraph:
            output_path = self.ogp.dumps_dir

        for dataset_name, dataset in datasets.items():
            self.download_dataset(dataset_name, dataset, output_path)

def main():
    RdfDumpCmd.main()
