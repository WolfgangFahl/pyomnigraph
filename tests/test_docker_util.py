"""
Created on 2025-05-28

@author: wf
"""

from omnigraph.docker_util import DockerUtil
from omnigraph.shell import Shell
from tests.basetest import Basetest


class TestDockerUtil(Basetest):
    """
    test docker utilities
    """

    def setUp(self, debug=False, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)
        self.shell = Shell()
        self.container_name = "test_container"
        self.docker_util = DockerUtil(self.shell, self.container_name, debug=debug)

    def test_initialization(self):
        """
        test DockerUtil initialization
        """
        self.assertEqual(self.docker_util.container_name, "test_container")
        self.assertIsNotNone(self.docker_util.shell)
        self.assertFalse(self.docker_util.debug)
