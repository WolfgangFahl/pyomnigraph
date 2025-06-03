"""
Created on 2025-05-30

@author: wf

Command line interface for RDF dump downloading.
"""

import os
import webbrowser
from argparse import ArgumentParser, Namespace

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
        super().__init__(description="Download RDF dump from SPARQL endpoint via paginated CONSTRUCT queries")

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
            "--limit",
            type=int,
            default=10000,
            help="Number of triples per request [default: %(default)s]",
        )
        parser.add_argument("-l", "--list", action="store_true", help="List available datasets [default: %(default)s]")
        parser.add_argument(
            "--count", action="store_true", help="List available datasets with triple counts[default: %(default)s]"
        )
        parser.add_argument("--dump", action="store_true", help="perform the dump [default: %(default)s]")
        parser.add_argument(
            "-4o",
            "--for-omnigraph",
            action="store_true",
            help="store dump at default omnigraph location [default: %(default)s]",
        )
        parser.add_argument(
            "--max-count",
            type=int,
            default=None,
            help="Maximum number of solutions/triples to download (uses dataset expected_solutions if not specified)",
        )
        parser.add_argument("--no-progress", action="store_true", help="Disable progress bar")
        parser.add_argument("--output-path", default=".", help="Path for dump files")
        parser.add_argument("--tryit", action="store_true", help="open the try it! URL [default: %(default)s]")

        return parser

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
            print(
                f"Starting download for dataset: {dataset_name} to {dataset_dir} in {self.rdf_format.label} format ..."
            )

        downloader = RdfDumpDownloader(dataset=dataset, output_path=dataset_dir, args=self.args)

        chunk_count = downloader.download()
        print(f"Dataset {dataset_name}: Downloaded {chunk_count} {self.rdf_format.extension} files.")

    def handle_args(self, args: Namespace):
        """
        Handle parsed CLI arguments.

        Args:
            args: parsed namespace
        """
        super().handle_args(args)
        datasets = self.datasets
        if self.args.about:
            self.about()

        if self.args.list:
            print("Available datasets:")
            for dataset in self.all_datasets.datasets.values():
                print(f"  {dataset.full_name}")
            return

        if self.args.count:
            print("Triple count for available datasets:")
            for dataset in datasets.values():
                tryit_url = dataset.getTryItUrl(dataset.database)
                print(f"  {dataset.full_name}")
                if self.args.tryit:
                    webbrowser.open(tryit_url)
                count = dataset.sparql.getValue(dataset.count_query.query, "count")
                print(f"  {count} triples")

        output_path = self.args.output_path
        if self.args.for_omnigraph:
            output_path = self.ogp.dumps_dir

        if self.args.dump:
            for dataset_name, dataset in datasets.items():
                self.download_dataset(dataset_name, dataset, output_path)


def main():
    RdfDumpCmd.main()
