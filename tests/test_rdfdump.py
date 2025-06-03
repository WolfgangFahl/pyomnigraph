"""
Created on 2025-05-26

@author: wf
"""

from argparse import Namespace

from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.rdf_dataset import RdfDatasets
from omnigraph.rdfdump import RdfDumpDownloader
from tests.basetest import Basetest


class TestRdfDumpDownloader(Basetest):
    """
    Test RDF Dump Downloader
    """

    def setUp(self, debug=True, profile=True):
        """
        setUp the test environment
        """
        Basetest.setUp(self, debug=debug, profile=profile)
        self.ogp = OmnigraphPaths()
        self.dumps_dir = self.ogp.dumps_dir
        self.datasets_yaml_path = self.ogp.examples_dir / "datasets.yaml"
        self.datasets = RdfDatasets.ofYaml(self.datasets_yaml_path)

    def test_rdf_datasets(self):
        """
        test rdf datasets
        """
        databases = {
            "wikidata_triplestores": "blazegraph",
            "wikidata_families": "qlever",
            "gov_full": "jena",
            "gov-w2306": "jena",
        }
        self.assertIsNotNone(self.datasets)
        for name, dataset in self.datasets.datasets.items():
            database = databases.get(name)
            tryit_url = dataset.getTryItUrl(database)
            if self.debug:
                print(f"{name}:{dataset.count_query.query}")
                print(f"  {tryit_url}")
            count = dataset.sparql.getValue(dataset.count_query.query, "count")
            if self.debug:
                print(f"  {count} solutions")

    def test_download_rdf_dump(self):
        """
        Test downloading RDF dump
        """
        download_limit = 20000  # Only download if expected_solutions below this

        for dataset in self.datasets.datasets.values():
            with self.subTest(dataset=dataset):
                name = dataset.name
                if not dataset.active:
                    self.skipTest(f" dataset: {name} is not active")
                if self.debug:
                    print(f"Checking dataset: {name}")

                # Check if dataset is small enough to download
                count = dataset.expected_solutions
                if count and count > download_limit:
                    msg = f"Dataset {name}: {count:,} > {download_limit:,} limit"
                    if self.debug:
                        print(msg)
                    self.skipTest(msg)

                if self.debug:
                    print(f"Downloading {name}: {count}")

                # Create dataset-specific output directory
                dataset_output_dir = self.dumps_dir / name

                args = Namespace(
                    limit=10000, max_count=count, no_progress=False, force=True, rdf_format="turtle", debug=self.debug
                )

                downloader = RdfDumpDownloader(dataset=dataset, output_path=str(dataset_output_dir), args=args)

                chunks = downloader.download()

                if self.debug:
                    print(f" Downloaded {chunks} chunks for {name}")

                self.assertGreater(chunks, 0)
