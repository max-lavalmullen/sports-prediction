"""
Celery tasks for prediction generation and management.

These tasks run on a schedule to:
1. Generate predictions for upcoming games
2. Update odds and recalculate edges
3. Archive old predictions
4. Track prediction accuracy
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from celery import shared_task
from loguru import logger
import json

# Import prediction service
try:
    from ml.prediction import prediction_service
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("ML prediction service not available for tasks")


@shared_task(bind=True, max_retries=3)
def generate_daily_predictions(self, sports: Optional[List[str]] = None):
    """
    Generate predictions for all upcoming games.

    This task runs daily (early morning) to generate predictions
    for all games scheduled that day.

    Args:
        sports: List of sports to generate predictions for
    """
    if not ML_AVAILABLE:
        logger.error("ML prediction service not available")
        return {"error": "ML service not available"}

    if sports is None:
        sports = ['nba', 'nfl', 'mlb', 'soccer']

    results = {}
    total_predictions = 0

    for sport in sports:
        try:
            predictions = prediction_service.get_todays_predictions(sport, refresh=True)
            count = len(predictions)
            total_predictions += count

            # Save predictions to file
            prediction_service.save_predictions(sport)

            results[sport] = {
                "status": "success",
                "predictions": count,
                "high_confidence": sum(1 for p in predictions if p.confidence == "high"),
                "value_bets": len(prediction_service.find_value_bets(sport)),
            }

            logger.info(f"Generated {count} predictions for {sport}")

        except Exception as e:
            logger.error(f"Error generating {sport} predictions: {e}")
            results[sport] = {"status": "error", "error": str(e)}

    return {
        "timestamp": datetime.now().isoformat(),
        "total_predictions": total_predictions,
        "results": results,
    }


@shared_task(bind=True, max_retries=3)
def update_predictions_with_odds(self, sport: str):
    """
    Update existing predictions with latest odds.

    This task runs frequently to recalculate edges as odds change.

    Args:
        sport: Sport to update
    """
    if not ML_AVAILABLE:
        return {"error": "ML service not available"}

    try:
        # Refresh predictions to get new odds
        predictions = prediction_service.get_todays_predictions(sport, refresh=True)

        # Find value bets with updated odds
        value_bets = prediction_service.find_value_bets(sport)

        return {
            "sport": sport,
            "predictions_updated": len(predictions),
            "value_bets_found": len(value_bets),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error updating {sport} predictions: {e}")
        self.retry(exc=e, countdown=60)


@shared_task
def generate_predictions_for_sport(sport: str):
    """
    Generate predictions for a specific sport.

    Args:
        sport: Sport code (nba, nfl, mlb, soccer)
    """
    if not ML_AVAILABLE:
        return {"error": "ML service not available"}

    try:
        predictions = prediction_service.get_todays_predictions(sport, refresh=True)
        value_bets = prediction_service.find_value_bets(sport)

        return {
            "sport": sport,
            "predictions": len(predictions),
            "value_bets": len(value_bets),
            "high_confidence": sum(1 for p in predictions if p.confidence == "high"),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error generating {sport} predictions: {e}")
        return {"error": str(e)}


@shared_task
def find_all_value_bets(min_edge: float = 0.03):
    """
    Find value bets across all sports.

    Args:
        min_edge: Minimum edge required
    """
    if not ML_AVAILABLE:
        return {"error": "ML service not available"}

    all_bets = []

    for sport in ['nba', 'nfl', 'mlb', 'soccer']:
        try:
            bets = prediction_service.find_value_bets(sport, min_edge=min_edge)
            for bet in bets:
                bet['sport'] = sport
            all_bets.extend(bets)
        except Exception as e:
            logger.error(f"Error finding value bets for {sport}: {e}")

    # Sort by edge
    all_bets.sort(key=lambda x: x.get('edge', 0), reverse=True)

    return {
        "timestamp": datetime.now().isoformat(),
        "total_value_bets": len(all_bets),
        "bets": all_bets[:20],  # Top 20
    }


@shared_task
def export_daily_predictions():
    """
    Export all predictions to files for archival.

    Runs at end of day to save predictions before results come in.
    """
    if not ML_AVAILABLE:
        return {"error": "ML service not available"}

    exports = []

    for sport in ['nba', 'nfl', 'mlb', 'soccer']:
        try:
            prediction_service.save_predictions(sport)
            exports.append(sport)
        except Exception as e:
            logger.error(f"Error exporting {sport} predictions: {e}")

    return {
        "timestamp": datetime.now().isoformat(),
        "exported_sports": exports,
    }


@shared_task
def clear_prediction_cache():
    """Clear the prediction cache to force fresh predictions."""
    if not ML_AVAILABLE:
        return {"error": "ML service not available"}

    try:
        prediction_service._prediction_cache.clear()
        return {"status": "success", "message": "Cache cleared"}
    except Exception as e:
        return {"error": str(e)}


@shared_task
def health_check():
    """
    Health check for prediction service.

    Returns status of ML service and model availability.
    """
    status = {
        "timestamp": datetime.now().isoformat(),
        "ml_available": ML_AVAILABLE,
        "models_loaded": {},
    }

    if ML_AVAILABLE:
        for sport in ['nba', 'nfl', 'mlb', 'soccer']:
            model = prediction_service.load_model(sport)
            status["models_loaded"][sport] = model is not None

    return status


# Convenience task to run all updates
@shared_task
def update_all_predictions():
    """Update predictions for all sports."""
    results = {}

    for sport in ['nba', 'nfl', 'mlb', 'soccer']:
        result = generate_predictions_for_sport.delay(sport)
        results[sport] = "queued"

    return {
        "timestamp": datetime.now().isoformat(),
        "queued_sports": list(results.keys()),
    }
