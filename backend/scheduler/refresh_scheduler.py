"""
Scheduler for incremental refresh
Runs every 2 days to check for contractor updates
"""
import sys
sys.path.insert(0, '/app')

import schedule
import time
import logging
from datetime import datetime
from backend.scraper.incremental_scraper import IncrementalScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_incremental_refresh():
    """Run incremental refresh for configured ZIP codes"""
    logger.info(f"Starting scheduled incremental refresh at {datetime.now()}")

    zipcodes = ["10013"]  # add zip codes to scale
    distance = 25 # change distance to scale

    scraper = IncrementalScraper(headless=True)

    total_stats = {
        'total_found': 0,
        'new_contractors': 0,
        'profiles_rescraped': 0,
        'updated_metadata': 0,
        'unchanged': 0
    }

    for zipcode in zipcodes:
        try:
            logger.info(f"Processing ZIP code: {zipcode}")
            stats = scraper.incremental_refresh(
                zipcode=zipcode,
                distance=distance,
                max_results=None  # Process all results
            )

            # Aggregate stats
            for key in total_stats:
                total_stats[key] += stats.get(key, 0)

        except Exception as e:
            logger.error(f"Error processing ZIP code {zipcode}: {str(e)}")
            continue

    logger.info(f"Scheduled refresh complete: {total_stats}")
    return total_stats


def main():
    """Main scheduler loop"""
    # Schedule incremental refresh every 2 days
    schedule.every(2).days.at("02:00").do(run_incremental_refresh)

    logger.info("Incremental refresh scheduler started")
    logger.info("Next run: Every 2 days at 02:00 AM")

    # Run once immediately on start (optional)
    # run_incremental_refresh()

    while True:
        schedule.run_pending()
        time.sleep(3600)  # Check every hour


if __name__ == "__main__":
    main()
