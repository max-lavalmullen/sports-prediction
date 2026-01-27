"""
Odds history models (Time-series data).
"""
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Index, Float
from sqlalchemy.orm import relationship
from app.core.database import Base

class OddsHistory(Base):
    """
    Historical odds data.
    This is a hypertable in TimescaleDB, partitioned by time.
    """
    __tablename__ = "odds_history"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), primary_key=True, nullable=False)
    sportsbook = Column(String(50), primary_key=True, nullable=False)
    market_type = Column(String(50), primary_key=True, nullable=False)  # moneyline, spread, total
    selection = Column(String(50), primary_key=True, nullable=False)    # home, away, over, under
    
    odds_american = Column(Integer)
    odds_decimal = Column(Numeric(6, 3))
    line = Column(Numeric(5, 2))  # spread or total line
    implied_probability = Column(Float)

    # Relationships
    game = relationship("Game", back_populates="odds_history")

    __table_args__ = (
        Index('idx_odds_game_time', 'game_id', 'time'),
        Index('idx_odds_sportsbook', 'sportsbook'),
    )


class PropOddsHistory(Base):
    """
    Historical player prop odds data.
    This is a hypertable in TimescaleDB.
    """
    __tablename__ = "prop_odds_history"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), primary_key=True, nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), primary_key=True, nullable=False)
    sportsbook = Column(String(50), primary_key=True, nullable=False)
    prop_type = Column(String(50), primary_key=True, nullable=False)  # points, rebounds, etc
    
    line = Column(Numeric(5, 2), nullable=False)
    over_odds = Column(Integer)
    under_odds = Column(Integer)
    
    over_implied_prob = Column(Float)
    under_implied_prob = Column(Float)

    __table_args__ = (
        Index('idx_prop_player_time', 'player_id', 'time'),
        Index('idx_prop_game', 'game_id'),
    )

    # Relationships
    # game relationship omitted to avoid redundancy/complexity if not needed immediately
    # player relationship omitted similarly, or can be added:
    # player = relationship("Player", backref="prop_odds")
