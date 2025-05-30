"""
Created on 2025-05-26

@author: wf

Download RDF dump via paginated CONSTRUCT queries.
"""
from omnigraph.rdf_dataset import RdfDataset, RdfDatasets
import argparse
import time
from pathlib import Path
import requests
from tqdm import tqdm

class RdfDumpDownloader:
    """
    Downloads an RDF dump from a SPARQL endpoint via
    paginated CONSTRUCT queries.
    """

    def __init__(
        self,
        dataset: RdfDataset,
        output_path: str,
        limit: int = 10000,
        max_triples: int = None,
        show_progress: bool = True,
    ):
        """
        Initialize the RDF dump downloader.

        Args:
            dataset: RdfDataset configuration
            output_path: the directory for the dump file
            limit: Number of triples per request
            max_triples: Maximum number of triples to download
            show_progress: Whether to show progress bar
        """
        self.dataset = dataset
        self.endpoint_url = dataset.endpoint_url
        self.output_path = output_path
        self.limit = limit
        self.max_triples = max_triples or dataset.expected_triples or 200000
        self.show_progress = show_progress
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

        total_chunks = self.max_triples // self.limit
        chunk_count = 0

        iterator = range(total_chunks)
        if self.show_progress:
            iterator = tqdm(iterator, desc="Downloading RDF dump")

        for chunk_idx in iterator:
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

            filename = output_dir / f"dump_{chunk_idx:06d}.ttl"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)

            chunk_count += 1
            time.sleep(0.5)

        return chunk_count


def main():
    """
    Main function with argument parsing.
    """
    parser = argparse.ArgumentParser(
        description="Download RDF dump from SPARQL endpoint via paginated CONSTRUCT queries"
    )

    parser.add_argument(
        "--url",
        type=str,
        default="https://gov-sparql.genealogy.net/dataset/sparql",
        help="SPARQL endpoint URL (default: gov.genealogy.net)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10000,
        help="Number of triples per request (default: 10000)",
    )

    parser.add_argument(
        "--max-triples",
        type=int,
        default=200000,
        help="Maximum number of triples to download (default: 200000)",
    )

    parser.add_argument("--no-progress", action="store_true", help="Disable progress bar")
    parser.add_argument("--output-path", default=".", help="Path for dump files")

    args = parser.parse_args()

    downloader = RdfDumpDownloader(
        endpoint_url=args.url,
        output_path=args.output_path,
        limit=args.limit,
        max_triples=args.max_triples,
        show_progress=not args.no_progress,
    )

    print(f"Starting download from: {args.url}")
    print(f"Limit per request: {args.limit}")
    print(f"Max triples: {args.max_triples}")

    chunk_count = downloader.download()
    print(f"Download completed. Downloaded {chunk_count} chunks.")


if __name__ == "__main__":
    main()
