"""
Created on 2025-05-26

@author: wf
"""

import json
from pathlib import Path

from tqdm import tqdm

from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.omniserver import OmniServer
from omnigraph.sparql_server import SparqlServer
from tests.basetest import Basetest


class TestSparqlServer(Basetest):
    """
    test starting blazegraph
    """

    def setUp(self, debug=True, profile=True):
        """
        setUp the test environment
        """
        Basetest.setUp(self, debug=debug, profile=profile)
        self.ogp = OmnigraphPaths()
        servers_yaml_path = self.ogp.examples_dir / "servers.yaml"
        self.servers = OmniServer.servers(str(servers_yaml_path))

    def clear_server(self, server: SparqlServer):
        """
        delete all trips
        """
        if self.debug:
            print("deleting all triples ...")
        clear_query = "DELETE { ?s ?p ?o } WHERE { ?s ?p ?o }"
        server.sparql.insert(clear_query)
        count_triples = server.count_triples()
        self.assertEqual(0, count_triples)

    def start_server(self, server: SparqlServer, verbose: bool = True):
        if server.is_running():
            if self.debug and verbose:
                print(f"{server.name} already running")
        else:
            started = server.start()
            self.assertTrue(started)
        if verbose:
            status = server.status()
            if self.debug:
                print(json.dumps(status, indent=2))
            count_triples = server.count_triples()
            if self.debug:
                print(f"{count_triples} triples found for {server.name}")

    def test_start(self):
        """
        test starting servers
        """
        for server in self.servers.values():
            self.start_server(server)

    def test_load_dumps(self):
        dumps_dir = self.ogp.examples_dir
        for server in self.servers.values():
            self.load_dump_files(server, dumps_dir)

    def load_dump_files(self, server: SparqlServer, dumps_dir: Path):
        """
        test loading dump files if available
        """
        if not dumps_dir.exists():
            self.skipTest(f"Dumps directory {dumps_dir} not available")
        self.start_server(server, verbose=False)
        # self.skipTest("protect existing servers")
        # return
        self.clear_server(server)

        # Get all TTL files
        dump_files = sorted(list(dumps_dir.glob("*.ttl")))
        if self.debug:
            print(f"Found {len(dump_files)} dump files in {dumps_dir}")

        # Load files individually
        loaded_count = 0
        for dump_file in tqdm(dump_files, desc="Loading dump files"):
            file_loaded = server.load_file(str(dump_file))
            if file_loaded:
                loaded_count += 1
            if self.debug:
                status = "✅" if file_loaded else "❌"
                print(f"{status} {dump_file.name}")

        if self.debug:
            print(f"Successfully loaded {loaded_count}/{len(dump_files)} files")

        # Count triples after loading
        final_count = server.count_triples()
        if self.debug:
            print(f"Total triples after loading: {final_count:,}")

        self.assertGreater(loaded_count, 0)
        self.assertGreater(final_count, 0)
