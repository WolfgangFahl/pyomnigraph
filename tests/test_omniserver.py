"""
Created on 2025-06-04

@author: wf
"""

from pathlib import Path

from lodstorage.prefix_config import PrefixConfigs

from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.omnigraph_cmd import OmnigraphCmd
from omnigraph.omniserver import OmniServer
from omnigraph.rdf_dataset import RdfDatasets
from omnigraph.server_config import ServerEnv
from omnigraph.sparql_server import SparqlServer
from tests.basetest import Basetest


class TestOmniServer(Basetest):
    """
    Test OmniServer functionality
    """

    def setUp(self, debug=False, profile=True):
        """
        setUp the test environment
        """
        Basetest.setUp(self, debug=debug, profile=profile)
        self.ogp = OmnigraphPaths()
        self.servers_yaml_path = self.ogp.examples_dir / "servers.yaml"
        self.prefixes_yaml_path = self.ogp.examples_dir / "prefixes.yaml"
        self.env = ServerEnv(debug=self.debug)
        self.omni_server = OmniServer(env=self.env)
        self.prefix_configs = PrefixConfigs.of_yaml(self.prefixes_yaml_path)

    def test_load_servers(self):
        """
        test loading server configurations from YAML
        """
        if not self.servers_yaml_path.exists():
            self.skipTest(f"Server config file not found: {self.servers_yaml_path}")

        servers_dict = self.omni_server.servers(self.servers_yaml_path, filter_active=False)

        if self.debug:
            print(f"Loaded {len(servers_dict)} servers")
            for name, server in servers_dict.items():
                print(f"{server.flag}  {name}: {server.full_name}")

        self.assertIsInstance(servers_dict, dict)
        for _server_name, server in servers_dict.items():
            self.assertIsInstance(server, SparqlServer)

    def test_get_server_commands(self):
        """
        test retrieving server command factories
        """
        server_cmds = self.omni_server.get_server_commands()

        expected_commands = [
            "bash",
            "clear",
            "count",
            "info",
            "load",
            "logs",
            "needed",
            "rm",
            "start",
            "status",
            "stop",
            "webui",
        ]

        self.assertIsInstance(server_cmds, dict)
        for cmd_name in expected_commands:
            self.assertIn(cmd_name, server_cmds)
            self.assertTrue(callable(server_cmds[cmd_name]))

    def test_list_servers(self):
        """
        test generating formatted server lists
        """
        if not self.servers_yaml_path.exists():
            self.skipTest(f"Server config file not found: {self.servers_yaml_path}")

        servers_dict = self.omni_server.servers(self.servers_yaml_path)
        table_formats = ["simple", "github", "mediawiki", "html"]

        for table_format in table_formats:
            markup = self.omni_server.list_servers(servers_dict, table_format)

            if self.debug:
                print(f"Table format: {table_format}")
                print(markup)

            self.assertIsInstance(markup, str)
            self.assertTrue(len(markup) > 0)

    def test_generate_endpoints_yaml(self):
        """
        test generating endpoints YAML from server configurations
        """
        if not self.servers_yaml_path.exists():
            self.skipTest(f"Server config file not found: {self.servers_yaml_path}")

        servers_dict = self.omni_server.servers(self.servers_yaml_path, filter_active=False)
        yaml_content = self.omni_server.generate_endpoints_yaml(servers_dict, self.prefix_configs)

        if self.debug:
            print("Generated endpoints YAML:")
            print(yaml_content)

        self.assertIsInstance(yaml_content, str)
        self.assertTrue(len(yaml_content) > 0)
        self.assertIn("endpoint:", yaml_content)
        self.assertIn("lang:", yaml_content)

    def test_patch_test_config(self):
        """
        test patching configuration for test environment
        """
        if not self.servers_yaml_path.exists():
            self.skipTest(f"Server config file not found: {self.servers_yaml_path}")

        # Test with patch_config function
        patch_config = lambda config: OmniServer.patch_test_config(config, self.ogp)
        test_omni_server = OmniServer(env=self.env, patch_config=patch_config)

        servers_dict = test_omni_server.servers(self.servers_yaml_path)

        for server_name, server in servers_dict.items():
            if self.debug:
                print(f"Test server {server_name}: port={server.config.port}")

            self.assertTrue(server.config.container_name.endswith("-test"))
            expected_test_dir = self.ogp.omnigraph_dir / "test" / server.name / "data"
            self.assertEqual(server.config.base_data_dir, expected_test_dir)

    def test_configure_dumps_dir_with_local_file(self):
        """
        Test configuring dumps directory with local rdf_file in dataset.
        """
        test_dataset_yaml = "/tmp/omnigraph_test/farm_dataset.yaml"
        test_rdf_file = "/tmp/omnigraph_test/apache_configs.ttl"

        # Skip if test files don't exist
        if not Path(test_dataset_yaml).exists():
            self.skipTest(f"Test dataset YAML not found: {test_dataset_yaml}")
        if not Path(test_rdf_file).exists():
            self.skipTest(f"Test RDF file not found: {test_rdf_file}")

        # Load datasets
        datasets = RdfDatasets.ofYaml(test_dataset_yaml)
        self.assertIn("apache_configs", datasets.datasets)
        dataset = datasets.datasets["apache_configs"]

        # Verify dataset has rdf_file
        self.assertEqual(dataset.rdf_file, test_rdf_file)

        # Create an OmnigraphCmd instance to test configure_dumps_dir
        cmd = OmnigraphCmd()

        # Load servers configuration
        if not self.servers_yaml_path.exists():
            self.skipTest(f"Server config file not found: {self.servers_yaml_path}")

        servers_dict = self.omni_server.servers(self.servers_yaml_path, filter_active=False)

        # Get a test server (use jena since that's what the dataset specifies)
        if "jena" not in servers_dict:
            self.skipTest("Jena server not found in configuration")

        server = servers_dict["jena"]

        # Test configure_dumps_dir with local file dataset
        cmd.configure_dumps_dir(server, dataset)

        # Verify dumps_dir is set to the parent directory of the rdf_file
        expected_dumps_dir = Path(test_rdf_file).expanduser().resolve().parent
        actual_dumps_dir = Path(server.config.dumps_dir)

        if self.debug:
            print(f"Dataset rdf_file: {dataset.rdf_file}")
            print(f"Expected dumps_dir: {expected_dumps_dir}")
            print(f"Actual dumps_dir: {actual_dumps_dir}")

        self.assertEqual(actual_dumps_dir, expected_dumps_dir)
