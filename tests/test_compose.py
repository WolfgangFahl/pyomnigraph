"""
Created on 2026-08-05

test the docker compose generation - see issue #29

@author: wf
"""

import shutil
import subprocess
from pathlib import Path

import yaml

from omnigraph.compose import ComposeGenerator
from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.omniserver import OmniServer
from omnigraph.sparql_server import ServerEnv
from tests.basetest import Basetest


class TestCompose(Basetest):
    """
    the compose file is generated from the docker run commands, so the two can
    not drift apart - a service per backend that runs via docker run, and the
    ones that can not be expressed are named
    """

    def setUp(self, debug=False, profile=True):
        """
        setUp the test environment
        """
        Basetest.setUp(self, debug=debug, profile=profile)
        self.ogp = OmnigraphPaths()
        omni_server = OmniServer(env=ServerEnv())
        servers = omni_server.servers(str(self.ogp.examples_dir / "servers.yaml"), filter_active=False)
        self.configs = {name: server.config for name, server in servers.items()}
        self.generator = ComposeGenerator()
        self.markup = self.generator.as_compose(self.configs, lambda config: config.base_data_dir or "/tmp/omnigraph")

    def test_service_of_run_command(self):
        """
        a docker run command translates into a service with its options
        """
        run_command = (
            "docker run --shm-size 1g -e AGRAPH_SUPER_USER=admin -d --name allegrograph-omnigraph "
            "-p 127.0.0.1:10035:10035 -v /tmp/x:/agraph/data franzinc/agraph:latest"
        )
        service = self.generator.service_of_run_command(run_command)
        self.assertIsNotNone(service)
        self.assertEqual("franzinc/agraph:latest", service.image)
        self.assertEqual("allegrograph-omnigraph", service.container_name)
        self.assertEqual(["127.0.0.1:10035:10035"], service.ports)
        self.assertEqual(["/tmp/x:/agraph/data"], service.volumes)
        self.assertEqual(["AGRAPH_SUPER_USER=admin"], service.environment)

    def test_compose_of_example_servers(self):
        """
        every backend that runs via docker run becomes a service and the ones
        that can not be expressed are named instead of silently dropped
        """
        compose = yaml.safe_load(self.markup.split("\n#")[0])
        services = compose["services"]
        for name in ["allegrograph", "blazegraph", "graphdb", "jena", "millenniumdb", "oxigraph", "virtuoso"]:
            self.assertIn(name, services, f"{name} missing from the compose file")
            self.assertIn("image", services[name])
            self.assertIn("container_name", services[name])
        # qlever builds its container through its own CLI around a prebuilt index
        self.assertNotIn("qlever", services)
        self.assertIn("not expressible as a compose service: qlever", self.markup)
        # the shm demand of #57/#63 travels from servers.yaml into the service -
        # without it a compose started allegrograph dies at boot as CI did
        self.assertEqual("2g", services["allegrograph"].get("shm_size"))

    def test_compose_validates(self):
        """
        docker compose accepts the generated file - config validates without
        starting anything
        """
        docker = shutil.which("docker")
        if docker is None:
            self.skipTest("docker is not available")
        compose_path = (
            Path(self.tempPath("omnigraph-compose.yaml"))
            if hasattr(self, "tempPath")
            else Path("/tmp/omnigraph-compose.yaml")
        )
        compose_path.write_text(self.markup)
        result = subprocess.run(
            [docker, "compose", "-f", str(compose_path), "config", "--quiet"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, f"docker compose rejects the file: {result.stderr[:500]}")
