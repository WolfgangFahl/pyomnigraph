"""
Created on 2025-05-26

@author: wf
"""

from argparse import Namespace
from pathlib import Path

from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.rdf_dataset import RdfDataset, RdfDatasets
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
            # Skip inactive datasets
            if not dataset.active:
                if self.debug:
                    print(f"Skipping inactive dataset: {name}")
                continue
            # Skip gov endpoints in public CI (not publicly accessible yet)
            if self.inPublicCI() and name.startswith("gov"):
                if self.debug:
                    print(f"Skipping {name} in public CI")
                continue
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

    def test_local_rdf_file_dataset(self):
        """
        Test loading dataset configuration with local rdf_file.
        """
        # Create a temporary test dataset YAML with local file
        test_yaml_path = "/tmp/omnigraph_test/test_dataset.yaml"
        test_rdf_file = "/tmp/omnigraph_test/test_data.ttl"

        # Verify test files exist
        if not Path(test_yaml_path).exists():
            self.skipTest(f"Test dataset YAML not found: {test_yaml_path}")
        if not Path(test_rdf_file).exists():
            self.skipTest(f"Test RDF file not found: {test_rdf_file}")

        # Load datasets from YAML
        datasets = RdfDatasets.ofYaml(test_yaml_path)
        self.assertIsNotNone(datasets)
        self.assertIn("test_local", datasets.datasets)

        dataset = datasets.datasets["test_local"]
        self.assertIsInstance(dataset, RdfDataset)
        self.assertEqual(dataset.name, "Test Local RDF File")
        self.assertEqual(dataset.rdf_file, test_rdf_file)
        self.assertIsNone(dataset.endpoint_url, "endpoint_url should be None for local file datasets")
        self.assertIsNone(dataset.sparql, "sparql should be None for local file datasets")

        if self.debug:
            print(f"Dataset: {dataset.name}")
            print(f"RDF file: {dataset.rdf_file}")
            print(f"Database: {dataset.database}")

        # Verify file path expansion works
        expanded_path = Path(dataset.rdf_file).expanduser().resolve()
        self.assertTrue(expanded_path.exists(), f"RDF file should exist: {expanded_path}")

        if self.debug:
            print(f"Expanded path: {expanded_path}")
            print(f"File parent: {expanded_path.parent}")
