"""
Game, Team, Player, and Venue models.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean,
    ForeignKey, JSON, Float, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class Sport(str, enum.Enum):
    NFL = "nfl"
    NBA = "nba"
    MLB = "mlb"
    SOCCER = "soccer"
    NCAAF = "ncaaf"
    NCAAB = "ncaab"


class GameStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    FINAL = "final"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class Venue(Base):
    """Stadium/arena information."""
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    city = Column(String(100))
    state = Column(String(50))
    country = Column(String(100), default="USA")
    capacity = Column(Integer)
    surface = Column(String(50))  # grass, turf, etc.
    is_dome = Column(Boolean, default=False)
    elevation_ft = Column(Integer)
    latitude = Column(Float)
    longitude = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    teams = relationship("Team", back_populates="venue")
    games = relationship("Game", back_populates="venue")


class Team(Base):
    """Team information."""
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    sport = Column(SQLEnum(Sport), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    abbreviation = Column(String(10))
    city = Column(String(100))
    league = Column(String(50))  # NFL, NBA, EPL, etc.
    conference = Column(String(50))
    division = Column(String(50))
    venue_id = Column(Integer, ForeignKey("venues.id"))
    logo_url = Column(String(500))
    primary_color = Column(String(7))  # hex color
    secondary_color = Column(String(7))
    external_ids = Column(JSON)  # {espn_id, sportradar_id, etc}
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    venue = relationship("Venue", back_populates="teams")
    players = relationship("Player", back_populates="team")
    home_games = relationship("Game", foreign_keys="Game.home_team_id", back_populates="home_team")
    away_games = relationship("Game", foreign_keys="Game.away_team_id", back_populates="away_team")


class Player(Base):
    """Player information."""
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    sport = Column(SQLEnum(Sport), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    first_name = Column(String(50))
    last_name = Column(String(50))
    team_id = Column(Integer, ForeignKey("teams.id"), index=True)
    position = Column(String(20), index=True)
    jersey_number = Column(Integer)
    height_inches = Column(Integer)
    weight_lbs = Column(Integer)
    birth_date = Column(DateTime)
    college = Column(String(100))
    draft_year = Column(Integer)
    draft_round = Column(Integer)
    draft_pick = Column(Integer)
    years_pro = Column(Integer)
    headshot_url = Column(String(500))
    external_ids = Column(JSON)
    is_active = Column(Boolean, default=True)
    injury_status = Column(String(50))  # healthy, questionable, out, etc.
    injury_detail = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    team = relationship("Team", back_populates="players")
    stats = relationship("PlayerGameStats", back_populates="player")


class Game(Base):
    """Game/match information."""
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    sport = Column(SQLEnum(Sport), nullable=False, index=True)
    external_id = Column(String(50), unique=True, index=True)
    season = Column(Integer, index=True)
    season_type = Column(String(20))  # regular, playoffs, preseason
    week = Column(Integer)  # NFL week, etc.

    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)

    scheduled_time = Column(DateTime, nullable=False, index=True)
    status = Column(SQLEnum(GameStatus), default=GameStatus.SCHEDULED, index=True)

    home_score = Column(Integer)
    away_score = Column(Integer)
    home_score_by_period = Column(JSON)  # [7, 14, 3, 10] for NFL quarters
    away_score_by_period = Column(JSON)

    venue_id = Column(Integer, ForeignKey("venues.id"))

    # Weather (for outdoor sports)
    weather_conditions = Column(JSON)  # {temp, wind, humidity, precipitation}

    # Officials
    officials = Column(JSON)  # [{name, position}]

    # Broadcast
    broadcast = Column(String(100))  # ESPN, FOX, etc.

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_games")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_games")
    venue = relationship("Venue", back_populates="games")
    predictions = relationship("Prediction", back_populates="game")
    bets = relationship("Bet", back_populates="game")
    player_stats = relationship("PlayerGameStats", back_populates="game")
    odds_history = relationship("OddsHistory", back_populates="game")

    @property
    def is_complete(self) -> bool:
        return self.status == GameStatus.FINAL

    @property
    def total_score(self) -> Optional[int]:
        if self.home_score is not None and self.away_score is not None:
            return self.home_score + self.away_score
        return None

    @property
    def spread(self) -> Optional[int]:
        if self.home_score is not None and self.away_score is not None:
            return self.home_score - self.away_score
        return None


class PlayerGameStats(Base):
    """Player statistics for a specific game."""
    __tablename__ = "player_game_stats"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)

    # General
    minutes_played = Column(Float)
    is_starter = Column(Boolean)

    # Sport-specific stats stored as JSON
    stats = Column(JSON, nullable=False)
    # NFL: {passing_yards, rushing_yards, receiving_yards, touchdowns, interceptions, ...}
    # NBA: {points, rebounds, assists, steals, blocks, turnovers, ...}
    # MLB: {at_bats, hits, runs, rbi, home_runs, strikeouts, ...}
    # Soccer: {goals, assists, shots, shots_on_target, passes, ...}

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    player = relationship("Player", back_populates="stats")
    game = relationship("Game", back_populates="player_stats")
