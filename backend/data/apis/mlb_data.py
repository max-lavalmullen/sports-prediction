"""
MLB Data Fetcher using pybaseball.

Fetches historical game data, Statcast data, player stats,
and team stats from Baseball Reference and Statcast via pybaseball.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from loguru import logger

try:
    from pybaseball import (
        schedule_and_record,
        batting_stats,
        pitching_stats,
        team_batting,
        team_pitching,
        statcast,
        statcast_pitcher,
        statcast_batter,
        playerid_lookup,
        cache,
    )
    # Enable caching for faster subsequent requests
    cache.enable()
    PYBASEBALL_AVAILABLE = True
except ImportError:
    PYBASEBALL_AVAILABLE = False
    logger.warning("pybaseball not installed. MLB data fetching will be unavailable.")


class MLBDataFetcher:
    """Fetches MLB data from Baseball Reference and Statcast."""

    # MLB team abbreviations
    TEAMS = [
        "ARI", "ATL", "BAL", "BOS", "CHC", "CHW", "CIN", "CLE",
        "COL", "DET", "HOU", "KC", "LAA", "LAD", "MIA", "MIL",
        "MIN", "NYM", "NYY", "OAK", "PHI", "PIT", "SD", "SF",
        "SEA", "STL", "TB", "TEX", "TOR", "WSH"
    ]

    def __init__(self):
        if not PYBASEBALL_AVAILABLE:
            raise ImportError("pybaseball package is required for MLB data fetching")

    def get_team_schedule(
        self,
        season: int,
        team: str
    ) -> pd.DataFrame:
        """
        Get schedule and results for a team.

        Args:
            season: Year (e.g., 2024)
            team: Team abbreviation (e.g., 'NYY', 'LAD')

        Returns:
            DataFrame with game schedule and results
        """
        try:
            schedule = schedule_and_record(season, team)
            return schedule
        except Exception as e:
            logger.error(f"Error fetching schedule for {team} {season}: {e}")
            return pd.DataFrame()

    def get_batting_stats(
        self,
        start_season: int,
        end_season: Optional[int] = None,
        qual: int = 50
    ) -> pd.DataFrame:
        """
        Get batting stats from FanGraphs.

        Args:
            start_season: Starting year
            end_season: Ending year (None for single season)
            qual: Minimum plate appearances to qualify

        Returns:
            DataFrame with batting statistics
        """
        try:
            if end_season is None:
                end_season = start_season

            stats = batting_stats(start_season, end_season, qual=qual)
            return stats
        except Exception as e:
            logger.error(f"Error fetching batting stats: {e}")
            return pd.DataFrame()

    def get_pitching_stats(
        self,
        start_season: int,
        end_season: Optional[int] = None,
        qual: int = 20
    ) -> pd.DataFrame:
        """
        Get pitching stats from FanGraphs.

        Args:
            start_season: Starting year
            end_season: Ending year (None for single season)
            qual: Minimum innings pitched to qualify

        Returns:
            DataFrame with pitching statistics
        """
        try:
            if end_season is None:
                end_season = start_season

            stats = pitching_stats(start_season, end_season, qual=qual)
            return stats
        except Exception as e:
            logger.error(f"Error fetching pitching stats: {e}")
            return pd.DataFrame()

    def get_team_batting(self, season: int) -> pd.DataFrame:
        """
        Get team-level batting stats.

        Args:
            season: Year

        Returns:
            DataFrame with team batting statistics
        """
        try:
            stats = team_batting(season)
            return stats
        except Exception as e:
            logger.error(f"Error fetching team batting: {e}")
            return pd.DataFrame()

    def get_team_pitching(self, season: int) -> pd.DataFrame:
        """
        Get team-level pitching stats.

        Args:
            season: Year

        Returns:
            DataFrame with team pitching statistics
        """
        try:
            stats = team_pitching(season)
            return stats
        except Exception as e:
            logger.error(f"Error fetching team pitching: {e}")
            return pd.DataFrame()

    def get_statcast_data(
        self,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Get Statcast pitch-by-pitch data.

        Args:
            start_date: Start date ('YYYY-MM-DD')
            end_date: End date ('YYYY-MM-DD')

        Returns:
            DataFrame with Statcast data
        """
        try:
            data = statcast(start_dt=start_date, end_dt=end_date)
            return data
        except Exception as e:
            logger.error(f"Error fetching Statcast data: {e}")
            return pd.DataFrame()

    def get_pitcher_statcast(
        self,
        player_id: int,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Get Statcast data for a specific pitcher.

        Args:
            player_id: MLB player ID
            start_date: Start date ('YYYY-MM-DD')
            end_date: End date ('YYYY-MM-DD')

        Returns:
            DataFrame with pitcher's Statcast data
        """
        try:
            data = statcast_pitcher(start_dt=start_date, end_dt=end_date, player_id=player_id)
            return data
        except Exception as e:
            logger.error(f"Error fetching pitcher Statcast: {e}")
            return pd.DataFrame()

    def get_batter_statcast(
        self,
        player_id: int,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Get Statcast data for a specific batter.

        Args:
            player_id: MLB player ID
            start_date: Start date ('YYYY-MM-DD')
            end_date: End date ('YYYY-MM-DD')

        Returns:
            DataFrame with batter's Statcast data
        """
        try:
            data = statcast_batter(start_dt=start_date, end_dt=end_date, player_id=player_id)
            return data
        except Exception as e:
            logger.error(f"Error fetching batter Statcast: {e}")
            return pd.DataFrame()

    def lookup_player(
        self,
        last_name: str,
        first_name: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Look up player ID by name.

        Args:
            last_name: Player's last name
            first_name: Player's first name (optional)

        Returns:
            DataFrame with player ID information
        """
        try:
            if first_name:
                result = playerid_lookup(last_name, first_name)
            else:
                result = playerid_lookup(last_name)
            return result
        except Exception as e:
            logger.error(f"Error looking up player: {e}")
            return pd.DataFrame()

    def get_game_results(self, season: int) -> pd.DataFrame:
        """
        Get all game results for a season.

        Args:
            season: Year

        Returns:
            DataFrame with all game results
        """
        all_games = []

        for team in self.TEAMS:
            try:
                schedule = self.get_team_schedule(season, team)
                if not schedule.empty:
                    schedule['team'] = team
                    all_games.append(schedule)
            except Exception as e:
                logger.warning(f"Could not fetch schedule for {team}: {e}")
                continue

        if not all_games:
            return pd.DataFrame()

        combined = pd.concat(all_games, ignore_index=True)

        # Remove duplicate games (each appears twice, once per team)
        combined = combined.drop_duplicates(subset=['Date', 'Opp'], keep='first')

        return combined

    def get_historical_games(
        self,
        seasons: List[int],
        include_statcast: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get historical games with optional Statcast data.

        Args:
            seasons: List of seasons
            include_statcast: Whether to include Statcast data (slow)

        Returns:
            List of game dictionaries
        """
        games = []

        for season in seasons:
            game_results = self.get_game_results(season)

            if game_results.empty:
                continue

            for _, game in game_results.iterrows():
                game_data = {
                    "season": season,
                    "date": game.get('Date'),
                    "team": game.get('team'),
                    "opponent": game.get('Opp'),
                    "result": game.get('W/L'),
                    "runs_scored": game.get('R'),
                    "runs_allowed": game.get('RA'),
                    "innings": game.get('Inn'),
                    "record": game.get('W-L'),
                    "home_away": "home" if game.get('Home_Away') == '' else "away",
                    "streak": game.get('Streak'),
                }
                games.append(game_data)

        logger.info(f"Fetched {len(games)} MLB games for seasons {seasons}")
        return games

    def get_pitcher_game_logs(
        self,
        player_name: str,
        season: int
    ) -> pd.DataFrame:
        """
        Get game-by-game pitching stats for a player.

        Args:
            player_name: "First Last" format
            season: Year

        Returns:
            DataFrame with pitcher game logs
        """
        try:
            parts = player_name.split()
            if len(parts) < 2:
                return pd.DataFrame()

            player_info = self.lookup_player(parts[1], parts[0])
            if player_info.empty:
                return pd.DataFrame()

            player_id = player_info.iloc[0]['key_mlbam']

            # Get Statcast data for the season
            start_date = f"{season}-03-01"
            end_date = f"{season}-11-01"

            return self.get_pitcher_statcast(player_id, start_date, end_date)

        except Exception as e:
            logger.error(f"Error fetching pitcher game logs: {e}")
            return pd.DataFrame()

    def get_advanced_batting_metrics(self, season: int) -> pd.DataFrame:
        """
        Get advanced batting metrics (wOBA, wRC+, etc.).

        Args:
            season: Year

        Returns:
            DataFrame with advanced batting metrics
        """
        stats = self.get_batting_stats(season)

        if stats.empty:
            return pd.DataFrame()

        # Select key advanced metrics
        key_columns = [
            'Name', 'Team', 'G', 'PA', 'HR', 'R', 'RBI', 'SB',
            'BB%', 'K%', 'ISO', 'BABIP', 'AVG', 'OBP', 'SLG', 'wOBA',
            'wRC+', 'WAR', 'Barrel%', 'HardHit%', 'xBA', 'xSLG', 'xwOBA'
        ]

        available_cols = [c for c in key_columns if c in stats.columns]
        return stats[available_cols]

    def get_advanced_pitching_metrics(self, season: int) -> pd.DataFrame:
        """
        Get advanced pitching metrics (FIP, xFIP, etc.).

        Args:
            season: Year

        Returns:
            DataFrame with advanced pitching metrics
        """
        stats = self.get_pitching_stats(season)

        if stats.empty:
            return pd.DataFrame()

        # Select key advanced metrics
        key_columns = [
            'Name', 'Team', 'G', 'GS', 'IP', 'W', 'L', 'SV',
            'ERA', 'WHIP', 'K/9', 'BB/9', 'HR/9', 'K%', 'BB%',
            'FIP', 'xFIP', 'SIERA', 'WAR', 'Stuff+', 'Location+', 'Pitching+'
        ]

        available_cols = [c for c in key_columns if c in stats.columns]
        return stats[available_cols]