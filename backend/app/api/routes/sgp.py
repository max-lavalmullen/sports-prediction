"""
SGP (Same-Game Parlay) API Endpoints.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.sgp_service import sgp_service

router = APIRouter()

class SGPLeg(BaseModel):
    type: str  # e.g., 'nba_player_points_over'
    prob: float
    description: Optional[str] = None

class SGPRequest(BaseModel):
    sport: str
    game_id: str
    legs: List[SGPLeg]
    market_odds_american: Optional[int] = None
    market_odds_decimal: Optional[float] = None

class SGPResponse(BaseModel):
    true_prob: float
    implied_prob: Optional[float] = None
    edge: Optional[float] = None
    ev: Optional[float] = None
    market_odds_american: Optional[int] = None
    market_odds_decimal: Optional[float] = None
    legs_count: int
    individual_probs: List[float]

@router.post("/calculate", response_model=SGPResponse)
async def calculate_sgp_probability(request: SGPRequest):
    """
    Calculate the true probability of a Same-Game Parlay using Monte Carlo simulation.
    
    Takes into account correlations between different legs (e.g., QB yards and WR yards).
    """
    if len(request.legs) < 2:
        raise HTTPException(status_code=400, detail="Parlay must have at least 2 legs")

    # Prepare legs for service
    legs_data = [{"type": leg.type, "prob": leg.prob} for leg in request.legs]
    
    # Calculate true prob
    result = sgp_service.calculate_parlay_probability(request.sport, legs_data)
    
    true_prob = result["true_prob"]
    
    # Calculate EV if odds provided
    odds_decimal = request.market_odds_decimal
    if not odds_decimal and request.market_odds_american:
        if request.market_odds_american > 0:
            odds_decimal = (request.market_odds_american / 100) + 1
        else:
            odds_decimal = (100 / abs(request.market_odds_american)) + 1
            
    response_data = {
        "true_prob": true_prob,
        "legs_count": result["legs"],
        "individual_probs": result["individual_probs"]
    }
    
    if odds_decimal:
        ev_calc = sgp_service.simulator.calculate_ev(true_prob, odds_decimal)
        response_data.update({
            "implied_prob": ev_calc["implied_prob"],
            "edge": ev_calc["edge"],
            "ev": ev_calc["ev"],
            "market_odds_decimal": odds_decimal,
            "market_odds_american": request.market_odds_american
        })
        
    return response_data

@router.get("/correlations/{sport}")
async def get_sport_correlations(sport: str):
    """Get all known correlations for a specific sport."""
    # This would ideally fetch all from DB
    return {"sport": sport, "message": "Fetching all correlations not yet implemented"}
