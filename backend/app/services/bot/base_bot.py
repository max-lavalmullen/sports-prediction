"""
Abstract Base Class for Betting Bots.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BotBet:
    id: str
    game_id: str
    selection: str
    odds: float
    stake: float
    status: str  # 'placed', 'matched', 'settled', 'cancelled'
    placed_at: datetime
    pnl: Optional[float] = None


class BaseBettingBot(ABC):
    """
    Abstract interface for betting bots.
    Can be implemented for paper trading, Betfair API, or other sportsbooks.
    """

    @abstractmethod
    def get_balance(self) -> float:
        """Get current available balance."""
        pass

    @abstractmethod
    def place_bet(
        self, 
        game_id: str, 
        selection: str, 
        odds: float, 
        stake: float,
        bet_type: str = 'back'
    ) -> Optional[BotBet]:
        """Place a bet."""
        pass

    @abstractmethod
    def get_active_bets(self) -> List[BotBet]:
        """Get currently active/unsettled bets."""
        pass

    @abstractmethod
    def cancel_bet(self, bet_id: str) -> bool:
        """Cancel a pending bet."""
        pass

    @abstractmethod
    def settle_bets(self) -> List[BotBet]:
        """Check for and settle completed bets."""
        pass
