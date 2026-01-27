"""
Odds API Integration.

Fetches real-time betting odds from The Odds API.
Supports moneylines, spreads, totals, and player props.

API Documentation: https://the-odds-api.com/
"""

import httpx
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass, field
from loguru import logger
import os
from enum import Enum


class OddsFormat(str, Enum):
    """Odds format options."""
    AMERICAN = "american"
    DECIMAL = "decimal"


class Market(str, Enum):
    """Available betting markets."""
    H2H = "h2h"  # Moneyline
    SPREADS = "spreads"
    TOTALS = "totals"
    OUTRIGHTS = "outrights"  # Futures
    # Player Props
    PLAYER_POINTS = "player_points"
    PLAYER_REBOUNDS = "player_rebounds"
    PLAYER_ASSISTS = "player_assists"
    PLAYER_THREES = "player_threes"
    PLAYER_BLOCKS = "player_blocks"
    PLAYER_STEALS = "player_steals"
    PLAYER_PRA = "player_points_rebounds_assists"  # Combined


# Sport keys for The Odds API
SPORT_KEYS = {
    "nba": "basketball_nba",
    "nfl": "americanfootball_nfl",
    "mlb": "baseball_mlb",
    "nhl": "icehockey_nhl",
    "ncaaf": "americanfootball_ncaaf",
    "ncaab": "basketball_ncaab",
    # Soccer
    "epl": "soccer_epl",
    "la_liga": "soccer_spain_la_liga",
    "bundesliga": "soccer_germany_bundesliga",
    "serie_a": "soccer_italy_serie_a",
    "ligue_1": "soccer_france_ligue_one",
    "mls": "soccer_usa_mls",
    "champions_league": "soccer_uefa_champs_league",
}


@dataclass
class OddsLine:
    """Represents a single betting line."""
    bookmaker: str
    market: str
    selection: str  # home, away, over, under, etc.
    price: int  # American odds
    price_decimal: float
    point: Optional[float] = None  # Spread or total line
    last_update: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bookmaker": self.bookmaker,
            "market": self.market,
            "selection": self.selection,
            "price": self.price,
            "price_decimal": self.price_decimal,
            "point": self.point,
            "last_update": self.last_update,
        }


@dataclass
class GameOdds:
    """Odds for a single game across all bookmakers."""
    game_id: str
    sport: str
    commence_time: str
    home_team: str
    away_team: str
    moneyline: List[OddsLine] = field(default_factory=list)
    spread: List[OddsLine] = field(default_factory=list)
    total: List[OddsLine] = field(default_factory=list)

    def get_best_odds(self, market: str, selection: str) -> Optional[OddsLine]:
        """Get best available odds for a selection."""
        lines = []
        if market == "h2h":
            lines = self.moneyline
        elif market == "spreads":
            lines = self.spread
        elif market == "totals":
            lines = self.total

        matching = [l for l in lines if l.selection.lower() == selection.lower()]
        if not matching:
            return None

        # Best odds = highest price for positive, lowest absolute for negative
        return max(matching, key=lambda x: x.price)

    def get_consensus_line(self, market: str) -> Optional[float]:
        """Get consensus line (average across books)."""
        lines = []
        if market == "spreads":
            lines = [l.point for l in self.spread if l.point is not None and l.selection.lower() == "home"]
        elif market == "totals":
            lines = [l.point for l in self.total if l.point is not None and l.selection.lower() == "over"]

        if not lines:
            return None
        return sum(lines) / len(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "sport": self.sport,
            "commence_time": self.commence_time,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "moneyline": [l.to_dict() for l in self.moneyline],
            "spread": [l.to_dict() for l in self.spread],
            "total": [l.to_dict() for l in self.total],
            "best_home_ml": self.get_best_odds("h2h", "home"),
            "best_away_ml": self.get_best_odds("h2h", "away"),
            "consensus_spread": self.get_consensus_line("spreads"),
            "consensus_total": self.get_consensus_line("totals"),
        }


class OddsAPIClient:
    """
    Client for The Odds API.

    Usage:
        client = OddsAPIClient(api_key="your-key")
        odds = client.get_odds("nba")
    """

    BASE_URL = "https://api.the-odds-api.com/v4"

    # Popular US bookmakers
    DEFAULT_BOOKMAKERS = [
        "fanduel",
        "draftkings",
        "betmgm",
        "caesars",
        "pointsbetus",
        "betrivers",
        "unibet_us",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        odds_format: OddsFormat = OddsFormat.AMERICAN,
        bookmakers: Optional[List[str]] = None,
    ):
        """
        Initialize the Odds API client.

        Args:
            api_key: The Odds API key (or set ODDS_API_KEY env var)
            odds_format: Format for odds (american or decimal)
            bookmakers: List of bookmaker keys to fetch
        """
        self.api_key = api_key or os.getenv("ODDS_API_KEY")
        if not self.api_key:
            logger.warning("No ODDS_API_KEY provided. Set via env var or constructor.")

        self.odds_format = odds_format
        self.bookmakers = bookmakers or self.DEFAULT_BOOKMAKERS
        self._remaining_requests: Optional[int] = None
        self._used_requests: Optional[int] = None

    @property
    def remaining_requests(self) -> Optional[int]:
        """Get remaining API requests for the month."""
        return self._remaining_requests

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Make API request and handle response."""
        if not self.api_key:
            logger.error("API key not configured")
            return None

        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        params["apiKey"] = self.api_key

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params)

                # Track usage from headers
                self._remaining_requests = int(response.headers.get("x-requests-remaining", 0))
                self._used_requests = int(response.headers.get("x-requests-used", 0))

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Invalid API key")
            elif e.response.status_code == 422:
                logger.error(f"Invalid parameters: {e.response.text}")
            elif e.response.status_code == 429:
                logger.error("Rate limit exceeded")
            else:
                logger.error(f"HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None

    def get_sports(self) -> List[Dict[str, Any]]:
        """
        Get list of available sports.

        Returns:
            List of sport dictionaries with keys: key, group, title, active
        """
        result = self._make_request("sports")
        return result if result else []

    def get_odds(
        self,
        sport: str,
        markets: Optional[List[Market]] = None,
        regions: str = "us",
        bookmakers: Optional[List[str]] = None,
    ) -> List[GameOdds]:
        """
        Get current odds for a sport.

        Args:
            sport: Sport key (nba, nfl, etc.) or API sport key
            markets: List of markets to fetch (default: h2h, spreads, totals)
            regions: Region for bookmakers (us, uk, eu, au)
            bookmakers: Override default bookmakers

        Returns:
            List of GameOdds objects
        """
        # Convert sport name to API key if needed
        sport_key = SPORT_KEYS.get(sport.lower(), sport)

        markets = markets or [Market.H2H, Market.SPREADS, Market.TOTALS]
        bookmakers = bookmakers or self.bookmakers

        params = {
            "regions": regions,
            "markets": ",".join([m.value for m in markets]),
            "oddsFormat": self.odds_format.value,
            "bookmakers": ",".join(bookmakers),
        }

        result = self._make_request(f"sports/{sport_key}/odds", params)

        if not result:
            return []

        return self._parse_odds_response(result, sport)

    def get_event_odds(
        self,
        sport: str,
        event_id: str,
        markets: Optional[List[Market]] = None,
    ) -> Optional[GameOdds]:
        """
        Get odds for a specific event.

        Args:
            sport: Sport key
            event_id: The Odds API event ID
            markets: Markets to fetch

        Returns:
            GameOdds object or None
        """
        sport_key = SPORT_KEYS.get(sport.lower(), sport)
        markets = markets or [Market.H2H, Market.SPREADS, Market.TOTALS]

        params = {
            "regions": "us",
            "markets": ",".join([m.value for m in markets]),
            "oddsFormat": self.odds_format.value,
        }

        result = self._make_request(f"sports/{sport_key}/events/{event_id}/odds", params)

        if not result:
            return None

        parsed = self._parse_odds_response([result], sport)
        return parsed[0] if parsed else None

    def get_player_props(
        self,
        sport: str,
        event_id: str,
        markets: Optional[List[Market]] = None,
        bookmakers: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get player prop odds for a specific event.

        Args:
            sport: Sport key (nba, nfl, etc.)
            event_id: The Odds API event ID
            markets: Prop markets to fetch (default: points, rebounds, assists)
            bookmakers: Override default bookmakers

        Returns:
            List of player prop odds
        """
        sport_key = SPORT_KEYS.get(sport.lower(), sport)
        bookmakers = bookmakers or self.bookmakers

        # Default to main player props
        if markets is None:
            markets = [
                Market.PLAYER_POINTS,
                Market.PLAYER_REBOUNDS,
                Market.PLAYER_ASSISTS,
            ]

        params = {
            "regions": "us",
            "markets": ",".join([m.value for m in markets]),
            "oddsFormat": self.odds_format.value,
            "bookmakers": ",".join(bookmakers),
        }

        result = self._make_request(f"sports/{sport_key}/events/{event_id}/odds", params)

        if not result:
            return []

        return self._parse_props_response(result)

    def _parse_props_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse player props API response."""
        props = []

        for bookmaker in data.get("bookmakers", []):
            book_name = bookmaker.get("key", "")

            for market in bookmaker.get("markets", []):
                market_key = market.get("key", "")

                # Skip non-prop markets
                if not market_key.startswith("player_"):
                    continue

                for outcome in market.get("outcomes", []):
                    prop = {
                        "bookmaker": book_name,
                        "market": market_key,
                        "player": outcome.get("description", ""),
                        "selection": outcome.get("name", ""),  # Over/Under
                        "line": outcome.get("point"),
                        "price": outcome.get("price"),
                        "last_update": bookmaker.get("last_update"),
                    }
                    props.append(prop)

        return props

    def get_scores(
        self,
        sport: str,
        days_from: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Get recent scores for a sport.

        Args:
            sport: Sport key
            days_from: Days back to fetch (1-3)

        Returns:
            List of score dictionaries
        """
        sport_key = SPORT_KEYS.get(sport.lower(), sport)

        params = {
            "daysFrom": min(days_from, 3),
        }

        result = self._make_request(f"sports/{sport_key}/scores", params)
        return result if result else []

    def _parse_odds_response(
        self,
        data: List[Dict[str, Any]],
        sport: str
    ) -> List[GameOdds]:
        """Parse API response into GameOdds objects."""
        games = []

        for event in data:
            game = GameOdds(
                game_id=event.get("id", ""),
                sport=sport,
                commence_time=event.get("commence_time", ""),
                home_team=event.get("home_team", ""),
                away_team=event.get("away_team", ""),
            )

            # Parse bookmaker odds
            for bookmaker in event.get("bookmakers", []):
                book_name = bookmaker.get("key", "")
                last_update = bookmaker.get("last_update", "")

                for market in bookmaker.get("markets", []):
                    market_key = market.get("key", "")

                    for outcome in market.get("outcomes", []):
                        line = OddsLine(
                            bookmaker=book_name,
                            market=market_key,
                            selection=outcome.get("name", ""),
                            price=outcome.get("price", 0) if self.odds_format == OddsFormat.AMERICAN else self._decimal_to_american(outcome.get("price", 2.0)),
                            price_decimal=outcome.get("price", 2.0) if self.odds_format == OddsFormat.DECIMAL else self._american_to_decimal(outcome.get("price", 100)),
                            point=outcome.get("point"),
                            last_update=last_update,
                        )

                        if market_key == "h2h":
                            game.moneyline.append(line)
                        elif market_key == "spreads":
                            game.spread.append(line)
                        elif market_key == "totals":
                            game.total.append(line)

            games.append(game)

        return games

    def _american_to_decimal(self, american: int) -> float:
        """Convert American odds to decimal."""
        if american > 0:
            return 1 + (american / 100)
        else:
            return 1 + (100 / abs(american))

    def _decimal_to_american(self, decimal: float) -> int:
        """Convert decimal odds to American."""
        if decimal >= 2.0:
            return int((decimal - 1) * 100)
        else:
            return int(-100 / (decimal - 1))


class OddsService:
    """
    High-level odds service with caching and helper methods.
    """

    def __init__(self, api_key: Optional[str] = None, cache_ttl_minutes: int = 2):
        """
        Initialize odds service.

        Args:
            api_key: The Odds API key
            cache_ttl_minutes: Cache TTL in minutes
        """
        self.client = OddsAPIClient(api_key=api_key)
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
        """Clear cache."""
        self._cache.clear()

    def get_current_odds(self, sport: str) -> List[GameOdds]:
        """
        Get current odds for a sport with caching.

        Args:
            sport: Sport key

        Returns:
            List of GameOdds
        """
        cache_key = f"odds_{sport}"
        cached = self._get_cached(cache_key)

        if cached is not None:
            return cached

        odds = self.client.get_odds(sport)
        self._set_cached(cache_key, odds)

        return odds

    def get_best_lines(self, sport: str) -> pd.DataFrame:
        """
        Get best available lines for all games in a sport.

        Args:
            sport: Sport key

        Returns:
            DataFrame with best lines for each game
        """
        odds = self.get_current_odds(sport)

        rows = []
        for game in odds:
            row = {
                "game_id": game.game_id,
                "commence_time": game.commence_time,
                "home_team": game.home_team,
                "away_team": game.away_team,
            }

            # Best moneylines
            best_home = game.get_best_odds("h2h", game.home_team)
            best_away = game.get_best_odds("h2h", game.away_team)
            if best_home:
                row["best_home_ml"] = best_home.price
                row["best_home_ml_book"] = best_home.bookmaker
            if best_away:
                row["best_away_ml"] = best_away.price
                row["best_away_ml_book"] = best_away.bookmaker

            # Consensus lines
            row["consensus_spread"] = game.get_consensus_line("spreads")
            row["consensus_total"] = game.get_consensus_line("totals")

            rows.append(row)

        return pd.DataFrame(rows)

    def find_value_bets(
        self,
        sport: str,
        model_probs: Dict[str, Dict[str, float]],
        min_edge: float = 0.03
    ) -> List[Dict[str, Any]]:
        """
        Find bets with positive expected value.

        Args:
            sport: Sport key
            model_probs: Dict of game_id -> {home_prob, away_prob}
            min_edge: Minimum edge required (default 3%)

        Returns:
            List of value bet opportunities
        """
        odds = self.get_current_odds(sport)
        value_bets = []

        for game in odds:
            if game.game_id not in model_probs:
                continue

            probs = model_probs[game.game_id]
            home_prob = probs.get("home_prob", 0.5)
            away_prob = probs.get("away_prob", 0.5)

            # Check home moneyline
            best_home = game.get_best_odds("h2h", game.home_team)
            if best_home:
                implied_prob = 1 / best_home.price_decimal
                edge = home_prob - implied_prob
                if edge >= min_edge:
                    value_bets.append({
                        "game_id": game.game_id,
                        "game": f"{game.away_team} @ {game.home_team}",
                        "bet_type": "moneyline",
                        "selection": game.home_team,
                        "odds": best_home.price,
                        "bookmaker": best_home.bookmaker,
                        "model_prob": home_prob,
                        "implied_prob": implied_prob,
                        "edge": edge,
                        "kelly_fraction": self._calculate_kelly(home_prob, best_home.price_decimal),
                    })

            # Check away moneyline
            best_away = game.get_best_odds("h2h", game.away_team)
            if best_away:
                implied_prob = 1 / best_away.price_decimal
                edge = away_prob - implied_prob
                if edge >= min_edge:
                    value_bets.append({
                        "game_id": game.game_id,
                        "game": f"{game.away_team} @ {game.home_team}",
                        "bet_type": "moneyline",
                        "selection": game.away_team,
                        "odds": best_away.price,
                        "bookmaker": best_away.bookmaker,
                        "model_prob": away_prob,
                        "implied_prob": implied_prob,
                        "edge": edge,
                        "kelly_fraction": self._calculate_kelly(away_prob, best_away.price_decimal),
                    })

        # Sort by edge
        value_bets.sort(key=lambda x: x["edge"], reverse=True)

        return value_bets

    def _calculate_kelly(self, prob: float, decimal_odds: float) -> float:
        """
        Calculate Kelly Criterion fraction.

        Kelly = (p * (d - 1) - (1 - p)) / (d - 1)
        where p = probability, d = decimal odds
        """
        if decimal_odds <= 1:
            return 0

        q = 1 - prob
        b = decimal_odds - 1

        kelly = (prob * b - q) / b

        # Cap at 25% (quarter Kelly is common practice)
        return max(0, min(kelly * 0.25, 0.25))

    def get_line_movement(
        self,
        sport: str,
        game_id: str,
        hours_back: int = 24
    ) -> Dict[str, Any]:
        """
        Get line movement for a game.

        Note: Full historical line data requires paid plans.
        This provides current snapshot only.

        Args:
            sport: Sport key
            game_id: Game ID
            hours_back: Hours of history (limited by API plan)

        Returns:
            Line movement data
        """
        game = self.client.get_event_odds(sport, game_id)

        if not game:
            return {}

        return {
            "game_id": game_id,
            "timestamp": datetime.now().isoformat(),
            "spread": game.get_consensus_line("spreads"),
            "total": game.get_consensus_line("totals"),
            "home_ml_best": game.get_best_odds("h2h", game.home_team),
            "away_ml_best": game.get_best_odds("h2h", game.away_team),
        }


# Singleton instance
odds_service = OddsService()


def get_odds(sport: str) -> List[Dict[str, Any]]:
    """
    Convenience function to get current odds.

    Args:
        sport: Sport key (nba, nfl, mlb, etc.)

    Returns:
        List of game odds dictionaries
    """
    odds = odds_service.get_current_odds(sport)
    return [o.to_dict() for o in odds]


def get_best_lines(sport: str) -> pd.DataFrame:
    """
    Convenience function to get best available lines.

    Args:
        sport: Sport key

    Returns:
        DataFrame with best lines
    """
    return odds_service.get_best_lines(sport)
