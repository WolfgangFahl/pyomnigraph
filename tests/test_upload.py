"""
Created on 2026-07-22

Tests for the upload command - native per-server bulk load (issue #27,
root cause fix for issue #25).

@author: wf
"""

import tempfile
from pathlib import Path

from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.omniserver import OmniServer
from omnigraph.sparql_server import ServerEnv
from tests.basetest import Basetest


class TestUpload(Basetest):
    """
    test the native bulk upload command
    """

    def setUp(self, debug=False, profile=True):
        """
        setUp the test environment
        """
        Basetest.setUp(self, debug=debug, profile=profile)
        self.ogp = OmnigraphPaths()
        self.servers_yaml_path = self.ogp.examples_dir / "servers.yaml"
        self.env = ServerEnv(debug=self.debug)
        self.omni_server = OmniServer(env=self.env)
        self.servers_dict = self.omni_server.servers(self.servers_yaml_path, filter_active=False)
        # dumps_dir is normally set per dataset by the load/upload command
        self.dumps_dir = tempfile.mkdtemp(prefix="omnigraph-dumps-")
        for server in self.servers_dict.values():
            server.config.dumps_dir = self.dumps_dir

    def test_upload_command_registered(self):
        """
        the upload command must be available in the server command registry
        """
        server_cmds = self.omni_server.get_server_commands()
        self.assertIn("upload", server_cmds)

    def test_jena_tdbloader_command(self):
        """
        Jena builds a tdb2.tdbloader docker command against the TDB2 location
        """
        jena = self.servers_dict.get("jena")
        self.assertIsNotNone(jena)
        dumps_dir = jena.config.dumps_dir
        files = [Path(dumps_dir) / "test1.ttl", Path(dumps_dir) / "test2.ttl"]
        command = jena.get_tdbloader_command(files)
        if self.debug:
            print(command)
        self.assertIn("tdb2.tdbloader", command)
        self.assertIn("--entrypoint java", command)
        self.assertIn(f"--loc /fuseki/databases/{jena.config.dataset}", command)
        self.assertIn(jena.config.image, command)
        self.assertIn("/dumps/test1.ttl", command)
        self.assertIn("/dumps/test2.ttl", command)

    def test_blazegraph_dataloader_xml(self):
        """
        Blazegraph builds a DataLoader servlet properties XML
        """
        blazegraph = self.servers_dict.get("blazegraph")
        self.assertIsNotNone(blazegraph)
        xml = blazegraph.get_dataloader_xml("/data/dumps")
        if self.debug:
            print(xml)
        self.assertIn('<entry key="namespace">kb</entry>', xml)
        self.assertIn('<entry key="fileOrDirs">/data/dumps</entry>', xml)
        self.assertIn('<entry key="propertyFile">/RWStore.properties</entry>', xml)
        self.assertIn("dataloader", blazegraph.config.dataloader_url)

    def test_qlever_index_commands(self):
        """
        QLever rebuilds its index via the qlever CLI instead of INSERT statements
        """
        qlever = self.servers_dict.get("qlever")
        self.assertIsNotNone(qlever)
        commands = qlever.get_index_commands([])
        if self.debug:
            print(commands)
        self.assertTrue(any("qlever index" in command for command in commands))
        self.assertTrue(any("qlever start" in command for command in commands))

    def test_upload_fallback_no_files(self):
        """
        the base upload falls back to the HTTP path; with no dump files
        matching it must report zero loads without contacting any server
        """
        oxigraph = self.servers_dict.get("oxigraph")
        self.assertIsNotNone(oxigraph)
        loaded_count = oxigraph.upload_dump_files("*.does-not-exist")
        self.assertEqual(0, loaded_count)
