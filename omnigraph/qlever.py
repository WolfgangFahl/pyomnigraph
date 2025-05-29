"""
Created on 2025-05-28

@author: wf
"""
import configparser
import os
import glob
from dataclasses import dataclass
from pathlib import Path
from tqdm import tqdm

from omnigraph.persistent_log import Log
from omnigraph.shell import Shell
from omnigraph.sparql_server import ServerConfig, ServerEnv, SparqlServer

from configparser import ConfigParser, ExtendedInterpolation
from pathlib import Path
from typing import Optional


class QLeverfile:
    """
    handle qlever control https://github.com/ad-freiburg/qlever-control
    QLeverfile in INI format
    """

    def __init__(self, path: Path, config: ConfigParser):
        self.path = path
        self.config = config

    @classmethod
    def ofFile(cls, path: Path) -> Optional["QLeverfile"]:
        """
        Create QLeverfile instance from given INI file
        """
        if not path.exists():
            return None
        config = ConfigParser(interpolation=ExtendedInterpolation())
        config.read(path)
        return cls(path, config)

    def get(self, section: str, key: str) -> Optional[str]:
        """
        Get a value from the config, if exists
        """
        if self.config.has_section(section) and self.config.has_option(section, key):
            return self.config.get(section, key)
        return None

    def sections(self) -> list[str]:
        """
        Return list of config sections
        """
        return self.config.sections()

    def as_dict(self) -> dict[str, dict[str, str]]:
        """
        Return full config as nested dictionary
        """
        return {
            section: dict(self.config.items(section))
            for section in self.config.sections()
        }

@dataclass
class QLeverConfig(ServerConfig):
    """
    specialized QLever configuration
    """
    def __post_init__(self):
        super().__post_init__()
        self.status_url = None
        self.sparql_url = f"{self.base_url}/api/sparql"
        self.docker_run_command = f"docker run -d --name {self.container_name} -e UID=$(id -u) -e GID=$(id -g) -v {self.data_dir}:/data -w /data -p {self.port}:7001 {self.image}"


class QLever(SparqlServer):
    """
    Dockerized QLever SPARQL server
    """

    def __init__(self, config: ServerConfig, env: ServerEnv):
        """
        Initialize the QLever server manager.

        Args:
            config: Server configuration
            env: Server environment (includes log, shell, debug, verbose)
        """
        super().__init__(config=config, env=env)

    def start(self, show_progress: bool = True) -> bool:
        """
        Start QLever using proper workflow.
        """
        if not self.config.data_dir:
            raise ValueError("Data directory needs to be specified")
        self.data_dir = self.config.data_dir
        self.dataset = self.config.dataset
        container_name = self.config.container_name
        started = False
        steps=0
        if self.dataset:
            # Run QLever setup workflow
            qleverfile=self.data_dir / "Qleverfile"
            if os.path.exists(qleverfile):
                step=True
                self.log.log("✅", container_name,f"{qleverfile} already exists")
            else:
                setup_cmd = f"cd {self.data_dir};qlever setup-config {self.dataset}"
                step=self.run_shell_command(setup_cmd)

            if step:
                steps+=1
                get_data_cmd = f"cd {self.data_dir};qlever get-data"
                step=self.run_shell_command(get_data_cmd)

            if step:
                steps+=1
                index_cmd = f"cd {self.data_dir};qlever index"
                step=self.run_shell_command(index_cmd)

            if step:
                steps+=1
                start_cmd = f"cd {self.data_dir};qlever start"
                step=self.run_shell_command(start_cmd)
            if step:
                steps+=1

            if steps>=4:
                started = self.wait_until_ready(timeout=10, show_progress=show_progress)

        return started

    def load_file(self, filepath: str) -> bool:
        """
        Load a single RDF file into QLever.

        Args:
            filepath: Path to RDF file

        Returns:
            True if loaded successfully
        """
        load_success = False
        try:
            with open(filepath, "rb") as f:
                result = self._make_request(
                    "POST",
                    f"{self.base_url}/api/upload",
                    files={"file": f},
                    timeout=300,
                )

            if result["success"]:
                self.log.log("✅", self.container_name, f"Loaded {filepath}")
                load_success = True
            else:
                error_msg = result.get("error", f"HTTP {result['status_code']}")
                self.log.log("❌", self.container_name, f"Failed to load {filepath}: {error_msg}")
                load_success = False

        except Exception as e:
            self.log.log("❌", self.container_name, f"Exception loading {filepath}: {e}")
            load_success = False

        return load_success

    def load_dump_files(self, file_pattern: str = "dump_*.ttl", use_bulk: bool = True) -> int:
        """
        Load all dump files matching pattern.

        Args:
            file_pattern: Glob pattern for dump files
            use_bulk: Use bulk loader if True, individual files if False

        Returns:
            Number of files loaded successfully
        """
        files = sorted(glob.glob(file_pattern))
        loaded_count = 0

        if not files:
            self.log.log(
                "⚠️",
                self.container_name,
                f"No files found matching pattern: {file_pattern}",
            )
            loaded_count = 0
        else:
            self.log.log("✅", self.container_name, f"Found {len(files)} files to load")

            # QLever typically loads files individually
            loaded_count = 0
            for filepath in tqdm(files, desc="Loading files"):
                file_result = self.load_file(filepath)
                if file_result:
                    loaded_count += 1
                else:
                    self.log.log("❌", self.container_name, f"Failed to load: {filepath}")

        return loaded_count
