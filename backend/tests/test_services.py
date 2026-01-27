"""
Unit tests for new services: Arbitrage, SGP, Backtest.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import date, datetime

from app.services.arbitrage_service import ArbitrageService, ArbitrageOpportunity
from app.services.sgp_service import SGPService
from app.services.backtest_service import BacktestService
from data.apis.odds_api import GameOdds, OddsLine

@pytest.fixture
def mock_odds_service():
    service = MagicMock()
    service.get_current_odds.return_value = []
    return service

@pytest.fixture
def arb_service(mock_odds_service):
    return ArbitrageService(odds_service=mock_odds_service)

@pytest.fixture
def sgp_service():
    return SGPService()

@pytest.fixture
def backtest_service():
    return BacktestService()

# --- Arbitrage Tests ---

def test_find_moneyline_arb(arb_service):
    """Test 2-way arbitrage detection."""
    # Setup a game with clear arbitrage
    # Book A: Home -110 (1.91), Away +100 (2.0)
    # Book B: Home -150 (1.67), Away +150 (2.5)
    # Arb: Bet Home on Book A (1.91) and Away on Book B (2.5)
    # Implied: 1/1.91 + 1/2.5 = 0.523 + 0.4 = 0.923 < 1.0 (Arb!)
    
    game = GameOdds(
        game_id="1", sport="nba", commence_time="", home_team="Lakers", away_team="Warriors",
        moneyline=[
            OddsLine("BookA", "h2h", "Lakers", -110, 1.91),
            OddsLine("BookA", "h2h", "Warriors", 100, 2.0),
            OddsLine("BookB", "h2h", "Lakers", -150, 1.67),
            OddsLine("BookB", "h2h", "Warriors", 150, 2.5),
        ]
    )
    
    arbs = arb_service._find_moneyline_arb(game)
    assert len(arbs) >= 1
    
    # Check the best arb
    arb = arbs[0]
    assert arb.opportunity_type == "arbitrage"
    assert arb.profit_pct > 0
    assert (arb.book1 == "BookA" and arb.selection1 == "Lakers") or (arb.book1 == "BookB" and arb.selection1 == "Warriors")

def test_calculate_stakes(arb_service):
    """Test stake calculation."""
    opp = ArbitrageOpportunity(
        game_id="1", sport="nba", home_team="H", away_team="A",
        market_type="h2h", opportunity_type="arbitrage",
        book1="B1", selection1="H", odds1=100, odds1_decimal=2.0,
        book2="B2", selection2="A", odds2=100, odds2_decimal=2.0,
        stake1_pct=50, stake2_pct=50, profit_pct=0
    )
    
    stakes = arb_service.calculate_stakes(1000, opp)
    assert stakes['stake1'] == 500
    assert stakes['stake2'] == 500
    assert stakes['guaranteed_profit'] == 0 # Break even

# --- SGP Tests ---

def test_sgp_simulation(sgp_service):
    """Test Monte Carlo simulation mechanics."""
    # 2 correlated legs with 50% prob each
    legs = [
        {"type": "leg1", "prob": 0.5},
        {"type": "leg2", "prob": 0.5}
    ]
    
    # Mock get_correlation to return high correlation
    with patch.object(sgp_service, 'get_correlation', return_value=0.9):
        result = sgp_service.calculate_parlay_probability("nba", legs)
        
        # With 0.9 correlation, prob should be close to 0.5 (they happen together)
        # Uncorrelated would be 0.25
        assert result['true_prob'] > 0.4
        assert result['true_prob'] < 0.6

# --- Backtest Tests ---

@pytest.mark.asyncio
async def test_backtest_strategy_logic(backtest_service):
    """Test strategy application logic."""
    # Mock Data
    game = (
        1, "nba", 110, 100, datetime.now(), 
        101, "moneyline", {"home_prob": 0.6, "away_prob": 0.4}, 
        "Lakers", "Warriors"
    )
    
    # Odds: Home 2.0 (+100) -> Edge = 0.6 - 0.5 = 0.1 (10%)
    odds = [
        ("BookA", "Lakers", 2.0, None),
        ("BookA", "Warriors", 1.9, None)
    ]
    
    config = {
        "min_edge": 0.05,
        "kelly_fraction": 0.5,
        "max_stake_pct": 0.1
    }
    
    bets = backtest_service._apply_strategy(game, odds, config, 10000)
    
    assert len(bets) == 1
    assert bets[0]['selection'] == "home" # Should bet on Lakers
    assert bets[0]['edge'] > 0.09 # Approx 0.1
    assert bets[0]['stake'] > 0 # Should have stake
