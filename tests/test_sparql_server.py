"""
Created on 2025-05-26

@author: wf
"""

import json
import tempfile
from pathlib import Path

from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.omniserver import OmniServer
from omnigraph.sparql_server import ServerEnv, SparqlServer
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
        self.tempdir = Path(tempfile.mkdtemp(prefix="omnigraph_test_"))
        servers_yaml_path = self.ogp.examples_dir / "servers.yaml"
        env = ServerEnv()
        omni_server = OmniServer(env=env)
        self.servers = omni_server.servers(str(servers_yaml_path))

    def clear_server(self, server: SparqlServer):
        """
        delete all trips
        """
        count_triples = server.clear()
        self.assertEqual(0, count_triples)

    def start_server(self, server: SparqlServer, verbose: bool = True):
        """
        Start the given SPARQL server with a unique data directory under self.tempdir.
        """
        server.config.data_dir = self.tempdir / server.name
        server.config.data_dir.mkdir(parents=True, exist_ok=True)
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
        Test loading dump files using the server's load_dump_files method.
        """
        if not dumps_dir.exists():
            self.skipTest(f"Dumps directory {dumps_dir} not available")

        self.start_server(server, verbose=False)
        self.clear_server(server)

        server.config.dumps_dir = dumps_dir
        loaded_count = server.load_dump_files()

        if self.debug:
            print(f"Successfully loaded {loaded_count} dump files from {dumps_dir}")

        final_count = server.count_triples()
        if self.debug:
            print(f"Total triples after loading: {final_count:,}")

        self.assertGreater(loaded_count, 0)
        self.assertGreater(final_count, 0)
