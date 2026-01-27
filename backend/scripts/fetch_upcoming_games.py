#!/usr/bin/env python3
"""
Fetch upcoming games from The Odds API and populate the database.
Run this script to initialize the database with upcoming games.

Usage:
    python scripts/fetch_upcoming_games.py
"""
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from loguru import logger

# Set up database connection
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.game import Game, Team, Sport, GameStatus
from sqlalchemy import select


SPORT_MAPPING = {
    "basketball_nba": ("NBA", Sport.NBA),
    "americanfootball_nfl": ("NFL", Sport.NFL),
    "baseball_mlb": ("MLB", Sport.MLB),
    "soccer_epl": ("EPL", Sport.SOCCER),
    "americanfootball_ncaaf": ("NCAAF", Sport.NCAAF),
    "basketball_ncaab": ("NCAAB", Sport.NCAAB),
}

SPORTS_TO_FETCH = [
    "basketball_nba",
    "americanfootball_nfl",
    "baseball_mlb",
    "soccer_epl",
]


async def fetch_events_from_api(sport_key: str) -> list:
    """Fetch upcoming events from The Odds API."""
    api_key = settings.ODDS_API_KEY
    if not api_key:
        logger.error("ODDS_API_KEY not configured!")
        return []

    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=30.0)

            # Log remaining API requests
            remaining = response.headers.get("x-requests-remaining", "unknown")
            logger.info(f"API requests remaining: {remaining}")

            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error fetching {sport_key}: {e}")
            return []


async def get_or_create_team(session, team_name: str, sport: Sport) -> Team:
    """Get existing team or create a new one."""
    # Try to find existing team
    result = await session.execute(
        select(Team).where(Team.name == team_name, Team.sport == sport)
    )
    team = result.scalars().first()

    if team:
        return team

    # Create new team
    team = Team(
        sport=sport,
        name=team_name,
        abbreviation=team_name[:3].upper(),  # Simple abbreviation
    )
    session.add(team)
    await session.flush()  # Get the ID
    logger.info(f"Created team: {team_name} ({sport.value})")
    return team


async def save_games_to_db(games_data: list, sport_key: str):
    """Save fetched games to the database."""
    if not games_data:
        return 0

    league_name, sport_enum = SPORT_MAPPING.get(sport_key, ("Unknown", Sport.NBA))

    async with AsyncSessionLocal() as session:
        saved = 0
        for game_data in games_data:
            try:
                external_id = game_data.get("id")
                home_team_name = game_data.get("home_team")
                away_team_name = game_data.get("away_team")
                commence_time_str = game_data.get("commence_time")

                if not all([external_id, home_team_name, away_team_name, commence_time_str]):
                    continue

                # Check if game already exists
                result = await session.execute(
                    select(Game).where(Game.external_id == external_id)
                )
                existing = result.scalars().first()

                if existing:
                    logger.debug(f"Game already exists: {away_team_name} @ {home_team_name}")
                    continue

                # Get or create teams
                home_team = await get_or_create_team(session, home_team_name, sport_enum)
                away_team = await get_or_create_team(session, away_team_name, sport_enum)

                # Parse commence time (remove timezone for DB compatibility)
                commence_time = datetime.fromisoformat(
                    commence_time_str.replace("Z", "+00:00")
                ).replace(tzinfo=None)

                # Create game
                game = Game(
                    sport=sport_enum,
                    external_id=external_id,
                    home_team_id=home_team.id,
                    away_team_id=away_team.id,
                    scheduled_time=commence_time,
                    status=GameStatus.SCHEDULED,
                    season=datetime.now().year,  # Integer
                    season_type="regular",
                )
                session.add(game)
                saved += 1
                logger.info(f"Added game: {away_team_name} @ {home_team_name} ({commence_time})")

            except Exception as e:
                logger.error(f"Error saving game: {e}")
                await session.rollback()
                continue

        await session.commit()
        return saved


async def main():
    """Main function to fetch and save all upcoming games."""
    logger.info("Starting to fetch upcoming games from The Odds API...")

    total_saved = 0

    for sport_key in SPORTS_TO_FETCH:
        logger.info(f"\nFetching {sport_key}...")
        games = await fetch_events_from_api(sport_key)
        logger.info(f"Found {len(games)} events for {sport_key}")

        if games:
            saved = await save_games_to_db(games, sport_key)
            total_saved += saved
            logger.info(f"Saved {saved} new games for {sport_key}")

    logger.info(f"\n=== Complete! Saved {total_saved} total games ===")


if __name__ == "__main__":
    asyncio.run(main())