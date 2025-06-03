"""
Created on 2025-05-30

@author: wf
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

from lodstorage.query import Query
from lodstorage.sparql import SPARQL
from lodstorage.yamlable import lod_storable


@dataclass
class RdfDataset:
    """
    Configuration for an RDF dataset to be downloaded.
    """

    name: str  # Human-readable dataset name
    base_url: str  # Base URL e.g. for tryit
    endpoint_url: str  # SPARQL endpoint URL
    description: Optional[str] = None  # Optional dataset description
    database: Optional[str] = "jena"  # the database type of the endpoint
    expected_solutions: Optional[int] = None  # Expected number of solutions
    select_pattern: str = "?s ?p ?o"  # Basic Graph Pattern for queries
    construct_template: Optional[str] = field(default="?s ?p ?o")
    active: Optional[bool] = False
    # fields to be configured by post_init
    id: Optional[str] = field(default=None)
    count_query: Optional[Query] = field(default=None)
    select_query: Optional[Query] = field(default=None)
    sparql: Optional[SPARQL] = field(default=None)

    def __post_init__(self):
        """
        Generate count_query and construct_pattern from select_pattern.
        """
        self.count_query = Query(
            name=f"{self.name}_count",
            query=f"SELECT (COUNT(*) AS ?count) WHERE {{ {self.select_pattern} }}",
            endpoint=self.endpoint_url,
            description=f"Count query for {self.name}",
        )
        self.select_query = Query(
            name=f"{self.name}_select",
            query=f"SELECT * WHERE {{ {self.select_pattern} }}",
            endpoint=self.endpoint_url,
            description=f"Select query for {self.name}",
        )
        self.sparql = SPARQL(self.endpoint_url)

    @property
    def full_name(self):
        ds_id = self.id or "?"
        full_name = f"{ds_id}→{self.name}({self.description})"
        return full_name

    def get_solution_count(self) -> int:
        """
        Get the number of solutions/results from the SPARQL endpoint.

        Returns:
            Number of solutions available from the count query
        """
        count = self.sparql.getValue(self.count_query.query, "count")
        return count

    def getTryItUrl(self, database: str = "blazegraph") -> str:
        """
        return the "try it!" url for the given database

        Args:
            database(str): the database to be used

        Returns:
            str: the "try it!" url for the given query
        """
        tryit_url = self.select_query.getTryItUrl(self.base_url, database)
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
        CONSTRUCT {{ {self.construct_template} }}
        WHERE     {{ {self.select_pattern} }}
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
        for ds_id, dataset in datasets.datasets.items():
            dataset.id = ds_id
        return datasets
