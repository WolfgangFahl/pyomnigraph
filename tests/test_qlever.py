"""
Created on 2025-05-29

@author: wf
"""

import json
import tempfile
from pathlib import Path

from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.servers.qlever import QLeverfile
from omnigraph.sparql_server import Step
from tests.basesparqltest import BaseSparqlTest
from tests.basetest import Basetest


class TestQLever(Basetest):
    """
    test qlever haandling
    """

    def setUp(self, debug=True, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)
        self.ogp = OmnigraphPaths()

    def testQLeverfile(self):
        """
        test reading a qlever file
        """
        qlever_path = self.ogp.omnigraph_dir / "test" / "qlever" / "olympics" / "Qleverfile"
        if not qlever_path.exists():
            self.skipTest(f"{qlever_path} not available")
        qlever_file = QLeverfile.ofFile(qlever_path)
        if self.debug:
            print(json.dumps(qlever_file.as_dict(), indent=2))
        self.assertIsNotNone(qlever_file)
        name = qlever_file.get("data", "NAME")
        self.assertEqual(name, "olympics")
        access_token = qlever_file.get("server", "ACCESS_TOKEN")
        if self.debug:
            print(f"access_token: {access_token}")


class TestQLeverConfig(BaseSparqlTest):
    """
    test the patching of the Qleverfile
    """

    def test_handle_config_patches_host_name(self):
        """
        handle_config must set host_name to localhost - qlever start waits
        until the server answers at host_name and never returns where the
        machine's host name resolves to an address the port does not answer on
        """
        server = self.servers["qlever"]
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            qlever_path = data_dir / "Qleverfile"
            qlever_path.write_text("[data]\nNAME = olympics\n\n[index]\nINPUT_FILES = *.ttl\n\n[server]\nPORT = 7019\n")
            setup_step = Step(name="setup-config", data_dir=data_dir, file_name="Qleverfile", step=1)
            server.step_list = [setup_step, Step(name="get-data", data_dir=data_dir, step=2)]
            server.handle_config(setup_step)
            qlever_file = QLeverfile.ofFile(qlever_path)
            host_name = qlever_file.get("server", "host_name")
            port = qlever_file.get("server", "port")
        self.assertEqual(host_name, "localhost")
        self.assertEqual(port, str(server.config.port))
