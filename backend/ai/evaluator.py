"""
LLM Evaluation Framework - GPT-as-Judge for Insight Quality Assessment
"""
import sys
sys.path.insert(0, '/app')

import os
import logging
import json
from datetime import datetime
from openai import OpenAI
from backend.db.connection import DatabaseManager
from backend.db.models import Contractor

logger = logging.getLogger(__name__)


class InsightEvaluator:
    """Evaluates AI-generated insights using GPT-4 as a judge"""

    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        self.client = OpenAI(api_key=api_key)
        self.db_manager = DatabaseManager()

    def evaluate_insight(self, contractor_data: dict, insight: str) -> dict:
        """
        Evaluate a single insight using GPT-4 as judge

        Args:
            contractor_data: Dictionary with contractor info
            insight: The generated insight text

        Returns:
            Dictionary with scores and feedback
        """
        prompt = self._build_evaluation_prompt(contractor_data, insight)

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Use GPT-4 for evaluation
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert evaluator of B2B sales intelligence content.
Your job is to assess the quality of AI-generated sales insights for roofing material distributors.
You must return ONLY valid JSON with numeric scores and brief feedback."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for consistent evaluation
                max_tokens=400,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content.strip())

            # Calculate weighted overall score
            # Accuracy: 40%, Actionability: 30%, Personalization: 20%, Conciseness: 10%
            overall = (
                result['accuracy'] * 0.40 +
                result['actionability'] * 0.30 +
                result['personalization'] * 0.20 +
                result['conciseness'] * 0.10
            )

            return {
                'accuracy': result['accuracy'],
                'actionability': result['actionability'],
                'personalization': result['personalization'],
                'conciseness': result['conciseness'],
                'overall': round(overall, 2),
                'feedback': result['feedback']
            }

        except Exception as e:
            logger.error(f"Error evaluating insight: {e}")
            return None

    def _build_evaluation_prompt(self, contractor_data: dict, insight: str) -> str:
        """Build evaluation prompt for GPT-4"""
        return f"""Evaluate this AI-generated sales insight on a scale of 1-5 for each dimension.

CONTRACTOR DATA:
- Name: {contractor_data.get('name')}
- Location: {contractor_data.get('location')}
- Rating: {contractor_data.get('rating')} stars ({contractor_data.get('reviews_count')} reviews)
- Certifications: {', '.join(contractor_data.get('certifications', [])) if contractor_data.get('certifications') else 'None'}
- Description: {contractor_data.get('description', 'N/A')[:300]}

GENERATED INSIGHT:
{insight}

EVALUATION CRITERIA:

1. **Accuracy & Relevance (1-5)**
   - Does it use correct contractor data (name, rating, certifications)?
   - Is all information factually accurate?
   - Is it relevant to B2B roofing materials sales?

2. **Actionability (1-5)**
   - Does it provide clear next steps for sales team?
   - Does it identify specific materials/services the contractor might need?
   - Does it suggest concrete engagement approaches?

3. **Personalization (1-5)**
   - Is it tailored to this contractor's specialization?
   - Does it reference unique strengths (rating, experience, certifications)?
   - Does it avoid generic template language?

4. **Conciseness (1-5)**
   - Is it appropriately brief (under 200 words)?
   - Does it avoid fluff and repetition?
   - Is it scannable for busy salespeople?

Return your evaluation as JSON with this exact structure:
{{
    "accuracy": <score 1-5>,
    "actionability": <score 1-5>,
    "personalization": <score 1-5>,
    "conciseness": <score 1-5>,
    "feedback": "<1-2 sentence summary of strengths and weaknesses>"
}}"""

    def evaluate_all_insights(self, limit: int = None):
        """
        Evaluate all insights that haven't been evaluated yet

        Args:
            limit: Maximum number to evaluate (None for all)
        """
        with self.db_manager.get_session() as session:
            # Get contractors with insights but no evaluation
            query = session.query(Contractor).filter(
                Contractor.ai_insights.isnot(None),
                Contractor.eval_overall.is_(None)
            )

            if limit:
                query = query.limit(limit)

            contractors = query.all()
            total = len(contractors)

            logger.info(f"Found {total} insights to evaluate")

            for idx, contractor in enumerate(contractors, 1):
                try:
                    logger.info(f"Evaluating {idx}/{total}: {contractor.name}")

                    # Get first insight (we only have one per contractor)
                    insight = contractor.ai_insights[0] if contractor.ai_insights else None
                    if not insight:
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

                    # Evaluate
                    scores = self.evaluate_insight(contractor_data, insight)

                    if scores:
                        # Save scores to database
                        contractor.eval_accuracy = scores['accuracy']
                        contractor.eval_actionability = scores['actionability']
                        contractor.eval_personalization = scores['personalization']
                        contractor.eval_conciseness = scores['conciseness']
                        contractor.eval_overall = scores['overall']
                        contractor.eval_feedback = scores['feedback']
                        contractor.eval_timestamp = datetime.utcnow()
                        session.commit()

                        logger.info(f"✓ Evaluated {contractor.name}: Overall {scores['overall']}/5")
                    else:
                        logger.warning(f"✗ Failed to evaluate {contractor.name}")

                except Exception as e:
                    logger.error(f"Error evaluating {contractor.name}: {e}")
                    session.rollback()
                    continue

            logger.info(f"Completed evaluation of {total} insights")


def main():
    """Main execution"""
    evaluator = InsightEvaluator()

    # Evaluate all insights
    # Use limit=5 for testing, None for all
    evaluator.evaluate_all_insights(limit=None)


if __name__ == "__main__":
    main()
