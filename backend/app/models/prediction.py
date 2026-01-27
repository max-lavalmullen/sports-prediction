"""
Prediction and Odds models.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Float,
    ForeignKey, JSON, Enum as SQLEnum, Index
)
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class PredictionType(str, enum.Enum):
    MONEYLINE = "moneyline"
    SPREAD = "spread"
    TOTAL = "total"
    PLAYER_PROP = "player_prop"
    FIRST_HALF = "first_half"
    FIRST_QUARTER = "first_quarter"


class Prediction(Base):
    """Model predictions for games."""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    prediction_type = Column(SQLEnum(PredictionType), nullable=False, index=True)
    model_version = Column(String(50), nullable=False)

    # Prediction results
    prediction = Column(JSON, nullable=False)
    # Moneyline: {home_prob, away_prob, draw_prob}
    # Spread: {predicted_spread, home_cover_prob, push_prob}
    # Total: {predicted_total, over_prob, under_prob}
    # Player prop: {player_id, prop_type, predicted_value, over_prob}

    # Confidence/uncertainty
    confidence = Column(JSON)
    # {lower_bound, upper_bound, confidence_level, std_dev}

    # Explainability
    feature_importance = Column(JSON)
    # {feature_name: importance_score, ...}

    # Model agreement (for ensembles)
    model_agreement = Column(Float)  # 0-1, how much base models agree

    # Value calculation (vs market)
    market_line = Column(Float)  # The line we're comparing against
    market_odds = Column(Integer)  # American odds
    edge = Column(Float)  # Our prob - implied prob
    expected_value = Column(Float)  # EV in units

    # Calibration
    calibration_bucket = Column(Float)  # Which calibration bucket this falls into

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    game = relationship("Game", back_populates="predictions")

    __table_args__ = (
        Index('idx_predictions_game_type', 'game_id', 'prediction_type'),
    )


class PlayerPropPrediction(Base):
    """Player prop predictions with full distributions."""
    __tablename__ = "player_prop_predictions"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    prop_type = Column(String(50), nullable=False, index=True)  # points, rebounds, etc.
    model_version = Column(String(50), nullable=False)

    # Quantile predictions
    prediction = Column(JSON, nullable=False)
    # {p10, p25, median, p75, p90, mean, std}

    # Current market
    market_line = Column(Float)
    market_over_odds = Column(Integer)
    market_under_odds = Column(Integer)

    # Edge calculation
    over_prob = Column(Float)
    under_prob = Column(Float)
    over_edge = Column(Float)
    under_edge = Column(Float)
    over_ev = Column(Float)
    under_ev = Column(Float)

    # Context
    matchup_rating = Column(Float)  # How favorable is this matchup
    usage_projection = Column(Float)  # Expected usage rate
    minutes_projection = Column(Float)  # Expected minutes

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('idx_prop_pred_player_game', 'player_id', 'game_id'),
    )
