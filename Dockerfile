FROM python:3.11-slim

# Install dependencies for Chromium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY data/ ./data/

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Create data directory if it doesn't exist
RUN mkdir -p /app/data

# Default command
CMD ["python", "backend/scraper/gaf_scraper.py"]
