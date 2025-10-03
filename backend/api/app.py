"""
Flask Web App for GAF Sales Intelligence Dashboard
"""
import sys
sys.path.insert(0, '/app')

from flask import Flask, render_template, request, jsonify
from backend.db.connection import DatabaseManager
from backend.db.models import Contractor, ScrapeRun
from backend.ai.insights_generator import InsightsGenerator
from sqlalchemy import desc, or_, func
import os
from openai import OpenAI

app = Flask(__name__, template_folder='templates')

db_manager = DatabaseManager()
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


@app.route('/')
def index():
    """Main dashboard page"""
    try:
        # Get query parameters for filtering
        search = request.args.get('search', '')
        location = request.args.get('location', '')
        min_rating = request.args.get('min_rating', type=float)
        sort_by = request.args.get('sort_by', 'lead_quality')  # Default to best leads first
        page = request.args.get('page', 1, type=int)
        per_page = 20

        with db_manager.get_session() as session:
            # Get stats
            total_contractors = session.query(Contractor).count()
            avg_rating = session.query(Contractor).filter(
                Contractor.rating.isnot(None)
            ).with_entities(Contractor.rating).all()
            avg_rating_value = sum([r[0] for r in avg_rating]) / len(avg_rating) if avg_rating else 0

            # Get unique locations for filter dropdown
            locations = session.query(Contractor.location).distinct().filter(
                Contractor.location.isnot(None)
            ).all()
            all_locations = sorted([loc[0] for loc in locations if loc[0]])

            # Build contractors query
            query = session.query(Contractor)

            # Apply filters
            if search:
                query = query.filter(
                    or_(
                        Contractor.name.ilike(f'%{search}%'),
                        Contractor.location.ilike(f'%{search}%')
                    )
                )
            if location:
                query = query.filter(Contractor.location.ilike(f'%{location}%'))
            if min_rating:
                query = query.filter(Contractor.rating >= min_rating)

            # Apply sorting
            if sort_by == 'lead_quality':
                # Sort by lead quality: rating * review_count (best leads first)
                # Use COALESCE to treat NULL as 0, pushing them to the bottom
                lead_score = func.coalesce(Contractor.rating, 0) * func.coalesce(Contractor.reviews_count, 0)
                query = query.order_by(desc(lead_score))
            elif sort_by in ['rating', 'reviews_count']:
                # For rating and reviews, put NULLs last (highest to lowest, NULLs at bottom)
                sort_column = getattr(Contractor, sort_by)
                query = query.order_by(desc(func.coalesce(sort_column, 0)))
            else:
                sort_column = getattr(Contractor, sort_by, Contractor.rating)
                query = query.order_by(desc(sort_column))

            # Pagination
            total = query.count()
            offset = (page - 1) * per_page
            contractors = query.limit(per_page).offset(offset).all()

            # Calculate pagination info
            total_pages = (total + per_page - 1) // per_page

            return render_template(
                'index.html',
                contractors=contractors,
                total_contractors=total_contractors,
                avg_rating=round(avg_rating_value, 2),
                all_locations=all_locations,
                search=search,
                location=location,
                min_rating=min_rating or '',
                sort_by=sort_by,
                page=page,
                total_pages=total_pages,
                total=total
            )

    except Exception as e:
        return f"Error: {str(e)}", 500


@app.route('/contractor/<int:contractor_id>')
def contractor_detail(contractor_id):
    """Contractor detail page"""
    try:
        with db_manager.get_session() as session:
            contractor = session.query(Contractor).filter(Contractor.id == contractor_id).first()

            if not contractor:
                return "Contractor not found", 404

            return render_template('contractor_detail.html', contractor=contractor)

    except Exception as e:
        return f"Error: {str(e)}", 500


@app.route('/evaluation')
def evaluation_dashboard():
    """LLM Evaluation Dashboard"""
    try:
        with db_manager.get_session() as session:
            # Get all contractors with evaluations
            contractors = session.query(Contractor).filter(
                Contractor.eval_overall.isnot(None)
            ).order_by(desc(Contractor.eval_overall)).all()

            # Calculate aggregate stats
            if contractors:
                avg_accuracy = sum(c.eval_accuracy for c in contractors) / len(contractors)
                avg_actionability = sum(c.eval_actionability for c in contractors) / len(contractors)
                avg_personalization = sum(c.eval_personalization for c in contractors) / len(contractors)
                avg_conciseness = sum(c.eval_conciseness for c in contractors) / len(contractors)
                avg_overall = sum(c.eval_overall for c in contractors) / len(contractors)
            else:
                avg_accuracy = avg_actionability = avg_personalization = avg_conciseness = avg_overall = 0

            # Get total counts
            total_insights = session.query(Contractor).filter(
                Contractor.ai_insights.isnot(None)
            ).count()

            evaluated = len(contractors)
            pending = total_insights - evaluated

            return render_template(
                'evaluation.html',
                contractors=contractors,
                avg_accuracy=round(avg_accuracy, 2),
                avg_actionability=round(avg_actionability, 2),
                avg_personalization=round(avg_personalization, 2),
                avg_conciseness=round(avg_conciseness, 2),
                avg_overall=round(avg_overall, 2),
                total_insights=total_insights,
                evaluated=evaluated,
                pending=pending
            )

    except Exception as e:
        return f"Error: {str(e)}", 500


@app.route('/api/generate-email/<int:contractor_id>', methods=['POST'])
def generate_email(contractor_id):
    """Generate sales email for contractor using GPT"""
    try:
        with db_manager.get_session() as session:
            contractor = session.query(Contractor).filter(Contractor.id == contractor_id).first()

            if not contractor:
                return jsonify({'error': 'Contractor not found'}), 404

            # Build prompt for GPT
            prompt = f"""Generate a personalized B2B sales email from a roofing materials distributor to this contractor.

Contractor Info:
- Name: {contractor.name}
- Location: {contractor.location}
- Rating: {contractor.rating} stars ({contractor.reviews_count} reviews)
- Certifications: {', '.join(contractor.certifications) if contractor.certifications else 'None'}
- Description: {contractor.description[:500] if contractor.description else 'N/A'}

Sales Person Placeholders (use exactly as shown):
- {{{{sales_person_name}}}}
- {{{{sales_company}}}}
- {{{{title}}}}
- {{{{mobile}}}} (format as xxx-xxx-xxxx)
- {{{{email}}}}
- {{{{website}}}}

Requirements:
1. Subject line: "[Contractor Name] × {{{{sales_company}}}} — [brief value prop relevant to their work]"
2. Personalize based on their rating, certifications, and specializations
3. Value proposition: premium materials, reliable delivery, competitive pricing
4. Mention specific materials they likely use (asphalt shingles, metal, flat roof systems, etc.)
5. Low-pressure CTA: ask for material list or 10-15 min call
6. Professional but friendly tone
7. Keep under 200 words
8. Use placeholder variables exactly as shown above (with double curly braces)

Output ONLY the email (subject + body), no additional commentary."""

            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a B2B sales email writer for roofing material distributors. Write personalized, professional emails that are concise and action-oriented."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=400
            )

            email_content = response.choices[0].message.content.strip()
            return jsonify({'email': email_content})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
