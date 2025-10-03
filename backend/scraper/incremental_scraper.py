"""
Incremental scraper that only re-scrapes changed contractors based on thresholds
"""
import sys
sys.path.insert(0, '/app')

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from backend.scraper.gaf_scraper import GAFContractorScraper
from backend.db.connection import DatabaseManager
from backend.db.models import Contractor, ScrapeRun
from backend.ai.insights_generator import InsightsGenerator

logger = logging.getLogger(__name__)


class IncrementalScraper:
    """
    Implements intelligent incremental refresh logic:
    - Lightweight listing page scrape every 2 days
    - Only re-scrape full profile if significant changes detected
    """

    def __init__(self, headless=True):
        self.scraper = GAFContractorScraper(headless=headless)
        self.db_manager = DatabaseManager()
        self.insights_generator = InsightsGenerator()

    def should_rescrape_profile(self, existing: Contractor, listing_data: Dict) -> Tuple[bool, str]:
        """
        Determine if we should re-scrape the full profile based on change thresholds

        Args:
            existing: Existing contractor from database
            listing_data: New data from listing page

        Returns:
            Tuple of (should_rescrape: bool, reason: str)
        """
        reasons = []

        # Always re-scrape if phone number changed
        new_phone = listing_data.get('phone')
        if new_phone and existing.phone != new_phone:
            return True, "Phone number changed"

        # Always re-scrape if profile URL changed
        new_url = listing_data.get('profile_url')
        if new_url and existing.profile_url != new_url:
            return True, "Profile URL changed"

        # Re-scrape if rating changed by more than 0.3
        new_rating = listing_data.get('rating')
        if new_rating and existing.rating:
            rating_change = abs(float(new_rating) - float(existing.rating))
            if rating_change > 0.3:
                return True, f"Rating changed by {rating_change} (from {existing.rating} to {new_rating})"

        # Re-scrape if reviews increased by 10 or more
        new_reviews = listing_data.get('reviews_count')
        if new_reviews and existing.reviews_count:
            review_change = new_reviews - existing.reviews_count
            if review_change >= 10:
                return True, f"Reviews increased by {review_change} (from {existing.reviews_count} to {new_reviews})"
            elif review_change < -5:  # Also catch if reviews decreased significantly
                return True, f"Reviews decreased by {abs(review_change)}"

        # No significant changes detected
        return False, "No significant changes"

    def incremental_refresh(self, zipcode: str, distance: int = 25, max_results: int = None) -> Dict:
        """
        Perform incremental refresh:
        1. Scrape listing pages (lightweight)
        2. Compare with existing data
        3. Only re-scrape profiles that meet threshold criteria

        Args:
            zipcode: ZIP code to search
            distance: Search radius in miles
            max_results: Maximum results to process

        Returns:
            Statistics dictionary
        """
        stats = {
            'total_found': 0,
            'new_contractors': 0,
            'profiles_rescraped': 0,
            'unchanged': 0,
            'updated_metadata': 0
        }

        # Start scrape run tracking
        scrape_run_id = None
        with self.db_manager.get_session() as session:
            scrape_run = ScrapeRun(
                zipcode=zipcode,
                distance=distance,
                started_at=datetime.utcnow(),
                status='running'
            )
            session.add(scrape_run)
            session.commit()
            scrape_run_id = scrape_run.id

        try:
            self.scraper.start()

            # Step 1: Lightweight listing page scrape (no profile visits yet)
            logger.info("Step 1: Scraping listing pages (lightweight)...")
            listing_data = self.scraper.scrape_contractors(
                zipcode=zipcode,
                distance=distance,
                max_results=max_results
            )
            stats['total_found'] = len(listing_data)

            # Step 2: Compare with existing data and decide what to re-scrape
            contractors_to_rescrape = []
            contractors_to_update_metadata = []
            new_contractors = []

            with self.db_manager.get_session() as session:
                for contractor_data in listing_data:
                    profile_url = contractor_data.get('profile_url')
                    if not profile_url:
                        continue

                    # Check if contractor exists
                    existing = session.query(Contractor).filter(
                        Contractor.profile_url == profile_url
                    ).first()

                    if not existing:
                        # New contractor - need full profile scrape
                        new_contractors.append(contractor_data)
                        logger.info(f"New contractor found: {contractor_data.get('name')}")
                    else:
                        # Existing contractor - check thresholds
                        should_rescrape, reason = self.should_rescrape_profile(existing, contractor_data)

                        if should_rescrape:
                            contractors_to_rescrape.append((contractor_data, reason))
                            logger.info(f"Will re-scrape {contractor_data.get('name')}: {reason}")
                        else:
                            # Just update lightweight metadata (rating, reviews, distance)
                            contractors_to_update_metadata.append(contractor_data)
                            logger.debug(f"No re-scrape needed for {contractor_data.get('name')}")

            # Step 3: Re-scrape profiles for new contractors (save as we go)
            logger.info(f"Step 2: Scraping {len(new_contractors)} new contractor profiles...")
            for idx, contractor_data in enumerate(new_contractors, 1):
                try:
                    description, certifications = self.scraper._scrape_profile_description(
                        contractor_data['profile_url']
                    )
                    contractor_data['description'] = description
                    contractor_data['certifications'] = certifications
                    logger.info(f"Scraped new profile: {contractor_data.get('name')} ({idx}/{len(new_contractors)})")

                    # Save immediately to database
                    new_stats = self.db_manager.save_contractors_batch([contractor_data])
                    stats['new_contractors'] += new_stats['new']

                    # Generate AI insights for new contractor
                    try:
                        insights = self.insights_generator.generate_insights(contractor_data)
                        if insights:
                            with self.db_manager.get_session() as session:
                                contractor = session.query(Contractor).filter(
                                    Contractor.profile_url == contractor_data['profile_url']
                                ).first()
                                if contractor:
                                    contractor.ai_insights = [insights]
                                    session.commit()
                                    logger.info(f"Generated insights for new contractor: {contractor_data.get('name')}")
                    except Exception as e:
                        logger.error(f"Error generating insights for {contractor_data.get('name')}: {e}")

                except Exception as e:
                    logger.error(f"Error scraping new profile {contractor_data.get('name')}: {e}")

            # Step 4: Re-scrape profiles for changed contractors (save as we go)
            logger.info(f"Step 3: Re-scraping {len(contractors_to_rescrape)} changed contractor profiles...")
            for idx, (contractor_data, reason) in enumerate(contractors_to_rescrape, 1):
                try:
                    description, certifications = self.scraper._scrape_profile_description(
                        contractor_data['profile_url']
                    )
                    contractor_data['description'] = description
                    contractor_data['certifications'] = certifications
                    logger.info(f"Re-scraped profile for {contractor_data.get('name')}: {reason} ({idx}/{len(contractors_to_rescrape)})")

                    # Save immediately to database
                    rescrape_stats = self.db_manager.save_contractors_batch([contractor_data])
                    stats['profiles_rescraped'] += rescrape_stats['updated']

                    # Regenerate AI insights for re-scraped contractor
                    try:
                        insights = self.insights_generator.generate_insights(contractor_data)
                        if insights:
                            with self.db_manager.get_session() as session:
                                contractor = session.query(Contractor).filter(
                                    Contractor.profile_url == contractor_data['profile_url']
                                ).first()
                                if contractor:
                                    contractor.ai_insights = [insights]
                                    session.commit()
                                    logger.info(f"Regenerated insights for {contractor_data.get('name')}")
                    except Exception as e:
                        logger.error(f"Error regenerating insights for {contractor_data.get('name')}: {e}")

                except Exception as e:
                    logger.error(f"Error re-scraping profile {contractor_data.get('name')}: {e}")

            # Step 5: Update metadata only for unchanged contractors
            logger.info("Step 4: Updating metadata for unchanged contractors...")

            # Update metadata only for unchanged contractors
            if contractors_to_update_metadata:
                metadata_stats = self._update_metadata_only(contractors_to_update_metadata)
                stats['updated_metadata'] = metadata_stats['updated']
                stats['unchanged'] = metadata_stats['unchanged']

            # Update scrape run
            with self.db_manager.get_session() as session:
                scrape_run = session.query(ScrapeRun).filter(ScrapeRun.id == scrape_run_id).first()
                if scrape_run:
                    scrape_run.contractors_found = stats['total_found']
                    scrape_run.contractors_new = stats['new_contractors']
                    scrape_run.contractors_updated = stats['profiles_rescraped'] + stats['updated_metadata']
                    scrape_run.completed_at = datetime.utcnow()
                    scrape_run.status = 'completed'

            logger.info(f"Incremental refresh complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Incremental refresh failed: {str(e)}")
            # Update scrape run with error
            with self.db_manager.get_session() as session:
                scrape_run = session.query(ScrapeRun).filter(ScrapeRun.id == scrape_run_id).first()
                if scrape_run:
                    scrape_run.completed_at = datetime.utcnow()
                    scrape_run.status = 'failed'
                    scrape_run.error_message = str(e)
            raise
        finally:
            self.scraper.close()

    def _update_metadata_only(self, contractors_data: List[Dict]) -> Dict:
        """
        Update only lightweight metadata (rating, reviews, distance) without re-scraping profile

        Args:
            contractors_data: List of contractor dictionaries

        Returns:
            Statistics dictionary
        """
        stats = {'updated': 0, 'unchanged': 0}

        with self.db_manager.get_session() as session:
            for contractor_data in contractors_data:
                profile_url = contractor_data.get('profile_url')
                if not profile_url:
                    continue

                existing = session.query(Contractor).filter(
                    Contractor.profile_url == profile_url
                ).first()

                if existing:
                    # Update only metadata fields
                    changed = False
                    if contractor_data.get('rating') and existing.rating != contractor_data.get('rating'):
                        existing.rating = contractor_data.get('rating')
                        changed = True
                    if contractor_data.get('reviews_count') and existing.reviews_count != contractor_data.get('reviews_count'):
                        existing.reviews_count = contractor_data.get('reviews_count')
                        changed = True
                    if contractor_data.get('distance') and existing.distance != contractor_data.get('distance'):
                        existing.distance = contractor_data.get('distance')
                        changed = True

                    # Update last_scraped_at timestamp
                    existing.last_scraped_at = datetime.utcnow()

                    if changed:
                        stats['updated'] += 1
                        logger.debug(f"Updated metadata for: {existing.name}")
                    else:
                        stats['unchanged'] += 1

        return stats


def main():
    """Main execution function for incremental refresh"""
    scraper = IncrementalScraper(headless=True)

    # Configuration
    zipcode = "10013"
    distance = 25
    max_results = None  # None for full scrape (~89 contractors)

    stats = scraper.incremental_refresh(
        zipcode=zipcode,
        distance=distance,
        max_results=max_results
    )

    print(f"\n{'='*60}")
    print(f"Incremental Refresh Complete")
    print(f"{'='*60}")
    print(f"Total contractors found: {stats['total_found']}")
    print(f"New contractors: {stats['new_contractors']}")
    print(f"Profiles re-scraped (significant changes): {stats['profiles_rescraped']}")
    print(f"Metadata updated (minor changes): {stats['updated_metadata']}")
    print(f"Unchanged: {stats['unchanged']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
