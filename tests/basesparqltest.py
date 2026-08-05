"""
Created on 2026-08-05

shared setup for tests that need running backends

@author: wf
"""

import os
from pathlib import Path
from typing import Callable, List

from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.omniserver import OmniServer
from omnigraph.server_config import LoadPath
from omnigraph.sparql_server import ServerEnv, SparqlServer
from tests.basetest import Basetest


class BaseSparqlTest(Basetest):
    """
    base class for tests that work against the configured backends
    """

    # a server that already failed to start is not waited for again - a failed
    # start costs its full ready_timeout and every test would pay it anew
    failed_servers = set()

    def setUp(self, debug=False, profile=True, force=True):
        """
        setUp the test environment with the test instances of the active servers

        Args:
            debug: show debug output
            profile: show timing
            force: allow clearing stores above the unforced clear limit
        """
        Basetest.setUp(self, debug=debug, profile=profile)
        home = Path("/tmp/home") if self.inPublicCI() else None
        self.ogp = OmnigraphPaths(home)
        env = ServerEnv(debug=self.debug, verbose=self.debug, force=force)
        omni_server = OmniServer(
            env=env,
            patch_config=lambda config: OmniServer.patch_test_config(config, self.ogp),
        )
        self.servers = omni_server.servers(str(self.ogp.examples_dir / "servers.yaml"))
        self.not_started = []

    def with_each_server(self, work: Callable[[str, SparqlServer], None]) -> List[str]:
        """
        Start each backend, hand it to work, then stop it again.

        One backend at a time keeps the memory bounded - eight stores at once
        exhaust a build machine, and a starved store never becomes ready, which
        then costs its full readiness budget before it is given up on.

        Args:
            work: callable taking the server name and the server

        Returns:
            names of the servers work was called for
        """
        worked_on = []
        for name, server in self.servers.items():
            if name in self.failed_servers:
                self.not_started.append(name)
                continue
            docker_status = server.docker_info()
            if not docker_status.success:
                self.skipTest("docker is not available")
            was_running = server.status().running
            started = was_running or server.start(show_progress=False)
            if not started:
                self.failed_servers.add(name)
                self.not_started.append(name)
                continue
            try:
                work(name, server)
                worked_on.append(name)
            finally:
                if not was_running:
                    server.stop()
        return worked_on

    def load_royals(self, server: SparqlServer) -> int:
        """
        Load the royals example into the given server.

        Args:
            server: the server to load into

        Returns:
            the triple count after loading
        """
        server.config.dumps_dir = self.ogp.examples_dir
        # a store holding exactly this dataset is built where the backend can
        # build - a backend whose runtime path can not clear would otherwise add
        # to whatever it already holds
        if LoadPath.BUILD in server.load_paths:
            server.load_dump_files(path=LoadPath.BUILD)
        else:
            server.clear()
            server.load_dump_files(path=LoadPath.LIVELOAD)
        triple_count = server.count_triples()
        return triple_count
