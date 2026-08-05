"""
Created on 2026-08-05

test addressing two datasets in parallel on one server - see issue #44

@author: wf
"""

from omnigraph.sparql_server import SparqlServer
from tests.basesparqltest import BaseSparqlTest


class TestDatasets(BaseSparqlTest):
    """
    two datasets on one server keep their own content
    """

    def setUp(self, debug=False, profile=True, force=True):
        """
        setUp the test environment
        """
        BaseSparqlTest.setUp(self, debug=debug, profile=profile, force=force)
        self.dumps_dir = self.ogp.examples_dir

    def load_into(self, server: SparqlServer, dataset: str) -> int:
        """
        Address the given dataset on the server and load the example dump into it.

        Args:
            server: the server to work on
            dataset: the dataset to address

        Returns:
            the triple count of that dataset
        """
        addressed = server.use_dataset(dataset)
        self.assertTrue(addressed, f"could not address dataset {dataset}")
        server.config.dumps_dir = self.dumps_dir
        server.clear()
        server.load_dump_files()
        triple_count = server.count_triples()
        return triple_count

    def test_two_datasets(self):
        """
        A second dataset holds its own triples and clearing one leaves the other.

        royals.ttl has 63 triples, so a server addressing two datasets reports 63
        for each of them, and 0 for the one that was cleared while the other keeps
        its 63.
        """
        checked = self.with_each_server(self.check_isolation)
        self.assertTrue(checked, "no backend could be started")

    def check_isolation(self, name: str, server: SparqlServer):
        """
        Check that two datasets on the given server keep their own content.

        Args:
            name: the server name
            server: the server to check
        """
        expected = 63
        if server.supports_datasets:
            count_a = self.load_into(server, "omnigraph_a")
            count_b = self.load_into(server, "omnigraph_b")
            self.assertEqual(expected, count_a, f"{name}: dataset a has {count_a} triples")
            self.assertEqual(expected, count_b, f"{name}: dataset b has {count_b} triples")
            # clearing b must not touch a
            server.use_dataset("omnigraph_b")
            server.clear()
            self.assertEqual(0, server.count_triples(), f"{name}: dataset b not cleared")
            server.use_dataset("omnigraph_a")
            self.assertEqual(
                expected,
                server.count_triples(),
                f"{name}: dataset a lost its triples when b was cleared",
            )
            if self.debug:
                print(f"{name}: two datasets isolated")
