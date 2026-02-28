"""
Created on 2025-05-26

@author: wf
"""

from pathlib import Path

from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.omniserver import OmniServer
from omnigraph.sparql_server import ServerEnv, SparqlServer
from tests.basetest import Basetest


class TestSparqlServer(Basetest):
    """
    test starting blazegraph
    """

    def setUp(self, debug=False, profile=True):
        """
        setUp the test environment
        """
        Basetest.setUp(self, debug=debug, profile=profile)
        home = Path("/tmp/home") if self.inPublicCI() else None
        self.ogp = OmnigraphPaths(home)
        servers_yaml_path = self.ogp.examples_dir / "servers.yaml"
        env = ServerEnv(debug=self.debug, verbose=self.debug)
        omni_server = OmniServer(
            env=env,
            patch_config=lambda config: OmniServer.patch_test_config(config, self.ogp),
        )
        self.all_servers = omni_server.servers(str(servers_yaml_path))
        # self.filter_servers("graphdb")
        self.filter_servers()

    def filter_servers(self, server_name: str = None):
        # Filter to single server if specified
        if server_name:
            server = self.all_servers.get(server_name)
            if server:
                self.servers = {server_name: server}
            else:
                raise ValueError(f"Server '{server_name}' not found. Available: {list(self.all_servers.keys())}")
        else:
            self.servers = self.all_servers

    def clear_server(self, server: SparqlServer):
        """
        delete all triples - skip if server is not running
        """
        server_status = server.status()
        if not server_status.running:
            self.skipTest(f"{server.full_name} is not running, skipping clear")
        before_clear = server.count_triples()
        if before_clear == -1:
            self.fail(f"{server.full_name}: Failed to count triples before clear (endpoint error)")
        count_triples = server.clear()
        expected = before_clear if server.config.unforced_clear_limit <= before_clear else 0
        self.assertEqual(
            expected,
            count_triples,
            f"{server.full_name}: Expected {expected} triples after clear, got {count_triples}",
        )

    def start_server(self, server: SparqlServer, verbose: bool = True) -> bool:
        """
        Start the given SPARQL server with a unique data directory.

        Skips the test if Docker is unavailable or the server cannot be started.

        Returns:
            True if server is running, False if it could not be started.
        """
        docker_status = server.docker_info()
        if not docker_status.success:
            self.skipTest(f"Docker not available for {server.full_name}, skipping")
        server_status = server.status()
        if server_status.running:
            if self.debug and verbose:
                print(f"{server.name} already running")
            return True
        started = server.start()
        if not started:
            self.skipTest(f"{server.full_name} could not be started, skipping")
        if verbose:
            if self.debug:
                print(server_status.get_summary(debug=self.debug))
        count_triples = server.count_triples()
        if self.debug:
            print(f"{count_triples} triples found for {server.name}")
        return True

    def test_start(self):
        """
        test starting servers
        """
        for server in self.servers.values():
            self.start_server(server)

    def test_load_dumps(self):
        """
        test loading dump files from examples directory
        """
        dumps_dir = self.ogp.examples_dir
        for server in self.servers.values():
            self.load_dump_files(server, dumps_dir)

    def load_dump_files(self, server: SparqlServer, dumps_dir: Path):
        """
        Test loading dump files using the server's load_dump_files method.
        """
        debug = self.debug
        if not dumps_dir.exists():
            self.skipTest(f"Dumps directory {dumps_dir} not available")

        self.start_server(server, verbose=False)
        self.clear_server(server)

        server.config.dumps_dir = dumps_dir
        loaded_count = server.load_dump_files()

        if debug:
            print(f"Successfully loaded {loaded_count} dump files from {dumps_dir} to {server.name}")

        final_count = server.count_triples()
        if debug:
            print(f"Total triples after loading: {final_count:,} for {server.name}")

        self.assertGreater(
            loaded_count,
            0,
            f"{server.full_name}: Expected to load at least 1 file, got {loaded_count}",
        )
        self.assertGreater(
            final_count,
            0,
            f"{server.full_name}: Expected triples after loading, got {final_count}",
        )
