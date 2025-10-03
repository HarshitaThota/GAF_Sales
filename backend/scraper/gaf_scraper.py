import json
import time
import tempfile
import shutil
import re
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

import sys
sys.path.insert(0, '/app')

from backend.db.connection import DatabaseManager
from backend.db.models import ScrapeRun, Contractor
from backend.ai.insights_generator import InsightsGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GAFContractorScraper:
    def __init__(self, headless=True):
        """Initialize the scraper with Chrome options"""
        self.options = Options()
        self.options.binary_location = "/usr/bin/chromium"
        self.temp_dir = tempfile.mkdtemp()
        if headless:
            self.options.add_argument('--headless')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_argument(f'--user-data-dir={self.temp_dir}')
        self.options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        self.driver = None

    def start(self):
        """Start the browser"""
        from selenium.webdriver.chrome.service import Service
        service = Service('/usr/bin/chromedriver')
        self.driver = webdriver.Chrome(service=service, options=self.options)
        logger.info("Browser started successfully")

    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")
        # Clean up temp directory
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def scrape_contractors(self, zipcode, distance=25, max_results=None):
        """
        Scrape contractor data from GAF website

        Args:
            zipcode: ZIP code to search (note: page loads with zipcode already)
            distance: Distance radius in miles (default 25)
            max_results: Maximum number of results to scrape (None for all)

        Returns:
            List of contractor dictionaries
        """
        url = f"https://www.gaf.com/en-us/roofing-contractors/residential?distance={distance}"

        logger.info(f"Navigating to {url}")
        self.driver.get(url)

        # Wait for page to load (zipcode should already be loaded in the page)
        logger.info("Waiting for page to load with zipcode...")
        time.sleep(5)

        try:
            # Wait for contractor cards to appear
            logger.info("Waiting for contractor cards to load...")
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article.certification-card"))
            )

            contractors = []
            page_num = 1
            max_pages = 10  # Limit to 10 pages to prevent infinite loop
            seen_contractors = set()  # Track contractor names to detect duplicates

            # Scrape all pages (approximately 9 pages with 10 results each for 90 total)
            reached_limit = False
            while page_num <= max_pages and not reached_limit:
                logger.info(f"Scraping page {page_num}...")

                # Wait a bit for dynamic content to load
                time.sleep(3)

                # Find all contractor elements on current page
                contractor_elements = self.driver.find_elements(By.CSS_SELECTOR, "article.certification-card")
                logger.info(f"Found {len(contractor_elements)} contractor cards on page {page_num}")

                for idx, element in enumerate(contractor_elements):
                    if max_results and len(contractors) >= max_results:
                        logger.info(f"Reached max_results limit of {max_results}")
                        reached_limit = True
                        break

                    try:
                        contractor_data = self._extract_contractor_data(element, len(contractors))
                        contractor_name = contractor_data.get('name')

                        # Skip duplicates
                        if contractor_name and contractor_name in seen_contractors:
                            logger.warning(f"Duplicate contractor found: {contractor_name}, stopping pagination")
                            reached_limit = True
                            break

                        if contractor_name:
                            seen_contractors.add(contractor_name)

                        contractors.append(contractor_data)
                        logger.info(f"Scraped contractor {len(contractors)}: {contractor_name or 'Unknown'}")
                    except Exception as e:
                        logger.error(f"Error extracting contractor {len(contractors) + 1}: {str(e)}")
                        continue

                # Try to find and click next page button if not reached limit
                if not reached_limit:
                    try:
                        # Look for pagination next button
                        next_button = self.driver.find_element(By.CSS_SELECTOR, "a[aria-label='Next page'], button[aria-label='Next page'], .pagination__next:not(.disabled)")

                        # Check if next button is disabled or not present
                        if "disabled" in next_button.get_attribute("class"):
                            logger.info("Reached last page (next button disabled)")
                            break

                        # Use JavaScript click to avoid interception
                        logger.info("Clicking next page button...")
                        self.driver.execute_script("arguments[0].click();", next_button)
                        page_num += 1

                        # Wait for new page to load
                        time.sleep(5)

                        # Wait for new contractor cards to load
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "article.certification-card"))
                        )

                    except NoSuchElementException:
                        logger.info("No next page button found, reached end of results")
                        break
                    except TimeoutException:
                        logger.warning("Timeout waiting for next page to load, stopping pagination")
                        break

            logger.info(f"Successfully scraped {len(contractors)} contractors across {page_num} pages")

            # Note: Profile scraping moved to separate step for incremental refresh
            # Use scrape_with_profiles() if you need full data in one call
            return contractors

        except TimeoutException:
            logger.error("Timeout waiting for page elements")
            # Save screenshot for debugging
            self.driver.save_screenshot("/app/data/debug_screenshot.png")
            raise
        except Exception as e:
            logger.error(f"Error during scraping: {str(e)}")
            self.driver.save_screenshot("/app/data/error_screenshot.png")
            raise


    def _extract_contractor_data(self, element, idx):
        """Extract data from a contractor card element using correct selectors"""
        data = {
            "id": idx + 1,
            "name": None,
            "rating": None,
            "reviews_count": None,
            "city": None,
            "distance": None,
            "phone": None,
            "profile_url": None,
            "description": None,
            "certifications": []
        }

        # Extract company name from h2.certification-card__heading > a.link--inline > span
        try:
            name_elem = element.find_element(By.CSS_SELECTOR, "h2.certification-card__heading a.link--inline span")
            data["name"] = name_elem.text.strip()
        except NoSuchElementException:
            logger.warning(f"Could not find name for contractor {idx + 1}")

        # Extract rating from .rating-stars__average (e.g., "5.0")
        try:
            rating_elem = element.find_element(By.CSS_SELECTOR, ".rating-stars__average")
            rating_text = rating_elem.text.strip()
            data["rating"] = float(rating_text) if rating_text else None
        except (NoSuchElementException, ValueError) as e:
            logger.debug(f"Could not extract rating for contractor {idx + 1}: {e}")

        # Extract review count from .rating-stars__total (e.g., "(437)")
        try:
            reviews_elem = element.find_element(By.CSS_SELECTOR, ".rating-stars__total")
            reviews_text = reviews_elem.text.strip()
            # Extract number from parentheses
            match = re.search(r'\((\d+)\)', reviews_text)
            if match:
                data["reviews_count"] = int(match.group(1))
        except (NoSuchElementException, ValueError) as e:
            logger.debug(f"Could not extract reviews count for contractor {idx + 1}: {e}")

        # Extract location from p.certification-card__city (e.g., "Wayne, NJ - 17.3 mi")
        try:
            location_elem = element.find_element(By.CSS_SELECTOR, "p.certification-card__city")
            location_text = location_elem.text.strip()
            # Split by " - " to separate city/state from distance
            if " - " in location_text:
                city_part, distance_part = location_text.split(" - ", 1)
                data["city"] = city_part.strip()
                # Extract numeric distance
                distance_match = re.search(r'([\d.]+)\s*mi', distance_part)
                if distance_match:
                    data["distance"] = float(distance_match.group(1))
            else:
                data["city"] = location_text
        except (NoSuchElementException, ValueError) as e:
            logger.debug(f"Could not extract location for contractor {idx + 1}: {e}")

        # Extract phone from a.certification-card__phone with href="tel:..."
        try:
            phone_elem = element.find_element(By.CSS_SELECTOR, "a.certification-card__phone")
            phone_href = phone_elem.get_attribute("href")
            if phone_href and phone_href.startswith("tel:"):
                data["phone"] = phone_href.replace("tel:", "").strip()
        except NoSuchElementException:
            logger.debug(f"Could not find phone for contractor {idx + 1}")

        # Extract profile URL from heading link
        try:
            profile_link = element.find_element(By.CSS_SELECTOR, "h2.certification-card__heading a.link--inline")
            profile_href = profile_link.get_attribute("href")
            if profile_href:
                # Make absolute URL if needed
                if profile_href.startswith("/"):
                    data["profile_url"] = f"https://www.gaf.com{profile_href}"
                else:
                    data["profile_url"] = profile_href
        except NoSuchElementException:
            logger.debug(f"Could not find profile URL for contractor {idx + 1}")

        return data

    def scrape_with_profiles(self, zipcode, distance=25, max_results=None):
        """
        Scrape contractors with full profile data (listing + profiles)

        This is the original behavior - scrapes listing AND visits each profile.
        For incremental refresh, use scrape_contractors() + selective profile visits.

        Args:
            zipcode: ZIP code to search
            distance: Distance radius in miles
            max_results: Maximum number of results

        Returns:
            List of contractor dictionaries with descriptions and certifications
        """
        # Get listing data
        contractors = self.scrape_contractors(zipcode, distance, max_results)

        # Enrich with profile data
        logger.info("Enriching with profile descriptions and certifications...")
        for contractor in contractors:
            if contractor.get('profile_url'):
                try:
                    description, certifications = self._scrape_profile_description(contractor['profile_url'])
                    contractor['description'] = description
                    contractor['certifications'] = certifications
                    logger.info(f"Fetched description for: {contractor.get('name')}")
                except Exception as e:
                    logger.error(f"Error fetching description for {contractor.get('name')}: {str(e)}")
                    continue

        return contractors

    def _scrape_profile_description(self, profile_url):
        """Visit contractor profile page and extract description"""
        try:
            logger.info(f"Visiting profile: {profile_url}")
            self.driver.get(profile_url)

            # Wait for profile content to load
            time.sleep(3)

            description = None
            certifications = []

            # Try to find description/about section with various selectors
            description_selectors = [
                ".contractor-profile__about",
                ".about-section",
                "[class*='about']",
                "[class*='description']",
                ".rtf p",
                "section p"
            ]

            for selector in description_selectors:
                try:
                    desc_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    desc_text = desc_elem.text.strip()
                    if len(desc_text) > 30:  # Only if substantial
                        description = desc_text
                        break
                except NoSuchElementException:
                    continue

            # Extract certifications
            try:
                cert_elements = self.driver.find_elements(By.CSS_SELECTOR, ".certification-badge, [class*='certification'], [class*='badge']")
                for cert_elem in cert_elements[:5]:  # Limit to first 5
                    cert_text = cert_elem.text.strip()
                    if cert_text and len(cert_text) < 100:
                        certifications.append(cert_text)
            except Exception as e:
                logger.debug(f"Could not extract certifications: {e}")

            return description, certifications

        except Exception as e:
            logger.error(f"Error scraping profile {profile_url}: {str(e)}")
            return None, []

    def save_to_json(self, contractors, output_path):
        """Save scraped data to JSON file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(contractors, f, indent=2, ensure_ascii=False)
        logger.info(f"Data saved to {output_path}")

    def save_to_database(self, contractors, zipcode, distance):
        """
        Save scraped data to PostgreSQL database and track scrape run

        Args:
            contractors: List of contractor dictionaries
            zipcode: ZIP code that was scraped
            distance: Search radius in miles

        Returns:
            Dictionary with save statistics
        """
        db_manager = DatabaseManager()

        # Record scrape run start
        scrape_run_id = None
        with db_manager.get_session() as session:
            scrape_run = ScrapeRun(
                zipcode=zipcode,
                distance=distance,
                contractors_found=len(contractors),
                started_at=datetime.utcnow(),
                status='running'
            )
            session.add(scrape_run)
            session.commit()
            scrape_run_id = scrape_run.id

        try:
            # Save contractors to database
            stats = db_manager.save_contractors_batch(contractors)

            # Generate AI insights for contractors without insights
            logger.info("Generating AI insights for contractors...")
            insights_generator = InsightsGenerator()
            insights_count = 0

            for contractor_data in contractors:
                try:
                    profile_url = contractor_data.get('profile_url')
                    if not profile_url:
                        continue

                    with db_manager.get_session() as session:
                        contractor = session.query(Contractor).filter(
                            Contractor.profile_url == profile_url
                        ).first()

                        if contractor and not contractor.ai_insights:
                            insights = insights_generator.generate_insights(contractor_data)
                            if insights:
                                contractor.ai_insights = [insights]
                                session.commit()
                                insights_count += 1
                                logger.info(f"Generated insights for: {contractor_data.get('name')}")
                except Exception as e:
                    logger.error(f"Error generating insights for {contractor_data.get('name')}: {e}")

            logger.info(f"Generated insights for {insights_count} contractors")

            # Update scrape run with completion stats
            with db_manager.get_session() as session:
                scrape_run = session.query(ScrapeRun).filter(ScrapeRun.id == scrape_run_id).first()
                if scrape_run:
                    scrape_run.contractors_new = stats['new']
                    scrape_run.contractors_updated = stats['updated']
                    scrape_run.completed_at = datetime.utcnow()
                    scrape_run.status = 'completed'

            logger.info(f"Database save complete: {stats}")
            return stats

        except Exception as e:
            # Update scrape run with error
            with db_manager.get_session() as session:
                scrape_run = session.query(ScrapeRun).filter(ScrapeRun.id == scrape_run_id).first()
                if scrape_run:
                    scrape_run.completed_at = datetime.utcnow()
                    scrape_run.status = 'failed'
                    scrape_run.error_message = str(e)
            logger.error(f"Database save failed: {str(e)}")
            raise


def main():
    """Main execution function"""
    scraper = GAFContractorScraper(headless=True)  # Headless for Docker

    try:
        scraper.start()

        # Configuration
        zipcode = "10013"
        distance = 25
        max_results = 10  # Limit to 10 for testing (change to None for full scrape)

        # Scrape contractors with full profiles
        contractors = scraper.scrape_with_profiles(
            zipcode=zipcode,
            distance=distance,
            max_results=max_results
        )

        # Save to database
        stats = scraper.save_to_database(contractors, zipcode, distance)

        print(f"\n{'='*60}")
        print(f"Successfully scraped {len(contractors)} contractors")
        print(f"{'='*60}")
        print(f"Database save statistics:")
        print(f"  - New contractors: {stats['new']}")
        print(f"  - Updated contractors: {stats['updated']}")
        print(f"  - Unchanged contractors: {stats['unchanged']}")
        print(f"{'='*60}")

        # Also save to JSON for backup/debugging
        output_path = "/app/data/contractors_raw.json"
        scraper.save_to_json(contractors, output_path)
        print(f"Backup JSON saved to {output_path}")

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
