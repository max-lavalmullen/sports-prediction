"""
NBA Data Fetcher using nba_api.

Fetches historical game data, player stats, team stats, and schedules
from the official NBA stats API via the nba_api package.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from loguru import logger

try:
    from nba_api.stats.endpoints import (
        leaguegamefinder,
        boxscoretraditionalv2,
        teamgamelog,
        playergamelog,
        commonteamroster,
        scoreboardv2,
        leaguestandings,
    )
    from nba_api.stats.static import teams, players
    NBA_API_AVAILABLE = True
except ImportError:
    NBA_API_AVAILABLE = False
    logger.warning("nba_api not installed. NBA data fetching will be unavailable.")


class NBADataFetcher:
    """Fetches NBA data from the official NBA stats API."""

    # NBA team ID mapping
    TEAM_ABBREVIATIONS = {
        "ATL": 1610612737, "BOS": 1610612738, "BKN": 1610612751,
        "CHA": 1610612766, "CHI": 1610612741, "CLE": 1610612739,
        "DAL": 1610612742, "DEN": 1610612743, "DET": 1610612765,
        "GSW": 1610612744, "HOU": 1610612745, "IND": 1610612754,
        "LAC": 1610612746, "LAL": 1610612747, "MEM": 1610612763,
        "MIA": 1610612748, "MIL": 1610612749, "MIN": 1610612750,
        "NOP": 1610612740, "NYK": 1610612752, "OKC": 1610612760,
        "ORL": 1610612753, "PHI": 1610612755, "PHX": 1610612756,
        "POR": 1610612757, "SAC": 1610612758, "SAS": 1610612759,
        "TOR": 1610612761, "UTA": 1610612762, "WAS": 1610612764,
    }

    def __init__(self):
        if not NBA_API_AVAILABLE:
            raise ImportError("nba_api package is required for NBA data fetching")
        self._teams_cache = None
        self._players_cache = None

    @property
    def all_teams(self) -> List[Dict]:
        """Get all NBA teams."""
        if self._teams_cache is None:
            self._teams_cache = teams.get_teams()
        return self._teams_cache

    @property
    def all_players(self) -> List[Dict]:
        """Get all NBA players."""
        if self._players_cache is None:
            self._players_cache = players.get_players()
        return self._players_cache

    def get_team_id(self, abbreviation: str) -> Optional[int]:
        """Get team ID from abbreviation."""
        return self.TEAM_ABBREVIATIONS.get(abbreviation.upper())

    def get_team_game_log(
        self,
        team_abbreviation: str,
        season: str = "2024-25",
        season_type: str = "Regular Season"
    ) -> pd.DataFrame:
        """
        Get game log for a team.

        Args:
            team_abbreviation: Team abbreviation (e.g., 'LAL', 'BOS')
            season: Season string (e.g., '2024-25')
            season_type: 'Regular Season', 'Playoffs', or 'Pre Season'

        Returns:
            DataFrame with game-by-game stats
        """
        team_id = self.get_team_id(team_abbreviation)
        if not team_id:
            logger.error(f"Unknown team abbreviation: {team_abbreviation}")
            return pd.DataFrame()

        try:
            game_log = teamgamelog.TeamGameLog(
                team_id=team_id,
                season=season,
                season_type_all_star=season_type
            )
            return game_log.get_data_frames()[0]
        except Exception as e:
            logger.error(f"Error fetching team game log: {e}")
            return pd.DataFrame()

    def get_player_game_log(
        self,
        player_name: str,
        season: str = "2024-25",
        season_type: str = "Regular Season"
    ) -> pd.DataFrame:
        """
        Get game log for a player.

        Args:
            player_name: Full player name (e.g., 'LeBron James')
            season: Season string (e.g., '2024-25')
            season_type: 'Regular Season' or 'Playoffs'

        Returns:
            DataFrame with game-by-game stats
        """
        # Find player ID
        player_dict = [p for p in self.all_players if p['full_name'].lower() == player_name.lower()]
        if not player_dict:
            logger.error(f"Player not found: {player_name}")
            return pd.DataFrame()

        player_id = player_dict[0]['id']

        try:
            game_log = playergamelog.PlayerGameLog(
                player_id=player_id,
                season=season,
                season_type_all_star=season_type
            )
            return game_log.get_data_frames()[0]
        except Exception as e:
            logger.error(f"Error fetching player game log: {e}")
            return pd.DataFrame()

    def get_games_by_date(self, game_date: str) -> pd.DataFrame:
        """
        Get all games for a specific date.

        Args:
            game_date: Date string in 'YYYY-MM-DD' format

        Returns:
            DataFrame with games scheduled for that date
        """
        try:
            scoreboard = scoreboardv2.ScoreboardV2(game_date=game_date)
            games_df = scoreboard.get_data_frames()[0]
            return games_df
        except Exception as e:
            logger.error(f"Error fetching games for {game_date}: {e}")
            return pd.DataFrame()

    def get_box_score(self, game_id: str) -> Dict[str, pd.DataFrame]:
        """
        Get detailed box score for a game.

        Args:
            game_id: NBA game ID (e.g., '0022400123')

        Returns:
            Dict with 'players' and 'teams' DataFrames
        """
        try:
            box_score = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
            dfs = box_score.get_data_frames()
            return {
                "players": dfs[0],
                "teams": dfs[1]
            }
        except Exception as e:
            logger.error(f"Error fetching box score for game {game_id}: {e}")
            return {"players": pd.DataFrame(), "teams": pd.DataFrame()}

    def get_season_games(
        self,
        season: str = "2024-25",
        season_type: str = "Regular Season"
    ) -> pd.DataFrame:
        """
        Get all games for a season.

        Args:
            season: Season string (e.g., '2024-25')
            season_type: 'Regular Season' or 'Playoffs'

        Returns:
            DataFrame with all games in the season
        """
        try:
            # Use league game finder for all games
            game_finder = leaguegamefinder.LeagueGameFinder(
                season_nullable=season,
                season_type_nullable=season_type,
                league_id_nullable="00"  # NBA
            )
            games_df = game_finder.get_data_frames()[0]

            # Remove duplicate games (each game appears twice, once per team)
            games_df = games_df.drop_duplicates(subset=['GAME_ID'])

            return games_df
        except Exception as e:
            logger.error(f"Error fetching season games: {e}")
            return pd.DataFrame()

    def get_standings(self, season: str = "2024-25") -> pd.DataFrame:
        """
        Get current standings.

        Args:
            season: Season string (e.g., '2024-25')

        Returns:
            DataFrame with team standings
        """
        try:
            standings = leaguestandings.LeagueStandings(season=season)
            return standings.get_data_frames()[0]
        except Exception as e:
            logger.error(f"Error fetching standings: {e}")
            return pd.DataFrame()

    def get_team_roster(self, team_abbreviation: str, season: str = "2024-25") -> pd.DataFrame:
        """
        Get team roster.

        Args:
            team_abbreviation: Team abbreviation (e.g., 'LAL')
            season: Season string

        Returns:
            DataFrame with team roster
        """
        team_id = self.get_team_id(team_abbreviation)
        if not team_id:
            return pd.DataFrame()

        try:
            roster = commonteamroster.CommonTeamRoster(
                team_id=team_id,
                season=season
            )
            return roster.get_data_frames()[0]
        except Exception as e:
            logger.error(f"Error fetching roster: {e}")
            return pd.DataFrame()

    def get_historical_games(
        self,
        start_date: str,
        end_date: str,
        include_box_scores: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get historical games within a date range.

        Args:
            start_date: Start date ('YYYY-MM-DD')
            end_date: End date ('YYYY-MM-DD')
            include_box_scores: Whether to fetch detailed box scores

        Returns:
            List of game dictionaries with stats
        """
        games = []
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            daily_games = self.get_games_by_date(date_str)

            if not daily_games.empty:
                for _, game in daily_games.iterrows():
                    game_data = {
                        "game_id": game.get("GAME_ID"),
                        "date": date_str,
                        "home_team": game.get("HOME_TEAM_ID"),
                        "away_team": game.get("VISITOR_TEAM_ID"),
                        "home_score": game.get("HOME_TEAM_SCORE"),
                        "away_score": game.get("VISITOR_TEAM_SCORE"),
                        "status": game.get("GAME_STATUS_TEXT"),
                    }

                    if include_box_scores and game_data["game_id"]:
                        game_data["box_score"] = self.get_box_score(game_data["game_id"])

                    games.append(game_data)

            current += timedelta(days=1)

        logger.info(f"Fetched {len(games)} NBA games from {start_date} to {end_date}")
        return games
