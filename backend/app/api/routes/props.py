"""
Player Props API endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.models.game import Player, Game
from app.models.prediction import PlayerPropPrediction


router = APIRouter()


class PropProjection(BaseModel):
    p10: float
    p25: float
    median: float
    p75: float
    p90: float
    mean: float
    std: float


class PropPredictionResponse(BaseModel):
    player_id: int
    player_name: str
    prop_type: str
    projection: PropProjection
    market_line: Optional[float]
    over_prob: float
    under_prob: float
    over_edge: Optional[float]
    under_edge: Optional[float]
    over_ev: Optional[float]
    under_ev: Optional[float]
    recommendation: Optional[str]  # "over", "under", or None


@router.get("/{player_id}", response_model=List[PropPredictionResponse])
async def get_player_props(
    player_id: int,
    game_id: Optional[int] = Query(None, description="Specific game"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get prop predictions for a specific player.

    Returns all prop types with full distributions and edge calculations.
    """
    # Verify player exists
    player = await db.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Get predictions
    query = select(PlayerPropPrediction).where(
        PlayerPropPrediction.player_id == player_id
    )

    if game_id:
        query = query.where(PlayerPropPrediction.game_id == game_id)

    query = query.order_by(PlayerPropPrediction.created_at.desc())

    result = await db.execute(query)
    predictions = result.scalars().all()

    return [
        PropPredictionResponse(
            player_id=player_id,
            player_name=player.name,
            prop_type=pred.prop_type,
            projection=PropProjection(**pred.prediction),
            market_line=pred.market_line,
            over_prob=pred.over_prob,
            under_prob=pred.under_prob,
            over_edge=pred.over_edge,
            under_edge=pred.under_edge,
            over_ev=pred.over_ev,
            under_ev=pred.under_ev,
            recommendation=_get_recommendation(pred)
        )
        for pred in predictions
    ]


@router.get("/game/{game_id}", response_model=List[PropPredictionResponse])
async def get_game_props(
    game_id: int,
    prop_type: Optional[str] = Query(None, description="Filter by prop type"),
    min_edge: float = Query(0.0, description="Minimum edge to include"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all player prop predictions for a game.

    Returns props for all players in the game with edge calculations.
    """
    # Verify game exists
    game = await db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Get predictions
    query = select(PlayerPropPrediction).where(
        PlayerPropPrediction.game_id == game_id
    )

    if prop_type:
        query = query.where(PlayerPropPrediction.prop_type == prop_type)

    result = await db.execute(query)
    predictions = result.scalars().all()

    # Filter by edge
    filtered = []
    for pred in predictions:
        max_edge = max(abs(pred.over_edge or 0), abs(pred.under_edge or 0))
        if max_edge >= min_edge:
            # Get player name
            player = await db.get(Player, pred.player_id)
            filtered.append(PropPredictionResponse(
                player_id=pred.player_id,
                player_name=player.name if player else "Unknown",
                prop_type=pred.prop_type,
                projection=PropProjection(**pred.prediction),
                market_line=pred.market_line,
                over_prob=pred.over_prob,
                under_prob=pred.under_prob,
                over_edge=pred.over_edge,
                under_edge=pred.under_edge,
                over_ev=pred.over_ev,
                under_ev=pred.under_ev,
                recommendation=_get_recommendation(pred)
            ))

    # Sort by absolute edge
    filtered.sort(
        key=lambda x: max(abs(x.over_edge or 0), abs(x.under_edge or 0)),
        reverse=True
    )

    return filtered


@router.get("/value", response_model=List[dict])
async def get_value_props(
    sport: Optional[str] = Query(None),
    prop_type: Optional[str] = Query(None),
    min_edge: float = Query(0.05, description="Minimum edge (default 5%)"),
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Get best value player props across all games.

    Returns props with positive edge, sorted by expected value.
    """
    query = select(PlayerPropPrediction)

    if prop_type:
        query = query.where(PlayerPropPrediction.prop_type == prop_type)

    result = await db.execute(query)
    predictions = result.scalars().all()

    # Find props with edge
    value_props = []
    for pred in predictions:
        over_edge = pred.over_edge or 0
        under_edge = pred.under_edge or 0

        if over_edge >= min_edge:
            player = await db.get(Player, pred.player_id)
            value_props.append({
                "player_id": pred.player_id,
                "player_name": player.name if player else "Unknown",
                "game_id": pred.game_id,
                "prop_type": pred.prop_type,
                "selection": "over",
                "line": pred.market_line,
                "projection": pred.prediction.get("median"),
                "prob": pred.over_prob,
                "edge": over_edge,
                "ev": pred.over_ev
            })

        if under_edge >= min_edge:
            player = await db.get(Player, pred.player_id)
            value_props.append({
                "player_id": pred.player_id,
                "player_name": player.name if player else "Unknown",
                "game_id": pred.game_id,
                "prop_type": pred.prop_type,
                "selection": "under",
                "line": pred.market_line,
                "projection": pred.prediction.get("median"),
                "prob": pred.under_prob,
                "edge": under_edge,
                "ev": pred.under_ev
            })

    # Sort by EV
    value_props.sort(key=lambda x: x.get("ev", 0) or 0, reverse=True)

    return value_props[:limit]


def _get_recommendation(pred: PlayerPropPrediction) -> Optional[str]:
    """Determine recommendation based on edge."""
    min_edge = 0.03  # 3% edge threshold

    over_edge = pred.over_edge or 0
    under_edge = pred.under_edge or 0

    if over_edge >= min_edge and over_edge > under_edge:
        return "over"
    elif under_edge >= min_edge and under_edge > over_edge:
        return "under"

    return None
