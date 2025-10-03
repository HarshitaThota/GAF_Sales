# GAF Sales Intelligence Platform

B2B sales intelligence platform for roofing material distributors to identify and analyze contractor leads using automated scraping and AI-powered insights.

## Features

- **Automated Web Scraping**: Selenium-based scraper extracts contractor data from GAF.com
- **Incremental Refresh**: Smart re-scraping based on change thresholds (rating, reviews, phone)
- **AI Insights**: GPT-4o-mini generates sales intelligence for each contractor
- **Web Dashboard**: Flask-based interface with search, filtering, and pagination
- **PostgreSQL Database**: Persistent storage with JSONB support for structured and unstructured data
- **Scheduled Updates**: Automatic incremental refresh every 2 days

## Tech Stack

### Backend
- **Python 3.11** - Core language
- **Selenium WebDriver** - Web scraping with headless Chromium
- **Flask** - Web framework with Jinja2 templates
- **SQLAlchemy** - ORM for database operations
- **PostgreSQL 15** - Relational database
- **OpenAI GPT-4o-mini** - AI insights generation

### Frontend
- **Jinja2 Templates** - Server-side HTML rendering
- **Pure CSS** - No frameworks, gradient UI design

### Infrastructure
- **Docker & Docker Compose** - Containerization
- **Python Schedule** - Automated task scheduling

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- OpenAI API key (add to `.env` file)

### Setup

1. Clone the repository and navigate to the project directory

2. Create `.env` file with your OpenAI API key:
```bash
OPENAI_API_KEY=your_key_here
```

3. Build and start all services:
```bash
docker-compose up --build
```

4. Access the dashboard at `http://localhost:3000`

### Docker Services

The platform runs 4 Docker containers:

- **postgres**: PostgreSQL database (port 5432)
- **scraper**: Initial full scrape on startup
- **scheduler**: Incremental refresh every 2 days
- **web**: Flask web dashboard (port 3000)

## Usage

### Running Individual Services

**Full scrape** (scrapes all contractors with profiles):
```bash
docker-compose run scraper python backend/scraper/gaf_scraper.py
```

**Incremental refresh** (only re-scrapes changed contractors):
```bash
docker-compose run scraper python backend/scraper/incremental_scraper.py
```

**Generate AI insights** (for contractors without insights):
```bash
docker-compose run scraper python backend/ai/insights_generator.py
```

### Managing Services

Stop all services:
```bash
docker-compose down
```

View logs:
```bash
docker-compose logs -f web
```

Reset database (deletes all data):
```bash
docker-compose down -v
docker-compose up --build
```

## Project Structure

```
.
├── backend/
│   ├── scraper/
│   │   ├── gaf_scraper.py           # Full scraper with profile visits
│   │   └── incremental_scraper.py   # Smart incremental refresh
│   ├── db/
│   │   ├── models.py                # SQLAlchemy models
│   │   ├── connection.py            # Database manager
│   │   └── init.sql                 # Database schema
│   ├── ai/
│   │   └── insights_generator.py    # OpenAI GPT integration
│   ├── api/
│   │   ├── app.py                   # Flask web app
│   │   └── templates/               # Jinja2 HTML templates
│   ├── scheduler/
│   │   └── refresh_scheduler.py     # Scheduled incremental refresh
│   └── requirements.txt
├── data/                             # Scraped data output (JSON backups)
├── Dockerfile
├── docker-compose.yml
└── .env                              # OpenAI API key
```

## Configuration

### Scraper Settings

Edit `backend/scraper/gaf_scraper.py`:
```python
zipcode = "10013"           # ZIP code to search
distance = 25               # Search radius in miles
max_results = 10            # Limit results (None for all ~89 contractors)
```

### Incremental Refresh Thresholds

Edit `backend/scraper/incremental_scraper.py`:
```python
# Re-scrape triggers:
- Phone number changed
- Profile URL changed
- Rating changed by > 0.3
- Reviews increased by >= 10
- Reviews decreased by >= 5
```

### Scheduler Frequency

Edit `backend/scheduler/refresh_scheduler.py`:
```python
schedule.every(2).days.at("02:00").do(run_incremental_refresh)
```

## Database Schema

### Contractors Table
- `id`, `name`, `phone`, `location`, `rating`, `reviews_count`
- `profile_url`, `distance`, `gaf_id`
- `description`, `certifications` (JSONB)
- `ai_insights` (JSONB array)
- `created_at`, `last_scraped_at`, `data_hash`

### Scrape Runs Table
- `id`, `zipcode`, `distance`, `started_at`, `completed_at`
- `contractors_found`, `contractors_new`, `contractors_updated`
- `status`, `error_message`

## AI Insights

Insights are automatically generated for:
- **New contractors** when first scraped
- **Updated contractors** when re-scraped due to significant changes
- Focus areas: reputation, quality indicators, B2B potential, specializations

Example insight:
> "Preferred Exterior Corp boasts a stellar 5.0-star rating from 50 reviews, underscoring their strong reputation in the roofing industry. As a GAF Master Elite® contractor with four decades of experience, they are well-positioned to be a valuable B2B customer for roofing materials..."

## Dashboard Features

- **Search**: Filter by contractor name or location
- **Filters**: Location dropdown, minimum rating selector
- **Sorting**: By rating, review count, or name
- **Pagination**: 20 contractors per page
- **Contractor Details**: Click any card to view full profile
- **AI Insights Preview**: First 150 characters on cards, full text on detail page

## Development

### Local Development (without Docker)

1. Install PostgreSQL 15
2. Create database: `gaf_sales`
3. Install Python dependencies:
```bash
pip install -r backend/requirements.txt
```
4. Run database init script:
```bash
psql -U postgres -d gaf_sales -f backend/db/init.sql
```
5. Run services individually:
```bash
python backend/scraper/gaf_scraper.py
python backend/api/app.py
```

## Troubleshooting

**Port 3000 already in use:**
```bash
docker ps -a | grep gaf
docker stop <container_id>
docker rm <container_id>
```

**Database connection errors:**
```bash
docker-compose down
docker-compose up --build
```

**Scraper timeouts:**
- Check internet connection
- Increase timeout in `gaf_scraper.py`: `WebDriverWait(self.driver, 30)`

**Missing insights:**
```bash
docker-compose run scraper python backend/ai/insights_generator.py
```
