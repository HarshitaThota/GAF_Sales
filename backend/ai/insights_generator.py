"""
AI Insights Generator for GAF Contractors
Generates sales insights using OpenAI GPT
"""
import sys
sys.path.insert(0, '/app')

import os
import logging
from openai import OpenAI
from dotenv import load_dotenv
from backend.db.connection import DatabaseManager
from backend.db.models import Contractor

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InsightsGenerator:
    """Generate AI insights for contractors using OpenAI GPT"""

    def __init__(self):
        """Initialize OpenAI client"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        self.client = OpenAI(api_key=api_key)
        self.db_manager = DatabaseManager()

    def generate_insights(self, contractor_data: dict) -> str:
        """
        Generate AI insights for a single contractor

        Args:
            contractor_data: Dictionary with contractor info (name, rating, description, etc.)

        Returns:
            Generated insights as a string
        """
        # Build the prompt
        prompt = self._build_prompt(contractor_data)

        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a B2B sales intelligence analyst helping roofing material distributors identify promising contractor leads. Generate concise, actionable insights based on contractor data."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=200
            )

            insights = response.choices[0].message.content.strip()
            return insights

        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return None

    def _build_prompt(self, contractor_data: dict) -> str:
        """Build the GPT prompt from contractor data"""
        name = contractor_data.get('name', 'Unknown')
        rating = contractor_data.get('rating', 'N/A')
        reviews_count = contractor_data.get('reviews_count', 0)
        description = contractor_data.get('description', '')
        certifications = contractor_data.get('certifications', [])
        location = contractor_data.get('location', 'Unknown')

        # Clean description
        if description and len(description) > 500:
            description = description[:500] + "..."

        # Build certifications string
        certs_str = ", ".join(certifications) if certifications else "None listed"

        prompt = f"""Generate a brief sales insight (2-3 sentences) for this roofing contractor:

            Contractor: {name}
            Location: {location}
            Rating: {rating} stars ({reviews_count} reviews)
            Certifications: {certs_str}
            Description: {description if description else "No description provided"}

            Focus on:
            - Their reputation and market standing
            - Quality indicators (rating, certifications, experience)
            - Potential as a B2B customer for roofing materials
            - Any unique strengths or specializations

            Keep it professional and concise."""

        return prompt

    def generate_insights_for_all(self, limit: int = None):
        """
        Generate insights for all contractors without insights

        Args:
            limit: Maximum number to process (None for all)
        """
        with self.db_manager.get_session() as session:
            # Get contractors without insights
            query = session.query(Contractor).filter(
                Contractor.ai_insights == None
            )

            if limit:
                query = query.limit(limit)

            contractors = query.all()

            total = len(contractors)
            logger.info(f"Found {total} contractors without insights")

            for idx, contractor in enumerate(contractors, 1):
                try:
                    logger.info(f"Processing {idx}/{total}: {contractor.name}")

                    # Prepare contractor data
                    contractor_data = {
                        'name': contractor.name,
                        'rating': float(contractor.rating) if contractor.rating else None,
                        'reviews_count': contractor.reviews_count,
                        'description': contractor.description,
                        'certifications': contractor.certifications,
                        'location': contractor.location
                    }

                    # Generate insights
                    insights = self.generate_insights(contractor_data)

                    if insights:
                        # Save as JSON array with one insight
                        contractor.ai_insights = [insights]
                        session.commit()
                        logger.info(f"✓ Generated insights for {contractor.name}")
                    else:
                        logger.warning(f"✗ Failed to generate insights for {contractor.name}")

                except Exception as e:
                    logger.error(f"Error processing {contractor.name}: {e}")
                    session.rollback()
                    continue

            logger.info(f"Completed insights generation for {total} contractors")


def main():
    """Main execution"""
    generator = InsightsGenerator()

    # Generate insights for all contractors without them
    # Use limit=10 for testing, None for all
    generator.generate_insights_for_all(limit=None)


if __name__ == "__main__":
    main()
