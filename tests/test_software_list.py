"""
Created on 2025-05-28

@author: wf
"""

from omnigraph.persistent_log import Log
from omnigraph.shell import Shell
from omnigraph.software import Software, SoftwareList
from tests.basetest import Basetest


class TestSoftwareList(Basetest):
    """
    test software list
    """

    def setUp(self, debug=True, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)
        self.shell = Shell()
        self.log = Log()
        self.log.do_print = debug
        self.software_list = SoftwareList()

    def test_check_available_software(self):
        """
        test checking for available software
        """
        self.software_list.software_list.append(Software("rcs", "apt-get install rcs"))
        self.software_list.check_installed(self.log, self.shell)
