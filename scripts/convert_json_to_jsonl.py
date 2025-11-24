#!/usr/bin/env python3
"""
JSON to JSONL Converter: Convert JSON places file to LightRAG-compatible JSONL format

Features:
- Read JSON array from file
- Generate rich text descriptions using the same logic as DB export
- Output to JSONL format (one JSON object per line)
- Support custom input/output paths

Usage example:
    python scripts/convert_json_to_jsonl.py --input data/places_florida.json
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict
from datetime import datetime
import argparse
from tqdm import tqdm

# Add project root directory to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def generate_place_description(place: Dict) -> str:
    """
    Generate rich text description for a place

    This method is adapted from export_places_from_db.py
    Differences: JSON data doesn't have llm_description and llm_tags fields

    Args:
        place: Place data dictionary

    Returns:
        Rich text description string
    """
    parts = []

    # 1. Basic information
    location = f"{place.get('state', '')} {place.get('city', '')}".strip()
    if not location:
        location = "Unknown location"
    primary_cat = place.get('primary_category') or "attraction"
    parts.append(f"{place['name']} is a {primary_cat} in {location}.")

    # 2. Google categories (core relationship field)
    if place.get('google_types'):
        types_str = ', '.join(place['google_types'])
        parts.append(f"\nGoogle Categories: {types_str}")

    # 3. Rating information
    if place.get('rating') is not None:
        rating_text = f"Rating: {place['rating']:.2f}"
        reviews_count = place.get('reviews_count', 0)
        reviews_text = f" ({reviews_count:,} reviews)" if reviews_count > 0 else ""
        parts.append(f"\n{rating_text}{reviews_text}")

    # 4. Price level (converted to dollar amount ranges)
    if place.get('price_level') is not None:
        price_ranges = {
            0: "Free or very cheap (under $10)",
            1: "Inexpensive ($10-25)",
            2: "Moderate ($25-50)",
            3: "Expensive ($50-100)",
            4: "Very expensive (over $100)"
        }
        price_text = price_ranges.get(place['price_level'], "Price unknown")
        parts.append(f"\nPrice Level: {price_text}")

    # 5. Editorial summary
    if place.get('editorial_summary'):
        parts.append(f"\n\nSummary: {place['editorial_summary']}")

    # Note: llm_description and llm_tags are not available in JSON format
    # These fields are only present in database records

    return ''.join(parts)


def convert_json_to_jsonl(input_file: Path, output_file: Path) -> Dict:
    """
    Convert JSON places file to JSONL format

    Args:
        input_file: Input JSON file path
        output_file: Output JSONL file path

    Returns:
        Statistics dictionary
    """
    logger.info(f"Reading input file: {input_file}")

    # Read JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        places = json.load(f)

    if not isinstance(places, list):
        raise ValueError("Input JSON must be an array of place objects")

    total_places = len(places)
    logger.info(f"Loaded {total_places} places from JSON file")

    # Statistics
    stats = {
        'total_records': 0,
        'total_size': 0,
        'avg_content_length': 0,
        'start_time': datetime.now()
    }

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Convert and write to JSONL
    logger.info(f"Converting to JSONL format: {output_file}")

    with open(output_file, 'w', encoding='utf-8') as f:
        for place in tqdm(places, desc="Converting", unit="places"):
            # Generate rich text description
            content = generate_place_description(place)

            # Build document in LightRAG format
            doc = {
                'doc_id': place['google_place_id'],
                'content': content,
                'metadata': {
                    'city': place.get('city'),
                    'state': place.get('state'),
                    'latitude': float(place['latitude']) if place.get('latitude') is not None else None,
                    'longitude': float(place['longitude']) if place.get('longitude') is not None else None,
                    'rating': float(place['rating']) if place.get('rating') is not None else None,
                    'reviews_count': place.get('reviews_count'),
                    'price_level': place.get('price_level'),
                    'google_types': place.get('google_types'),
                    'primary_category': place.get('primary_category')
                }
            }

            # Write as single line JSON
            f.write(json.dumps(doc, ensure_ascii=False) + '\n')

            # Update statistics
            stats['total_records'] += 1
            stats['total_size'] += len(content)

    # Calculate average
    if stats['total_records'] > 0:
        stats['avg_content_length'] = stats['total_size'] / stats['total_records']

    stats['end_time'] = datetime.now()
    stats['duration'] = (stats['end_time'] - stats['start_time']).total_seconds()

    return stats


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Convert JSON places file to LightRAG JSONL format'
    )
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Input JSON file path (e.g., data/places_florida.json)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output JSONL file path (default: same as input with .jsonl extension)'
    )

    args = parser.parse_args()

    # Resolve paths
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = PROJECT_ROOT / input_path

    if not input_path.exists():
        logger.error(f"Input file does not exist: {input_path}")
        return 1

    # Determine output path
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = PROJECT_ROOT / output_path
    else:
        # Default: replace .json with .jsonl
        output_path = input_path.with_suffix('.jsonl')

    # Output configuration
    logger.info("=" * 60)
    logger.info("JSON to JSONL Conversion")
    logger.info("=" * 60)
    logger.info(f"Input file:  {input_path}")
    logger.info(f"Output file: {output_path}")
    logger.info("=" * 60)

    try:
        # Convert
        stats = convert_json_to_jsonl(input_path, output_path)

        # Output statistics
        logger.info("=" * 60)
        logger.info("Conversion completed!")
        logger.info("=" * 60)
        logger.info(f"Total records: {stats['total_records']}")
        logger.info(f"Output file: {output_path}")

        # Calculate file size
        file_size = output_path.stat().st_size
        if file_size < 1024:
            size_str = f"{file_size} B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"

        logger.info(f"File size: {size_str}")
        logger.info(f"Average content length: {stats['avg_content_length']:.0f} characters")
        logger.info(f"Processing time: {stats['duration']:.2f} seconds")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"Conversion failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
