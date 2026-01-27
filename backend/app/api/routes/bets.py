"""
Bet Tracking API endpoints.
"""
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models.bet import Bet, BetResult, BetType, BankrollHistory


router = APIRouter()


class BetCreate(BaseModel):
    """Create a new bet."""
    game_id: Optional[int] = None
    prediction_id: Optional[int] = None
    bet_type: BetType
    selection: str = Field(..., description="e.g., 'Lakers -4.5' or 'Josh Allen Over 275.5 Pass Yds'")
    odds_american: int
    line: Optional[float] = None
    stake: float = Field(..., gt=0)
    sportsbook: Optional[str] = None
    model_probability: Optional[float] = None
    model_edge: Optional[float] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


class BetUpdate(BaseModel):
    """Update bet result."""
    result: BetResult
    actual_result: Optional[float] = None
    closing_line: Optional[float] = None


class BetResponse(BaseModel):
    """Bet response model."""
    id: int
    game_id: Optional[int]
    bet_type: str
    selection: str
    odds_american: int
    odds_decimal: float
    line: Optional[float]
    stake: float
    potential_payout: float
    result: str
    profit_loss: Optional[float]
    sportsbook: Optional[str]
    placed_at: datetime
    settled_at: Optional[datetime]
    model_edge: Optional[float]
    clv: Optional[float]
    tags: Optional[List[str]]

    class Config:
        from_attributes = True


class BetStats(BaseModel):
    """Betting statistics."""
    total_bets: int
    pending_bets: int
    wins: int
    losses: int
    pushes: int
    win_rate: float

    total_staked: float
    total_profit: float
    roi: float
    average_odds: float
    average_stake: float

    # CLV stats
    avg_clv: Optional[float]
    clv_positive_rate: Optional[float]

    # Streaks
    current_streak: int
    best_streak: int
    worst_streak: int

    # By category
    by_sport: dict
    by_bet_type: dict
    by_sportsbook: dict


@router.post("/", response_model=BetResponse)
async def create_bet(
    bet: BetCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Log a new bet.

    Tracks stake, odds, and optionally links to model predictions.
    """
    # Calculate decimal odds and potential payout
    from decimal import Decimal
    if bet.odds_american > 0:
        odds_decimal = Decimal(str(bet.odds_american)) / 100 + 1
    else:
        odds_decimal = Decimal('100') / abs(bet.odds_american) + 1

    potential_payout = Decimal(str(bet.stake)) * odds_decimal

    # Calculate EV if we have model probability
    model_ev = None
    if bet.model_probability and bet.model_edge:
        implied_prob = 1 / float(odds_decimal)
        model_ev = bet.model_probability * (float(odds_decimal) - 1) - (1 - bet.model_probability)

    db_bet = Bet(
        game_id=bet.game_id,
        prediction_id=bet.prediction_id,
        bet_type=bet.bet_type.value if hasattr(bet.bet_type, 'value') else bet.bet_type,
        selection=bet.selection,
        odds_american=bet.odds_american,
        odds_decimal=odds_decimal,
        line=bet.line,
        stake=bet.stake,
        potential_payout=potential_payout,
        sportsbook=bet.sportsbook,
        model_probability=bet.model_probability,
        model_edge=bet.model_edge,
        model_ev=model_ev,
        notes=bet.notes,
        tags=bet.tags
    )

    db.add(db_bet)
    await db.commit()
    await db.refresh(db_bet)

    return BetResponse(
        id=db_bet.id,
        game_id=db_bet.game_id,
        bet_type=db_bet.bet_type,
        selection=db_bet.selection,
        odds_american=db_bet.odds_american,
        odds_decimal=float(db_bet.odds_decimal) if db_bet.odds_decimal else 0,
        line=float(db_bet.line) if db_bet.line else None,
        stake=float(db_bet.stake) if db_bet.stake else 0,
        potential_payout=float(db_bet.potential_payout) if db_bet.potential_payout else 0,
        result=db_bet.result,
        profit_loss=float(db_bet.profit_loss) if db_bet.profit_loss else None,
        sportsbook=db_bet.sportsbook,
        placed_at=db_bet.placed_at,
        settled_at=db_bet.settled_at,
        model_edge=float(db_bet.model_edge) if db_bet.model_edge else None,
        clv=float(db_bet.clv) if db_bet.clv else None,
        tags=db_bet.tags
    )


@router.put("/{bet_id}", response_model=BetResponse)
async def update_bet(
    bet_id: int,
    update: BetUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update bet result (settle the bet).

    Records outcome and calculates P/L and CLV.
    """
    bet = await db.get(Bet, bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")

    # Store enum value as string
    result_value = update.result.value if hasattr(update.result, 'value') else update.result
    bet.result = result_value
    bet.actual_result = update.actual_result
    bet.settled_at = datetime.utcnow()

    # Calculate P/L
    if result_value == "win":
        bet.profit_loss = bet.potential_payout - bet.stake
    elif result_value == "loss":
        bet.profit_loss = -bet.stake
    else:  # PUSH or CANCELLED
        bet.profit_loss = 0.0

    # Calculate CLV if closing line provided
    if update.closing_line is not None and bet.line is not None:
        bet.closing_line = update.closing_line
        # CLV = our line - closing line (for spreads/totals)
        # Positive CLV means we got a better number
        bet.clv = bet.line - update.closing_line

    await db.commit()
    await db.refresh(bet)

    return BetResponse(
        id=bet.id,
        game_id=bet.game_id,
        bet_type=bet.bet_type,
        selection=bet.selection,
        odds_american=bet.odds_american,
        odds_decimal=float(bet.odds_decimal) if bet.odds_decimal else 0,
        line=float(bet.line) if bet.line else None,
        stake=float(bet.stake) if bet.stake else 0,
        potential_payout=float(bet.potential_payout) if bet.potential_payout else 0,
        result=bet.result,
        profit_loss=float(bet.profit_loss) if bet.profit_loss else None,
        sportsbook=bet.sportsbook,
        placed_at=bet.placed_at,
        settled_at=bet.settled_at,
        model_edge=float(bet.model_edge) if bet.model_edge else None,
        clv=float(bet.clv) if bet.clv else None,
        tags=bet.tags
    )


@router.get("/", response_model=List[BetResponse])
async def get_bets(
    result: Optional[BetResult] = Query(None),
    bet_type: Optional[BetType] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Get bet history with optional filters.
    """
    query = select(Bet)

    if result:
        result_value = result.value if hasattr(result, 'value') else result
        query = query.where(Bet.result == result_value)
    if bet_type:
        bet_type_value = bet_type.value if hasattr(bet_type, 'value') else bet_type
        query = query.where(Bet.bet_type == bet_type_value)
    if start_date:
        query = query.where(Bet.placed_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.where(Bet.placed_at <= datetime.combine(end_date, datetime.max.time()))

    query = query.order_by(Bet.placed_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    bets = result.scalars().all()

    return [
        BetResponse(
            id=bet.id,
            game_id=bet.game_id,
            bet_type=bet.bet_type,
            selection=bet.selection,
            odds_american=bet.odds_american,
            odds_decimal=float(bet.odds_decimal) if bet.odds_decimal else 0,
            line=float(bet.line) if bet.line else None,
            stake=float(bet.stake) if bet.stake else 0,
            potential_payout=float(bet.potential_payout) if bet.potential_payout else 0,
            result=bet.result,
            profit_loss=float(bet.profit_loss) if bet.profit_loss else None,
            sportsbook=bet.sportsbook,
            placed_at=bet.placed_at,
            settled_at=bet.settled_at,
            model_edge=float(bet.model_edge) if bet.model_edge else None,
            clv=float(bet.clv) if bet.clv else None,
            tags=bet.tags
        )
        for bet in bets
    ]


@router.get("/stats", response_model=BetStats)
async def get_bet_stats(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive betting statistics.

    Returns ROI, win rate, streaks, and breakdowns by category.
    """
    query = select(Bet)

    if start_date:
        query = query.where(Bet.placed_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.where(Bet.placed_at <= datetime.combine(end_date, datetime.max.time()))

    result = await db.execute(query)
    bets = result.scalars().all()

    if not bets:
        return BetStats(
            total_bets=0, pending_bets=0, wins=0, losses=0, pushes=0, win_rate=0,
            total_staked=0, total_profit=0, roi=0, average_odds=0, average_stake=0,
            avg_clv=None, clv_positive_rate=None,
            current_streak=0, best_streak=0, worst_streak=0,
            by_sport={}, by_bet_type={}, by_sportsbook={}
        )

    # Calculate stats - use string values since db uses VARCHAR
    settled = [b for b in bets if b.result != "pending"]
    pending = [b for b in bets if b.result == "pending"]
    wins = [b for b in settled if b.result == "win"]
    losses = [b for b in settled if b.result == "loss"]
    pushes = [b for b in settled if b.result == "push"]

    total_staked = sum(float(b.stake) for b in settled if b.stake)
    total_profit = sum(float(b.profit_loss or 0) for b in settled)
    roi = total_profit / total_staked if total_staked > 0 else 0

    # CLV stats
    clv_bets = [b for b in settled if b.clv is not None]
    avg_clv = float(sum(float(b.clv) for b in clv_bets) / len(clv_bets)) if clv_bets else None
    clv_positive_rate = len([b for b in clv_bets if float(b.clv) > 0]) / len(clv_bets) if clv_bets else None

    # Streaks (simplified)
    current_streak = 0
    best_streak = 0
    worst_streak = 0

    return BetStats(
        total_bets=len(bets),
        pending_bets=len(pending),
        wins=len(wins),
        losses=len(losses),
        pushes=len(pushes),
        win_rate=len(wins) / len(settled) if settled else 0,
        total_staked=total_staked,
        total_profit=total_profit,
        roi=roi,
        average_odds=sum(int(b.odds_american) for b in settled) / len(settled) if settled else 0,
        average_stake=float(total_staked / len(settled)) if settled else 0,
        avg_clv=avg_clv,
        clv_positive_rate=clv_positive_rate,
        current_streak=current_streak,
        best_streak=best_streak,
        worst_streak=worst_streak,
        by_sport={},  # Would group by game.sport
        by_bet_type={bt.value: len([b for b in settled if b.bet_type == bt.value]) for bt in BetType},
        by_sportsbook={}  # Would group by sportsbook
    )


@router.get("/kelly", response_model=dict)
async def calculate_kelly(
    probability: float = Query(..., ge=0, le=1, description="Your estimated probability of winning"),
    odds_american: int = Query(..., description="American odds"),
    bankroll: float = Query(10000, gt=0, description="Current bankroll"),
    kelly_fraction: float = Query(0.25, ge=0, le=1, description="Kelly fraction (0.25 = quarter Kelly)")
):
    """
    Calculate optimal stake using Kelly Criterion.

    Returns recommended stake based on edge and bankroll.
    """
    # Convert to decimal odds
    if odds_american > 0:
        odds_decimal = (odds_american / 100) + 1
    else:
        odds_decimal = (100 / abs(odds_american)) + 1

    # Implied probability
    implied_prob = 1 / odds_decimal

    # Edge
    edge = probability - implied_prob

    if edge <= 0:
        return {
            "recommendation": "NO BET",
            "reason": "Negative or zero edge",
            "edge": edge,
            "implied_probability": implied_prob,
            "your_probability": probability,
            "kelly_stake": 0,
            "kelly_pct": 0
        }

    # Kelly formula: f* = (bp - q) / b
    # where b = decimal odds - 1, p = probability, q = 1 - p
    b = odds_decimal - 1
    q = 1 - probability
    kelly_pct = (b * probability - q) / b

    # Apply fraction
    adjusted_kelly_pct = kelly_pct * kelly_fraction
    stake = bankroll * adjusted_kelly_pct

    return {
        "recommendation": "BET",
        "edge": edge,
        "edge_pct": edge * 100,
        "implied_probability": implied_prob,
        "your_probability": probability,
        "full_kelly_pct": kelly_pct,
        "adjusted_kelly_pct": adjusted_kelly_pct,
        "recommended_stake": round(stake, 2),
        "max_loss": round(stake, 2),
        "potential_profit": round(stake * b, 2),
        "expected_value": round(stake * edge * b, 2)
    }
