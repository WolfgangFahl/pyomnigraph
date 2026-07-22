"""
Created on 2026-07-22

Tests for npq (named parameterized query) support in RdfDataset - issue #36.

@author: wf
"""

from omnigraph.ominigraph_paths import OmnigraphPaths
from omnigraph.rdf_dataset import RdfDataset, RdfDatasets
from tests.basetest import Basetest


class TestRdfDatasetParams(Basetest):
    """
    test npq parameter support in RdfDataset
    """

    def setUp(self, debug=False, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)
        self.ogp = OmnigraphPaths()
        self.datasets_yaml_path = self.ogp.examples_dir / "datasets.yaml"

    def get_npq_dataset(self, orcids: str = '"0000-0002-0821-6995"') -> RdfDataset:
        """create an npq test dataset with the given orcids param"""
        dataset = RdfDataset(
            name="npq-test",
            endpoint_url="https://example.org/sparql",
            select_pattern="VALUES ?orcid { {{ orcids }} } ?author ?p ?orcid",
            construct_template="?author ?p ?orcid",
            params={"orcids": orcids},
        )
        return dataset

    def test_params_applied_from_yaml_defaults(self):
        """dataset params are substituted into the query templates"""
        dataset = self.get_npq_dataset()
        self.assertNotIn("{{", dataset.select_pattern)
        self.assertIn('VALUES ?orcid { "0000-0002-0821-6995" }', dataset.select_pattern)
        self.assertIn('"0000-0002-0821-6995"', dataset.count_query.query)

    def test_params_cli_override(self):
        """apply_params re-applies from raw templates so overrides work"""
        dataset = self.get_npq_dataset()
        dataset.apply_params({"orcids": '"0000-0001-6324-7164"'})
        dataset.build_queries()
        self.assertIn('"0000-0001-6324-7164"', dataset.select_pattern)
        self.assertNotIn("0000-0002-0821-6995", dataset.select_pattern)
        self.assertIn('"0000-0001-6324-7164"', dataset.count_query.query)

    def test_example_npq_datasets(self):
        """the papers_of_my_network example datasets resolve their params"""
        datasets = RdfDatasets.ofYaml(str(self.datasets_yaml_path))
        for ds_id in ["papers_of_my_network_wikidata", "papers_of_my_network_dblp"]:
            dataset = datasets.datasets.get(ds_id)
            self.assertIsNotNone(dataset, ds_id)
            self.assertNotIn("{{", dataset.select_pattern)
            self.assertIn("0000-0002-0821-6995", dataset.select_pattern)
