"""
Created on 2025-05-26

@author: wf

Download RDF dump via paginated CONSTRUCT queries.
"""

import argparse
import time
from argparse import Namespace
from pathlib import Path
from typing import Optional

import requests
from tqdm import tqdm

from omnigraph.rdf_dataset import RdfDataset, RdfDatasets


class RdfDumpDownloader:
    """
    Downloads an RDF dump from a SPARQL endpoint via
    paginated CONSTRUCT queries.
    """

    def __init__(self, dataset: RdfDataset, output_path: str, args: Optional[Namespace] = None):
        """
        Initialize the RDF dump downloader.

        Args:
            dataset: RdfDataset configuration
            output_path: the directory for the dump file
            args: parsed CLI arguments (optional)
        """
        self.dataset = dataset
        self.endpoint_url = dataset.endpoint_url
        self.output_path = output_path
        self.limit = args.limit if args else 10000
        self.max_count = (
            args.max_count if args and args.max_count is not None else dataset.expected_solutions or 200000
        )
        self.show_progress = not args.no_progress if args else True
        self.force = args.force if args else False
        self.headers = {"Accept": "text/turtle"}

    def fetch_chunk(self, offset: int) -> str:
        """
        Fetch a chunk of RDF data from the endpoint.

        Args:
            offset: Query offset

        Returns:
            RDF content as string

        Raises:
            Exception: If HTTP request fails
        """
        query = self.dataset.get_construct_query(offset, self.limit)
        response = requests.post(
            self.endpoint_url,
            data={"query": query},
            headers=self.headers,
            timeout=60,
        )
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
        return response.text.strip()

    def download(self) -> int:
        """
        Download the RDF dump in chunks.

        Returns:
            Number of chunks downloaded
        """
        # make sure the output_path is created
        output_dir = Path(self.output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        total_triples_downloaded = 0

        total_chunks = self.max_count // self.limit
        chunk_count = 0

        iterator = range(total_chunks)
        if self.show_progress:
            iterator = tqdm(iterator, desc="Downloading RDF dump")

        for chunk_idx in iterator:
            filename = output_dir / f"dump_{chunk_idx:06d}.ttl"
            if filename.exists() and not self.force:
                print(f"Skipping existing file: {filename}")
                continue
            offset = chunk_idx * self.limit
            try:
                content = self.fetch_chunk(offset)
            except Exception as e:
                print(f"Error at offset {offset}: {e}")
                break

            if content:
                triple_count = content.count(" .") - content.count("@prefix")
                total_triples_downloaded += triple_count
            else:
                print(f"Offset {offset}: Empty response → stopping.")
                break

            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)

            chunk_count += 1
            time.sleep(0.5)

        return chunk_count
