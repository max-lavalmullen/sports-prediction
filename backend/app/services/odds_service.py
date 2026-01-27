"""
Odds fetching and processing service.
"""
import asyncio
from datetime import datetime
from typing import Optional, List, Dict
import httpx
from loguru import logger
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.api.websocket.odds import push_odds_update
from app.api.websocket.alerts import push_value_alert
from app.models.odds import OddsHistory
from app.models.game import Game


class OddsService:
    """Service for fetching and processing odds from various APIs."""

    def __init__(self):
        self.api_key = settings.ODDS_API_KEY
        self.base_url = settings.ODDS_API_BASE_URL

    async def fetch_odds(
        self,
        sport: str,
        markets: List[str] = ["h2h", "spreads", "totals"]
    ) -> List[Dict]:
        """
        Fetch current odds from The Odds API.

        Args:
            sport: Sport key (e.g., 'basketball_nba', 'americanfootball_nfl')
            markets: List of market types to fetch

        Returns:
            List of games with odds from multiple sportsbooks
        """
        if not self.api_key:
            logger.warning("ODDS_API_KEY not configured")
            return []

        url = f"{self.base_url}/sports/{sport}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "markets": ",".join(markets),
            "oddsFormat": "american"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=30.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Error fetching odds: {e}")
                return []

    async def fetch_live_odds(self, sport: str) -> List[Dict]:
        """
        Fetch live/in-play odds from The Odds API.

        Note: Live odds require a separate endpoint and may have different
        rate limits. Not all sportsbooks provide live odds through the API.

        Args:
            sport: Sport key (e.g., 'basketball_nba', 'americanfootball_nfl')

        Returns:
            List of live games with current odds
        """
        if not self.api_key:
            logger.warning("ODDS_API_KEY not configured")
            return []

        # The Odds API uses the same endpoint but filters for live events
        url = f"{self.base_url}/sports/{sport}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american",
            "eventIds": "",  # Empty fetches all, can filter specific games
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=30.0)
                response.raise_for_status()
                all_games = response.json()

                # Filter for games that are currently live (commenced but not completed)
                live_games = []
                now = datetime.utcnow()

                for game in all_games:
                    commence_time_str = game.get("commence_time")
                    if commence_time_str:
                        # Parse ISO format timestamp
                        commence_time = datetime.fromisoformat(
                            commence_time_str.replace("Z", "+00:00")
                        ).replace(tzinfo=None)

                        # Game is live if it started within reasonable game duration
                        # NBA: ~2.5 hrs, NFL: ~3.5 hrs, MLB: ~3 hrs, Soccer: ~2 hrs
                        max_duration_hours = {
                            "basketball_nba": 3,
                            "americanfootball_nfl": 4,
                            "baseball_mlb": 4,
                            "soccer_epl": 2.5,
                        }.get(sport, 3)

                        hours_since_start = (now - commence_time).total_seconds() / 3600

                        if 0 <= hours_since_start <= max_duration_hours:
                            game["is_live"] = True
                            live_games.append(game)

                logger.info(f"Found {len(live_games)} live games for {sport}")
                return live_games

            except httpx.HTTPError as e:
                logger.error(f"Error fetching live odds: {e}")
                return []

    async def fetch_player_props(
        self,
        sport: str,
        event_id: str,
        prop_markets: List[str]
    ) -> List[Dict]:
        """
        Fetch player prop odds for a specific event.

        Args:
            sport: Sport key
            event_id: Specific game/event ID
            prop_markets: Prop types (e.g., ['player_points', 'player_rebounds'])
        """
        if not self.api_key:
            return []

        url = f"{self.base_url}/sports/{sport}/events/{event_id}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "markets": ",".join(prop_markets),
            "oddsFormat": "american"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=30.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Error fetching props: {e}")
                return []

    def calculate_implied_probability(self, american_odds: int) -> float:
        """Convert American odds to implied probability."""
        if american_odds > 0:
            return 100 / (american_odds + 100)
        else:
            return abs(american_odds) / (abs(american_odds) + 100)

    def calculate_no_vig_probability(
        self,
        odds_a: int,
        odds_b: int
    ) -> tuple[float, float]:
        """Calculate no-vig fair probabilities for a two-way market."""
        prob_a = self.calculate_implied_probability(odds_a)
        prob_b = self.calculate_implied_probability(odds_b)

        total = prob_a + prob_b  # Will be > 1 due to vig

        fair_a = prob_a / total
        fair_b = prob_b / total

        return fair_a, fair_b

    def find_best_odds(self, odds_list: List[Dict]) -> Dict:
        """Find best available odds across sportsbooks for each selection."""
        best = {}

        for book_odds in odds_list:
            sportsbook = book_odds.get("sportsbook")
            for market in book_odds.get("markets", []):
                market_key = market.get("key")

                if market_key not in best:
                    best[market_key] = {}

                for outcome in market.get("outcomes", []):
                    selection = outcome.get("name")
                    price = outcome.get("price")

                    if selection not in best[market_key]:
                        best[market_key][selection] = {
                            "odds": price,
                            "sportsbook": sportsbook
                        }
                    elif price > best[market_key][selection]["odds"]:
                        best[market_key][selection] = {
                            "odds": price,
                            "sportsbook": sportsbook
                        }

        return best

    async def save_odds_to_db(self, session: AsyncSession, odds_data: List[Dict]):
        """Save fetched odds to database."""
        for game_data in odds_data:
            external_id = game_data.get("id")
            
            # Find internal game ID
            result = await session.execute(
                select(Game).where(Game.external_id == external_id)
            )
            game = result.scalars().first()
            
            if not game:
                # Ideally create game here if it doesn't exist
                # For now, skip
                continue

            timestamp = datetime.utcnow()
            
            for bookmaker in game_data.get("bookmakers", []):
                sportsbook = bookmaker.get("title")
                for market in bookmaker.get("markets", []):
                    market_key = market.get("key")
                    for outcome in market.get("outcomes", []):
                        selection = outcome.get("name")
                        price = outcome.get("price")
                        point = outcome.get("point")  # spread or total

                        odds_entry = OddsHistory(
                            time=timestamp,
                            game_id=game.id,
                            sportsbook=sportsbook,
                            market_type=market_key,
                            selection=selection,
                            odds_american=price if abs(price) >= 100 else None, # API returns decimal sometimes? No, American format requested
                            odds_decimal=self.calculate_decimal_odds(price), # Helper needed or conversion
                            line=point
                        )
                        session.add(odds_entry)
        
        await session.commit()

    def calculate_decimal_odds(self, american_odds: int) -> float:
        """Convert American odds to Decimal."""
        if american_odds > 0:
            return 1 + (american_odds / 100)
        else:
            return 1 + (100 / abs(american_odds))


odds_service = OddsService()


@shared_task(name="app.services.odds_service.fetch_live_odds")
def fetch_live_odds():
    """Celery task to fetch and store live odds."""
    import asyncio

    async def _fetch():
        sports = [
            "basketball_nba",
            "americanfootball_nfl",
            "baseball_mlb",
            "soccer_epl"
        ]

        async with AsyncSessionLocal() as session:
            for sport in sports:
                odds = await odds_service.fetch_odds(sport)
                
                # Save to DB
                await odds_service.save_odds_to_db(session, odds)

                for game in odds:
                    # Push to WebSocket
                    await push_odds_update({
                        "sport": sport,
                        "game_id": game.get("id"),
                        "home_team": game.get("home_team"),
                        "away_team": game.get("away_team"),
                        "bookmakers": game.get("bookmakers", []),
                        "timestamp": datetime.utcnow().isoformat()
                    })

    asyncio.run(_fetch())
