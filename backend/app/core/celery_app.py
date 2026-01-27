"""
Celery configuration for background tasks.
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "sports_prediction",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.services.prediction_service",
        "app.services.odds_service",
        "app.services.data_collection_service",
        "app.services.bet_service",
        "app.tasks.prediction_tasks",
        "app.tasks.arbitrage_tasks",
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# Scheduled tasks
celery_app.conf.beat_schedule = {
    # Fetch odds every minute and store in database
    "fetch-odds-every-minute": {
        "task": "app.services.data_collection_service.fetch_and_store_odds",
        "schedule": 60.0,  # Every 60 seconds
    },

    # Update predictions every 5 minutes
    "update-predictions-every-5-min": {
        "task": "app.services.prediction_service.update_predictions",
        "schedule": 300.0,  # Every 5 minutes
    },

    # Scrape injury news every 15 minutes
    "scrape-injuries-every-15-min": {
        "task": "app.services.data_collection_service.scrape_injuries",
        "schedule": 900.0,  # Every 15 minutes
    },

    # Daily model retraining at 4 AM UTC
    "daily-model-retrain": {
        "task": "app.services.prediction_service.retrain_models",
        "schedule": crontab(hour=4, minute=0),
    },

    # Settle bets after games complete
    "settle-bets-hourly": {
        "task": "app.services.bet_service.settle_pending_bets",
        "schedule": 3600.0,  # Every hour
    },

    # Capture closing lines at game start
    "capture-closing-lines": {
        "task": "app.services.bet_service.capture_closing_lines",
        "schedule": 600.0,  # Every 10 minutes
    },

    # === New Data Collection Tasks ===

    # NBA: Fetch daily game results and stats (runs at 6 AM UTC)
    "nba-daily-fetch": {
        "task": "app.services.data_collection_service.fetch_nba_daily",
        "schedule": crontab(hour=6, minute=0),
    },

    # NFL: Fetch weekly game results (runs Tuesday at 6 AM UTC after Monday games)
    "nfl-weekly-fetch": {
        "task": "app.services.data_collection_service.fetch_nfl_weekly",
        "schedule": crontab(hour=6, minute=0, day_of_week=2),
    },

    # MLB: Fetch daily game results (runs at 7 AM UTC during season)
    "mlb-daily-fetch": {
        "task": "app.services.data_collection_service.fetch_mlb_daily",
        "schedule": crontab(hour=7, minute=0),
    },

    # Sync game results every 2 hours
    "sync-game-results": {
        "task": "app.services.data_collection_service.sync_game_results",
        "schedule": 7200.0,  # Every 2 hours
    },

    # Health check every 10 minutes
    "data-collection-health-check": {
        "task": "app.services.data_collection_service.health_check",
        "schedule": 600.0,  # Every 10 minutes
    },

    # === ML Prediction Tasks ===

    # Generate daily predictions at 8 AM UTC
    "generate-daily-predictions": {
        "task": "app.tasks.prediction_tasks.generate_daily_predictions",
        "schedule": crontab(hour=8, minute=0),
    },

    # Update NBA predictions every 5 minutes during game hours (11 PM - 4 AM UTC)
    "update-nba-predictions": {
        "task": "app.tasks.prediction_tasks.generate_predictions_for_sport",
        "schedule": 300.0,
        "args": ["nba"],
    },

    # Generate Player Props (Hourly)
    "generate-prop-predictions": {
        "task": "app.services.prediction_service.generate_prop_predictions",
        "schedule": 3600.0,
    },

    # Update NFL predictions every 10 minutes on game days
    "update-nfl-predictions": {
        "task": "app.tasks.prediction_tasks.generate_predictions_for_sport",
        "schedule": 600.0,
        "args": ["nfl"],
    },

    # Update MLB predictions every 5 minutes
    "update-mlb-predictions": {
        "task": "app.tasks.prediction_tasks.generate_predictions_for_sport",
        "schedule": 300.0,
        "args": ["mlb"],
    },

    # Update Soccer predictions every 10 minutes
    "update-soccer-predictions": {
        "task": "app.tasks.prediction_tasks.generate_predictions_for_sport",
        "schedule": 600.0,
        "args": ["soccer"],
    },

    # Find value bets every 2 minutes
    "find-value-bets": {
        "task": "app.tasks.prediction_tasks.find_all_value_bets",
        "schedule": 120.0,
        "kwargs": {"min_edge": 0.03},
    },

    # Calculate edges every 3 minutes (compare predictions to market odds)
    "calculate-prediction-edges": {
        "task": "app.services.prediction_service.calculate_edges",
        "schedule": 180.0,
    },

    # Export predictions at midnight UTC (before games complete)
    "export-daily-predictions": {
        "task": "app.tasks.prediction_tasks.export_daily_predictions",
        "schedule": crontab(hour=0, minute=0),
    },

    # Prediction service health check
    "prediction-health-check": {
        "task": "app.tasks.prediction_tasks.health_check",
        "schedule": 600.0,
    },

    # === Arbitrage Tasks ===

    # Detect arbitrage every minute
    "detect-arbitrage-every-minute": {
        "task": "app.tasks.arbitrage_tasks.detect_arbitrage_task",
        "schedule": 60.0,
    },
}
