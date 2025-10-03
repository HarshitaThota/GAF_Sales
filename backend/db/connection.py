"""
Database connection and session management
"""
import os
import hashlib
import json
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
from typing import Optional, Dict, List

from backend.db.models import Base, Contractor, ScrapeRun

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and operations"""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager

        Args:
            database_url: PostgreSQL connection string. If None, reads from DATABASE_URL env var
        """
        self.database_url = database_url or os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL not provided and not found in environment variables")

        # Create engine
        self.engine = create_engine(
            self.database_url,
            poolclass=NullPool,  # Don't maintain connection pool for scraper
            echo=False  # Set to True for SQL query logging
        )

        # Create session factory
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        logger.info("Database connection established")

    @contextmanager
    def get_session(self) -> Session:
        """
        Context manager for database sessions

        Usage:
            with db_manager.get_session() as session:
                session.query(Contractor).all()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        finally:
            session.close()

    @staticmethod
    def calculate_data_hash(contractor_data: Dict) -> str:
        """
        Calculate MD5 hash of key fields for change detection

        Args:
            contractor_data: Dictionary of contractor data

        Returns:
            MD5 hash string
        """
        # Include only fields that matter for change detection
        key_fields = {
            'name': contractor_data.get('name'),
            'phone': contractor_data.get('phone'),
            'location': contractor_data.get('city'),  # city from scraper becomes location
            'rating': contractor_data.get('rating'),
            'reviews_count': contractor_data.get('reviews_count'),
            'description': contractor_data.get('description'),
        }

        # Create deterministic string representation
        hash_string = json.dumps(key_fields, sort_keys=True)
        return hashlib.md5(hash_string.encode()).hexdigest()

    @staticmethod
    def extract_gaf_id(profile_url: str) -> str:
        """
        Extract GAF ID from profile URL

        Example: https://www.gaf.com/.../matute-roofing-1113654 -> 1113654
        """
        if not profile_url:
            return None

        # Extract the last part of URL
        parts = profile_url.rstrip('/').split('/')
        if parts:
            last_part = parts[-1]
            # Try to extract number from end
            if '-' in last_part:
                potential_id = last_part.split('-')[-1]
                if potential_id.isdigit():
                    return potential_id

        return profile_url  # Fallback to full URL

    @staticmethod
    def clean_phone_number(phone: str) -> str:
        """
        Clean and format phone number to +1 (xxx) xxx-xxxx format

        Args:
            phone: Raw phone number string

        Returns:
            Formatted phone number or None if invalid
        """
        if not phone:
            return None

        # Remove all non-digit characters
        digits = ''.join(filter(str.isdigit, phone))

        # Handle different lengths
        if len(digits) == 11 and digits.startswith('1'):
            # Remove leading 1
            digits = digits[1:]
        elif len(digits) != 10:
            # Invalid phone number length
            return phone  # Return original if can't parse

        # Format as +1 (xxx) xxx-xxxx
        return f"+1 ({digits[:3]}) {digits[3:6]}-{digits[6:]}"

    @staticmethod
    def clean_certifications(certifications: List[str]) -> List[str]:
        """
        Clean certification data by removing duplicates and unnecessary prefixes

        Args:
            certifications: Raw list of certification strings

        Returns:
            Cleaned list of unique certification names
        """
        if not certifications:
            return []

        cleaned = set()  # Use set to automatically handle duplicates

        for cert in certifications:
            if not cert or not isinstance(cert, str):
                continue

            # Split by newlines to handle multi-line certification blocks
            lines = cert.split('\n')

            for line in lines:
                line = line.strip()

                # Skip common header/label lines
                skip_phrases = [
                    'Certifications & Awards',
                    'Certifications and Awards',
                    'Certifications',
                    'Awards',
                    'Award',
                    'Certification'
                ]

                # Skip if it's just a label (exact match)
                if line in skip_phrases:
                    continue

                # Remove prefix if it starts with these
                for prefix in skip_phrases:
                    if line.startswith(prefix + '\n'):
                        line = line[len(prefix):].strip()
                    elif line.startswith(prefix + ':'):
                        line = line[len(prefix) + 1:].strip()

                # Add non-empty substantial certification names
                if len(line) > 3 and line not in skip_phrases:
                    cleaned.add(line)

        return sorted(list(cleaned))  # Return sorted list for consistency

    def upsert_contractor(self, session: Session, contractor_data: Dict):
        """
        Insert or update contractor in database

        Args:
            session: SQLAlchemy session
            contractor_data: Dictionary of contractor data from scraper

        Returns:
            Tuple of (Contractor object, is_new: bool)
        """
        profile_url = contractor_data.get('profile_url')
        if not profile_url:
            raise ValueError("profile_url is required")

        # Calculate hash for change detection
        data_hash = self.calculate_data_hash(contractor_data)

        # Extract GAF ID from URL
        gaf_id = self.extract_gaf_id(profile_url)

        # Clean phone number
        cleaned_phone = self.clean_phone_number(contractor_data.get('phone'))

        # Clean certifications data
        cleaned_certs = self.clean_certifications(contractor_data.get('certifications', []))

        # Check if contractor exists
        existing = session.query(Contractor).filter(
            Contractor.profile_url == profile_url
        ).first()

        if existing:
            # Check if data has changed
            if existing.data_hash != data_hash:
                # Update existing contractor
                existing.name = contractor_data.get('name')
                existing.phone = cleaned_phone
                existing.location = contractor_data.get('city')  # city from scraper becomes location
                existing.distance = contractor_data.get('distance')
                existing.rating = contractor_data.get('rating')
                existing.reviews_count = contractor_data.get('reviews_count')
                existing.description = contractor_data.get('description')
                existing.certifications = cleaned_certs
                existing.data_hash = data_hash
                existing.gaf_id = gaf_id

                logger.info(f"Updated contractor: {existing.name}")
                return existing, False
            else:
                logger.debug(f"No changes for contractor: {existing.name}")
                return existing, False
        else:
            # Create new contractor
            new_contractor = Contractor(
                gaf_id=gaf_id,
                name=contractor_data.get('name'),
                phone=cleaned_phone,
                location=contractor_data.get('city'),  # city from scraper becomes location
                distance=contractor_data.get('distance'),
                rating=contractor_data.get('rating'),
                reviews_count=contractor_data.get('reviews_count'),
                profile_url=profile_url,
                description=contractor_data.get('description'),
                certifications=cleaned_certs,
                data_hash=data_hash
            )

            session.add(new_contractor)
            logger.info(f"Inserted new contractor: {new_contractor.name}")
            return new_contractor, True

    def save_contractors_batch(self, contractors_data: List[Dict]) -> Dict[str, int]:
        """
        Save multiple contractors to database

        Args:
            contractors_data: List of contractor dictionaries

        Returns:
            Dictionary with counts: {'total': 10, 'new': 5, 'updated': 3, 'unchanged': 2}
        """
        stats = {'total': len(contractors_data), 'new': 0, 'updated': 0, 'unchanged': 0}

        with self.get_session() as session:
            for contractor_data in contractors_data:
                try:
                    contractor, is_new = self.upsert_contractor(session, contractor_data)

                    if is_new:
                        stats['new'] += 1
                    else:
                        # Check if it was actually updated (not just queried)
                        if session.is_modified(contractor):
                            stats['updated'] += 1
                        else:
                            stats['unchanged'] += 1

                except Exception as e:
                    logger.error(f"Error saving contractor {contractor_data.get('name')}: {str(e)}")
                    continue

        logger.info(f"Batch save complete: {stats}")
        return stats
