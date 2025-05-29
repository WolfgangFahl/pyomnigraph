"""
Created on 2025-05-27

@author: wf
"""

import re
from dataclasses import dataclass

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

        self.docker_run_command = f"docker run -d --name {self.container_name} -p {self.port}:8080 {self.image}"


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

    def status(self) -> dict:
        """
        Get server status information.

        Returns:
            Dictionary with status information, empty dict if error
        """
        status_dict = {}

        response = self.make_request("GET", self.config.status_url)

        if response.success:
            status_dict["status"] = "ready"
            # For servers that return HTML status, parse it
            if response.response.text:
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
                                    status_dict[sanitized_name] = sanitized_value
                                break
        else:
            if response.error:
                status_dict["status"] = f"error: {response.error}"
            elif response.response:
                status_dict["status"] = f"status_code: {response.response.status_code}"
            else:
                status_dict["status"] = "unknown error"

        return status_dict

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
