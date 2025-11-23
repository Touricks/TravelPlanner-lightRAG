#!/usr/bin/env python3
"""
Simple LightRAG Query CLI

Usage:
    python scripts/query.py -q "What attractions are in New York?"
    python scripts/query.py -q "Tell me about Central Park" --verbose
"""

import sys
import os
import argparse
import warnings
from pathlib import Path

# Parse args early to check verbose flag
parser = argparse.ArgumentParser(description="Query LightRAG Travel Planner")
parser.add_argument("-q", "--query", type=str, required=True, help="Your question")
parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed logs")
args = parser.parse_args()


class QuietOutput:
    """Suppress stdout/stderr"""
    def write(self, x): pass
    def flush(self): pass


# Suppress all output before importing lightrag (unless verbose)
if not args.verbose:
    import logging
    logging.disable(logging.CRITICAL)
    warnings.filterwarnings("ignore")
    os.environ["LIGHTRAG_LOG_LEVEL"] = "ERROR"
    _original_stdout = sys.stdout
    _original_stderr = sys.stderr
    sys.stdout = QuietOutput()
    sys.stderr = QuietOutput()

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

import asyncio
from config.lightrag_config import initialize_rag_async, QueryParam


async def main():
    rag = await initialize_rag_async()

    # Restore output before printing result
    if not args.verbose:
        sys.stdout = _original_stdout
        sys.stderr = _original_stderr

    result = await rag.aquery(args.query, param=QueryParam(mode="mix"))
    print(result)


if __name__ == '__main__':
    asyncio.run(main())
