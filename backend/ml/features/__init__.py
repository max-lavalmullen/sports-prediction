"""
Feature Engineering Module.

Sport-specific feature engineering pipelines for model training and prediction.
"""

from .nba_features import NBAFeatureEngineer, CORE_FEATURE_COLUMNS as NBA_FEATURES
from .nfl_features import NFLFeatureEngineer, NFL_CORE_FEATURES
from .mlb_features import MLBFeatureEngineer, MLB_CORE_FEATURES
from .soccer_features import SoccerFeatureEngineer, SOCCER_CORE_FEATURES


def get_feature_engineer(sport: str):
    """Get the appropriate feature engineer for a sport."""
    sport = sport.lower()
    if sport == "nba":
        return NBAFeatureEngineer()
    elif sport == "nfl":
        return NFLFeatureEngineer()
    elif sport == "mlb":
        return MLBFeatureEngineer()
    elif sport in ["soccer", "football", "epl", "mls"]:
        return SoccerFeatureEngineer()
    else:
        raise ValueError(f"Unknown sport: {sport}")


def get_feature_columns(sport: str):
    """Get the core feature columns for a sport."""
    sport = sport.lower()
    if sport == "nba":
        return NBA_FEATURES
    elif sport == "nfl":
        return NFL_CORE_FEATURES
    elif sport == "mlb":
        return MLB_CORE_FEATURES
    elif sport in ["soccer", "football", "epl", "mls"]:
        return SOCCER_CORE_FEATURES
    else:
        raise ValueError(f"Unknown sport: {sport}")


__all__ = [
    "NBAFeatureEngineer",
    "NFLFeatureEngineer",
    "MLBFeatureEngineer",
    "SoccerFeatureEngineer",
    "get_feature_engineer",
    "get_feature_columns",
    "NBA_FEATURES",
    "NFL_CORE_FEATURES",
    "MLB_CORE_FEATURES",
    "SOCCER_CORE_FEATURES",
]