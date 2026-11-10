"""
Created on 2026-11-10

@author: wf
"""

import tempfile
from unittest.mock import MagicMock, patch

from tests.basesparqltest import BaseSparqlTest


class TestMillenniumDB(BaseSparqlTest):
    """
    test the MillenniumDB start path without docker
    """

    def test_start_fails_on_import_failure(self):
        """
        a failing mdb import must make start return False
        and no server container must be created
        """
        server = self.servers["millenniumdb"]
        with tempfile.TemporaryDirectory() as tmp_dir:
            server.config.base_data_dir = tmp_dir
            server.config.dumps_dir = None
            no_container = MagicMock(running=False, exists=False)
            docker_ok = MagicMock(success=True)
            import_failed = MagicMock(returncode=1, stderr="filesystem error: simulated")
            with (
                patch.object(server, "status", return_value=no_container),
                patch.object(server, "docker_info", return_value=docker_ok),
                patch.object(server.shell, "run", return_value=import_failed),
                patch.object(server.docker_util, "run_shell_command") as docker_run,
            ):
                started = server.start(show_progress=False)
        self.assertFalse(started)
        docker_run.assert_not_called()
