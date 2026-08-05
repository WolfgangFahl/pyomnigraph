"""
Created on 2026-08-05

docker compose generation from the server configurations - see issue #29

@author: wf
"""

import shlex
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yaml

from omnigraph.server_config import ServerConfig


@dataclass
class ComposeService:
    """
    one service of a docker compose file
    """

    image: str
    container_name: str
    ports: List[str] = field(default_factory=list)
    volumes: List[str] = field(default_factory=list)
    environment: List[str] = field(default_factory=list)
    command: Optional[str] = None
    platform: Optional[str] = None
    user: Optional[str] = None
    shm_size: Optional[str] = None

    def as_dict(self) -> Dict:
        """
        Get the compose representation.

        Returns:
            dict of the compose keys that are set
        """
        service = {"image": self.image, "container_name": self.container_name}
        if self.platform:
            service["platform"] = self.platform
        if self.user:
            service["user"] = self.user
        if self.shm_size:
            service["shm_size"] = self.shm_size
        if self.ports:
            service["ports"] = self.ports
        if self.volumes:
            service["volumes"] = self.volumes
        if self.environment:
            service["environment"] = self.environment
        if self.command:
            service["command"] = self.command
        service["restart"] = "unless-stopped"
        return service


class ComposeGenerator:
    """
    Generate a docker compose file from the docker run commands of the server
    configurations, so that the compose file and the CLI cannot drift apart.
    """

    def __init__(self, project_name: str = "omnigraph"):
        """
        Initialize the generator.

        Args:
            project_name: name of the compose project
        """
        self.project_name = project_name

    def service_of_run_command(self, run_command: str) -> ComposeService:
        """
        Translate a docker run command into a compose service.

        Args:
            run_command: the complete docker run command

        Returns:
            the ComposeService or None if the command can not be translated
        """
        service = None
        tokens = shlex.split(run_command)
        if len(tokens) > 2 and tokens[0] == "docker" and tokens[1] == "run":
            tokens = tokens[2:]
            ports = []
            volumes = []
            environment = []
            platform = None
            user = None
            shm_size = None
            image = None
            container_name = None
            command_parts = []
            index = 0
            while index < len(tokens):
                token = tokens[index]
                if image is not None:
                    command_parts.append(token)
                elif token in ("-d", "--rm", "--init"):
                    pass
                elif token == "--name":
                    index += 1
                    container_name = tokens[index]
                elif token in ("-e", "--env"):
                    index += 1
                    environment.append(tokens[index])
                elif token in ("-p", "--publish"):
                    index += 1
                    ports.append(tokens[index])
                elif token in ("-v", "--volume"):
                    index += 1
                    volumes.append(tokens[index])
                elif token == "--platform":
                    index += 1
                    platform = tokens[index]
                elif token in ("-u", "--user"):
                    index += 1
                    user = tokens[index]
                elif token == "--shm-size":
                    index += 1
                    shm_size = tokens[index]
                elif token.startswith("-"):
                    # unknown flag with a value, e.g. --restart=x is self contained
                    if "=" not in token and index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
                        index += 1
                else:
                    image = token
                index += 1
            if image and container_name:
                service = ComposeService(
                    image=image,
                    container_name=container_name,
                    ports=ports,
                    volumes=volumes,
                    environment=environment,
                    command=" ".join(command_parts) if command_parts else None,
                    platform=platform,
                    user=user,
                    shm_size=shm_size,
                )
        return service

    def as_compose(self, configs: Dict[str, ServerConfig], data_dir_of) -> str:
        """
        Generate the compose file for the given server configurations.

        Args:
            configs: server name to ServerConfig
            data_dir_of: callable returning the data directory of a config

        Returns:
            the compose file as yaml
        """
        services = {}
        skipped = []
        for name, config in configs.items():
            run_command = None
            try:
                run_command = config.get_docker_run_command(data_dir=data_dir_of(config))
            except Exception:
                run_command = None
            service = self.service_of_run_command(run_command) if run_command else None
            if service:
                services[name] = service.as_dict()
            else:
                skipped.append(name)
        compose = {"name": self.project_name, "services": services}
        markup = yaml.dump(compose, sort_keys=False, default_flow_style=False)
        if skipped:
            names = ", ".join(sorted(skipped))
            markup += f"\n# not expressible as a compose service: {names}\n"
        return markup
