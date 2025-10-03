# Incremental Refresh Strategy

## Overview

The incremental refresh system intelligently updates contractor data by:
1. **Lightweight listing page scrapes** every 2 days
2. **Selective profile re-scraping** based on threshold rules
3. **Metadata-only updates** for minor changes

This approach minimizes scraping load while keeping data fresh.

## Re-scrape Threshold Rules

The system will **re-scrape the full profile** (description, certifications) if:

| Change Type | Threshold | Reason |
|-------------|-----------|--------|
| Phone number | Any change | Critical contact info |
| Profile URL | Any change | Contractor identity |
| Rating | Change > 0.3 | Significant quality indicator |
| Reviews | Increase ≥ 10 | Major credibility change |
| Reviews | Decrease ≥ 5 | Potential issue flag |

## Metadata-Only Updates

For **minor changes below thresholds**, we only update:
- Rating (if changed by ≤ 0.3)
- Reviews count (if changed by < 10)
- Distance (if location search radius changes)
- Last scraped timestamp

**No profile visit required** - saves time and resources.

## Architecture

### Files

```
backend/
├── scraper/
│   ├── gaf_scraper.py           # Base scraper (listing + profile)
│   └── incremental_scraper.py   # Intelligent incremental refresh
└── scheduler/
    └── refresh_scheduler.py     # Runs every 2 days at 2 AM
```

### Flow Diagram

```
┌─────────────────────────────────────┐
│  Scheduled Run (Every 2 Days)       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 1: Scrape Listing Pages      │
│  (Lightweight - no profile visits)  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 2: Compare with Database      │
│  - Check thresholds for each        │
│  - Categorize: New / Changed / Same │
└──────────────┬──────────────────────┘
               │
         ┌─────┴─────┐
         │           │
         ▼           ▼
┌────────────┐  ┌─────────────────┐
│ New        │  │ Significant     │
│ Contractor │  │ Changes?        │
└─────┬──────┘  └────┬────────────┘
      │              │
      │  Yes         │ Yes
      ▼              ▼
┌─────────────────────────────────────┐
│  Step 3: Re-scrape Profiles         │
│  - Visit profile pages              │
│  - Extract description, certs       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 4: Update Database            │
│  - New contractors: Full insert     │
│  - Changed: Update all fields       │
│  - Minor changes: Metadata only     │
└─────────────────────────────────────┘
```

## Usage

### One-Time Manual Refresh

```bash
docker-compose run scraper python backend/scraper/incremental_scraper.py
```

### Scheduled Refresh (Every 2 Days)

```bash
docker-compose run scraper python backend/scheduler/refresh_scheduler.py
```

### Configuration

Edit `backend/scheduler/refresh_scheduler.py`:

```python
# Change ZIP codes
zipcodes = ["10013", "10001", "90210"]

# Change schedule (every 2 days at 2 AM)
schedule.every(2).days.at("02:00").do(run_incremental_refresh)

# Or change to different intervals:
schedule.every().day.at("03:00")       # Daily at 3 AM
schedule.every().monday.at("09:00")    # Weekly on Monday
schedule.every(3).days.at("12:00")     # Every 3 days at noon
```

## Example Output

```
============================================================
Incremental Refresh Complete
============================================================
Total contractors found: 89
New contractors: 3
Profiles re-scraped (significant changes): 7
Metadata updated (minor changes): 65
Unchanged: 14
============================================================
```

### Interpretation

- **3 new contractors** → Scraped full profiles
- **7 re-scraped** → Met threshold (phone change, rating +0.5, reviews +15, etc.)
- **65 metadata updates** → Rating went from 4.8→4.9, reviews 100→105, etc.
- **14 unchanged** → Exactly the same as last scrape

## Performance Benefits

| Metric | Full Scrape | Incremental |
|--------|-------------|-------------|
| Listing pages scraped | ~10 pages | ~10 pages |
| Profile visits | 89 | ~10 (new + changed) |
| Time required | ~15 min | ~3 min |
| Server load | High | Low |

**Result**: ~80% faster, much gentler on server resources.

## Database Tracking

The `scrape_runs` table tracks each refresh:

```sql
SELECT
    id,
    zipcode,
    contractors_found,
    contractors_new,
    contractors_updated,
    started_at,
    status
FROM scrape_runs
ORDER BY started_at DESC;
```

## Future Enhancements

- [ ] Email alerts when new contractors appear
- [ ] Slack notifications for significant rating drops
- [ ] Dashboard to visualize refresh stats
- [ ] Machine learning to predict optimal refresh intervals
- [ ] Rate limiting and retry logic for failed scrapes
