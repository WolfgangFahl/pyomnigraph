"""
Created on 2025-05-30

@author: wf
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from lodstorage.sparql import SPARQL
from lodstorage.query import Query
from lodstorage.yamlable import lod_storable


@dataclass
class RdfDataset:
    """
    Configuration for an RDF dataset to be downloaded.
    """

    name: str  # Human-readable dataset name
    base_url: str # Base URL e.g. for tryit
    endpoint_url: str  # SPARQL endpoint URL
    expected_triples: Optional[int] = None  # Expected number of triples
    select_pattern: str = "?s ?p ?o"  # Basic Graph Pattern for queries
    description: Optional[str] = None  # Optional dataset description
    active: Optional[bool] = False
    # fields to be configured by post_init
    count_query: Optional[str] = field(default=None)
    construct_pattern: Optional[str] = field(default=None)

    def __post_init__(self):
        """
        Generate count_query and construct_pattern from select_pattern.
        """
        self.count_query = Query(
            name=f"{self.name}_count",
            query=f"SELECT (COUNT(*) AS ?count) WHERE {{ {self.select_pattern} }}",
            endpoint=self.endpoint_url,
            description=f"Count query for {self.name}"
        )
        self.select_query = Query(
            name=f"{self.name}_select",
            query=f"SELECT * WHERE {{ {self.select_pattern} }}",
            endpoint=self.endpoint_url,
            description=f"Select query for {self.name}"
        )
        self.construct_pattern = self.select_pattern
        self.sparql=SPARQL(self.endpoint_url)

    def getTryItUrl(self, database: str = "blazegraph")->str:
        """
        return the "try it!" url for the given database

        Args:
            database(str): the database to be used

        Returns:
            str: the "try it!" url for the given query
        """
        tryit_url=self.select_query.getTryItUrl(self.base_url, database)
        return tryit_url

    def get_construct_query(self, offset: int, limit: int) -> str:
        """
        Generate CONSTRUCT query with offset and limit.

        Args:
            offset: Query offset
            limit: Query limit

        Returns:
            SPARQL CONSTRUCT query string
        """
        query = f"""
        CONSTRUCT {{ {self.construct_pattern} }}
        WHERE     {{ {self.construct_pattern} }}
        OFFSET {offset}
        LIMIT {limit}
        """
        return query


@lod_storable
class RdfDatasets:
    """Collection of server configurations loaded from YAML."""

    datasets: Dict[str, RdfDataset] = field(default_factory=dict)

    @classmethod
    def ofYaml(cls, yaml_path: str) -> "RdfDatasets":
        """Load server configurations from YAML file."""
        datasets = cls.load_from_yaml_file(yaml_path)
        return datasets
