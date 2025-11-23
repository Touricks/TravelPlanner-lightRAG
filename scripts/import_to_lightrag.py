#!/usr/bin/env python3
"""
Data Import Script: Import JSONL data into LightRAG with PostgreSQL storage

Features:
- Reads JSONL format place descriptions
- Initializes LightRAG with PostgreSQL + pgvector storage
- Batch imports documents for knowledge graph construction
- Progress tracking and statistics

Usage:
    python scripts/import_to_lightrag.py --input data/places_test_50.jsonl --limit 50
    python scripts/import_to_lightrag.py --input data/places_export.jsonl
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from dotenv import load_dotenv
from tqdm import tqdm

# Add project root and config to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'config'))

# Load environment variables
load_dotenv(PROJECT_ROOT / '.env')

# Configure logging
LOG_DIR = PROJECT_ROOT / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'import_lightrag.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def read_jsonl_documents(file_path: Path, limit: int = None) -> List[Dict]:
    """
    Read JSONL file

    Args:
        file_path: Path to JSONL file
        limit: Maximum number of records to read (optional)

    Returns:
        List of document dictionaries
    """
    documents = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            doc = json.loads(line.strip())
            documents.append(doc)
    return documents


async def import_documents(
    rag,
    documents: List[Dict]
) -> Dict:
    """
    Import documents into LightRAG

    Args:
        rag: LightRAG instance
        documents: List of document dictionaries

    Returns:
        Statistics dictionary
    """
    start_time = datetime.now()
    total_docs = len(documents)

    logger.info(f"Starting import of {total_docs} documents")

    # Extract text content
    texts = [doc['content'] for doc in documents]

    # Import with progress tracking
    logger.info("Inserting documents into LightRAG...")
    logger.info("This will extract entities, relations, and build the knowledge graph...")

    try:
        # Batch insert
        await rag.ainsert(texts)

        logger.info("Document insertion completed")

    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        raise

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    return {
        'total': total_docs,
        'processed': total_docs,
        'duration': duration,
        'speed': total_docs / duration if duration > 0 else 0
    }


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Import data into LightRAG with PostgreSQL storage')
    parser.add_argument('--input', type=str, default='data/places_export.jsonl', help='Input JSONL file')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of records')
    parser.add_argument('--use-postgres', action='store_true', default=True, help='Use PostgreSQL storage (default: True)')
    parser.add_argument('--working-dir', type=str, default='./travel_rag', help='LightRAG working directory')

    args = parser.parse_args()

    # Output configuration
    logger.info("=" * 60)
    logger.info("LightRAG Import Configuration")
    logger.info("=" * 60)
    logger.info(f"Input file: {args.input}")
    logger.info(f"Record limit: {args.limit or 'No limit'}")
    logger.info(f"Working directory: {args.working_dir}")
    logger.info(f"Storage backend: {'PostgreSQL + pgvector' if args.use_postgres else 'Local files'}")
    logger.info("=" * 60)

    # Read data
    input_path = PROJECT_ROOT / args.input
    logger.info(f"Reading file: {input_path}")
    documents = read_jsonl_documents(input_path, limit=args.limit)
    logger.info(f"Successfully read {len(documents)} records")

    # Initialize LightRAG using config module
    logger.info("Initializing LightRAG...")

    try:
        from config.lightrag_config import initialize_rag_async

        # Initialize with PostgreSQL storage
        rag = await initialize_rag_async(use_postgres=args.use_postgres)

        logger.info("LightRAG initialization completed")

    except Exception as e:
        logger.error(f"Failed to initialize LightRAG: {e}", exc_info=True)
        logger.error("Please ensure:")
        logger.error("1. PostgreSQL is running")
        logger.error("2. pgvector extension is installed: CREATE EXTENSION IF NOT EXISTS vector;")
        logger.error("3. .env file has correct POSTGRES_* and QWEN_API_KEY credentials")
        return 1

    try:
        # Import data
        stats = await import_documents(rag, documents)

        # Output statistics
        logger.info("=" * 60)
        logger.info("Import completed!")
        logger.info("=" * 60)
        logger.info(f"Total documents: {stats['total']}")
        logger.info(f"Successfully imported: {stats['processed']}")
        logger.info(f"Processing time: {stats['duration']:.1f} seconds")
        logger.info(f"Average speed: {stats['speed']:.2f} documents/second")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Knowledge graph has been built in PostgreSQL!")
        logger.info("You can now query using:")
        logger.info("  - Naive mode: Simple keyword search")
        logger.info("  - Local mode: Entity-focused retrieval")
        logger.info("  - Global mode: Community-level insights")
        logger.info("  - Hybrid mode: Combined local + global")
        logger.info("  - Mix mode: Best overall (recommended)")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
