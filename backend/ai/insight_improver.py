"""
Insight Improvement System - Regenerates low-quality insights with targeted fixes
"""
import sys
sys.path.insert(0, '/app')

import os
import logging
from datetime import datetime
from openai import OpenAI
from backend.db.connection import DatabaseManager
from backend.db.models import Contractor
from backend.ai.evaluator import InsightEvaluator

logger = logging.getLogger(__name__)


class InsightImprover:
    """Improves low-quality insights based on evaluation scores"""

    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        self.client = OpenAI(api_key=api_key)
        self.db_manager = DatabaseManager()
        self.evaluator = InsightEvaluator()

    def identify_weaknesses(self, scores: dict) -> str:
        """
        Identify the weakest areas based on scores

        Args:
            scores: Dict with accuracy, actionability, personalization, conciseness scores

        Returns:
            Targeted feedback string for improvement
        """
        issues = []

        if scores['accuracy'] < 3.5:
            issues.append("be more accurate and fact-based, referencing specific contractor data")

        if scores['actionability'] < 3.5:
            issues.append("provide clearer action items and specific materials/services the contractor might need")

        if scores['personalization'] < 3.5:
            issues.append("make it more personalized to this contractor's unique strengths and specializations")

        if scores['conciseness'] < 3.5:
            issues.append("be more concise and avoid repetitive language")

        if not issues:
            # Find the lowest score
            min_score = min(scores['accuracy'], scores['actionability'],
                          scores['personalization'], scores['conciseness'])

            if min_score == scores['accuracy']:
                issues.append("improve factual accuracy")
            elif min_score == scores['actionability']:
                issues.append("add more actionable insights")
            elif min_score == scores['personalization']:
                issues.append("increase personalization")
            else:
                issues.append("improve conciseness")

        return ", ".join(issues)

    def regenerate_insight(self, contractor_data: dict, old_insight: str, feedback: str, weaknesses: str) -> str:
        """
        Regenerate insight with targeted improvements

        Args:
            contractor_data: Contractor info
            old_insight: Previous low-quality insight
            feedback: GPT-4 evaluation feedback
            weaknesses: Identified weaknesses

        Returns:
            Improved insight
        """
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

        prompt = f"""The previous sales insight for this contractor scored poorly. Generate an IMPROVED version.

CONTRACTOR INFO:
- Name: {name}
- Location: {location}
- Rating: {rating} stars ({reviews_count} reviews)
- Certifications: {certs_str}
- Description: {description if description else "No description provided"}

PREVIOUS INSIGHT (LOW QUALITY):
{old_insight}

EVALUATION FEEDBACK:
{feedback}

IMPROVEMENT AREAS:
You need to {weaknesses}.

REQUIREMENTS:
1. Write 2-3 sentences focused on B2B sales for roofing material distributors
2. Reference specific contractor strengths (rating, certifications, experience)
3. Identify what materials they likely need (asphalt shingles, metal, flat roof systems, etc.)
4. Suggest concrete next steps for sales engagement
5. Be personalized to THIS contractor - avoid generic language
6. Keep it professional, concise, and scannable

Generate the IMPROVED insight now:"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a B2B sales intelligence analyst. Generate concise, actionable, personalized insights for roofing material distributors."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=250
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error regenerating insight: {e}")
            return None

    def improve_low_quality_insights(self, threshold: float = 3.8, max_iterations: int = 2):
        """
        Find and improve insights with overall score below threshold

        Args:
            threshold: Minimum acceptable overall score (default 3.8)
            max_iterations: Maximum regeneration attempts per insight
        """
        with self.db_manager.get_session() as session:
            # Get contractors with low evaluation scores
            low_quality = session.query(Contractor).filter(
                Contractor.eval_overall < threshold,
                Contractor.eval_overall.isnot(None)
            ).all()

            total = len(low_quality)
            logger.info(f"Found {total} insights with score < {threshold}")

            improved_count = 0

            for contractor in low_quality:
                try:
                    logger.info(f"Improving insight for {contractor.name} (score: {contractor.eval_overall})")

                    # Get current scores
                    current_scores = {
                        'accuracy': contractor.eval_accuracy,
                        'actionability': contractor.eval_actionability,
                        'personalization': contractor.eval_personalization,
                        'conciseness': contractor.eval_conciseness
                    }

                    # Identify weaknesses
                    weaknesses = self.identify_weaknesses(current_scores)
                    old_insight = contractor.ai_insights[0] if contractor.ai_insights else None
                    old_feedback = contractor.eval_feedback or "Score too low"

                    if not old_insight:
                        logger.warning(f"No insight found for {contractor.name}")
                        continue

                    # Prepare contractor data
                    contractor_data = {
                        'name': contractor.name,
                        'rating': float(contractor.rating) if contractor.rating else None,
                        'reviews_count': contractor.reviews_count,
                        'description': contractor.description,
                        'certifications': contractor.certifications,
                        'location': contractor.location
                    }

                    # Try to improve (with max iterations)
                    for iteration in range(1, max_iterations + 1):
                        logger.info(f"  Attempt {iteration}/{max_iterations}")

                        # Regenerate with targeted improvements
                        new_insight = self.regenerate_insight(
                            contractor_data,
                            old_insight,
                            old_feedback,
                            weaknesses
                        )

                        if not new_insight:
                            logger.warning(f"  Failed to regenerate")
                            break

                        # Evaluate the new insight
                        new_scores = self.evaluator.evaluate_insight(contractor_data, new_insight)

                        if not new_scores:
                            logger.warning(f"  Failed to evaluate new insight")
                            break

                        logger.info(f"  New score: {new_scores['overall']} (was {contractor.eval_overall})")

                        # If improved above threshold, save and break
                        if new_scores['overall'] >= threshold:
                            contractor.ai_insights = [new_insight]
                            contractor.eval_accuracy = new_scores['accuracy']
                            contractor.eval_actionability = new_scores['actionability']
                            contractor.eval_personalization = new_scores['personalization']
                            contractor.eval_conciseness = new_scores['conciseness']
                            contractor.eval_overall = new_scores['overall']
                            contractor.eval_feedback = new_scores['feedback']
                            contractor.eval_timestamp = datetime.utcnow()
                            session.commit()

                            logger.info(f"  ✓ Improved! {contractor.eval_overall} → {new_scores['overall']}")
                            improved_count += 1
                            break
                        else:
                            # Prepare for next iteration with new feedback
                            old_insight = new_insight
                            old_feedback = new_scores['feedback']
                            weaknesses = self.identify_weaknesses(new_scores)

                            if iteration == max_iterations:
                                logger.warning(f"  ✗ Could not improve above {threshold} after {max_iterations} attempts")

                except Exception as e:
                    logger.error(f"Error improving {contractor.name}: {e}")
                    session.rollback()
                    continue

            logger.info(f"Improvement complete: {improved_count}/{total} insights improved to >={threshold}")


def main():
    """Main execution"""
    improver = InsightImprover()

    # Improve insights below 3.8
    improver.improve_low_quality_insights(threshold=3.8, max_iterations=2)


if __name__ == "__main__":
    main()
