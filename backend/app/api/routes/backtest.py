"""
Backtesting API endpoints.
"""
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models.game import Sport


router = APIRouter()


class StrategyConfig(BaseModel):
    """Betting strategy configuration."""
    sports: List[Sport] = Field(default_factory=lambda: [Sport.NBA, Sport.NFL])
    bet_types: List[str] = Field(default=["spread", "total", "moneyline"])
    min_edge: float = Field(default=0.03, ge=0, le=0.5, description="Minimum edge to bet")
    min_confidence: float = Field(default=0.0, ge=0, le=1)
    kelly_fraction: float = Field(default=0.25, ge=0, le=1, description="Kelly criterion fraction")
    max_stake_pct: float = Field(default=0.05, ge=0, le=0.5, description="Max stake as % of bankroll")
    flat_stake: Optional[float] = Field(default=None, description="Fixed stake amount (overrides Kelly)")


class BacktestRequest(BaseModel):
    """Backtest request parameters."""
    strategy: StrategyConfig
    start_date: date
    end_date: date
    initial_bankroll: float = Field(default=10000.0, gt=0)
    use_closing_odds: bool = Field(default=False, description="Use closing odds instead of available odds")


class BacktestResult(BaseModel):
    """Summary of backtest results."""
    # Overall metrics
    total_bets: int
    wins: int
    losses: int
    pushes: int
    win_rate: float

    # Financial metrics
    initial_bankroll: float
    final_bankroll: float
    total_profit: float
    total_staked: float
    roi: float
    yield_pct: float

    # Risk metrics
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]

    # Closing line value
    avg_clv: float
    clv_positive_pct: float

    # Breakdown
    by_sport: dict
    by_bet_type: dict
    monthly_returns: List[dict]

    # Data for charts
    equity_curve: List[dict]  # [{date, bankroll, cumulative_pl}]
    drawdown_curve: List[dict]  # [{date, drawdown_pct}]


class SimulationRequest(BaseModel):
    """Monte Carlo simulation request."""
    n_simulations: int = Field(default=10000, ge=100, le=100000)
    n_bets: int = Field(default=1000, ge=10, le=10000)
    initial_bankroll: float = Field(default=10000.0, gt=0)
    win_rate: float = Field(default=0.54, ge=0.40, le=0.70, description="Expected win rate")
    avg_odds: int = Field(default=-110, description="Average American odds")
    kelly_fraction: float = Field(default=0.25, ge=0, le=1, description="Kelly criterion fraction")


class SimulationResult(BaseModel):
    """Monte Carlo simulation results."""
    n_simulations: int
    n_bets: int

    # Outcome distribution
    median_final_bankroll: float
    p5_final_bankroll: float
    p25_final_bankroll: float
    p75_final_bankroll: float
    p95_final_bankroll: float

    # Risk metrics
    probability_of_profit: float
    probability_of_ruin: float  # Bankroll <= 0
    probability_of_halving: float  # Bankroll <= 50% initial

    # Expected metrics
    expected_roi: float
    expected_profit: float

    # Distribution data for charts
    final_bankroll_distribution: List[float]  # Sample of outcomes
    percentile_curves: dict  # {p5: [...], p25: [...], median: [...], p75: [...], p95: [...]}


@router.post("/run", response_model=BacktestResult)
async def run_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Run a backtest of a betting strategy on historical data.

    This simulates applying your strategy to past games using
    the predictions and odds that were available at the time.
    """
    # Validate date range
    if request.start_date >= request.end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    if request.end_date > date.today():
        raise HTTPException(status_code=400, detail="end_date cannot be in the future")

    # Run backtest (simplified - full implementation would be in a service)
    result = await _run_backtest(request, db)

    return result


@router.post("/simulate", response_model=SimulationResult)
async def run_simulation(
    request: SimulationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Run Monte Carlo simulation to project future performance.

    Simulates many possible outcomes based on historical edge
    and variance to estimate probability of profit, ruin, etc.
    """
    result = await _run_simulation(request, db)
    return result


@router.get("/strategies", response_model=List[dict])
async def get_saved_strategies(
    db: AsyncSession = Depends(get_db)
):
    """Get list of saved strategy configurations."""
    # Placeholder - would load from database
    return [
        {
            "id": 1,
            "name": "Conservative Value",
            "config": {
                "sports": ["nba", "nfl"],
                "bet_types": ["spread"],
                "min_edge": 0.05,
                "kelly_fraction": 0.25
            },
            "historical_roi": 0.08
        },
        {
            "id": 2,
            "name": "Aggressive Props",
            "config": {
                "sports": ["nba"],
                "bet_types": ["player_prop"],
                "min_edge": 0.03,
                "kelly_fraction": 0.5
            },
            "historical_roi": 0.12
        }
    ]


from app.services.backtest_service import backtest_service


async def _run_backtest(request: BacktestRequest, db: AsyncSession) -> BacktestResult:
    """Execute backtest logic."""
    sports_list = [s.value for s in request.strategy.sports]
    
    result = await backtest_service.run_backtest(
        sports=sports_list,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_bankroll=request.initial_bankroll,
        strategy_config=request.strategy.dict()
    )
    
    # Calculate additional metrics for response
    bets = result.get('total_bets_count', 0)
    wins = result.get('wins', 0)
    
    # Calculate total staked safely
    roi = result.get('roi', 0)
    total_profit = result.get('total_profit', 0)
    total_staked = total_profit / roi if roi != 0 else 0

    return BacktestResult(
        total_bets=bets,
        wins=wins,
        losses=result.get('losses', bets - wins - result.get('pushes', 0)),
        pushes=result.get('pushes', 0),
        win_rate=result.get('win_rate', 0),
        initial_bankroll=request.initial_bankroll,
        final_bankroll=result.get('final_bankroll', request.initial_bankroll),
        total_profit=total_profit,
        total_staked=total_staked,
        roi=roi,
        yield_pct=roi,
        max_drawdown=result.get('max_drawdown', 0),
        max_drawdown_pct=result.get('max_drawdown_pct', 0),
        sharpe_ratio=None,
        sortino_ratio=None,
        avg_clv=0,
        clv_positive_pct=0,
        by_sport={},
        by_bet_type={},
        monthly_returns=[],
        equity_curve=result.get('equity_curve', []),
        drawdown_curve=[]
    )


async def _run_simulation(request: SimulationRequest, db: AsyncSession) -> SimulationResult:
    """Execute Monte Carlo simulation."""
    import numpy as np

    # Convert American odds to decimal
    if request.avg_odds > 0:
        decimal_odds = (request.avg_odds / 100) + 1
    else:
        decimal_odds = (100 / abs(request.avg_odds)) + 1

    # Calculate implied probability and edge
    implied_prob = 1 / decimal_odds
    edge = request.win_rate - implied_prob

    # Kelly criterion for bet sizing
    b = decimal_odds - 1  # net odds
    q = 1 - request.win_rate
    full_kelly = (b * request.win_rate - q) / b if b > 0 else 0
    stake_pct = max(0, min(full_kelly * request.kelly_fraction, 0.10))  # Cap at 10%

    # Run Monte Carlo simulations
    final_bankrolls = []
    percentile_curves = {
        "p5": [],
        "p25": [],
        "median": [],
        "p75": [],
        "p95": []
    }

    all_curves = []

    for sim in range(request.n_simulations):
        bankroll = request.initial_bankroll
        curve = [bankroll]

        for bet in range(request.n_bets):
            if bankroll <= 0:
                curve.extend([0] * (request.n_bets - bet))
                break

            stake = bankroll * stake_pct
            won = np.random.random() < request.win_rate

            if won:
                bankroll += stake * b
            else:
                bankroll -= stake

            if bet % 50 == 0:  # Sample every 50 bets for curves
                curve.append(bankroll)

        final_bankrolls.append(bankroll)
        all_curves.append(curve)

    final_bankrolls = np.array(final_bankrolls)

    # Calculate percentile curves
    all_curves = np.array(all_curves)
    n_points = all_curves.shape[1]
    for i in range(n_points):
        point_values = all_curves[:, i]
        percentile_curves["p5"].append(float(np.percentile(point_values, 5)))
        percentile_curves["p25"].append(float(np.percentile(point_values, 25)))
        percentile_curves["median"].append(float(np.percentile(point_values, 50)))
        percentile_curves["p75"].append(float(np.percentile(point_values, 75)))
        percentile_curves["p95"].append(float(np.percentile(point_values, 95)))

    # Calculate expected ROI
    expected_roi = (np.mean(final_bankrolls) - request.initial_bankroll) / request.initial_bankroll

    return SimulationResult(
        n_simulations=request.n_simulations,
        n_bets=request.n_bets,
        median_final_bankroll=float(np.median(final_bankrolls)),
        p5_final_bankroll=float(np.percentile(final_bankrolls, 5)),
        p25_final_bankroll=float(np.percentile(final_bankrolls, 25)),
        p75_final_bankroll=float(np.percentile(final_bankrolls, 75)),
        p95_final_bankroll=float(np.percentile(final_bankrolls, 95)),
        probability_of_profit=float((final_bankrolls > request.initial_bankroll).mean()),
        probability_of_ruin=float((final_bankrolls <= 0).mean()),
        probability_of_halving=float((final_bankrolls <= request.initial_bankroll * 0.5).mean()),
        expected_roi=float(expected_roi),
        expected_profit=float(np.mean(final_bankrolls) - request.initial_bankroll),
        final_bankroll_distribution=final_bankrolls[:100].tolist(),
        percentile_curves=percentile_curves
    )
