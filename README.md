# Sports Prediction Platform

A personal ML-powered sports betting analytics platform covering **NFL, NBA, MLB, and Soccer**.

**Features:**
- ML predictions (moneylines, spreads, totals, player props)
- Real-time odds from 10+ sportsbooks via The Odds API
- Same-game parlay correlation analysis
- Bet tracking with CLV (Closing Line Value) analysis
- Strategy backtesting
- Walk-forward cross-validation (no data leakage)

---

## Quick Start (5 minutes)

### Prerequisites

- **Docker** and **Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)
- **Python 3.11+** - [Install Python](https://www.python.org/downloads/)
- **Node.js 18+** - [Install Node.js](https://nodejs.org/)

### 1. Clone and Setup

```bash
# Navigate to project
cd "sports model"

# Run the setup script (creates .env, installs dependencies)
python setup.py
```

### 2. Get Your API Key (Required for Live Odds)

You need **ONE** API key:

| API | Free Tier | Get It |
|-----|-----------|--------|
| **The Odds API** | 500 requests/month | [https://the-odds-api.com](https://the-odds-api.com) |

1. Go to [the-odds-api.com](https://the-odds-api.com)
2. Click "Get API Key" (free)
3. Enter your email and verify
4. Copy your API key
5. Add it to your `.env` file:
   ```
   ODDS_API_KEY=your_key_here
   ```

> **Note:** The free tier (500 requests/month) is plenty for personal use. Odds are fetched every minute but cached, so you won't hit the limit with normal usage.

### 3. Start Everything

```bash
# Start all services (database, redis, backend, frontend)
docker-compose up -d

# Check that everything is running
docker-compose ps
```

### 4. Initialize Data (First Time Only)

```bash
# Backfill historical data (takes 5-15 minutes)
cd backend
python scripts/backfill_all_sports.py --sport all --seasons 2

# Train ML models (takes 5-10 minutes)
python scripts/run_training_pipeline.py
```

### 5. Open the App

- **Frontend:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **API Health:** http://localhost:8000/health

---

## Detailed Setup Guide

### Environment Configuration

Copy the example environment file and customize:

```bash
cp backend/.env.example .env
```

**Required Settings:**

| Variable | Description | Where to Get |
|----------|-------------|--------------|
| `ODDS_API_KEY` | Real-time odds from 10+ sportsbooks | [the-odds-api.com](https://the-odds-api.com) (free) |

**Optional Settings:**

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | Auto-configured for Docker |
| `REDIS_URL` | Redis connection | Auto-configured for Docker |
| `MODEL_PATH` | Where trained models are saved | `./ml/saved_models` |
| `BANKROLL_DEFAULT` | Starting bankroll for simulations | `10000` |
| `KELLY_FRACTION_DEFAULT` | Kelly criterion multiplier | `0.25` (quarter Kelly) |
| `MIN_EDGE_THRESHOLD` | Minimum edge for value bets | `0.03` (3%) |

### Data Sources (All Free)

The platform uses these **free** data sources (no additional API keys needed):

| Sport | Source | What It Provides |
|-------|--------|------------------|
| **NBA** | `nba_api` | Games, box scores, player stats, schedules |
| **NFL** | `nfl_data_py` | Games, play-by-play, rosters, schedules |
| **MLB** | `pybaseball` | Games, Statcast data, player stats |
| **Soccer** | `soccerdata` | EPL, La Liga, Bundesliga, Serie A, Ligue 1 |
| **Odds** | The Odds API | Live odds from 10+ US sportsbooks |

---

## Commands Reference

### Docker Commands

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f backend
docker-compose logs -f celery_worker

# Restart a specific service
docker-compose restart backend

# Rebuild after code changes
docker-compose up -d --build
```

### Data Commands

```bash
cd backend

# Backfill all sports (recommended: 2-3 seasons)
python scripts/backfill_all_sports.py --sport all --seasons 2

# Backfill specific sport
python scripts/backfill_all_sports.py --sport nba --seasons 3
python scripts/backfill_all_sports.py --sport nfl --seasons 2

# Export data for training
python scripts/export_training_data.py --sport all
```

### Training Commands

```bash
cd backend

# Full training pipeline (export + train + validate)
python scripts/run_training_pipeline.py

# Train specific sports
python scripts/run_training_pipeline.py --sports nba nfl

# Train with hyperparameter tuning (slower but better)
python scripts/run_training_pipeline.py --tune

# Use ensemble models
python scripts/run_training_pipeline.py --model-type ensemble

# Skip export if CSV files exist
python scripts/run_training_pipeline.py --skip-export
```

### Development Commands

```bash
# Backend only (without Docker)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend only
cd frontend
npm install
npm run dev

# Run tests
cd backend
pytest
pytest --cov=app  # with coverage

# Celery worker (for background tasks)
celery -A app.core.celery_app worker --loglevel=info

# Celery beat (for scheduled tasks)
celery -A app.core.celery_app beat --loglevel=info
```

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     FRONTEND (React)                          │
│  Dashboard │ Predictions │ Bet Tracker │ Analytics │ Settings │
└──────────────────────────────────────────────────────────────┘
                              │
                    HTTP/REST + WebSocket
                              │
┌──────────────────────────────────────────────────────────────┐
│                   BACKEND (FastAPI + Celery)                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ API: /predictions, /props, /bets, /analytics, /backtest │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ ML: XGBoost + LightGBM + CatBoost → Ensemble → Calibrate│ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Tasks: Fetch odds, Update predictions, Settle bets      │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
         │                    │                    │
┌────────┴───────┐   ┌───────┴───────┐   ┌───────┴────────┐
│  PostgreSQL    │   │    Redis      │   │  External APIs │
│  + TimescaleDB │   │  (cache/jobs) │   │  (odds, stats) │
└────────────────┘   └───────────────┘   └────────────────┘
```

---

## Project Structure

```
sports model/
├── backend/
│   ├── app/
│   │   ├── api/routes/        # REST endpoints
│   │   ├── core/              # Config, database, celery
│   │   ├── models/            # SQLAlchemy models
│   │   └── services/          # Business logic
│   ├── data/apis/             # Data fetchers (NBA, NFL, etc.)
│   ├── ml/
│   │   ├── features/          # Feature engineering
│   │   ├── models/            # ML models (XGB, ensemble)
│   │   ├── training/          # Training pipelines
│   │   ├── prediction/        # Prediction service
│   │   └── saved_models/      # Trained model files
│   ├── scripts/
│   │   ├── backfill_all_sports.py    # Historical data import
│   │   ├── export_training_data.py   # DB → CSV export
│   │   └── run_training_pipeline.py  # Full training pipeline
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/             # React pages
│   │   ├── components/        # UI components
│   │   ├── hooks/             # Custom hooks
│   │   └── stores/            # Zustand state
│   └── package.json
├── docker-compose.yml
├── .env                       # Your configuration (create this)
└── README.md
```

---

## Scheduled Tasks (Automatic)

Once running, these tasks execute automatically:

| Task | Frequency | Description |
|------|-----------|-------------|
| Fetch odds | Every 1 min | Get latest odds from all sportsbooks |
| Update predictions | Every 5 min | Regenerate predictions with new odds |
| Collect NBA data | Daily 6 AM UTC | Fetch yesterday's game results |
| Collect NFL data | Tuesday 6 AM UTC | Fetch weekly game results |
| Collect MLB data | Daily 7 AM UTC | Fetch yesterday's game results |
| Settle bets | Every 1 hour | Update bet outcomes |
| Retrain models | Daily 4 AM UTC | Retrain with new data |
| Health check | Every 10 min | Verify services are running |

---

## Troubleshooting

### "No predictions available"

1. Make sure you've run the backfill: `python scripts/backfill_all_sports.py --sport all`
2. Make sure you've trained models: `python scripts/run_training_pipeline.py`
3. Check if there are games today (off-season = no games)

### "ODDS_API_KEY not set"

Add your API key to `.env`:
```
ODDS_API_KEY=your_key_here
```

### Database connection errors

1. Make sure Docker is running: `docker-compose ps`
2. Check database logs: `docker-compose logs db`
3. Restart: `docker-compose restart db`

### Frontend won't start

```bash
cd frontend
rm -rf node_modules
npm install
npm run dev
```

### Model training fails

1. Make sure you have data: `python scripts/backfill_all_sports.py --sport nba`
2. Export the data: `python scripts/export_training_data.py --sport nba`
3. Check the export file exists: `ls data/historical/`

### Port already in use

```bash
# Find what's using the port
lsof -i :8000

# Kill it or use a different port
docker-compose down
# Edit docker-compose.yml to use different ports
docker-compose up -d
```

---

## API Documentation

Once running, full API docs are at: http://localhost:8000/docs

**Key Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/predictions` | GET | Get predictions by sport/date |
| `/api/v1/predictions/value` | GET | Get value bets (edge > threshold) |
| `/api/v1/props` | GET | Player prop predictions |
| `/api/v1/bets` | GET/POST | List/create bets |
| `/api/v1/analytics/roi` | GET | ROI breakdown |
| `/api/v1/backtest` | POST | Run backtest simulation |
| `/ws/odds` | WebSocket | Real-time odds updates |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui |
| State | Zustand (local), TanStack Query (server) |
| Backend | FastAPI, Python 3.11+, Celery |
| Database | PostgreSQL 15 + TimescaleDB |
| Cache | Redis |
| ML | XGBoost, LightGBM, CatBoost, scikit-learn |
| Data | nba_api, nfl_data_py, pybaseball, The Odds API |

---

## Support

- **Architecture details:** See `ARCHITECTURE_PLAN.md`
- **Issues:** Check the troubleshooting section above
- **Code questions:** The codebase is well-documented with docstrings

---

## License

Personal use only. Not for commercial deployment.
