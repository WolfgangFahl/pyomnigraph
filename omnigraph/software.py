import os
from dataclasses import dataclass, field
from typing import List

from lodstorage.yamlable import lod_storable

from omnigraph.persistent_log import Log
from omnigraph.shell import Shell


@dataclass
class Software:
    """
    Single software requirement definition
    """

    command: str
    info: str


@lod_storable
class SoftwareList:
    """
    Collection of software requirements loadable from YAML
    """

    software_list: List[Software] = field(default_factory=list)

    def check_installed(self, log: Log, shell: Shell, verbose: bool = True) -> int:
        """
        Check if necessary software
        commands are available and suggest installation packages
        """
        missing_counter = 0

        log.log("✅", "info", f"PATH={os.environ.get('PATH')}")

        for needed in self.software_list:
            process = shell.run(f"which {needed.command}", tee=verbose)
            where = None if process.returncode != 0 else process.stdout.strip()

            if not where:
                log.log("❌", "error", f"Missing required command: {needed.command} - {needed.info}")
                missing_counter += 1
            else:
                log.log("✅", "info", f"{needed.command} available at {where}")

        return missing_counter
