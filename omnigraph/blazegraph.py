"""
Created on 2025-05-27

@author: wf
"""

from dataclasses import dataclass
from pathlib import Path
import re
import os
from omnigraph.server_config import ServerLifecycleState, ServerStatus
from omnigraph.sparql_server import ServerConfig, ServerEnv, SparqlServer


@dataclass
class BlazegraphConfig(ServerConfig):
    """
    Blazegraph configuration
    """

    def __post_init__(self):
        super().__post_init__()
        blazegraph_base = f"{self.base_url}/bigdata"
        self.status_url = f"{blazegraph_base}/status"
        self.sparql_url = f"{blazegraph_base}/namespace/{self.dataset}/sparql"
        self.upload_url = self.sparql_url
        self.web_url = f"{blazegraph_base}/#query"
        self.dataloader_url = f"{blazegraph_base}/dataloader"

    def get_docker_run_command(self, data_dir) -> str:
        """
        Generate docker run command with bind mount for Blazegraph journal directory.

        Args:
            data_dir: Host directory path to bind mount to container

        Returns:
            Complete docker run command string
        """
        docker_run_command = (
            f"docker run -d --name {self.container_name} "
            f"-e BLAZEGRAPH_UID={os.getuid()} "
            f"-e BLAZEGRAPH_GID={os.getgid()} "
            f"-p {self.port}:8080 "
            f"-v {data_dir}/RWStore.properties:/RWStore.properties "
            f"-v {data_dir}:/data "
            f"{self.image}"
        )
        return docker_run_command

class Blazegraph(SparqlServer):
    """
    Dockerized Blazegraph SPARQL server
    """

    def __init__(self, config: ServerConfig, env: ServerEnv):
        """
        Initialize the Blazegraph manager.

        Args:
            config: Server configuration
            env: Server environment (includes log, shell, debug, verbose)
        """
        super().__init__(config=config, env=env)

    def pre_create(self):
        """
        Prepare Blazegraph data directory and RWStore.properties.
        """
        data_dir = Path(self.config.base_data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        rwstore_path = data_dir / "RWStore.properties"
        if not rwstore_path.exists():
            header = self.config.generator_header()
            props = f"""{header}

    # Blazegraph journal configuration
    com.bigdata.journal.AbstractJournal.file=/data/blazegraph.jnl

    # Enable text index
    com.bigdata.rdf.store.AbstractTripleStore.textIndex=true

    # No OWL reasoning
    com.bigdata.rdf.store.AbstractTripleStore.axiomsClass=com.bigdata.rdf.axioms.NoAxioms

    # No justification or truth maintenance
    com.bigdata.rdf.sail.truthMaintenance=false
    com.bigdata.rdf.store.AbstractTripleStore.justify=false

    # Default namespace
    com.bigdata.rdf.sail.namespace={self.config.dataset}
    """
            rwstore_path.write_text(props)


    def status(self) -> ServerStatus:
        """
        Get server status information.

        Returns:
            ServerStatus object with status information
        """
        server_status = super().status()
        if server_status.exists and server_status.running:
            response = self.make_request("GET", self.config.status_url)

            if response.success:
                lifecycle = ServerLifecycleState.READY

            if response.response and response.response.text:
                html_content = response.response.text
                # Only parse HTML if it looks like HTML content
                if "<" in html_content and ">" in html_content:
                    name_value_pattern = r'(?:<span id="(?P<name1>[^"]+)">(?P<value1>[^<]+)</span[^>]*>|&#47;(?P<name2>[^=]+)=(?P<value2>[^\s&#]+))'
                    matches = re.finditer(name_value_pattern, html_content, re.DOTALL)

                    for match in matches:
                        for name_group, value_group in {
                            "name1": "value1",
                            "name2": "value2",
                        }.items():
                            name = match.group(name_group)
                            if name:
                                value = match.group(value_group)
                                sanitized_value = value.replace("</p", "").replace("&#47;", "/")
                                sanitized_name = name.replace("-", "_").replace("/", "_")
                                sanitized_name = sanitized_name.replace("&#47;", "/")
                                if not sanitized_name.startswith("/"):
                                    server_status.status_dict[sanitized_name] = sanitized_value
                                break

                server_status.http_status_code = (response.response.status_code if response.response else None,)
            else:
                if response.error:
                    error = Exception(response.error)
                    lifecycle = ServerLifecycleState.ERROR
                elif response.response:
                    error = Exception(f"GET {self.config.status_url} request failed")
                    lifecycle = ServerLifecycleState.ERROR
                else:
                    error = Exception("unknown error")
                    lifecycle = ServerLifecycleState.UNKNOWN

                server_status.at = lifecycle
                server_status.error = error
                server_status.http_status_code = (response.response.status_code if response.response else None,)
            if server_status.at == ServerLifecycleState.READY:
                self.add_triple_count2_server_status(server_status)
        return server_status

    def test_geosparql(self) -> bool:
        """
        Test if GeoSPARQL functions work.

        Returns:
            True if GeoSPARQL is available
        """
        test_query = """
        PREFIX geo: <http://www.opengis.net/ont/geosparql#>
        PREFIX geof: <http://www.opengis.net/def/function/geosparql/>

        SELECT * WHERE {
            BIND(geof:distance("POINT(0 0)"^^geo:wktLiteral, "POINT(1 1)"^^geo:wktLiteral) AS ?dist)
        } LIMIT 1
        """

        response = self.make_request(
            "POST",
            self.sparql_url,
            data={"query": test_query},
            headers={"Accept": "application/sparql-results+json"},
        )

        geosparql_available = response.success
        return geosparql_available
