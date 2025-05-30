"""
Created on 2025-05-27

@author: wf
"""

from pathlib import Path


class OmnigraphPaths:
    """
    Omnigraph Default Paths
    """

    def __init__(self):
        """
        constructor
        """
        self.home_dir = Path.home()
        self.omnigraph_dir = self.home_dir / ".omnigraph"
        self.omnigraph_dir.mkdir(exist_ok=True)
        self.dumps_dir = self.omnigraph_dir / "rdf_dumps"
        self.dumps_dir.mkdir(exist_ok=True)
        self.examples_dir = (Path(__file__).parent / "resources" / "examples").resolve()
