"""
Created on 2025-05-28

@author: wf
"""
from configparser import ConfigParser, ExtendedInterpolation
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from omnigraph.sparql_server import ServerConfig, ServerEnv, SparqlServer
import rdflib


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
        self.access_token = None
        self.status_url = f"{self.base_url}"
        self.sparql_url = f"{self.base_url}/api/sparql"
        self.docker_run_command = f"docker run -d --name {self.container_name} -e UID=$(id -u) -e GID=$(id -g) -v {self.data_dir}:/data -w /data -p {self.port}:7001 {self.image}"

@dataclass
class Step:
    """
    a setup step
    """
    name: str
    data_dir: Path
    setup_cmd: Optional[str] = None
    file_name: Optional[str] = None
    step: int = 0
    success: bool = False

    @property
    def path(self) -> Optional[Path]:
        if self.file_name:
            return self.data_dir / self.file_name
        return None

    def perform(self, server:SparqlServer):
        """
        perform the setup_cmd if self.path is not created yet
        """
        if self.path and self.path.exists():
            self.success = True
            msg = f"{self.path} already exists"
            server.log.log("✅", self.name, msg)
        else:
            command=f"cd {self.data_dir};{self.setup_cmd}"
            success_msg=f"{self.name} done"
            error_msg=f"{self.name} failed"
            self.success=server.run_shell_command(command, success_msg, error_msg)

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
        if self.dataset:
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
                    setup_cmd=f"qlever start",
                    step=4,
                ),
            ]
            steps=0
            for index,step in enumerate(step_list)  :
                step.perform(server=self)
                if not step.success:
                    break
                if step.name=="setup-config":
                    qlever_file = QLeverfile.ofFile(step.path)
                    qlever_name = qlever_file.get("data", "NAME")
                    self.config.access_token=qlever_file.get("server","ACCESS_TOKEN")
                    msg=f"qlever setup-config for {qlever_name} done"
                    self.log.log("✅", container_name,msg)
                    input_files=qlever_file.get("index","input_files")
                    step_list[index+1].file_name=input_files
                steps=step.step

            if steps>=3:
                started = self.wait_until_ready(timeout=10, show_progress=show_progress)

        return started

    def upload_request(self, file_content: bytes) -> dict:
        """Upload request for QLever using SPARQL INSERT statements."""
        turtle_data = file_content.decode('utf-8')
        sparql_insert = self._convert_turtle_to_insert(turtle_data)
        access_token=self.config.access_token

        response = self._make_request(
            "POST",
            self.config.sparql_url,
            headers={
                "Content-Type": "application/sparql-update",
                "Authorization": f"Bearer {access_token}"
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