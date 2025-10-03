"""
Database models for GAF Sales Intelligence Platform
"""
from sqlalchemy import Column, Integer, String, Text, DECIMAL, Float, TIMESTAMP, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class Contractor(Base):
    """
    Contractor model - stores both structured and unstructured data
    """
    __tablename__ = 'contractors'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Structured data
    gaf_id = Column(String(50), unique=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    phone = Column(String(50))
    location = Column(String(100), index=True)
    distance = Column(DECIMAL(5, 2))

    # Performance metrics
    rating = Column(DECIMAL(2, 1))
    reviews_count = Column(Integer)

    # URLs
    profile_url = Column(Text, unique=True, nullable=False)

    # Unstructured data (TEXT for long content, JSONB for structured arrays/objects)
    description = Column(Text)  # Raw company description
    certifications = Column(JSONB)  # Array of certification strings

    # AI-generated insights (to be populated later)
    ai_insights = Column(JSONB)  # Array of key talking points for sales

    # LLM Evaluation Scores (GPT-as-Judge)
    eval_accuracy = Column(Float)  # Accuracy & Relevance score (1-5)
    eval_actionability = Column(Float)  # Actionability score (1-5)
    eval_personalization = Column(Float)  # Personalization score (1-5)
    eval_conciseness = Column(Float)  # Conciseness score (1-5)
    eval_overall = Column(Float)  # Weighted average score
    eval_feedback = Column(Text)  # GPT's qualitative feedback
    eval_timestamp = Column(TIMESTAMP)  # When evaluation was performed

    # Metadata for data quality
    data_hash = Column(String(64))  # MD5 hash for change detection
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    last_scraped_at = Column(TIMESTAMP, server_default=func.now())

    # Table constraints
    __table_args__ = (
        CheckConstraint('rating >= 0 AND rating <= 5', name='valid_rating'),
        Index('idx_contractors_rating_desc', rating.desc()),
        Index('idx_contractors_updated_at_desc', updated_at.desc()),
        Index('idx_contractors_location', location),
    )

    def __repr__(self):
        return f"<Contractor(id={self.id}, name='{self.name}', location='{self.location}', rating={self.rating})>"

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'gaf_id': self.gaf_id,
            'name': self.name,
            'phone': self.phone,
            'location': self.location,
            'distance': float(self.distance) if self.distance else None,
            'rating': float(self.rating) if self.rating else None,
            'reviews_count': self.reviews_count,
            'profile_url': self.profile_url,
            'description': self.description,
            'certifications': self.certifications,
            'ai_insights': self.ai_insights,
            'data_hash': self.data_hash,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_scraped_at': self.last_scraped_at.isoformat() if self.last_scraped_at else None,
        }


class ScrapeRun(Base):
    """
    Track scraping runs for monitoring and debugging
    """
    __tablename__ = 'scrape_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    zipcode = Column(String(10), nullable=False)
    distance = Column(Integer)  # Search radius in miles
    contractors_found = Column(Integer)
    contractors_new = Column(Integer)
    contractors_updated = Column(Integer)
    started_at = Column(TIMESTAMP, nullable=False)
    completed_at = Column(TIMESTAMP)
    status = Column(String(20))  # 'running', 'completed', 'failed'
    error_message = Column(Text)

    def __repr__(self):
        return f"<ScrapeRun(id={self.id}, zipcode='{self.zipcode}', status='{self.status}')>"

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'zipcode': self.zipcode,
            'distance': self.distance,
            'contractors_found': self.contractors_found,
            'contractors_new': self.contractors_new,
            'contractors_updated': self.contractors_updated,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status,
            'error_message': self.error_message,
        }
