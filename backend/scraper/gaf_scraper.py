import json
import time
import tempfile
import shutil
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

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
            while page_num <= max_pages:
                logger.info(f"Scraping page {page_num}...")

                # Wait a bit for dynamic content to load
                time.sleep(3)

                # Find all contractor elements on current page
                contractor_elements = self.driver.find_elements(By.CSS_SELECTOR, "article.certification-card")
                logger.info(f"Found {len(contractor_elements)} contractor cards on page {page_num}")

                for idx, element in enumerate(contractor_elements):
                    if max_results and len(contractors) >= max_results:
                        logger.info(f"Reached max_results limit of {max_results}")
                        return contractors

                    try:
                        contractor_data = self._extract_contractor_data(element, len(contractors))
                        contractor_name = contractor_data.get('name')

                        # Skip duplicates
                        if contractor_name and contractor_name in seen_contractors:
                            logger.warning(f"Duplicate contractor found: {contractor_name}, stopping pagination")
                            return contractors

                        if contractor_name:
                            seen_contractors.add(contractor_name)

                        # Visit profile to get description
                        if contractor_data.get('profile_url'):
                            current_url = self.driver.current_url  # Save current page
                            description, certifications = self._scrape_profile_description(contractor_data['profile_url'])
                            contractor_data['description'] = description
                            contractor_data['certifications'] = certifications

                            # Navigate back to listing page
                            self.driver.get(current_url)
                            time.sleep(2)
                            # Re-find contractor cards after navigation
                            WebDriverWait(self.driver, 10).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "article.certification-card"))
                            )

                        contractors.append(contractor_data)
                        logger.info(f"Scraped contractor {len(contractors)}: {contractor_name or 'Unknown'}")
                    except Exception as e:
                        logger.error(f"Error extracting contractor {len(contractors) + 1}: {str(e)}")
                        continue

                # Try to find and click next page button
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


def main():
    """Main execution function"""
    scraper = GAFContractorScraper(headless=True)  # Headless for Docker

    try:
        scraper.start()

        # Scrape contractors for ZIP code 10013
        # Set max_results=5 for testing with descriptions, None for all
        contractors = scraper.scrape_contractors(
            zipcode="10013",
            distance=25,
            max_results=5  # Limit for testing with profile scraping
        )

        # Save results to Docker volume path
        output_path = "/app/data/contractors_raw.json"
        scraper.save_to_json(contractors, output_path)

        print(f"\nSuccessfully scraped {len(contractors)} contractors")
        print(f"Data saved to {output_path}")

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
