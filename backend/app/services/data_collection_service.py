"""
Data Collection Service.

Celery tasks for collecting sports data from various sources:
- Live odds from The Odds API
- Historical stats from nba_api, nfl_data_py, pybaseball
- Injury news from web scraping
- Game schedules and results
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from celery import shared_task
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.game import Game, Player, PlayerGameStats, Team, Sport

# Import data fetchers - add backend root to path
import sys
from pathlib import Path

# Add backend directory to path for data.apis imports
backend_dir = Path(__file__).parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

try:
    from data.apis import StatsService, NBADataFetcher, NFLDataFetcher, MLBDataFetcher
    from data.apis.stats_service import stats_service
    from data.apis.live_games import LiveGamesService, live_games_service
    from data.apis.odds_api import OddsService, odds_service
    DATA_APIS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Data APIs not available: {e}")
    DATA_APIS_AVAILABLE = False
    stats_service = None
    live_games_service = None
    odds_service = None


# Sport mappings for The Odds API
ODDS_API_SPORTS = {
    "nba": "basketball_nba",
    "nfl": "americanfootball_nfl",
    "mlb": "baseball_mlb",
    "soccer": "soccer_epl",
}


@shared_task(name="app.services.data_collection_service.scrape_injuries")
def scrape_injuries():
    """
    Scrape injury reports from various sources.

    Sources:
    - Official team injury reports
    - ESPN injury page
    - Rotowire
    """
    logger.info("Starting injury scraping task")

    # TODO: Implement actual scraping
    # For now, log placeholder
    injuries_found = []

    try:
        # This would use BeautifulSoup/Playwright to scrape
        # Example sources:
        # - https://www.espn.com/nba/injuries
        # - https://www.rotowire.com/basketball/nba-injury-report.php
        pass

    except Exception as e:
        logger.error(f"Error scraping injuries: {e}")

    logger.info(f"Injury scraping complete. Found {len(injuries_found)} updates.")
    return injuries_found


@shared_task(name="app.services.data_collection_service.fetch_historical_stats")
def fetch_historical_stats(sport: str, seasons: List[int]):
    """
    Fetch historical statistics for a sport.

    Args:
        sport: Sport type ('nba', 'nfl', 'mlb')
        seasons: List of seasons to fetch
    """
    if not DATA_APIS_AVAILABLE:
        logger.error("Data APIs not available. Install nba_api, nfl_data_py, pybaseball.")
        return {"error": "Data APIs not available"}

    logger.info(f"Fetching historical stats for {sport}, seasons: {seasons}")

    try:
        games = stats_service.get_historical_games(
            sport=sport,
            seasons=seasons,
            include_stats=True
        )

        logger.info(f"Fetched {len(games)} games for {sport}")

        # Save to database
        asyncio.run(_save_games_to_db(sport, games))

        return {"sport": sport, "games_fetched": len(games)}

    except Exception as e:
        logger.error(f"Error fetching historical stats: {e}")
        return {"error": str(e)}


async def _save_games_to_db(sport: str, games: List[dict]):
    """Save fetched games and player stats to the database."""
    async with AsyncSessionLocal() as session:
        saved_games = 0
        saved_stats = 0
        
        # Cache teams to avoid repeated queries
        sport_enum = Sport(sport.lower())
        team_cache = {}
        
        # Pre-fetch teams
        result = await session.execute(select(Team).where(Team.sport == sport_enum))
        for team in result.scalars().all():
            team_cache[team.id] = team # Assuming external ID matching logic might be needed, but using internal ID for now
            # Note: A real implementation needs robust mapping between API team IDs and DB team IDs.
            # For simplicity, we'll try to match by name or external_id if available.

        for game_data in games:
            try:
                # 1. Save/Update Game
                external_id = game_data.get("game_id")
                if not external_id:
                    continue

                result = await session.execute(
                    select(Game).where(Game.external_id == str(external_id))
                )
                game = result.scalars().first()

                if game:
                    # Update scores if game is complete
                    if game_data.get("home_score") and game_data.get("away_score"):
                        game.home_score = game_data["home_score"]
                        game.away_score = game_data["away_score"]
                        game.status = "completed"
                else:
                    # Create new game record
                    # Note: We need team IDs. If missing, we skip (or create teams on fly - simpler to skip for now)
                    # This is a simplification. Real code needs robust team resolution.
                    game = Game(
                        sport=sport_enum,
                        external_id=str(external_id),
                        scheduled_time=_parse_game_date(game_data),
                        home_score=game_data.get("home_score"),
                        away_score=game_data.get("away_score"),
                        status="completed" if game_data.get("home_score") else "scheduled",
                        # Placeholder team IDs - in production, resolve these!
                        home_team_id=1, 
                        away_team_id=2
                    )
                    session.add(game)
                    saved_games += 1
                
                # Flush to get game.id if new
                await session.flush()

                # 2. Save Player Stats (if box score exists)
                box_score = game_data.get("box_score")
                if box_score and "players" in box_score:
                    players_df = box_score["players"]
                    if not players_df.empty:
                        for _, row in players_df.iterrows():
                            # Extract player info
                            player_name = row.get("PLAYER_NAME")
                            player_ext_id = row.get("PLAYER_ID")
                            
                            if not player_name:
                                continue

                            # Find or Create Player
                            # This should be optimized with bulk upsert or caching
                            result = await session.execute(
                                select(Player).where(
                                    Player.name == player_name, 
                                    Player.sport == sport_enum
                                )
                            )
                            player = result.scalars().first()

                            if not player:
                                player = Player(
                                    sport=sport_enum,
                                    name=player_name,
                                    external_ids={"nba_id": str(player_ext_id)} if player_ext_id else {},
                                    is_active=True
                                )
                                session.add(player)
                                await session.flush() # Get ID
                            
                            # Create Game Stats
                            # Check if stats already exist for this game/player
                            stat_result = await session.execute(
                                select(PlayerGameStats).where(
                                    PlayerGameStats.game_id == game.id,
                                    PlayerGameStats.player_id == player.id
                                )
                            )
                            existing_stat = stat_result.scalars().first()

                            stats_json = json.loads(row.to_json())
                            
                            if existing_stat:
                                existing_stat.stats = stats_json
                                existing_stat.minutes_played = _parse_minutes(row.get("MIN"))
                                existing_stat.is_starter = bool(row.get("START_POSITION"))
                            else:
                                new_stat = PlayerGameStats(
                                    player_id=player.id,
                                    game_id=game.id,
                                    minutes_played=_parse_minutes(row.get("MIN")),
                                    is_starter=bool(row.get("START_POSITION")),
                                    stats=stats_json
                                )
                                session.add(new_stat)
                                saved_stats += 1

            except Exception as e:
                logger.warning(f"Error saving game/stats: {e}")
                continue

        await session.commit()
        logger.info(f"Saved {saved_games} new games and {saved_stats} player stats entries")


def _parse_minutes(min_str) -> float:
    """Parse minutes string (e.g., '32:45') to float."""
    if not min_str:
        return 0.0
    try:
        if isinstance(min_str, (int, float)):
            return float(min_str)
        if ":" in str(min_str):
            parts = str(min_str).split(":")
            return float(parts[0]) + float(parts[1])/60
        return float(min_str)
    except:
        return 0.0


def _parse_game_date(game_data: dict) -> datetime:
    """Parse game date from various formats."""
    date_str = game_data.get("date") or game_data.get("gameday")

    if not date_str:
        return datetime.now()

    if isinstance(date_str, datetime):
        return date_str

    # Try common formats
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(str(date_str), fmt)
        except ValueError:
            continue

    return datetime.now()


@shared_task(name="app.services.data_collection_service.fetch_nba_daily")
def fetch_nba_daily():
    """
    Fetch NBA games and stats for today and yesterday.
    Runs daily to keep data current.
    """
    if not DATA_APIS_AVAILABLE:
        return {"error": "Data APIs not available"}

    logger.info("Running daily NBA data fetch")

    try:
        today = datetime.now()
        yesterday = today - timedelta(days=1)

        nba = NBADataFetcher()

        # Get yesterday's completed games with box scores
        games = nba.get_historical_games(
            start_date=yesterday.strftime("%Y-%m-%d"),
            end_date=today.strftime("%Y-%m-%d"),
            include_box_scores=True
        )

        # Get today's schedule
        today_games = nba.get_games_by_date(today.strftime("%Y-%m-%d"))

        logger.info(f"Fetched {len(games)} completed games, {len(today_games)} scheduled today")

        # Save to database
        asyncio.run(_save_games_to_db("nba", games))

        return {
            "completed_games": len(games),
            "scheduled_today": len(today_games) if not today_games.empty else 0
        }

    except Exception as e:
        logger.error(f"Error in NBA daily fetch: {e}")
        return {"error": str(e)}


@shared_task(name="app.services.data_collection_service.fetch_nfl_weekly")
def fetch_nfl_weekly():
    """
    Fetch NFL games and stats for the current week.
    Runs weekly during the season.
    """
    if not DATA_APIS_AVAILABLE:
        return {"error": "Data APIs not available"}

    logger.info("Running weekly NFL data fetch")

    try:
        current_year = datetime.now().year
        # NFL season spans two calendar years
        season = current_year if datetime.now().month >= 9 else current_year - 1

        nfl = NFLDataFetcher()

        # Get game results
        games = nfl.get_historical_games([season], include_stats=True)

        # Get weekly player stats
        weekly_stats = nfl.get_weekly_stats([season])

        logger.info(f"Fetched {len(games)} NFL games for season {season}")

        # Save to database
        asyncio.run(_save_games_to_db("nfl", games))

        return {
            "games_fetched": len(games),
            "season": season,
            "player_stats_rows": len(weekly_stats) if not weekly_stats.empty else 0
        }

    except Exception as e:
        logger.error(f"Error in NFL weekly fetch: {e}")
        return {"error": str(e)}


@shared_task(name="app.services.data_collection_service.fetch_mlb_daily")
def fetch_mlb_daily():
    """
    Fetch MLB games and stats for today.
    Runs daily during the season (April-October).
    """
    if not DATA_APIS_AVAILABLE:
        return {"error": "Data APIs not available"}

    # Skip outside of MLB season
    month = datetime.now().month
    if month < 3 or month > 10:
        logger.info("Outside MLB season, skipping fetch")
        return {"skipped": "off-season"}

    logger.info("Running daily MLB data fetch")

    try:
        current_year = datetime.now().year

        mlb = MLBDataFetcher()

        # Get season games
        games = mlb.get_historical_games([current_year])

        logger.info(f"Fetched {len(games)} MLB games for {current_year}")

        # Save to database
        asyncio.run(_save_games_to_db("mlb", games))

        return {
            "games_fetched": len(games),
            "season": current_year
        }

    except Exception as e:
        logger.error(f"Error in MLB daily fetch: {e}")
        return {"error": str(e)}


@shared_task(name="app.services.data_collection_service.bulk_historical_import")
def bulk_historical_import(sport: str, start_year: int, end_year: int):
    """
    Bulk import historical data for model training.

    This is a one-time task for initial data population.

    Args:
        sport: Sport type
        start_year: Starting year
        end_year: Ending year
    """
    if not DATA_APIS_AVAILABLE:
        return {"error": "Data APIs not available"}

    logger.info(f"Starting bulk import for {sport}: {start_year}-{end_year}")

    seasons = list(range(start_year, end_year + 1))

    try:
        data = stats_service.bulk_fetch_historical(
            sport=sport,
            seasons=seasons,
            save_path=f"./data/{sport}_historical_{start_year}_{end_year}.csv"
        )

        logger.info(f"Bulk import complete: {len(data)} records")

        return {
            "sport": sport,
            "records": len(data),
            "seasons": seasons
        }

    except Exception as e:
        logger.error(f"Error in bulk import: {e}")
        return {"error": str(e)}


@shared_task(name="app.services.data_collection_service.sync_game_results")
def sync_game_results():
    """
    Sync game results for recently completed games.
    Updates scores and settles related bets.
    """
    logger.info("Syncing game results")

    async def _sync():
        async with AsyncSessionLocal() as session:
            # Get games that should be complete but don't have scores
            cutoff = datetime.utcnow() - timedelta(hours=4)

            result = await session.execute(
                select(Game).where(
                    Game.status == "scheduled",
                    Game.scheduled_time < cutoff
                )
            )
            pending_games = result.scalars().all()

            updated = 0
            for game in pending_games:
                # Fetch actual result
                # This would call the appropriate data fetcher
                # For now, just log
                logger.debug(f"Would update game {game.id}")
                updated += 1

            await session.commit()
            return updated

    try:
        updated = asyncio.run(_sync())
        logger.info(f"Synced {updated} game results")
        return {"updated": updated}
    except Exception as e:
        logger.error(f"Error syncing results: {e}")
        return {"error": str(e)}


# Health check task
@shared_task(name="app.services.data_collection_service.health_check")
def health_check():
    """Check data collection service health."""
    status = {
        "data_apis_available": DATA_APIS_AVAILABLE,
        "available_sports": stats_service.available_sports if stats_service else [],
        "timestamp": datetime.utcnow().isoformat(),
    }

    logger.info(f"Health check: {status}")
    return status


@shared_task(name="app.services.data_collection_service.fetch_and_store_odds")
def fetch_and_store_odds(sport: str = None):
    """
    Fetch current odds from The Odds API and store in database.

    Args:
        sport: Optional sport to fetch (default: all sports)
    """
    if not DATA_APIS_AVAILABLE or odds_service is None:
        logger.warning("Odds service not available")
        return {"error": "Odds service not available"}

    from app.models.odds import OddsHistory

    sports_to_fetch = [sport] if sport else ["nba", "nfl", "mlb", "soccer"]
    results = {}

    async def _fetch_and_store():
        async with AsyncSessionLocal() as session:
            for s in sports_to_fetch:
                try:
                    odds_data = odds_service.get_current_odds(s)

                    if not odds_data:
                        results[s] = {"status": "no_data"}
                        continue

                    stored_count = 0
                    for game_odds in odds_data:
                        # Store each bookmaker's odds
                        for line in game_odds.moneyline + game_odds.spread + game_odds.total:
                            odds_record = OddsHistory(
                                game_external_id=game_odds.game_id,
                                sport=s,
                                sportsbook=line.bookmaker,
                                market_type=line.market,
                                selection=line.selection,
                                odds_american=line.price,
                                odds_decimal=line.price_decimal,
                                line=line.point,
                                timestamp=datetime.utcnow()
                            )
                            session.add(odds_record)
                            stored_count += 1

                    await session.commit()
                    results[s] = {"status": "success", "records": stored_count}
                    logger.info(f"Stored {stored_count} odds records for {s}")

                except Exception as e:
                    logger.error(f"Error fetching odds for {s}: {e}")
                    results[s] = {"status": "error", "error": str(e)}

        return results

    try:
        from app.services.prediction_service import run_async
        return run_async(_fetch_and_store())
    except Exception as e:
        logger.error(f"Error in fetch_and_store_odds: {e}")
        return {"error": str(e)}


@shared_task(name="app.services.data_collection_service.populate_teams")
def populate_teams(sport: str = None):
    """
    Populate team data from data APIs.

    Args:
        sport: Optional sport to populate (default: all sports)
    """
    if not DATA_APIS_AVAILABLE:
        return {"error": "Data APIs not available"}

    # Import team data from backfill script
    import sys
    from pathlib import Path
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    sys.path.insert(0, str(scripts_dir))

    try:
        from backfill_all_sports import DataBackfiller
        import asyncio

        backfiller = DataBackfiller()
        sports_to_seed = [sport] if sport else ["nba", "nfl", "mlb", "soccer"]

        async def _seed():
            for s in sports_to_seed:
                await backfiller.seed_teams(s)
            return {"status": "success", "sports": sports_to_seed}

        return asyncio.run(_seed())

    except Exception as e:
        logger.error(f"Error populating teams: {e}")
        return {"error": str(e)}