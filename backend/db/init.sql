-- GAF Sales Intelligence Database Schema

-- Create contractors table (structured data)
CREATE TABLE IF NOT EXISTS contractors (
    id SERIAL PRIMARY KEY,
    gaf_id VARCHAR(50) UNIQUE,  -- Unique identifier from GAF URL
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    location VARCHAR(100),
    distance DECIMAL(5,2),  -- Distance in miles

    -- Performance metrics (structured)
    rating DECIMAL(2,1),
    reviews_count INTEGER,

    -- URLs
    profile_url TEXT UNIQUE NOT NULL,

    -- Unstructured data (TEXT/JSONB for flexibility)
    description TEXT,  -- Company description from profile
    certifications JSONB,  -- Array of certification names

    -- AI-generated insights (to be populated later)
    ai_insights JSONB,  -- Array of sales talking points

    -- LLM Evaluation Scores (GPT-as-Judge)
    eval_accuracy FLOAT,  -- Accuracy & Relevance score (1-5)
    eval_actionability FLOAT,  -- Actionability score (1-5)
    eval_personalization FLOAT,  -- Personalization score (1-5)
    eval_conciseness FLOAT,  -- Conciseness score (1-5)
    eval_overall FLOAT,  -- Weighted average score
    eval_feedback TEXT,  -- GPT's qualitative feedback
    eval_timestamp TIMESTAMP,  -- When evaluation was performed

    -- Metadata for data quality tracking
    data_hash VARCHAR(64),  -- MD5 hash of key fields for change detection
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexes for common queries
    CONSTRAINT valid_rating CHECK (rating >= 0 AND rating <= 5)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_contractors_name ON contractors(name);
CREATE INDEX IF NOT EXISTS idx_contractors_location ON contractors(location);
CREATE INDEX IF NOT EXISTS idx_contractors_rating ON contractors(rating DESC);
CREATE INDEX IF NOT EXISTS idx_contractors_updated_at ON contractors(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_contractors_gaf_id ON contractors(gaf_id);

-- Create scrape_runs table to track scraping history
CREATE TABLE IF NOT EXISTS scrape_runs (
    id SERIAL PRIMARY KEY,
    zipcode VARCHAR(10) NOT NULL,
    distance INTEGER,  -- Search radius in miles
    contractors_found INTEGER,
    contractors_new INTEGER,
    contractors_updated INTEGER,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR(20),  -- 'running', 'completed', 'failed'
    error_message TEXT
);

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column() 
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to auto-update updated_at
CREATE TRIGGER update_contractors_updated_at
    BEFORE UPDATE ON contractors
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert initial test data (optional)
-- This can be removed for production
INSERT INTO contractors (gaf_id, name, phone, location, distance, rating, reviews_count, profile_url, description)
VALUES ('test-1', 'Test Contractor', '555-0100', 'New York, NY', 10.5, 4.8, 100, 'https://test.com/contractor-1', 'This is a test contractor')
ON CONFLICT (profile_url) DO NOTHING;
