"""
Created on 2025-05-29

@author: wf
"""

import json

from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.qlever import QLeverfile
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
