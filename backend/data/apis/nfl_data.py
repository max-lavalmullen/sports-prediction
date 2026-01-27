"""
NFL Data Fetcher using nfl_data_py.

Fetches historical play-by-play data, player stats, team stats,
and schedules from nflfastR data via the nfl_data_py package.
"""

import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any
from loguru import logger

try:
    import nfl_data_py as nfl
    NFL_DATA_AVAILABLE = True
except ImportError:
    NFL_DATA_AVAILABLE = False
    logger.warning("nfl_data_py not installed. NFL data fetching will be unavailable.")


class NFLDataFetcher:
    """Fetches NFL data from nflfastR via nfl_data_py."""

    # NFL team abbreviations
    TEAMS = [
        "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
        "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
        "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
        "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS"
    ]

    def __init__(self):
        if not NFL_DATA_AVAILABLE:
            raise ImportError("nfl_data_py package is required for NFL data fetching")
        self._pbp_cache: Dict[int, pd.DataFrame] = {}
        self._schedule_cache: Dict[int, pd.DataFrame] = {}

    def get_play_by_play(
        self,
        seasons: List[int],
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Get play-by-play data for specified seasons.

        Args:
            seasons: List of seasons (e.g., [2023, 2024])
            columns: Specific columns to return (None for all)

        Returns:
            DataFrame with play-by-play data
        """
        try:
            # Check cache first
            cached_seasons = [s for s in seasons if s in self._pbp_cache]
            uncached_seasons = [s for s in seasons if s not in self._pbp_cache]

            if uncached_seasons:
                logger.info(f"Fetching PBP data for seasons: {uncached_seasons}")
                new_pbp = nfl.import_pbp_data(uncached_seasons, columns=columns)

                # Cache by season
                for season in uncached_seasons:
                    self._pbp_cache[season] = new_pbp[new_pbp['season'] == season]

            # Combine cached data
            all_data = pd.concat([self._pbp_cache[s] for s in seasons], ignore_index=True)
            return all_data

        except Exception as e:
            logger.error(f"Error fetching play-by-play data: {e}")
            return pd.DataFrame()

    def get_schedules(self, seasons: List[int]) -> pd.DataFrame:
        """
        Get game schedules for specified seasons.

        Args:
            seasons: List of seasons (e.g., [2023, 2024])

        Returns:
            DataFrame with schedule/game data
        """
        try:
            schedules = nfl.import_schedules(seasons)
            return schedules
        except Exception as e:
            logger.error(f"Error fetching schedules: {e}")
            return pd.DataFrame()

    def get_weekly_stats(
        self,
        seasons: List[int],
        stat_type: str = "passing"
    ) -> pd.DataFrame:
        """
        Get weekly player stats.

        Args:
            seasons: List of seasons
            stat_type: Type of stats ('passing', 'rushing', 'receiving')

        Returns:
            DataFrame with weekly player stats
        """
        try:
            stats = nfl.import_weekly_data(seasons)
            return stats
        except Exception as e:
            logger.error(f"Error fetching weekly stats: {e}")
            return pd.DataFrame()

    def get_seasonal_stats(self, seasons: List[int]) -> pd.DataFrame:
        """
        Get season-level player stats.

        Args:
            seasons: List of seasons

        Returns:
            DataFrame with seasonal player stats
        """
        try:
            stats = nfl.import_seasonal_data(seasons)
            return stats
        except Exception as e:
            logger.error(f"Error fetching seasonal stats: {e}")
            return pd.DataFrame()

    def get_roster_data(self, seasons: List[int]) -> pd.DataFrame:
        """
        Get roster data for specified seasons.

        Args:
            seasons: List of seasons

        Returns:
            DataFrame with roster information
        """
        try:
            rosters = nfl.import_rosters(seasons)
            return rosters
        except Exception as e:
            logger.error(f"Error fetching rosters: {e}")
            return pd.DataFrame()

    def get_team_stats(self, seasons: List[int]) -> pd.DataFrame:
        """
        Calculate team-level stats from play-by-play data.

        Args:
            seasons: List of seasons

        Returns:
            DataFrame with team stats aggregated by game
        """
        try:
            pbp = self.get_play_by_play(seasons)

            if pbp.empty:
                return pd.DataFrame()

            # Calculate EPA-based team stats
            team_stats = pbp.groupby(['game_id', 'posteam', 'season', 'week']).agg({
                'epa': 'sum',
                'success': 'mean',
                'yards_gained': 'sum',
                'play_id': 'count',
                'pass': 'sum',
                'rush': 'sum',
                'touchdown': 'sum',
                'interception': 'sum',
                'fumble_lost': 'sum',
            }).reset_index()

            team_stats.columns = [
                'game_id', 'team', 'season', 'week',
                'total_epa', 'success_rate', 'total_yards', 'total_plays',
                'pass_plays', 'rush_plays', 'touchdowns', 'interceptions', 'fumbles_lost'
            ]

            # Calculate per-play metrics
            team_stats['epa_per_play'] = team_stats['total_epa'] / team_stats['total_plays']
            team_stats['yards_per_play'] = team_stats['total_yards'] / team_stats['total_plays']

            return team_stats

        except Exception as e:
            logger.error(f"Error calculating team stats: {e}")
            return pd.DataFrame()

    def get_game_results(self, seasons: List[int]) -> pd.DataFrame:
        """
        Get game results with scores.

        Args:
            seasons: List of seasons

        Returns:
            DataFrame with game results
        """
        schedules = self.get_schedules(seasons)

        if schedules.empty:
            return pd.DataFrame()

        # Filter to completed games
        completed = schedules[schedules['result'].notna()].copy()

        return completed[[
            'game_id', 'season', 'week', 'gameday', 'gametime',
            'home_team', 'away_team', 'home_score', 'away_score',
            'result', 'total', 'spread_line', 'total_line',
            'home_moneyline', 'away_moneyline', 'stadium', 'roof', 'surface'
        ]]

    def get_betting_lines(self, seasons: List[int]) -> pd.DataFrame:
        """
        Get historical betting lines for games.

        Args:
            seasons: List of seasons

        Returns:
            DataFrame with betting lines (spread, total, moneyline)
        """
        schedules = self.get_schedules(seasons)

        if schedules.empty:
            return pd.DataFrame()

        return schedules[[
            'game_id', 'season', 'week', 'gameday',
            'home_team', 'away_team',
            'spread_line', 'total_line',
            'home_moneyline', 'away_moneyline',
            'home_score', 'away_score', 'result', 'total'
        ]]

    def get_historical_games(
        self,
        seasons: List[int],
        include_stats: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get historical games with optional detailed stats.

        Args:
            seasons: List of seasons
            include_stats: Whether to include team stats

        Returns:
            List of game dictionaries
        """
        games = []
        game_results = self.get_game_results(seasons)

        if game_results.empty:
            return games

        team_stats = None
        if include_stats:
            team_stats = self.get_team_stats(seasons)

        for _, game in game_results.iterrows():
            game_data = {
                "game_id": game['game_id'],
                "season": game['season'],
                "week": game['week'],
                "date": game['gameday'],
                "home_team": game['home_team'],
                "away_team": game['away_team'],
                "home_score": game['home_score'],
                "away_score": game['away_score'],
                "spread_line": game.get('spread_line'),
                "total_line": game.get('total_line'),
                "venue": game.get('stadium'),
            }

            if team_stats is not None and not team_stats.empty:
                home_stats = team_stats[
                    (team_stats['game_id'] == game['game_id']) &
                    (team_stats['team'] == game['home_team'])
                ]
                away_stats = team_stats[
                    (team_stats['game_id'] == game['game_id']) &
                    (team_stats['team'] == game['away_team'])
                ]

                if not home_stats.empty:
                    game_data['home_epa'] = home_stats.iloc[0]['total_epa']
                    game_data['home_success_rate'] = home_stats.iloc[0]['success_rate']
                if not away_stats.empty:
                    game_data['away_epa'] = away_stats.iloc[0]['total_epa']
                    game_data['away_success_rate'] = away_stats.iloc[0]['success_rate']

            games.append(game_data)

        logger.info(f"Fetched {len(games)} NFL games for seasons {seasons}")
        return games

    def get_qb_stats(self, seasons: List[int]) -> pd.DataFrame:
        """
        Get quarterback statistics.

        Args:
            seasons: List of seasons

        Returns:
            DataFrame with QB stats
        """
        weekly = self.get_weekly_stats(seasons)

        if weekly.empty:
            return pd.DataFrame()

        # Filter to QBs with significant attempts
        qb_stats = weekly[weekly['attempts'] >= 10][[
            'player_id', 'player_name', 'season', 'week',
            'attempts', 'completions', 'passing_yards', 'passing_tds',
            'interceptions', 'sacks', 'sack_yards', 'passing_epa',
            'cpoe', 'dakota'
        ]]

        return qb_stats