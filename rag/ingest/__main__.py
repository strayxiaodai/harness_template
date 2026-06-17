"""CLI entry point for document ingest."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from rag.ingest.documents import ingest_documents

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """Run document ingest from the command line."""
    parser = argparse.ArgumentParser(description="Ingest documents into RAG indexes")
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Directory containing source documents",
    )
    args = parser.parse_args()
    manifest = ingest_documents(args.source)
    logger.info("Ingest complete: %s", manifest.model_dump())


if __name__ == "__main__":
    main()
