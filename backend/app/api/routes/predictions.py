"""
Predictions API endpoints.

Provides both database-backed predictions and live ML predictions.
"""
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from loguru import logger

from app.core.database import get_db
from app.models.game import Game, Sport, GameStatus, Team
from app.models.prediction import Prediction, PredictionType

# Import ML prediction service
try:
    from ml.prediction import prediction_service, get_predictions as ml_get_predictions, get_value_bets as ml_get_value_bets
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("ML prediction service not available")


router = APIRouter()


# Pydantic schemas
class ConfidenceInterval(BaseModel):
    lower: float
    upper: float
    confidence_level: float = 0.9


class MoneylinePrediction(BaseModel):
    home_prob: float
    away_prob: float
    draw_prob: Optional[float] = None  # For soccer


class SpreadPrediction(BaseModel):
    predicted_spread: float
    home_cover_prob: float
    push_prob: float


class TotalPrediction(BaseModel):
    predicted_total: float
    over_prob: float
    under_prob: float


class PredictionResponse(BaseModel):
    game_id: int
    prediction_type: str
    model_version: str
    prediction: dict
    confidence: Optional[ConfidenceInterval] = None
    edge: Optional[float] = None
    expected_value: Optional[float] = None
    model_agreement: Optional[float] = None
    feature_importance: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


class GameWithPredictions(BaseModel):
    id: int
    sport: str
    home_team: str
    away_team: str
    scheduled_time: datetime
    status: str
    predictions: dict  # {moneyline: {...}, spread: {...}, total: {...}}

    class Config:
        alias_generator = to_camel
        populate_by_name = True


@router.get("/", response_model=List[GameWithPredictions])
async def get_predictions(
    sport: Optional[Sport] = Query(None, description="Filter by sport"),
    date: Optional[date] = Query(None, description="Filter by game date"),
    prediction_types: Optional[str] = Query(
        "moneyline,spread,total",
        description="Comma-separated prediction types"
    ),
    min_edge: Optional[float] = Query(None, description="Minimum edge to include"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get predictions for upcoming games.

    Returns games with their associated predictions, optionally filtered
    by sport, date, prediction types, and minimum edge.
    """
    # Build query with eager loading of team relationships
    query = (
        select(Game)
        .options(selectinload(Game.home_team), selectinload(Game.away_team))
        .where(Game.status == GameStatus.SCHEDULED)
    )

    if sport:
        query = query.where(Game.sport == sport)

    if date:
        start = datetime.combine(date, datetime.min.time())
        end = datetime.combine(date, datetime.max.time())
        query = query.where(Game.scheduled_time.between(start, end))

    query = query.order_by(Game.scheduled_time)

    result = await db.execute(query)
    games = result.scalars().all()

    # Get predictions for each game
    response = []
    types = [PredictionType(t.strip()) for t in prediction_types.split(",")]

    for game in games:
        pred_query = select(Prediction).where(
            Prediction.game_id == game.id,
            Prediction.prediction_type.in_(types)
        )

        if min_edge is not None:
            pred_query = pred_query.where(Prediction.edge >= min_edge)

        pred_result = await db.execute(pred_query)
        predictions = pred_result.scalars().all()

        pred_dict = {
            pred.prediction_type.value: {
                "prediction": pred.prediction,
                "confidence": pred.confidence,
                "edge": pred.edge,
                "ev": pred.expected_value,
                "model_agreement": pred.model_agreement
            }
            for pred in predictions
        }

        response.append(GameWithPredictions(
            id=game.id,
            sport=game.sport.value,
            home_team=game.home_team.name if game.home_team else "TBD",
            away_team=game.away_team.name if game.away_team else "TBD",
            scheduled_time=game.scheduled_time,
            status=game.status.value,
            predictions=pred_dict
        ))

    return response


@router.get("/game/{game_id}", response_model=dict)
async def get_game_prediction(
    game_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed predictions for a specific game.

    Returns all prediction types with full details including
    feature importance and model agreement.
    """
    # Get game with relationships
    query = (
        select(Game)
        .options(
            selectinload(Game.home_team),
            selectinload(Game.away_team),
            selectinload(Game.venue)
        )
        .where(Game.id == game_id)
    )
    result = await db.execute(query)
    game = result.scalars().first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Get all predictions
    pred_query = select(Prediction).where(Prediction.game_id == game_id)
    result = await db.execute(pred_query)
    predictions = result.scalars().all()

    return {
        "game": {
            "id": game.id,
            "sport": game.sport.value,
            "home_team": game.home_team.name if game.home_team else "TBD",
            "away_team": game.away_team.name if game.away_team else "TBD",
            "scheduled_time": game.scheduled_time,
            "status": game.status.value,
            "venue": game.venue.name if game.venue else None,
            "weather": game.weather_conditions,
        },
        "predictions": {
            pred.prediction_type.value: {
                "prediction": pred.prediction,
                "confidence": pred.confidence,
                "edge": pred.edge,
                "ev": pred.expected_value,
                "model_version": pred.model_version,
                "model_agreement": pred.model_agreement,
                "feature_importance": pred.feature_importance,
                "market_line": pred.market_line,
                "market_odds": pred.market_odds,
                "created_at": pred.created_at.isoformat()
            }
            for pred in predictions
        },
        "value_bets": [
            {
                "type": pred.prediction_type.value,
                "edge": pred.edge,
                "ev": pred.expected_value,
                "confidence": pred.model_agreement
            }
            for pred in predictions
            if pred.edge and pred.edge > 0.02  # 2% edge threshold
        ]
    }


@router.get("/value", response_model=List[dict])
async def get_value_bets(
    sport: Optional[Sport] = Query(None),
    min_edge: float = Query(0.03, description="Minimum edge (default 3%)"),
    min_ev: Optional[float] = Query(None, description="Minimum expected value"),
    min_confidence: Optional[float] = Query(None, description="Minimum model agreement"),
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current value bets across all upcoming games.

    Returns predictions with positive edge, sorted by expected value.
    """
    # Get upcoming games
    game_query = select(Game.id).where(
        Game.status == GameStatus.SCHEDULED,
        Game.scheduled_time > datetime.utcnow()
    )

    if sport:
        game_query = game_query.where(Game.sport == sport)

    # Get predictions with edge
    query = select(Prediction).where(
        Prediction.game_id.in_(game_query),
        Prediction.edge >= min_edge
    )

    if min_ev is not None:
        query = query.where(Prediction.expected_value >= min_ev)

    if min_confidence is not None:
        query = query.where(Prediction.model_agreement >= min_confidence)

    query = query.order_by(Prediction.expected_value.desc()).limit(limit)

    result = await db.execute(query)
    predictions = result.scalars().all()

    return [
        {
            "game_id": pred.game_id,
            "prediction_type": pred.prediction_type.value,
            "selection": _get_selection(pred),
            "edge": pred.edge,
            "ev": pred.expected_value,
            "our_prob": pred.prediction.get("home_prob") or pred.prediction.get("over_prob"),
            "market_odds": pred.market_odds,
            "market_line": pred.market_line,
            "model_agreement": pred.model_agreement,
            "confidence": pred.confidence
        }
        for pred in predictions
    ]


def _get_selection(pred: Prediction) -> str:
    """Helper to format selection string."""
    if pred.prediction_type == PredictionType.MONEYLINE:
        if pred.prediction.get("home_prob", 0) > pred.prediction.get("away_prob", 0):
            return "Home ML"
        return "Away ML"
    elif pred.prediction_type == PredictionType.SPREAD:
        return f"Home {pred.market_line:+.1f}"
    elif pred.prediction_type == PredictionType.TOTAL:
        if pred.prediction.get("over_prob", 0) > 0.5:
            return f"Over {pred.market_line}"
        return f"Under {pred.market_line}"
    return "Unknown"


# ============================================================================
# Live ML Prediction Endpoints (no database required)
# ============================================================================

class LivePredictionResponse(BaseModel):
    """Response model for live ML predictions."""
    game_id: str
    sport: str
    date: str
    home_team: str
    away_team: str
    home_win_prob: float
    away_win_prob: float
    draw_prob: Optional[float] = None
    predicted_spread: Optional[float] = None
    predicted_total: Optional[float] = None
    home_ml_edge: Optional[float] = None
    away_ml_edge: Optional[float] = None
    recommended_bet: Optional[str] = None
    kelly_fraction: Optional[float] = None
    confidence: Optional[str] = None
    generated_at: str


class ValueBetResponse(BaseModel):
    """Response model for value bets."""
    game_id: str
    game: str
    bet_type: str
    selection: str
    odds: Optional[int] = None
    model_prob: float
    edge: float
    kelly: float
    confidence: Optional[str] = None


@router.get("/live/{sport}", response_model=List[LivePredictionResponse])
async def get_live_predictions(
    sport: str,
    refresh: bool = Query(False, description="Force refresh predictions")
):
    """
    Get live ML predictions for today's games.

    This endpoint uses the ML prediction service directly without database,
    generating real-time predictions based on current team stats.

    Args:
        sport: Sport code (nba, nfl, mlb, soccer)
        refresh: Force refresh even if cached
    """
    if not ML_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ML prediction service not available"
        )

    sport = sport.lower()
    if sport not in ['nba', 'nfl', 'mlb', 'soccer']:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sport: {sport}. Valid options: nba, nfl, mlb, soccer"
        )

    try:
        predictions = prediction_service.get_todays_predictions(sport, refresh=refresh)

        return [
            LivePredictionResponse(
                game_id=p.game_id,
                sport=p.sport,
                date=p.date,
                home_team=p.home_team,
                away_team=p.away_team,
                home_win_prob=p.home_win_prob,
                away_win_prob=p.away_win_prob,
                draw_prob=p.draw_prob,
                predicted_spread=p.predicted_spread,
                predicted_total=p.predicted_total,
                home_ml_edge=p.home_ml_edge,
                away_ml_edge=p.away_ml_edge,
                recommended_bet=p.recommended_bet,
                kelly_fraction=p.kelly_fraction,
                confidence=p.confidence,
                generated_at=p.generated_at,
            )
            for p in predictions
        ]
    except Exception as e:
        logger.error(f"Error generating live predictions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating predictions: {str(e)}"
        )


@router.get("/live/{sport}/value", response_model=List[ValueBetResponse])
async def get_live_value_bets(
    sport: str,
    min_edge: float = Query(0.03, description="Minimum edge (default 3%)"),
    min_kelly: float = Query(0.01, description="Minimum Kelly fraction (default 1%)")
):
    """
    Get live value betting opportunities.

    Returns predictions where the model finds positive expected value
    compared to current market odds.

    Args:
        sport: Sport code
        min_edge: Minimum edge required (default 3%)
        min_kelly: Minimum Kelly fraction (default 1%)
    """
    if not ML_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ML prediction service not available"
        )

    sport = sport.lower()
    if sport not in ['nba', 'nfl', 'mlb', 'soccer']:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sport: {sport}"
        )

    try:
        value_bets = prediction_service.find_value_bets(
            sport,
            min_edge=min_edge,
            min_kelly=min_kelly
        )

        return [
            ValueBetResponse(**bet)
            for bet in value_bets
        ]
    except Exception as e:
        logger.error(f"Error finding value bets: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error finding value bets: {str(e)}"
        )


@router.get("/live/{sport}/summary")
async def get_predictions_summary(sport: str):
    """
    Get summary of today's predictions for a sport.

    Returns count of games, high confidence picks, and value bets.
    """
    if not ML_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ML prediction service not available"
        )

    sport = sport.lower()
    if sport not in ['nba', 'nfl', 'mlb', 'soccer']:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sport: {sport}"
        )

    try:
        return prediction_service.get_predictions_summary(sport)
    except Exception as e:
        logger.error(f"Error getting predictions summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/live/all")
async def get_all_live_predictions():
    """
    Get live predictions for all sports.

    Returns summary and predictions for NBA, NFL, MLB, and Soccer.
    """
    if not ML_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ML prediction service not available"
        )

    results = {}
    for sport in ['nba', 'nfl', 'mlb', 'soccer']:
        try:
            summary = prediction_service.get_predictions_summary(sport)
            results[sport] = summary
        except Exception as e:
            logger.warning(f"Error getting {sport} predictions: {e}")
            results[sport] = {"error": str(e)}

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(),
        "sports": results,
    }
