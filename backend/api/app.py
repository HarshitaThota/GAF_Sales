"""
Flask API for GAF Sales Intelligence Dashboard
"""
import sys
sys.path.insert(0, '/app')

from flask import Flask, jsonify, request
from flask_cors import CORS
from backend.db.connection import DatabaseManager
from backend.db.models import Contractor, ScrapeRun
from sqlalchemy import desc, or_

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

db_manager = DatabaseManager()


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'GAF Sales Intelligence API'})


@app.route('/api/contractors', methods=['GET'])
def get_contractors():
    """
    Get all contractors with optional filtering

    Query params:
    - location: Filter by location (city/state)
    - min_rating: Minimum rating (0-5)
    - min_reviews: Minimum review count
    - limit: Max results (default 100)
    - offset: Pagination offset (default 0)
    - search: Search in name or location
    - sort_by: Sort field (rating, reviews_count, name)
    - sort_order: asc or desc
    """
    try:
        # Get query parameters
        location = request.args.get('location')
        min_rating = request.args.get('min_rating', type=float)
        min_reviews = request.args.get('min_reviews', type=int)
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        search = request.args.get('search')
        sort_by = request.args.get('sort_by', 'rating')
        sort_order = request.args.get('sort_order', 'desc')

        with db_manager.get_session() as session:
            # Build query
            query = session.query(Contractor)

            # Apply filters
            if location:
                query = query.filter(Contractor.location.ilike(f'%{location}%'))

            if min_rating:
                query = query.filter(Contractor.rating >= min_rating)

            if min_reviews:
                query = query.filter(Contractor.reviews_count >= min_reviews)

            if search:
                query = query.filter(
                    or_(
                        Contractor.name.ilike(f'%{search}%'),
                        Contractor.location.ilike(f'%{search}%')
                    )
                )

            # Apply sorting
            sort_column = getattr(Contractor, sort_by, Contractor.rating)
            if sort_order == 'desc':
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(sort_column)

            # Get total count before pagination
            total = query.count()

            # Apply pagination
            contractors = query.limit(limit).offset(offset).all()

            return jsonify({
                'contractors': [c.to_dict() for c in contractors],
                'total': total,
                'limit': limit,
                'offset': offset
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/contractors/<int:contractor_id>', methods=['GET'])
def get_contractor(contractor_id):
    """Get single contractor by ID"""
    try:
        with db_manager.get_session() as session:
            contractor = session.query(Contractor).filter(Contractor.id == contractor_id).first()

            if not contractor:
                return jsonify({'error': 'Contractor not found'}), 404

            return jsonify(contractor.to_dict())

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get dashboard statistics"""
    try:
        with db_manager.get_session() as session:
            total_contractors = session.query(Contractor).count()

            # Average rating
            avg_rating = session.query(Contractor).filter(
                Contractor.rating.isnot(None)
            ).with_entities(Contractor.rating).all()
            avg_rating_value = sum([r[0] for r in avg_rating]) / len(avg_rating) if avg_rating else 0

            # Top rated contractors (5 stars with most reviews)
            top_contractors = session.query(Contractor).filter(
                Contractor.rating == 5.0
            ).order_by(desc(Contractor.reviews_count)).limit(10).all()

            # Recent scrape runs
            recent_runs = session.query(ScrapeRun).order_by(
                desc(ScrapeRun.started_at)
            ).limit(5).all()

            return jsonify({
                'total_contractors': total_contractors,
                'average_rating': round(avg_rating_value, 2),
                'top_contractors': [c.to_dict() for c in top_contractors],
                'recent_scrape_runs': [run.to_dict() for run in recent_runs]
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/locations', methods=['GET'])
def get_locations():
    """Get unique locations for filtering"""
    try:
        with db_manager.get_session() as session:
            locations = session.query(Contractor.location).distinct().filter(
                Contractor.location.isnot(None)
            ).all()

            return jsonify({
                'locations': sorted([loc[0] for loc in locations if loc[0]])
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
