"""
Created on 2025-05-26

@author: wf

Download RDF dump via paginated CONSTRUCT queries.
"""

import time
from argparse import Namespace
from pathlib import Path
from typing import Optional

from lodstorage.rdf_format import RdfFormat
from lodstorage.sparql import SPARQL
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
        self.args = args
        self.rdf_format = RdfFormat.by_label(args.rdf_format)
        self.dataset = dataset
        self.endpoint_url = dataset.endpoint_url
        self.sparql = SPARQL(self.endpoint_url)
        self.output_path = output_path
        self.limit = args.limit if args else 10000
        self.max_count = args.max_count if args and args.max_count is not None else dataset.expected_solutions or 200000
        self.show_progress = not args.no_progress if args else True
        self.force = args.force if args else False
        self.debug = args.debug if args else False

    def fetch_chunk(self, offset: int, rdf_format: str = "turtle") -> str:
        """
        Fetch a chunk of RDF data in the given format using direct HTTP POST.

        Args:
            offset: Query offset
            rdf_format: RDF format label

        Returns:
            RDF content as string
        """
        query = self.dataset.get_construct_query(offset, self.limit)
        if self.debug:
            print(query)
        content = self.sparql.post_query_direct(query=query, rdf_format=rdf_format)
        # Better debugging
        if self.debug:
            print(f"Chunk {offset}: content length = {len(content) if content else 0}")
        return content

    def download(self) -> int:
        """
        Download the RDF dump in chunks.

        Returns:
            Number of chunks downloaded
        """
        # make sure the output_path is created
        output_dir = Path(self.output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get actual count from dataset
        actual_count = self.dataset.get_solution_count()
        total_chunks = (actual_count + self.limit - 1) // self.limit  # Round up
        chunk_count = 0

        iterator = range(total_chunks)
        if self.show_progress:
            iterator = tqdm(iterator, desc=f"Downloading RDF dump ({actual_count} results)")

        for chunk_idx in iterator:
            filename = output_dir / f"dump_{chunk_idx:06d}{self.rdf_format.extension}"
            if filename.exists() and not self.force:
                if self.show_progress:
                    iterator.set_description(f"Skipping existing file: {filename}")
                continue

            offset = chunk_idx * self.limit
            try:
                content = self.fetch_chunk(offset=offset, rdf_format=self.rdf_format.label)
            except Exception as e:
                print(f"Error at offset {offset}: {e}")
                break

            if not content or content.strip() == "":
                break

            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)

            chunk_count += 1
            time.sleep(0.5)

        return chunk_count
