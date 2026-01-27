"""
Arbitrage Detection API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.arbitrage_service import arbitrage_service, ArbitrageOpportunity


router = APIRouter()


class StakeCalculation(BaseModel):
    stake1: float
    stake2: float
    stake3: Optional[float] = None
    book1: str
    book2: str
    book3: Optional[str] = None
    selection1: str
    selection2: str
    selection3: Optional[str] = None
    guaranteed_profit: float
    profit_pct: float


class ArbitrageResponse(BaseModel):
    game_id: str
    sport: str
    home_team: str
    away_team: str
    market_type: str
    opportunity_type: str
    book1: str
    selection1: str
    odds1: int
    line1: Optional[float]
    book2: str
    selection2: str
    odds2: int
    line2: Optional[float]
    book3: Optional[str] = None
    selection3: Optional[str] = None
    odds3: Optional[int] = None
    profit_pct: float
    stake1_pct: float
    stake2_pct: float
    stake3_pct: Optional[float] = 0.0
    middle_size: Optional[float] = None
    combined_hold: Optional[float] = None
    detected_at: str


@router.get("/{sport}", response_model=List[ArbitrageResponse])
async def get_arbitrage_opportunities(
    sport: str,
    include_arbs: bool = Query(True, description="Include true arbitrage"),
    include_middles: bool = Query(True, description="Include middle opportunities"),
    include_low_hold: bool = Query(False, description="Include low-hold markets"),
    max_hold: float = Query(2.0, description="Maximum hold % for low-hold filter"),
):
    """
    Find arbitrage and betting opportunities for a sport.

    **Opportunity Types:**
    - `arbitrage`: Guaranteed profit regardless of outcome (rare)
    - `middle`: Potential to win both sides if score lands in specific range
    - `low_hold`: Markets with low combined vig (< 2%)

    **Markets Checked:**
    - Moneylines (h2h)
    - Spreads (for middles)
    - Totals (for middles)

    Returns opportunities sorted by profit potential.
    """
    opportunities = arbitrage_service.find_all_opportunities(
        sport=sport,
        include_arbs=include_arbs,
        include_middles=include_middles,
        include_low_hold=include_low_hold,
        max_hold_pct=max_hold,
    )

    return [ArbitrageResponse(**o.to_dict()) for o in opportunities]


@router.get("/{sport}/arbs-only", response_model=List[ArbitrageResponse])
async def get_pure_arbitrage(sport: str):
    """
    Get only true arbitrage opportunities (guaranteed profit).

    These are rare and typically last only seconds to minutes.
    Requires accounts at multiple sportsbooks to execute.
    """
    opportunities = arbitrage_service.find_arbitrage(sport)
    return [ArbitrageResponse(**o.to_dict()) for o in opportunities]


@router.get("/{sport}/middles", response_model=List[ArbitrageResponse])
async def get_middles(sport: str):
    """
    Get middle betting opportunities.

    A middle is when you can bet both sides of a spread/total
    with a chance to win both if the final score lands in between.

    Example: Home -3 at Book A, Away +4.5 at Book B
    If Home wins by exactly 4, both bets win!
    """
    opportunities = arbitrage_service.find_middles(sport)
    return [ArbitrageResponse(**o.to_dict()) for o in opportunities]


@router.post("/calculate-stakes", response_model=StakeCalculation)
async def calculate_optimal_stakes(
    game_id: str,
    sport: str,
    total_stake: float = Query(..., gt=0, description="Total amount to wager"),
    book1: str = Query(..., description="Bookmaker for side 1"),
    book2: str = Query(..., description="Bookmaker for side 2"),
):
    """
    Calculate optimal stake allocation for an arbitrage opportunity.

    Given a total stake amount, returns how much to bet on each side
    to guarantee equal profit regardless of outcome.
    """
    # Find the specific opportunity
    opportunities = arbitrage_service.find_all_opportunities(sport)

    matching = [
        o for o in opportunities
        if o.game_id == game_id and o.book1 == book1 and o.book2 == book2
    ]

    if not matching:
        # Try reversed
        matching = [
            o for o in opportunities
            if o.game_id == game_id and o.book2 == book1 and o.book1 == book2
        ]

    if not matching:
        return StakeCalculation(
            stake1=0,
            stake2=0,
            book1=book1,
            book2=book2,
            selection1="Not found",
            selection2="Not found",
            guaranteed_profit=0,
            profit_pct=0,
        )

    opp = matching[0]
    result = arbitrage_service.calculate_stakes(total_stake, opp)

    return StakeCalculation(**result)


@router.get("/summary", response_model=dict)
async def get_arbitrage_summary():
    """
    Get summary of arbitrage opportunities across all sports.
    """
    sports = ["nba", "nfl", "mlb", "nhl"]
    summary = {
        "timestamp": None,
        "total_arbs": 0,
        "total_middles": 0,
        "by_sport": {},
    }

    from datetime import datetime
    summary["timestamp"] = datetime.now().isoformat()

    for sport in sports:
        try:
            opps = arbitrage_service.find_all_opportunities(sport)

            arbs = [o for o in opps if o.opportunity_type == "arbitrage"]
            middles = [o for o in opps if o.opportunity_type == "middle"]

            summary["by_sport"][sport] = {
                "arbs": len(arbs),
                "middles": len(middles),
                "best_arb_profit": max([o.profit_pct for o in arbs], default=0),
                "best_middle_size": max([o.middle_size or 0 for o in middles], default=0),
            }

            summary["total_arbs"] += len(arbs)
            summary["total_middles"] += len(middles)

        except Exception as e:
            summary["by_sport"][sport] = {"error": str(e)}

    return summary
