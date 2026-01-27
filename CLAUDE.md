# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sports Prediction Platform: A real-time sports prediction system for NFL, NBA, MLB, and Soccer covering moneylines, spreads, totals, player props, and same-game parlay correlations.

## Build & Run Commands

### Start Development Environment
```bash
docker-compose up -d
```
This starts: PostgreSQL+TimescaleDB (port 5432), Redis (port 6379), FastAPI backend (port 8000), Celery worker/beat, React frontend (port 3000).

### Backend Only
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Only
```bash
cd frontend
npm install
npm run dev        # Development server
npm run build      # Production build (runs tsc && vite build)
npm run lint       # ESLint
```

### Run Tests
```bash
cd backend
pytest                          # All tests
pytest tests/test_file.py       # Single file
pytest -k "test_name"           # Single test by name
pytest --cov=app                # With coverage
```

## Architecture

### Backend Structure (FastAPI + Celery)
- `backend/app/main.py` - FastAPI app entry point, route registration
- `backend/app/api/routes/` - REST endpoints: predictions, props, backtest, bets, analytics
- `backend/app/api/websocket/` - WebSocket endpoints: odds streaming, alerts
- `backend/app/core/` - Config, database, Celery setup
- `backend/app/models/` - SQLAlchemy models: game, bet, prediction, odds
- `backend/app/services/` - Business logic layer

### ML Pipeline (backend/ml/)
- `features/` - Sport-specific feature engineering (nba_features.py, nfl_features.py)
- `models/` - Model implementations: base_model.py, xgb_model.py, ensemble.py, elo.py
- `training/` - Training orchestration (trainer.py)

The ML layer uses an ensemble architecture: sport-specific models (XGBoost/LightGBM/CatBoost) feed into a meta-learner for calibrated probability outputs.

### Frontend Structure (React + TypeScript)
- `frontend/src/App.tsx` - Main app with routing
- `frontend/src/pages/` - Page components: Dashboard, Analytics, Backtesting, BetTracker, Simulation, Settings
- `frontend/src/hooks/` - Custom hooks: useWebSocket, usePredictions, useBetting
- `frontend/src/stores/` - Zustand stores: settingsStore, alertStore

Tech stack: React 18, TypeScript, TanStack Query, Zustand, Recharts, shadcn/ui, Tailwind CSS, Vite.

### Database
PostgreSQL with TimescaleDB extension for time-series data. Schema in `backend/db/init/01_schema.sql`.

Key tables: teams, players, games, predictions, bets, odds_history (hypertable), prop_odds_history (hypertable).

### API Patterns
- REST: `/api/v1/predictions`, `/api/v1/props`, `/api/v1/backtest`, `/api/v1/bets`, `/api/v1/analytics`
- WebSocket: `/ws/odds`, `/ws/alerts`

## Environment Variables

Copy `.env.example` to `.env`. Key variables:
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis connection
- `ODDS_API_KEY` - For The Odds API
- `VITE_API_URL` / `VITE_WS_URL` - Frontend API endpoints
