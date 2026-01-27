"""
Bet tracking and bankroll management models.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Float, Text,
    ForeignKey, JSON, Boolean, Index, Numeric
)
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class BetResult(str, enum.Enum):
    PENDING = "pending"
    WIN = "win"
    LOSS = "loss"
    PUSH = "push"
    CANCELLED = "cancelled"


class BetType(str, enum.Enum):
    MONEYLINE = "moneyline"
    SPREAD = "spread"
    TOTAL = "total"
    PLAYER_PROP = "player_prop"
    PARLAY = "parlay"
    TEASER = "teaser"
    LIVE = "live"


class Bet(Base):
    """Individual bet tracking."""
    __tablename__ = "bets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)  # For multi-user support

    # Game reference
    game_id = Column(Integer, ForeignKey("games.id"), index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"))

    # Bet details - use String to match database VARCHAR columns
    bet_type = Column(String(50), nullable=False, index=True)
    selection = Column(String(100), nullable=False)  # "Lakers -4.5", "Josh Allen Over 275.5 Pass Yds"
    description = Column(Text)  # Detailed description (TEXT in DB)

    # Odds and stakes - use Numeric to match DB schema
    odds_american = Column(Integer, nullable=False)
    odds_decimal = Column(Numeric(6, 3), nullable=False)
    line = Column(Numeric(5, 2))  # Spread/total/prop line
    stake = Column(Numeric(10, 2), nullable=False)
    potential_payout = Column(Numeric(10, 2), nullable=False)

    # Result - use String to match database VARCHAR column
    result = Column(String(20), default="pending", index=True)
    profit_loss = Column(Numeric(10, 2))
    actual_result = Column(Text)  # Actual score/stat for verification (TEXT in DB)

    # Metadata
    sportsbook = Column(String(50))
    placed_at = Column(DateTime, default=datetime.utcnow, index=True)
    settled_at = Column(DateTime)

    # Model info at time of bet - use Numeric to match DB schema
    model_probability = Column(Numeric(5, 4))  # Our predicted probability
    model_edge = Column(Numeric(5, 4))  # Edge at time of bet
    model_ev = Column(Numeric(6, 4))  # Expected value
    kelly_fraction = Column(Numeric(5, 4))  # Recommended Kelly stake %
    closing_line = Column(Numeric(5, 2))  # Line at game start for CLV calculation
    clv = Column(Numeric(5, 4))  # Closing line value (positive = beat the close)

    # Parlay legs (if parlay)
    parlay_legs = Column(JSON)  # [{selection, odds, result}, ...]

    # Tags for analysis
    tags = Column(JSON)  # ["value", "sharp", "steam", ...]
    notes = Column(Text)  # Notes field (TEXT in DB)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    game = relationship("Game", back_populates="bets")
    prediction = relationship("Prediction")

    __table_args__ = (
        Index('idx_bets_user_result', 'user_id', 'result'),
        Index('idx_bets_placed', 'placed_at'),
    )

    @property
    def is_settled(self) -> bool:
        return self.result != "pending"

    def calculate_profit_loss(self) -> float:
        """Calculate P/L based on result."""
        if self.result == "win":
            return float(self.potential_payout - self.stake) if self.potential_payout and self.stake else 0.0
        elif self.result == "loss":
            return float(-self.stake) if self.stake else 0.0
        elif self.result == "push":
            return 0.0
        return 0.0


class BankrollHistory(Base):
    """Track bankroll over time."""
    __tablename__ = "bankroll_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)

    date = Column(DateTime, nullable=False, index=True)

    # Balances
    starting_balance = Column(Float, nullable=False)
    ending_balance = Column(Float, nullable=False)

    # Daily stats
    bets_placed = Column(Integer, default=0)
    bets_won = Column(Integer, default=0)
    bets_lost = Column(Integer, default=0)
    bets_pushed = Column(Integer, default=0)

    total_staked = Column(Float, default=0.0)
    total_won = Column(Float, default=0.0)
    total_lost = Column(Float, default=0.0)
    daily_profit_loss = Column(Float, default=0.0)

    # Metrics
    roi = Column(Float)  # Daily ROI
    win_rate = Column(Float)
    avg_odds = Column(Float)
    avg_edge = Column(Float)
    avg_clv = Column(Float)

    # Running totals
    cumulative_profit = Column(Float)
    cumulative_roi = Column(Float)
    max_drawdown = Column(Float)
    current_drawdown = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_bankroll_user_date', 'user_id', 'date'),
    )


class BettingSession(Base):
    """Group bets into sessions for analysis."""
    __tablename__ = "betting_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)

    name = Column(String(100))
    description = Column(String(500))

    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)

    # Configuration
    starting_bankroll = Column(Float, nullable=False)
    current_bankroll = Column(Float)
    target_bankroll = Column(Float)
    stop_loss = Column(Float)

    # Strategy
    strategy_name = Column(String(100))
    strategy_config = Column(JSON)
    # {bet_types, sports, min_edge, kelly_fraction, max_stake_pct, ...}

    # Stats
    total_bets = Column(Integer, default=0)
    total_profit = Column(Float, default=0.0)
    roi = Column(Float)
    max_drawdown = Column(Float)
    sharpe_ratio = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
