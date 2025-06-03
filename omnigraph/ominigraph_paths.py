"""
Created on 2025-05-27

@author: wf
"""

from pathlib import Path
from typing import Optional

class OmnigraphPaths:
    """
    Omnigraph Default Paths
    """

    def __init__(self, home_dir: Optional[Path] = None):
        """
        Initialize default Omnigraph paths

        Args:
            home_dir: Optional custom home directory path (default: Path.home())
        """
        self.home_dir = home_dir if home_dir else Path.home()
        self.omnigraph_dir = self.home_dir / ".omnigraph"
        self.omnigraph_dir.mkdir(parents=True, exist_ok=True)
        self.dumps_dir = self.omnigraph_dir / "rdf_dumps"
        self.dumps_dir.mkdir(exist_ok=True)
        self.examples_dir = (Path(__file__).parent / "resources" / "examples").resolve()
