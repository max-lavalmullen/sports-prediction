"""
Sports Data APIs.

This module provides interfaces to various free sports data APIs
for fetching historical stats, schedules, game results, and betting odds.
"""

from .nba_data import NBADataFetcher
from .nfl_data import NFLDataFetcher
from .mlb_data import MLBDataFetcher
from .soccer_data import SoccerDataFetcher
from .stats_service import StatsService
from .live_games import LiveGamesService, Game, get_todays_games, get_upcoming_games
from .odds_api import OddsAPIClient, OddsService, GameOdds, get_odds, get_best_lines

__all__ = [
    "NBADataFetcher",
    "NFLDataFetcher",
    "MLBDataFetcher",
    "SoccerDataFetcher",
    "StatsService",
    "LiveGamesService",
    "Game",
    "get_todays_games",
    "get_upcoming_games",
    "OddsAPIClient",
    "OddsService",
    "GameOdds",
    "get_odds",
    "get_best_lines",
]
