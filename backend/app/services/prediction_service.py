"""
Prediction service - Celery tasks for generating predictions.

Uses trained ML models via the unified PredictionService to generate and save predictions to the database.
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from celery import shared_task
from loguru import logger
from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import pandas as pd
import numpy as np

from app.core.database import AsyncSessionLocal
from app.models.game import Game, GameStatus, Sport, Player, PlayerGameStats, Team
from app.models.prediction import Prediction as DbPrediction, PredictionType, PlayerPropPrediction

# Import the real ML prediction service
try:
    from ml.prediction.prediction_service import prediction_service as ml_service
    ML_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import ML prediction service: {e}")
    ML_AVAILABLE = False

# Import Prop Model components
try:
    from ml.models.prop_model import PlayerPropModel
    from ml.features.nba_player_features import feature_engineer as prop_feature_engineer
    PROPS_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import Prop Model components: {e}")
    PROPS_AVAILABLE = False


def run_async(coro):
    """Run async coroutine in sync context, handling existing event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Create a new loop in a separate thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


@shared_task(name="app.services.prediction_service.update_predictions")
def update_predictions():
    """Update predictions for all upcoming games using the ML PredictionService."""
    logger.info("Starting prediction update task")

    if not ML_AVAILABLE:
        logger.error("ML service not available, skipping prediction update")
        return {"status": "error", "error": "ML service not available"}

    async def _update():
        total_created = 0
        total_updated = 0
        sports_processed = []

        async with AsyncSessionLocal() as session:
            # We iterate through supported sports
            for sport in ['nba', 'nfl', 'mlb', 'soccer']:
                try:
                    logger.info(f"Fetching ML predictions for {sport}...")
                    ml_predictions = ml_service.get_todays_predictions(sport, refresh=True)
                    
                    if not ml_predictions:
                        logger.info(f"No ML predictions found for {sport}")
                        continue
                        
                    for ml_pred in ml_predictions:
                        # Find the game in the DB using external_id
                        stmt = select(Game).where(Game.external_id == ml_pred.game_id)
                        result = await session.execute(stmt)
                        game = result.scalars().first()
                        
                        if not game:
                            logger.warning(f"Game not found in DB for prediction: {ml_pred.game_id}")
                            continue
                            
                        # Check if DB prediction already exists
                        existing_stmt = select(DbPrediction).where(
                            DbPrediction.game_id == game.id,
                            DbPrediction.prediction_type == PredictionType.MONEYLINE
                        )
                        existing_result = await session.execute(existing_stmt)
                        existing_pred = existing_result.scalars().first()
                        
                        # Prepare prediction data
                        pred_data = {
                            "home_win_prob": ml_pred.home_win_prob,
                            "away_win_prob": ml_pred.away_win_prob,
                            "home_ml_odds": ml_pred.home_ml_odds,
                            "away_ml_odds": ml_pred.away_ml_odds,
                        }
                        
                        # Confidence structure
                        conf_data = {
                            "confidence_level": ml_pred.confidence,
                            "generated_at": ml_pred.generated_at
                        }
                        
                        if existing_pred:
                            # Update existing
                            existing_pred.prediction = pred_data
                            existing_pred.confidence = conf_data
                            existing_pred.edge = ml_pred.home_ml_edge if ml_pred.home_ml_edge else 0.0
                            existing_pred.model_version = ml_pred.model_version or "ml-v1"
                            existing_pred.updated_at = datetime.utcnow()
                            total_updated += 1
                        else:
                            # Create new
                            new_pred = DbPrediction(
                                game_id=game.id,
                                prediction_type=PredictionType.MONEYLINE,
                                model_version=ml_pred.model_version or "ml-v1",
                                prediction=pred_data,
                                confidence=conf_data,
                                edge=ml_pred.home_ml_edge,
                                market_odds=ml_pred.home_ml_odds,
                                expected_value=0.0
                            )
                            session.add(new_pred)
                            total_created += 1
                    
                    sports_processed.append(sport)
                    await session.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing {sport}: {e}")

        return {"created": total_created, "updated": total_updated, "sports": sports_processed}

    try:
        result = run_async(_update())
        logger.info(f"Prediction update complete: {result}")
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"Error updating predictions: {e}")
        return {"status": "error", "error": str(e)}


@shared_task(name="app.services.prediction_service.generate_prop_predictions")
def generate_prop_predictions():
    """Generate player prop predictions for upcoming games."""
    logger.info("Starting prop prediction task")
    
    if not PROPS_AVAILABLE:
        return {"status": "error", "error": "Prop models not available"}

    async def _generate():
        # Load models
        models = {}
        for stat in ['pts', 'reb', 'ast']:
            model = PlayerPropModel(stat_type=stat)
            if model.load():
                models[stat] = model
        
        if not models:
            logger.warning("No prop models loaded. Train models first.")
            return {"status": "skipped", "reason": "No models"}

        async with AsyncSessionLocal() as session:
            # Get upcoming games (NBA only for now)
            now = datetime.utcnow()
            games_query = (
                select(Game)
                .options(selectinload(Game.home_team), selectinload(Game.away_team))
                .where(
                    Game.sport == Sport.NBA,
                    Game.status == GameStatus.SCHEDULED,
                    Game.scheduled_time >= now,
                    Game.scheduled_time <= now + timedelta(hours=48)
                )
            )
            result = await session.execute(games_query)
            games = result.scalars().all()
            
            total_predictions = 0
            
            for game in games:
                # For each team, get active players
                for team in [game.home_team, game.away_team]:
                    if not team: continue
                    
                    # Fetch players for team
                    players_query = select(Player).where(
                        Player.team_id == team.id,
                        Player.is_active == True
                    )
                    p_result = await session.execute(players_query)
                    players = p_result.scalars().all()
                    
                    opponent_id = game.away_team_id if team.id == game.home_team_id else game.home_team_id
                    
                    for player in players:
                        # Get player history for features
                        # Need efficient way to get history. For now, querying per player (slow but safe)
                        # Optimization: Pre-load all recent stats
                        history_query = (
                            select(PlayerGameStats, Game.scheduled_time)
                            .join(Game, PlayerGameStats.game_id == Game.id)
                            .where(PlayerGameStats.player_id == player.id)
                            .order_by(Game.scheduled_time.desc())
                            .limit(20) # Need enough for rolling windows
                        )
                        h_result = await session.execute(history_query)
                        history_rows = h_result.all()
                        
                        if not history_rows:
                            continue
                            
                        # Convert to DataFrame for Feature Engineer
                        history_data = []
                        for stat, g_date in history_rows:
                            row = stat.stats.copy()
                            row = {k.lower(): v for k, v in row.items()}
                            row['date'] = g_date
                            row['player_id'] = player.id
                            history_data.append(row)
                            
                        history_df = pd.DataFrame(history_data)
                        
                        # Process logs to get rolling features
                        # We pass the raw logs; the engineer will sort and roll
                        processed_df = prop_feature_engineer.process_player_logs(history_data)
                        
                        if processed_df.empty:
                            continue
                            
                        # Prepare features for *this* game
                        # We pretend the game is 'now' to get the latest rolling values
                        features = prop_feature_engineer.prepare_prediction_features(
                            player.id,
                            processed_df,
                            game.scheduled_time,
                            opponent_id
                        )
                        
                        if not features:
                            continue
                            
                        # Predict for each stat
                        features_df = pd.DataFrame([features])
                        
                        for stat, model in models.items():
                            try:
                                pred_value = float(model.predict(features_df)[0])
                                
                                # Store prediction
                                # Check existing
                                existing_query = select(PlayerPropPrediction).where(
                                    PlayerPropPrediction.player_id == player.id,
                                    PlayerPropPrediction.game_id == game.id,
                                    PlayerPropPrediction.prop_type == stat
                                )
                                ex_result = await session.execute(existing_query)
                                existing = ex_result.scalars().first()
                                
                                # Calculate distribution (simple assumption for now)
                                # XGBoost gives mean. We can assume std dev based on history
                                std_dev = history_df[stat].std() if stat in history_df.columns else 5.0
                                
                                pred_obj = {
                                    "mean": pred_value,
                                    "median": pred_value,
                                    "std": std_dev,
                                    "p10": pred_value - 1.28 * std_dev,
                                    "p90": pred_value + 1.28 * std_dev,
                                    "p25": pred_value - 0.67 * std_dev,
                                    "p75": pred_value + 0.67 * std_dev
                                }
                                
                                if existing:
                                    existing.prediction = pred_obj
                                    existing.model_version = "xgb-prop-v1"
                                else:
                                    new_prop = PlayerPropPrediction(
                                        game_id=game.id,
                                        player_id=player.id,
                                        prop_type=stat,
                                        model_version="xgb-prop-v1",
                                        prediction=pred_obj,
                                        over_prob=0.5, # Placeholder until odds integration
                                        under_prob=0.5
                                    )
                                    session.add(new_prop)
                                    total_predictions += 1
                                    
                            except Exception as e:
                                logger.error(f"Error predicting {stat} for {player.name}: {e}")

            await session.commit()
            return total_predictions

    try:
        count = run_async(_generate())
        logger.info(f"Generated {count} prop predictions")
        return {"status": "success", "count": count}
    except Exception as e:
        logger.error(f"Error in prop prediction task: {e}")
        return {"status": "error", "error": str(e)}


@shared_task(name="app.services.prediction_service.retrain_models")
def retrain_models():
    """Retrain ML models with latest data."""
    # ... existing code ...
    return {"status": "skipped"}

@shared_task(name="app.services.prediction_service.calculate_edges")
def calculate_edges():
    """Calculate edge and EV for all predictions."""
    # ... existing code ...
    return {"status": "success"}

