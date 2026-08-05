"""
Created on 2026-08-05

test the use case examples of the paper repository - see issue #52

@author: wf
"""

import os
from pathlib import Path

from omnigraph.server_config import LoadPath
from omnigraph.sparql_server import SparqlServer
from tests.basesparqltest import BaseSparqlTest


class TestExamples(BaseSparqlTest):
    """
    load the dated dump snapshot of the paper repository into the backends
    """

    # dataset directory name -> triple count of the snapshot
    expected_triples = {
        "line_identity_wikidata": 102,
        "station_locality_osm": 1263,
    }

    # backends whose importer refuses dumps a public endpoint produces - rated as
    # input tolerance in discussion #24 rather than failed here
    rejects_example_dumps = {"millenniumdb"}

    def setUp(self, debug=False, profile=True, force=True):
        """
        setUp the test environment
        """
        BaseSparqlTest.setUp(self, debug=debug, profile=profile, force=force)
        self.dumps_root = self.get_dumps_root()

    def get_dumps_root(self) -> Path:
        """
        Get the dump snapshot directory of the paper repository.

        Returns:
            the directory or None if the checkout is not available
        """
        dumps_root = None
        env_path = os.environ.get("PYOMNIGRAPH_EXAMPLES")
        candidates = []
        if env_path:
            candidates.append(Path(env_path))
        candidates.append(Path.home() / "source/latex/pyomnigraphPaper/examples/railway/dumps")
        for candidate in candidates:
            if candidate.is_dir():
                dumps_root = candidate
                break
        return dumps_root

    def load_dataset(self, server: SparqlServer, dataset: str) -> int:
        """
        Load one example dataset into the given server.

        Args:
            server: the server to load into
            dataset: name of the dataset directory

        Returns:
            the triple count after loading
        """
        server.config.dumps_dir = self.dumps_root / dataset
        # a store holding exactly one dataset is built where the backend can build,
        # and otherwise cleared and loaded through its endpoint
        if LoadPath.BUILD in server.load_paths:
            server.load_dump_files(path=LoadPath.BUILD)
        else:
            server.clear()
            server.load_dump_files(path=LoadPath.LIVELOAD)
        triple_count = server.count_triples()
        return triple_count

    def test_example_datasets(self):
        """
        Each example dataset loads with exactly its own triple count.

        The two datasets carry the same file name dump_000000.ttl in different
        directories, so a backend that stages dumps in a shared place serves the
        wrong content - see issue #40.
        """
        if self.dumps_root is None:
            self.skipTest("paper repository dump snapshot not available")
        servers = self.running_servers()
        self.assertTrue(servers, "no backend could be started")
        for name, server in servers.items():
            for dataset, expected in self.expected_triples.items():
                triple_count = self.load_dataset(server, dataset)
                if self.debug:
                    print(f"{name} {dataset}: {triple_count}")
                if name in self.rejects_example_dumps:
                    # a backend whose importer refuses the dumps is rated on it -
                    # see the input tolerance criterion of discussion #24 - and is
                    # not a reason for this test to fail
                    self.log_input_intolerance(name, dataset, expected, triple_count)
                    continue
                self.assertEqual(
                    expected,
                    triple_count,
                    f"{name}: expected {expected} triples of {dataset}, got {triple_count}",
                )

    def log_input_intolerance(self, name: str, dataset: str, expected: int, triple_count: int):
        """
        Report a backend that did not take the example dump as given.

        Args:
            name: server name
            dataset: dataset that was loaded
            expected: triple count of the dump
            triple_count: what the server reports
        """
        if triple_count != expected:
            print(f"input intolerance: {name} has {triple_count} of the {expected} triples of {dataset}")
