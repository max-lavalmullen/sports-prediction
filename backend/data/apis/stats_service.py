"""
Unified Stats Service.

Provides a single interface for fetching sports data across
NBA, NFL, MLB, and Soccer using sport-specific data fetchers.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Literal
from loguru import logger

from .nba_data import NBADataFetcher, NBA_API_AVAILABLE
from .nfl_data import NFLDataFetcher, NFL_DATA_AVAILABLE
from .mlb_data import MLBDataFetcher, PYBASEBALL_AVAILABLE
from .soccer_data import SoccerDataFetcher, HTTPX_AVAILABLE

SOCCER_AVAILABLE = HTTPX_AVAILABLE

SportType = Literal["nba", "nfl", "mlb", "soccer"]


class StatsService:
    """
    Unified service for fetching sports statistics.

    Provides a consistent interface across different sports and data sources.
    """

    def __init__(self):
        """Initialize available data fetchers."""
        self._nba: Optional[NBADataFetcher] = None
        self._nfl: Optional[NFLDataFetcher] = None
        self._mlb: Optional[MLBDataFetcher] = None
        self._soccer: Optional[SoccerDataFetcher] = None

        # Initialize available fetchers
        if NBA_API_AVAILABLE:
            try:
                self._nba = NBADataFetcher()
                logger.info("NBA data fetcher initialized")
            except Exception as e:
                logger.error(f"Failed to initialize NBA fetcher: {e}")

        if NFL_DATA_AVAILABLE:
            try:
                self._nfl = NFLDataFetcher()
                logger.info("NFL data fetcher initialized")
            except Exception as e:
                logger.error(f"Failed to initialize NFL fetcher: {e}")

        if PYBASEBALL_AVAILABLE:
            try:
                self._mlb = MLBDataFetcher()
                logger.info("MLB data fetcher initialized")
            except Exception as e:
                logger.error(f"Failed to initialize MLB fetcher: {e}")

        if SOCCER_AVAILABLE:
            try:
                self._soccer = SoccerDataFetcher()
                logger.info("Soccer data fetcher initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Soccer fetcher: {e}")

    @property
    def available_sports(self) -> List[str]:
        """Get list of available sports based on installed packages."""
        sports = []
        if self._nba is not None:
            sports.append("nba")
        if self._nfl is not None:
            sports.append("nfl")
        if self._mlb is not None:
            sports.append("mlb")
        if self._soccer is not None:
            sports.append("soccer")
        return sports

    def is_sport_available(self, sport: str) -> bool:
        """Check if a sport is available for data fetching."""
        return sport.lower() in self.available_sports

    def get_fetcher(self, sport: str):
        """Get the appropriate fetcher for a sport."""
        sport = sport.lower()
        if sport == "nba":
            return self._nba
        elif sport == "nfl":
            return self._nfl
        elif sport == "mlb":
            return self._mlb
        elif sport == "soccer":
            return self._soccer
        else:
            raise ValueError(f"Unknown sport: {sport}")

    def get_historical_games(
        self,
        sport: SportType,
        seasons: Optional[List[int]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_stats: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get historical games for a sport.

        Args:
            sport: Sport type ('nba', 'nfl', 'mlb')
            seasons: List of seasons/years (used by NFL, MLB)
            start_date: Start date for date range (used by NBA)
            end_date: End date for date range (used by NBA)
            include_stats: Whether to include detailed stats

        Returns:
            List of game dictionaries with standardized format
        """
        sport = sport.lower()

        if not self.is_sport_available(sport):
            logger.error(f"Sport {sport} is not available")
            return []

        try:
            if sport == "nba":
                if start_date and end_date:
                    return self._nba.get_historical_games(
                        start_date, end_date,
                        include_box_scores=include_stats
                    )
                else:
                    # Default to last 30 days
                    end = datetime.now()
                    start = end - timedelta(days=30)
                    return self._nba.get_historical_games(
                        start.strftime("%Y-%m-%d"),
                        end.strftime("%Y-%m-%d"),
                        include_box_scores=include_stats
                    )

            elif sport == "nfl":
                if seasons is None:
                    seasons = [datetime.now().year]
                return self._nfl.get_historical_games(seasons, include_stats=include_stats)

            elif sport == "mlb":
                if seasons is None:
                    seasons = [datetime.now().year]
                return self._mlb.get_historical_games(seasons)

            elif sport == "soccer":
                # Get soccer matches as team logs
                start_year = seasons[0] if seasons else 2020
                matches = self._soccer.get_historical_data(start_season=start_year)
                if matches.empty:
                    return []
                # Convert to list of dicts
                return matches.to_dict('records')

        except Exception as e:
            logger.error(f"Error fetching historical games for {sport}: {e}")
            return []

    def get_team_stats(
        self,
        sport: SportType,
        team: str,
        season: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get team statistics.

        Args:
            sport: Sport type
            team: Team abbreviation
            season: Season string (format varies by sport)

        Returns:
            DataFrame with team stats
        """
        sport = sport.lower()

        if not self.is_sport_available(sport):
            return pd.DataFrame()

        try:
            if sport == "nba":
                season = season or "2024-25"
                return self._nba.get_team_game_log(team, season=season)

            elif sport == "nfl":
                year = int(season) if season else datetime.now().year
                stats = self._nfl.get_team_stats([year])
                return stats[stats['team'] == team]

            elif sport == "mlb":
                year = int(season) if season else datetime.now().year
                batting = self._mlb.get_team_batting(year)
                pitching = self._mlb.get_team_pitching(year)
                return pd.merge(
                    batting[batting['Team'] == team],
                    pitching[pitching['Team'] == team],
                    on='Team',
                    suffixes=('_bat', '_pitch')
                )

        except Exception as e:
            logger.error(f"Error fetching team stats: {e}")
            return pd.DataFrame()

    def get_player_stats(
        self,
        sport: SportType,
        player_name: str,
        season: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get player statistics.

        Args:
            sport: Sport type
            player_name: Player's full name
            season: Season string

        Returns:
            DataFrame with player stats
        """
        sport = sport.lower()

        if not self.is_sport_available(sport):
            return pd.DataFrame()

        try:
            if sport == "nba":
                season = season or "2024-25"
                return self._nba.get_player_game_log(player_name, season=season)

            elif sport == "nfl":
                year = int(season) if season else datetime.now().year
                weekly = self._nfl.get_weekly_stats([year])
                return weekly[weekly['player_name'].str.lower() == player_name.lower()]

            elif sport == "mlb":
                year = int(season) if season else datetime.now().year
                return self._mlb.get_pitcher_game_logs(player_name, year)

        except Exception as e:
            logger.error(f"Error fetching player stats: {e}")
            return pd.DataFrame()

    def get_today_games(self, sport: SportType) -> pd.DataFrame:
        """
        Get games scheduled for today.

        Args:
            sport: Sport type

        Returns:
            DataFrame with today's games
        """
        sport = sport.lower()
        today = datetime.now().strftime("%Y-%m-%d")

        if not self.is_sport_available(sport):
            return pd.DataFrame()

        try:
            if sport == "nba":
                return self._nba.get_games_by_date(today)

            elif sport == "nfl":
                # NFL schedules work differently - get current week
                year = datetime.now().year
                schedules = self._nfl.get_schedules([year])
                return schedules[schedules['gameday'] == today]

            elif sport == "mlb":
                # MLB - aggregate from team schedules
                games = []
                for team in self._mlb.TEAMS[:5]:  # Sample teams to avoid too many requests
                    schedule = self._mlb.get_team_schedule(datetime.now().year, team)
                    if not schedule.empty:
                        today_games = schedule[schedule['Date'] == today]
                        if not today_games.empty:
                            games.append(today_games)
                return pd.concat(games) if games else pd.DataFrame()

        except Exception as e:
            logger.error(f"Error fetching today's games: {e}")
            return pd.DataFrame()

    def get_standings(self, sport: SportType, season: Optional[str] = None) -> pd.DataFrame:
        """
        Get current standings.

        Args:
            sport: Sport type
            season: Season string

        Returns:
            DataFrame with standings
        """
        sport = sport.lower()

        if not self.is_sport_available(sport):
            return pd.DataFrame()

        try:
            if sport == "nba":
                season = season or "2024-25"
                return self._nba.get_standings(season=season)

            elif sport == "nfl":
                # NFL standings would need additional implementation
                logger.warning("NFL standings not yet implemented")
                return pd.DataFrame()

            elif sport == "mlb":
                # MLB standings from team records
                year = int(season) if season else datetime.now().year
                standings = []
                for team in self._mlb.TEAMS:
                    schedule = self._mlb.get_team_schedule(year, team)
                    if not schedule.empty:
                        last_game = schedule.iloc[-1]
                        standings.append({
                            'team': team,
                            'record': last_game.get('W-L', 'N/A'),
                        })
                return pd.DataFrame(standings)

        except Exception as e:
            logger.error(f"Error fetching standings: {e}")
            return pd.DataFrame()

    def get_betting_relevant_data(
        self,
        sport: SportType,
        game_id: str
    ) -> Dict[str, Any]:
        """
        Get all data relevant for betting predictions on a specific game.

        Args:
            sport: Sport type
            game_id: Game identifier

        Returns:
            Dictionary with comprehensive game data for predictions
        """
        sport = sport.lower()

        if not self.is_sport_available(sport):
            return {}

        data = {
            "game_id": game_id,
            "sport": sport,
            "fetched_at": datetime.now().isoformat(),
        }

        try:
            if sport == "nba":
                box_score = self._nba.get_box_score(game_id)
                data["box_score"] = {
                    "players": box_score["players"].to_dict() if not box_score["players"].empty else {},
                    "teams": box_score["teams"].to_dict() if not box_score["teams"].empty else {},
                }

            elif sport == "nfl":
                # Get relevant PBP data for the game
                # This would require parsing game_id to get season
                pass

            elif sport == "mlb":
                # Get Statcast data if available
                pass

        except Exception as e:
            logger.error(f"Error fetching betting data for game {game_id}: {e}")

        return data

    def bulk_fetch_historical(
        self,
        sport: SportType,
        seasons: List[int],
        save_path: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Bulk fetch historical data for multiple seasons.
        Useful for initial data population.

        Args:
            sport: Sport type
            seasons: List of seasons to fetch
            save_path: Optional path to save CSV

        Returns:
            Combined DataFrame with all historical data
        """
        sport = sport.lower()
        all_data = []

        if not self.is_sport_available(sport):
            return pd.DataFrame()

        for season in seasons:
            logger.info(f"Fetching {sport} data for season {season}")

            try:
                if sport == "nba":
                    season_str = f"{season}-{str(season+1)[-2:]}"
                    games = self._nba.get_season_games(season=season_str)
                    if not games.empty:
                        games['season'] = season
                        all_data.append(games)

                elif sport == "nfl":
                    games = self._nfl.get_game_results([season])
                    if not games.empty:
                        all_data.append(games)

                elif sport == "mlb":
                    games = self._mlb.get_game_results(season)
                    if not games.empty:
                        games['season'] = season
                        all_data.append(games)

            except Exception as e:
                logger.error(f"Error fetching {sport} season {season}: {e}")
                continue

        if not all_data:
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)

        if save_path:
            combined.to_csv(save_path, index=False)
            logger.info(f"Saved {len(combined)} records to {save_path}")

        return combined


# Singleton instance
stats_service = StatsService()