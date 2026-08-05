"""
Created on 2026-08-05

the royals example must load into every active backend

@author: wf
"""

from tests.basesparqltest import BaseSparqlTest


class TestRoyals(BaseSparqlTest):
    """
    the mandatory baseline: every active backend takes the royals example
    """

    expected_triples = 63

    def test_royals_load(self):
        """
        Every active backend clears, loads royals.ttl and reports its 63 triples.

        This is the baseline a backend has to meet to be active at all - a
        backend that can not do this is misconfigured rather than limited.
        """
        servers = self.running_servers()
        self.assertTrue(servers, "no backend could be started")
        # every active backend has to take royals - a backend that can not is
        # misconfigured, so a failed start is a failure of this test
        self.assertEqual([], self.not_started, f"backends that did not start: {self.not_started}")
        for name, server in servers.items():
            triple_count = self.load_royals(server)
            if self.debug:
                print(f"{name}: {triple_count} triples")
            self.assertEqual(
                self.expected_triples,
                triple_count,
                f"{name}: expected {self.expected_triples} royals triples, got {triple_count}",
            )
