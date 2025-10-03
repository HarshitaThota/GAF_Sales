# GAF Sales Intelligence Platform

B2B sales intelligence platform for roofing material distributors to identify and prioritize contractor leads using automated scraping, AI-powered insights, and on-demand email generation.

## Features

- **Automated Web Scraping**: Selenium-based scraper extracts 89 contractor profiles from GAF.com
- **Incremental Refresh**: Smart re-scraping based on change thresholds (rating >0.3, reviews ≥10)
- **AI Insights Generation**: GPT-4o-mini creates personalized sales intelligence for each contractor
- **LLM Evaluation Framework**: GPT-4 as Judge evaluates insight quality on 4 dimensions (accuracy, actionability, personalization, conciseness)
- **Auto-Improvement Loop**: Regenerates insights scoring <3.8 with targeted feedback
- **Lead Quality Ranking**: Prioritizes contractors by rating × reviews (best leads first)
- **On-Demand Email Drafting**: GPT generates personalized B2B sales emails with preview modal
- **Web Dashboard**: Flask + Jinja2 interface with search, filtering, sorting, and pagination
- **PostgreSQL Database**: Persistent storage with JSONB for structured + unstructured data
- **Scheduled Updates**: Automatic incremental refresh every 2 days

## Tech Stack

### Backend
- **Python 3.11** - Core language
- **Selenium WebDriver** - Web scraping with headless Chromium (bypasses JavaScript rendering)
- **Flask + Jinja2** - Server-side rendering (faster than React SPA, simpler deployment)
- **SQLAlchemy** - ORM for database operations
- **PostgreSQL 15** - Relational database with JSONB support
- **OpenAI GPT-4o-mini** - AI insights generation and email drafting
- **OpenAI GPT-4** - LLM evaluation (GPT-as-Judge)

### Frontend
- **Jinja2 Templates** - Server-side HTML rendering
- **Vanilla JavaScript** - Modal interactions, async fetch for email generation
- **Pure CSS** - Gradient UI design, responsive grid layout

### Infrastructure
- **Docker & Docker Compose** - Multi-container orchestration
- **Python Schedule** - Automated task scheduling (not Celery - simpler for single-worker tasks)

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- OpenAI API key

### Setup

1. Clone the repository:
```bash
git clone <repo_url>
cd GAF_Sales
```

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
- **scraper**: Initial full scrape on startup (~5 min for 89 contractors)
- **scheduler**: Incremental refresh every 2 days at 2am
- **web**: Flask web dashboard (port 3000)

## Usage

### Dashboard Features

**Main Dashboard** (`/`)
- Contractor cards sorted by lead quality (rating × reviews)
- AI insights displayed prominently below contractor name
- Search by name or location
- Filter by location and minimum rating
- Sort by lead quality, rating, reviews, or name
- Draft sales email button on each card
- Click contractor name for full profile

**Email Generation**
- Click "📧 Draft Sales Email" on any contractor card
- GPT-4o-mini generates personalized email in ~3 seconds
- Preview modal shows full email with subject line
- One-click copy to clipboard
- Includes placeholders for salesperson info ({{sales_person_name}}, {{sales_company}}, etc.)

**Contractor Detail** (`/contractor/<id>`)
- Full profile with complete description
- All certifications (not just first 2)
- Phone number, distance, rating breakdown
- Full AI insights
- Link to GAF.com profile

**Evaluation Dashboard** (`/evaluation`)
- Aggregate scores across all insights (accuracy, actionability, personalization, conciseness)
- Individual contractor evaluation scores and feedback
- Average overall score: 4.2/5

### Running Individual Services

**Full scrape** (scrapes all 89 contractors):
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

**Evaluate insights** (GPT-4 as Judge):
```bash
docker-compose run scraper python backend/ai/evaluator.py
```

**Improve low-quality insights** (score <3.8):
```bash
docker-compose run scraper python backend/ai/insight_improver.py
```

### Managing Services

Stop all services:
```bash
docker-compose down
```

View logs:
```bash
docker-compose logs -f web
docker-compose logs -f scheduler
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
│   │   ├── models.py                # SQLAlchemy ORM models
│   │   ├── connection.py            # Database connection manager
│   │   └── init.sql                 # PostgreSQL schema initialization
│   ├── ai/
│   │   ├── insights_generator.py    # GPT-4o-mini insight generation
│   │   ├── evaluator.py             # GPT-4 as Judge (4-dimension scoring)
│   │   └── insight_improver.py      # Auto-regeneration for low scores
│   ├── api/
│   │   ├── app.py                   # Flask routes and API endpoints
│   │   └── templates/
│   │       ├── index.html           # Main dashboard
│   │       ├── contractor_detail.html  # Full contractor profile
│   │       └── evaluation.html      # LLM evaluation dashboard
│   ├── scheduler/
│   │   └── refresh_scheduler.py     # Scheduled incremental refresh
│   └── requirements.txt
├── data/                             # Scraped data output (JSON backups)
├── Dockerfile
├── docker-compose.yml
├── .env                              # OpenAI API key
└── README.md
```

## Configuration

### Scraper Settings

Edit `backend/scraper/gaf_scraper.py` and `backend/scraper/incremental_scraper.py`:
```python
zipcode = "10013"           # ZIP code to search
distance = 25               # Search radius in miles
max_results = None          # None for all ~89 contractors, or set limit (e.g., 10)
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

### LLM Evaluation Threshold

Edit `backend/ai/insight_improver.py`:
```python
threshold = 3.8  # Minimum overall score (1-5 scale)
max_iterations = 2  # Max regeneration attempts
```

## Database Schema

### Contractors Table
- **Basic Info**: `id`, `name`, `phone`, `location`, `rating`, `reviews_count`
- **GAF Data**: `profile_url`, `distance`, `gaf_id`
- **Rich Content**: `description` (TEXT), `certifications` (JSONB array)
- **AI Generated**: `ai_insights` (JSONB array)
- **LLM Evaluation**: `eval_accuracy`, `eval_actionability`, `eval_personalization`, `eval_conciseness`, `eval_overall`, `eval_feedback`, `eval_timestamp`
- **Metadata**: `created_at`, `last_scraped_at`, `data_hash`

### Scrape Runs Table
- **Run Info**: `id`, `zipcode`, `distance`, `started_at`, `completed_at`
- **Metrics**: `contractors_found`, `contractors_new`, `contractors_updated`
- **Status**: `status`, `error_message`

## AI System Architecture

### 1. Insights Generation (GPT-4o-mini)
- Analyzes contractor rating, certifications, description, reviews
- Generates 2-3 sentence sales intelligence focused on B2B potential
- Runs automatically after scraping new/updated contractors
- Temperature: 0.7 for creative but consistent output

### 2. LLM Evaluation (GPT-4 as Judge)
- **4 Dimensions with Weights**:
  - Accuracy & Relevance (40%): Factually correct contractor data
  - Actionability (30%): Clear next steps for sales team
  - Personalization (20%): Tailored to contractor's unique strengths
  - Conciseness (10%): Brief, scannable text
- **Scoring**: 1-5 scale per dimension, weighted average for overall
- **Output**: Quantitative scores + qualitative feedback
- Temperature: 0.3 for consistent evaluation

### 3. Auto-Improvement Loop
- Identifies insights with overall score <3.8
- Analyzes weakest dimensions (e.g., "low actionability")
- Regenerates with targeted instructions (e.g., "provide specific materials/services needed")
- Re-evaluates until score ≥3.8 or max 2 iterations
- Prevents quality degradation over time

### 4. Email Generation (GPT-4o-mini)
- On-demand generation (not pre-generated)
- Personalized based on contractor certifications, rating, specializations
- Includes subject line, body with value prop, soft CTA
- Placeholder variables for salesperson info
- Temperature: 0.7 for natural, professional tone

## Lead Scoring Framework

**How leads are prioritized:**

**Tier 1 - Hot Leads** (rating × reviews > 200)
- 5.0★ with 50+ reviews
- GAF Master Elite® certified
- <10 miles from distributor

**Tier 2 - Warm Leads** (rating × reviews 80-200)
- 4.5-4.9★ with 20+ reviews
- Multiple certifications
- Growing review count

**Tier 3 - Nurture** (rating × reviews < 80)
- 4.0-4.4★ with <20 reviews
- 20-25 miles away
- Potential for growth

**Formula**: `lead_quality = rating × reviews_count`

## Evaluation Results

**Current Performance** (11 contractors evaluated):
- Average Overall Score: **4.2/5**
- Accuracy: **4.0/5**
- Actionability: **3.0/5** (weakest dimension - being addressed)
- Personalization: **5.0/5**
- Conciseness: **5.0/5**

All insights scored above 3.8 threshold, indicating high-quality AI-generated sales intelligence.

## Why This Tech Stack?

**Selenium over Scrapy**: GAF.com renders contractor data via JavaScript - Selenium executes JS and waits for dynamic content to load.

**PostgreSQL over MongoDB**: Need relational integrity for contractor-scrape relationships + JSONB for flexibility with certifications/insights arrays.

**Flask + Jinja2 over React SPA**: Server-side rendering is faster for read-heavy dashboards, simpler deployment (no build step), and better SEO.

**GPT-4o-mini for generation**: Cost-effective ($0.15/1M input tokens) and fast (~2s response time) for high-volume insight generation.

**GPT-4 for evaluation**: More consistent and rigorous judgment than GPT-4o-mini evaluating itself.

**Docker Compose over Kubernetes**: 4-container app doesn't need K8s complexity - Docker Compose is sufficient for single-host deployment.

**Python Schedule over Celery**: Simple cron-like scheduling without Redis/RabbitMQ overhead - incremental refresh is a single-worker task.

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
5. Set environment variable:
```bash
export OPENAI_API_KEY=your_key_here
```
6. Run services individually:
```bash
python backend/scraper/gaf_scraper.py
python backend/ai/insights_generator.py
python backend/api/app.py
```

## Troubleshooting

**Port 3000 already in use:**
```bash
lsof -ti:3000 | xargs kill -9
# or change port in docker-compose.yml
```

**Database connection errors:**
```bash
docker-compose down
docker-compose up --build
```

**Scraper timeouts:**
- Check internet connection
- Increase timeout in `gaf_scraper.py`: `WebDriverWait(self.driver, 30)`
- GAF.com may have rate limiting - add delays

**Missing insights:**
```bash
docker-compose run scraper python backend/ai/insights_generator.py
```

**Evaluation not showing:**
```bash
docker-compose run scraper python backend/ai/evaluator.py
```

**Low insight scores:**
```bash
docker-compose run scraper python backend/ai/insight_improver.py
```

## Future Enhancements

- CRM integration (Salesforce, HubSpot)
- Email send + tracking via SendGrid/Mailgun
- Predictive lead scoring with historical conversion data
- Multi-region support (different ZIP codes)
- Contractor change alerts (Slack/email notifications)
- A/B testing for email templates
- Competitive analysis (compare contractor portfolios)

## License

MIT
