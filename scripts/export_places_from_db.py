#!/usr/bin/env python3
"""
Data Export Script: Export data from PostgreSQL Places table to LightRAG-compatible JSONL format

Features:
- Asynchronous PostgreSQL database connection
- Batch extraction of Places table data
- Generate rich text descriptions
- Output to JSONL format file
- Support filtering and limit conditions

Usage example:
    python scripts/export_places_to_lightrag.py --city Tampa --limit 100
"""

import asyncio
import asyncpg
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from dotenv import load_dotenv
from tqdm import tqdm
import argparse

# Add project root directory to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
load_dotenv(PROJECT_ROOT / '.env')

# Configure logging
LOG_DIR = PROJECT_ROOT / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'export_places.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PlacesExporter:
    """Places Data Exporter"""

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str
    ):
        """
        Initialize the exporter

        Args:
            host: PostgreSQL host
            port: PostgreSQL port
            database: Database name
            user: Username
            password: Password
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.conn = None

    async def connect(self):
        """Establish database connection"""
        try:
            self.conn = await asyncpg.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            logger.info(f"Successfully connected to database: {self.database}")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    async def close(self):
        """Close database connection"""
        if self.conn:
            await self.conn.close()
            logger.info("Database connection closed")

    def generate_place_description(self, place: Dict) -> str:
        """
        Generate rich text description for a place

        Args:
            place: Place data dictionary

        Returns:
            Rich text description string
        """
        parts = []

        # 1. Basic information
        location = f"{place['state']} {place['city']}" if place['state'] else place['city']
        primary_cat = place['primary_category'] if place['primary_category'] else "attraction"
        parts.append(f"{place['name']} is a {primary_cat} in {location}.")

        # 2. Google categories (core relationship field)
        if place['google_types']:
            types_str = ', '.join(place['google_types'])
            parts.append(f"\nGoogle Categories: {types_str}")

        # 3. Rating information
        if place['rating'] is not None:
            rating_text = f"Rating: {place['rating']}"
            reviews_text = f" ({place['reviews_count']:,} reviews)" if place['reviews_count'] and place['reviews_count'] > 0 else ""
            parts.append(f"\n{rating_text}{reviews_text}")

        # 4. Price level (converted to dollar amount ranges)
        if place['price_level'] is not None:
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
        if place['editorial_summary']:
            parts.append(f"\n\nSummary: {place['editorial_summary']}")

        # 6. LLM description
        if place['llm_description']:
            parts.append(f"\n\nDescription: {place['llm_description']}")

        # 7. Scene tags
        if place['llm_tags']:
            tags_str = ', '.join(place['llm_tags'])
            parts.append(f"\n\nSuitable for: {tags_str}")

        return ''.join(parts)

    async def export_places(
        self,
        output_path: Path,
        city: Optional[str] = None,
        limit: Optional[int] = None,
        min_rating: float = 3.0,
        min_reviews: int = 10,
        batch_size: int = 100
    ) -> Dict:
        """
        Export Places data to JSONL file

        Args:
            output_path: Output file path
            city: Filter by city (optional)
            limit: Limit number of records (optional)
            min_rating: Minimum rating
            min_reviews: Minimum review count
            batch_size: Batch processing size

        Returns:
            Statistics dictionary
        """
        # Build query
        query = """
            SELECT
                google_place_id,
                name,
                city,
                state,
                latitude,
                longitude,
                rating,
                reviews_count,
                price_level,
                google_types,
                primary_category,
                editorial_summary,
                llm_description,
                llm_tags
            FROM places
            WHERE
                rating IS NOT NULL
                AND rating >= $1
                AND reviews_count >= $2
        """
        params = [min_rating, min_reviews]

        # Add city filter
        if city:
            query += " AND city = $3"
            params.append(city)
            order_param_idx = 4
        else:
            order_param_idx = 3

        # Build count query to get total
        count_query = """
            SELECT COUNT(*)
            FROM places
            WHERE
                rating IS NOT NULL
                AND rating >= $1
                AND reviews_count >= $2
        """
        if city:
            count_query += " AND city = $3"

        # Execute count query (note: does not include limit parameter)
        count_params = params[:order_param_idx - 1] if not limit else params[:order_param_idx - 1]
        total_count = await self.conn.fetchval(count_query, *count_params)

        # If limit is set, take the smaller value
        if limit and total_count > limit:
            total_count = limit

        # Add sorting and limit to main query
        query += " ORDER BY reviews_count DESC"
        if limit:
            query += f" LIMIT ${order_param_idx}"
            params.append(limit)

        logger.info(f"Starting export, estimated records: {total_count}")

        # Prepare output file
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Statistics
        stats = {
            'total_records': 0,
            'total_size': 0,
            'avg_content_length': 0,
            'start_time': datetime.now()
        }

        # Batch extraction and writing
        with open(output_path, 'w', encoding='utf-8') as f:
            # Execute query to get all records
            records = await self.conn.fetch(query, *params)

            # Progress bar
            pbar = tqdm(total=len(records), desc="Export progress", unit="records")

            for record in records:
                # Convert to dictionary
                place = dict(record)

                # Generate rich text
                content = self.generate_place_description(place)

                # Build document
                doc = {
                    'doc_id': place['google_place_id'],
                    'content': content,
                    'metadata': {
                        'city': place['city'],
                        'state': place['state'],
                        'latitude': float(place['latitude']) if place['latitude'] else None,
                        'longitude': float(place['longitude']) if place['longitude'] else None,
                        'rating': float(place['rating']) if place['rating'] else None,
                        'reviews_count': place['reviews_count'],
                        'price_level': place['price_level'],
                        'google_types': place['google_types'],
                        'primary_category': place['primary_category']
                    }
                }

                # Write to file
                f.write(json.dumps(doc, ensure_ascii=False) + '\n')

                # Update statistics
                stats['total_records'] += 1
                stats['total_size'] += len(content)

                # Update progress bar
                pbar.update(1)

            pbar.close()

        # Calculate average
        if stats['total_records'] > 0:
            stats['avg_content_length'] = stats['total_size'] / stats['total_records']

        stats['end_time'] = datetime.now()
        stats['duration'] = (stats['end_time'] - stats['start_time']).total_seconds()

        return stats


async def main():
    """Main function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Export data from PostgreSQL Places table to LightRAG JSONL format'
    )
    parser.add_argument(
        '--city',
        type=str,
        default=None,
        help='Filter by city (e.g. Tampa)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of records (default: all)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data/places_export.jsonl',
        help='Output file path (default: data/places_export.jsonl)'
    )
    parser.add_argument(
        '--min-rating',
        type=float,
        default=3.0,
        help='Minimum rating filter (default: 3.0)'
    )
    parser.add_argument(
        '--min-reviews',
        type=int,
        default=10,
        help='Minimum review count filter (default: 10)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Batch processing size (default: 100)'
    )

    args = parser.parse_args()

    # Read database configuration from environment variables
    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'travel_kg'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }

    # Output configuration information
    logger.info("=" * 60)
    logger.info("Data Export Configuration")
    logger.info("=" * 60)
    logger.info(f"Database: {db_config['database']}")
    logger.info(f"City filter: {args.city or 'All'}")
    logger.info(f"Record limit: {args.limit or 'No limit'}")
    logger.info(f"Minimum rating: {args.min_rating}")
    logger.info(f"Minimum reviews: {args.min_reviews}")
    logger.info(f"Output file: {args.output}")
    logger.info("=" * 60)

    # Create exporter
    exporter = PlacesExporter(**db_config)

    try:
        # Connect to database
        await exporter.connect()

        # Export data
        output_path = PROJECT_ROOT / args.output
        stats = await exporter.export_places(
            output_path=output_path,
            city=args.city,
            limit=args.limit,
            min_rating=args.min_rating,
            min_reviews=args.min_reviews,
            batch_size=args.batch_size
        )

        # Output statistics
        logger.info("=" * 60)
        logger.info("Export completed!")
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
        logger.info(f"Average text length: {stats['avg_content_length']:.0f} characters")
        logger.info(f"Processing time: {stats['duration']:.1f} seconds")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        return 1

    finally:
        # Close connection
        await exporter.close()

    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
