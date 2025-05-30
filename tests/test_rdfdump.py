"""
Created on 2025-05-26

@author: wf
"""
from lodstorage.sparql import SPARQL
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
        self.datasets_yaml_path = self.ogp.examples_dir / "datasets.yaml"
        self.datasets=RdfDatasets.ofYaml(self.datasets_yaml_path)

    def test_rdf_datasets(self):
        """
        test rdf datasets
        """
        databases = {
            "wikidata_triplestores": "blazegraph",
            "gov_full": "jena",
            "gov-w2306": "jena",
        }
        self.assertIsNotNone(self.datasets)
        for name,dataset in self.datasets.datasets.items():
            database=databases.get(name)
            tryit_url= dataset.getTryItUrl(database)
            if self.debug:
                print(f"{name}:{dataset.count_query.query}")
                print(f"  {tryit_url}")
            count=dataset.sparql.getValue(dataset.count_query.query,"count")
            if self.debug:
                print(f"  {count} triples")


    def test_download_rdf_dump(self):
        """
        Test downloading RDF dump
        """
        # First, get the total number of triples to download
        sparql = SPARQL(self.endpoint_url)
        count_query = "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
        total_triples = int(sparql.getValue(count_query, "count"))

        if self.debug:
            print(f"Total triples in endpoint: {total_triples:,}")
        self.skipTest("rdf dump takes >1h")
        return
        limit = 100000
        # Set max_triples to download all (with some buffer)
        max_triples = total_triples + limit  # Add buffer for safety

        downloader = RdfDumpDownloader(
            endpoint_url=self.endpoint_url,
            output_path=self.dumps_dir,  # Specify output directory
            limit=100000,  # Larger chunks for efficiency
            max_triples=max_triples,
            show_progress=True,
        )

        if self.debug:
            print(f"Starting download of {total_triples:,} triples from: {self.endpoint_url}")

        chunks = downloader.download()

        if self.debug:
            print(f"Downloaded {chunks*limit} triples")

        self.assertGreater(chunks, 0)
