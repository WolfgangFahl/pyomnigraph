"""
Created on 2025-05-30

@author: wf
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

from basemkit.yamlable import lod_storable
from lodstorage.params import Params
from lodstorage.query import Query
from lodstorage.sparql import SPARQL


@dataclass
class RdfDataset:
    """
    Configuration for an RDF dataset to be downloaded.
    """

    name: str  # Human-readable dataset name
    base_url: Optional[str] = None  # Base URL e.g. for tryit
    endpoint_url: Optional[str] = None  # SPARQL endpoint URL
    description: Optional[str] = None  # Optional dataset description
    database: Optional[str] = "jena"  # the database type of the endpoint
    expected_solutions: Optional[int] = None  # Expected number of solutions
    select_pattern: str = "?s ?p ?o"  # Basic Graph Pattern for queries
    construct_template: Optional[str] = field(default="?s ?p ?o")
    params: Optional[Dict[str, str]] = None  # npq parameters for {{ name }} templates (issue #36)
    prefix_sets: Optional[list] = field(default_factory=list)
    active: Optional[bool] = False
    rdf_file: Optional[str] = None  # Path to local RDF file (alternative to endpoint_url)
    # fields to be configured by post_init
    id: Optional[str] = field(default=None)
    count_query: Optional[Query] = field(default=None)
    select_query: Optional[Query] = field(default=None)
    sparql: Optional[SPARQL] = field(default=None)

    def apply_params(self, params_dict: Optional[Dict[str, str]] = None) -> None:
        """
        Apply npq parameters to select_pattern and construct_template.

        {{ name }} templates are replaced with the values of the merged
        params: the dataset's own params overridden by the given ones.
        Substitution always starts from the raw templates, so CLI overrides
        can be re-applied after YAML defaults. The blanket Params audit is
        off - it rejects quoted VALUES lists (see issue #36); values stem
        from local configuration and CLI.

        Args:
            params_dict: additional parameter values overriding self.params
        """
        # preserve the raw templates on first call
        if not hasattr(self, "raw_templates"):
            self.raw_templates = {
                "select_pattern": self.select_pattern,
                "construct_template": self.construct_template,
            }
        merged = dict(self.params) if self.params else {}
        if params_dict:
            merged.update(params_dict)
        if merged:
            for attr, raw_template in self.raw_templates.items():
                if raw_template:
                    params = Params(raw_template, with_audit=False)
                    if params.has_params:
                        params.set(merged)
                        setattr(self, attr, params.apply_parameters())

    def build_queries(self) -> None:
        """
        (Re)build count_query and select_query from the current select_pattern.
        Only initializes SPARQL-related fields if endpoint_url is provided.
        """
        if self.endpoint_url:
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

    def __post_init__(self):
        """
        Apply npq params and generate the queries from select_pattern.
        """
        self.apply_params()
        self.build_queries()

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
