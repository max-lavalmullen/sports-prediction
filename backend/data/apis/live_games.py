"""
Live Games Service.

Provides unified access to today's games and upcoming fixtures
across all sports with caching and scheduling support.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass, field
from loguru import logger
import asyncio

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from .stats_service import StatsService, SportType


@dataclass
class Game:
    """Standardized game representation across sports."""
    game_id: str
    sport: str
    date: str
    time: Optional[str]
    home_team: str
    away_team: str
    home_team_abbr: Optional[str] = None
    away_team_abbr: Optional[str] = None
    venue: Optional[str] = None
    status: str = "scheduled"  # scheduled, in_progress, final
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    league: Optional[str] = None
    season: Optional[str] = None
    week: Optional[int] = None
    # Betting lines (if available)
    spread_line: Optional[float] = None
    total_line: Optional[float] = None
    home_moneyline: Optional[int] = None
    away_moneyline: Optional[int] = None
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "game_id": self.game_id,
            "sport": self.sport,
            "date": self.date,
            "time": self.time,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "home_team_abbr": self.home_team_abbr,
            "away_team_abbr": self.away_team_abbr,
            "venue": self.venue,
            "status": self.status,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "league": self.league,
            "season": self.season,
            "week": self.week,
            "spread_line": self.spread_line,
            "total_line": self.total_line,
            "home_moneyline": self.home_moneyline,
            "away_moneyline": self.away_moneyline,
            "metadata": self.metadata,
        }


class LiveGamesService:
    """
    Service for fetching live and upcoming games across all sports.

    Features:
    - Unified interface for all sports
    - Caching with TTL to minimize API calls
    - Standardized game format
    - Support for date ranges
    """

    def __init__(self, cache_ttl_minutes: int = 5):
        """
        Initialize the live games service.

        Args:
            cache_ttl_minutes: Cache time-to-live in minutes
        """
        self.stats_service = StatsService()
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self._cache: Dict[str, tuple[datetime, Any]] = {}

    def _get_cached(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self._cache:
            cached_time, value = self._cache[key]
            if datetime.now() - cached_time < self.cache_ttl:
                return value
        return None

    def _set_cached(self, key: str, value: Any):
        """Set value in cache."""
        self._cache[key] = (datetime.now(), value)

    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()

    def get_todays_games(
        self,
        sports: Optional[List[SportType]] = None
    ) -> List[Game]:
        """
        Get all games scheduled for today.

        Args:
            sports: List of sports to fetch (default: all available)

        Returns:
            List of Game objects
        """
        if sports is None:
            sports = self.stats_service.available_sports

        all_games = []
        today = datetime.now().strftime("%Y-%m-%d")

        for sport in sports:
            cache_key = f"today_{sport}_{today}"
            cached = self._get_cached(cache_key)

            if cached is not None:
                all_games.extend(cached)
                continue

            games = self._fetch_games_for_sport(sport, today)
            self._set_cached(cache_key, games)
            all_games.extend(games)

        return sorted(all_games, key=lambda g: (g.date, g.time or ""))

    def get_games_by_date(
        self,
        date: str,
        sports: Optional[List[SportType]] = None
    ) -> List[Game]:
        """
        Get games for a specific date.

        Args:
            date: Date string in YYYY-MM-DD format
            sports: List of sports to fetch

        Returns:
            List of Game objects
        """
        if sports is None:
            sports = self.stats_service.available_sports

        all_games = []

        for sport in sports:
            cache_key = f"date_{sport}_{date}"
            cached = self._get_cached(cache_key)

            if cached is not None:
                all_games.extend(cached)
                continue

            games = self._fetch_games_for_sport(sport, date)
            self._set_cached(cache_key, games)
            all_games.extend(games)

        return sorted(all_games, key=lambda g: (g.date, g.time or ""))

    def get_upcoming_games(
        self,
        days_ahead: int = 7,
        sports: Optional[List[SportType]] = None
    ) -> List[Game]:
        """
        Get upcoming games for the next N days.

        Args:
            days_ahead: Number of days to look ahead
            sports: List of sports to fetch

        Returns:
            List of Game objects
        """
        all_games = []
        start_date = datetime.now()

        for i in range(days_ahead):
            date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            games = self.get_games_by_date(date, sports)
            all_games.extend(games)

        return all_games

    def _fetch_games_for_sport(self, sport: str, date: str) -> List[Game]:
        """
        Fetch games for a specific sport and date.

        Args:
            sport: Sport type
            date: Date string

        Returns:
            List of Game objects
        """
        sport = sport.lower()
        games = []

        try:
            if sport == "nba":
                games = self._fetch_nba_games(date)
            elif sport == "nfl":
                games = self._fetch_nfl_games(date)
            elif sport == "mlb":
                games = self._fetch_mlb_games(date)
            elif sport == "soccer":
                games = self._fetch_soccer_games(date)
        except Exception as e:
            logger.error(f"Error fetching {sport} games for {date}: {e}")

        return games

    def _fetch_nba_games(self, date: str) -> List[Game]:
        """Fetch NBA games for a date."""
        games = []
        fetcher = self.stats_service._nba

        if fetcher is None:
            return games

        try:
            df = fetcher.get_games_by_date(date)

            if df.empty:
                return games

            for _, row in df.iterrows():
                game = Game(
                    game_id=str(row.get("GAME_ID", "")),
                    sport="nba",
                    date=date,
                    time=row.get("GAME_STATUS_TEXT", ""),
                    home_team=str(row.get("HOME_TEAM_ID", "")),
                    away_team=str(row.get("VISITOR_TEAM_ID", "")),
                    home_score=row.get("HOME_TEAM_SCORE"),
                    away_score=row.get("VISITOR_TEAM_SCORE"),
                    status=self._parse_nba_status(row.get("GAME_STATUS_ID")),
                    league="NBA",
                )
                games.append(game)

        except Exception as e:
            logger.error(f"Error fetching NBA games: {e}")

        return games

    def _fetch_nfl_games(self, date: str) -> List[Game]:
        """Fetch NFL games for a date."""
        games = []
        fetcher = self.stats_service._nfl

        if fetcher is None:
            return games

        try:
            year = datetime.strptime(date, "%Y-%m-%d").year
            schedules = fetcher.get_schedules([year])

            if schedules.empty:
                return games

            # Filter to games on the specified date
            day_games = schedules[schedules['gameday'] == date]

            for _, row in day_games.iterrows():
                game = Game(
                    game_id=str(row.get("game_id", "")),
                    sport="nfl",
                    date=date,
                    time=row.get("gametime", ""),
                    home_team=row.get("home_team", ""),
                    away_team=row.get("away_team", ""),
                    home_team_abbr=row.get("home_team", ""),
                    away_team_abbr=row.get("away_team", ""),
                    venue=row.get("stadium", ""),
                    home_score=row.get("home_score"),
                    away_score=row.get("away_score"),
                    spread_line=row.get("spread_line"),
                    total_line=row.get("total_line"),
                    home_moneyline=row.get("home_moneyline"),
                    away_moneyline=row.get("away_moneyline"),
                    league="NFL",
                    season=str(row.get("season", "")),
                    week=row.get("week"),
                    status="final" if pd.notna(row.get("result")) else "scheduled",
                )
                games.append(game)

        except Exception as e:
            logger.error(f"Error fetching NFL games: {e}")

        return games

    def _fetch_mlb_games(self, date: str) -> List[Game]:
        """Fetch MLB games for a date."""
        games = []
        fetcher = self.stats_service._mlb

        if fetcher is None:
            return games

        try:
            year = datetime.strptime(date, "%Y-%m-%d").year

            # Check a few teams to find games on this date
            seen_games = set()

            for team in fetcher.TEAMS[:10]:  # Sample teams
                try:
                    schedule = fetcher.get_team_schedule(year, team)
                    if schedule.empty:
                        continue

                    day_games = schedule[schedule['Date'] == date]

                    for _, row in day_games.iterrows():
                        # Create unique key to avoid duplicates
                        game_key = f"{date}_{row.get('Opp', '')}_{team}"
                        if game_key in seen_games:
                            continue
                        seen_games.add(game_key)

                        is_home = row.get('Home_Away', '') == ''
                        game = Game(
                            game_id=f"mlb_{date}_{team}_{row.get('Opp', '')}",
                            sport="mlb",
                            date=date,
                            time=row.get('Time', ''),
                            home_team=team if is_home else row.get('Opp', ''),
                            away_team=row.get('Opp', '') if is_home else team,
                            home_team_abbr=team if is_home else row.get('Opp', ''),
                            away_team_abbr=row.get('Opp', '') if is_home else team,
                            home_score=row.get('R') if is_home else row.get('RA'),
                            away_score=row.get('RA') if is_home else row.get('R'),
                            league="MLB",
                            status="final" if pd.notna(row.get('W/L')) else "scheduled",
                        )
                        games.append(game)

                except Exception as e:
                    logger.debug(f"Could not fetch {team} schedule: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error fetching MLB games: {e}")

        return games

    def _fetch_soccer_games(self, date: str) -> List[Game]:
        """Fetch soccer games for a date."""
        games = []
        fetcher = self.stats_service._soccer

        if fetcher is None:
            return games

        # For historical data, we can check cached matches
        # Live fixtures would need an external API (implemented in odds integration)
        logger.debug(f"Soccer live games for {date} - requires odds API integration")

        return games

    def _parse_nba_status(self, status_id: Any) -> str:
        """Parse NBA game status ID to string."""
        try:
            status_id = int(status_id)
            if status_id == 1:
                return "scheduled"
            elif status_id == 2:
                return "in_progress"
            elif status_id == 3:
                return "final"
        except (ValueError, TypeError):
            pass
        return "scheduled"

    def get_games_needing_predictions(
        self,
        sports: Optional[List[SportType]] = None
    ) -> List[Game]:
        """
        Get upcoming games that need predictions generated.

        Returns games that:
        - Are scheduled for today or tomorrow
        - Don't have a final status
        - Are from enabled sports

        Args:
            sports: Sports to check

        Returns:
            List of Game objects needing predictions
        """
        games = self.get_upcoming_games(days_ahead=2, sports=sports)

        return [g for g in games if g.status != "final"]

    def get_games_summary(self) -> Dict[str, Any]:
        """
        Get summary of today's games across all sports.

        Returns:
            Dictionary with game counts and status breakdown
        """
        games = self.get_todays_games()

        summary = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_games": len(games),
            "by_sport": {},
            "by_status": {
                "scheduled": 0,
                "in_progress": 0,
                "final": 0,
            }
        }

        for game in games:
            # By sport
            if game.sport not in summary["by_sport"]:
                summary["by_sport"][game.sport] = 0
            summary["by_sport"][game.sport] += 1

            # By status
            if game.status in summary["by_status"]:
                summary["by_status"][game.status] += 1

        return summary


# Singleton instance
live_games_service = LiveGamesService()


def get_todays_games(sports: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Convenience function to get today's games as dictionaries.

    Args:
        sports: List of sport types

    Returns:
        List of game dictionaries
    """
    games = live_games_service.get_todays_games(sports)
    return [g.to_dict() for g in games]


def get_upcoming_games(days: int = 7, sports: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Convenience function to get upcoming games.

    Args:
        days: Days to look ahead
        sports: List of sport types

    Returns:
        List of game dictionaries
    """
    games = live_games_service.get_upcoming_games(days, sports)
    return [g.to_dict() for g in games]
