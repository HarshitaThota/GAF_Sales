# GAF Sales Intelligence Platform

B2B sales intelligence platform for generating leads from GAF contractor data.

## Setup

### Local Development

1. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

2. Run the scraper:
```bash
python backend/scraper/gaf_scraper.py
```

### Docker

1. Build and run with Docker Compose:
```bash
docker-compose up --build
```

2. Run in detached mode:
```bash
docker-compose up -d
```

3. View logs:
```bash
docker-compose logs -f
```

4. Stop:
```bash
docker-compose down
```

## Project Structure

```
.
├── backend/
│   ├── scraper/
│   │   ├── gaf_scraper.py    # Main scraper logic
│   │   └── __init__.py
│   └── requirements.txt
├── data/                      # Scraped data output
├── Dockerfile
├── docker-compose.yml
└── .env
```

## Configuration

Edit `.env` for configuration (if needed in future):
```
ZIPCODE=10013
DISTANCE=25
```
