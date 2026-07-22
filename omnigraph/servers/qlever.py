"""
Created on 2025-05-28

@author: wf
"""

import os
import shutil
from configparser import ConfigParser, ExtendedInterpolation
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import rdflib

from omnigraph.server_config import ServerLifecycleState, ServerStatus
from omnigraph.sparql_server import (
    Response,
    ServerConfig,
    ServerEnv,
    SparqlServer,
    Step,
)


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

    def set(self, section: str, key: str, value: str):
        """
        Set a value in the config
        """
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, value)

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

    def save(self):
        """
        Save the config back to file
        """
        with self.path.open("w") as f:
            self.config.write(f)


@dataclass
class QLeverConfig(ServerConfig):
    """
    specialized QLever configuration
    """

    def __post_init__(self):
        super().__post_init__()
        self.access_token = None
        self.status_url = f"{self.base_url}"
        self.sparql_url = f"{self.base_url}/api/sparql"
        # the docker run command is dynamically created by the qlever (control) command later
        self.docker_run_command = None
        #  docker_run_command = f"docker run -d --name {self.container_name} -e UID=$(id -u) -e GID=$(id -g) -v {self.data_dir}:/data -w /data -p {self.port}:7001 {self.image}"


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

    def status(self) -> ServerStatus:
        """
        Check QLever server status from container logs.

        Returns:
        ServerStatus object with status information
        """
        server_status = super().status()

        # Treat UP as READY
        if server_status.at == ServerLifecycleState.UP:
            server_status.at = ServerLifecycleState.READY
        self.add_triple_count2_server_status(server_status)

        return server_status

    def get_step_list(self) -> List[Step]:
        step_list = [
            Step(
                name="setup-config",
                data_dir=self.data_dir,
                file_name="Qleverfile",
                setup_cmd=f"qlever setup-config {self.dataset}",
                step=1,
            ),
            Step(
                name="get-data",
                data_dir=self.data_dir,
                file_name=None,  # dynamically determined below
                setup_cmd=f"qlever get-data",
                step=2,
            ),
            Step(
                name="index",
                data_dir=self.data_dir,
                file_name=f"{self.dataset}.meta-data.json",
                setup_cmd=f"qlever index",
                step=3,
            ),
            Step(
                name="start",
                data_dir=self.data_dir,
                setup_cmd=f"qlever start --server-container {self.config.container_name}",
                step=4,
            ),
            Step(
                name="ui",
                data_dir=self.data_dir,
                setup_cmd=f"qlever ui",
                step=5,
            ),
        ]
        return step_list

    def handle_config(self, step: Step):
        """
        handle config setting for following step and
        patch QLeverfile to port
        """
        qlever_file = QLeverfile.ofFile(step.path)
        qlever_name = qlever_file.get("data", "NAME")
        self.config.access_token = qlever_file.get("server", "ACCESS_TOKEN")
        msg = f"qlever setup-config for {qlever_name} done"
        self.log.log("✅", self.config.container_name, msg)
        input_files = qlever_file.get("index", "input_files")
        # patch the port
        qlever_file.set("server", "port", str(self.config.port))
        # path the name
        qlever_file.save()
        # steps are index from 1 so step.step in the step_list
        # is the following step
        self.step_list[step.step].file_name = input_files

    def start(self, show_progress: bool = True) -> bool:
        """
        Start QLever using proper workflow.
        """
        if not self.config.data_dir:
            raise ValueError("Data directory needs to be specified")
        self.data_dir = self.config.data_dir
        if not os.path.exists(self.config.data_dir):
            raise ValueError(f"Data directory {self.data.dir} needs to exist")
        self.dataset = self.config.dataset
        started = False
        if self.dataset:
            steps = 0
            self.step_list = self.get_step_list()
            for step in self.step_list:
                step.perform(server=self)
                if not step.success:
                    break
                if step.name == "setup-config":
                    self.handle_config(step)
                steps = step.step

            if steps >= 5:
                started = self.wait_until_ready(show_progress=show_progress)

        return started

    def _get_access_token(self) -> Optional[str]:
        """
        Get the access token for QLever authentication.

        First checks if already set in config, otherwise reads from QLeverfile.

        Returns:
            Access token string or None if not found
        """
        # Return cached token if available
        if hasattr(self.config, "access_token") and self.config.access_token:
            return self.config.access_token

        # Try to read from QLeverfile
        if self.config.data_dir:
            qleverfile_path = Path(self.config.data_dir) / "Qleverfile"
            qlever_file = QLeverfile.ofFile(qleverfile_path)
            if qlever_file:
                access_token = qlever_file.get("server", "ACCESS_TOKEN")
                # Cache it for future use
                self.config.access_token = access_token
                return access_token

        return None

    def get_index_commands(self, files: List[Path]) -> List[str]:
        """
        Build the qlever CLI commands to (re)index the given dump files.

        QLever loads bulk data by building its index from files - there is no
        native HTTP bulk-write path; the SPARQL INSERT route is only suitable
        for small increments.

        Args:
            files: dump files staged in the data directory

        Returns:
            list of shell commands to run in the data directory
        """
        commands = [
            "qlever stop",
            "qlever index --overwrite-existing",
            f"qlever start --server-container {self.config.container_name}",
        ]
        return commands

    def upload_dump_files(self, file_pattern: str = None) -> int:
        """
        Bulk-load dump files by rebuilding the QLever index from them -
        the native path; the turtle-to-INSERT conversion of upload_request
        is unsuitable for bulk data.

        Args:
            file_pattern: Glob pattern for dump files

        Returns:
            Number of files loaded successfully
        """
        container_name = self.config.container_name
        files = self.get_dump_files(file_pattern)
        loaded_count = 0
        if not files:
            self.log.log("⚠️", container_name, f"No dump files found for pattern: {file_pattern}")
            return loaded_count
        data_dir = Path(self.config.data_dir)
        qleverfile_path = data_dir / "Qleverfile"
        qlever_file = QLeverfile.ofFile(qleverfile_path)
        if qlever_file is None:
            self.log.log("❌", container_name, f"no Qleverfile in {data_dir} - run start (setup-config) first")
            return loaded_count
        # stage the dumps in the data directory and register them as input files
        for file in files:
            target = data_dir / file.name
            if not target.exists():
                shutil.copy2(file, target)
        input_files = " ".join(file.name for file in files)
        qlever_file.set("index", "INPUT_FILES", input_files)
        qlever_file.save()
        ok = True
        for command in self.get_index_commands(files):
            shell_result = self.run_shell_command(f"cd {data_dir};{command}")
            if not shell_result.success:
                self.log.log("❌", container_name, f"failed: {command}")
                ok = False
                break
        if ok:
            loaded_count = len(files)
            self.log.log("✅", container_name, f"index rebuilt from {loaded_count} file(s)")
        return loaded_count

    def upload_request(self, file_content: bytes) -> Response:
        """Upload request for QLever using SPARQL INSERT statements."""
        turtle_data = file_content.decode("utf-8")
        sparql_insert = self._convert_turtle_to_insert(turtle_data)

        # Get access token - read from QLeverfile if not already set
        access_token = self._get_access_token()

        response = self.make_request(
            "POST",
            self.config.sparql_url,
            headers={
                "Content-Type": "application/sparql-update",
                "Authorization": f"Bearer {access_token}",
            },
            data=sparql_insert,
            timeout=self.config.upload_timeout,
        )
        return response

    def _convert_turtle_to_insert(self, turtle_data: str) -> str:
        """Convert Turtle data to SPARQL INSERT statement."""

        graph = rdflib.Graph()
        graph.parse(data=turtle_data, format="turtle")

        triples_list = []
        for subject, predicate, obj in graph:
            triple_str = f"{subject.n3()} {predicate.n3()} {obj.n3()} ."
            triples_list.append(triple_str)

        triples_block = "\n    ".join(triples_list)
        sparql_insert = f"INSERT DATA {{\n    {triples_block}\n}}"

        return sparql_insert
