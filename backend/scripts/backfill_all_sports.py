#!/usr/bin/env python3
"""
Comprehensive Data Backfill Script.

Populates the database with:
1. Team data (NBA, NFL, MLB, Soccer)
2. Player rosters
3. Historical games and results
4. Player game statistics

Usage:
    python scripts/backfill_all_sports.py --sport nba --seasons 3
    python scripts/backfill_all_sports.py --sport all --seasons 2
    python scripts/backfill_all_sports.py --sport nfl --seasons 1 --skip-stats
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

# Import after path setup
from app.core.database import AsyncSessionLocal, engine
from app.models.game import Game, Player, PlayerGameStats, Team, Venue, Sport, GameStatus

# Data fetchers
try:
    from data.apis.nba_data import NBADataFetcher, NBA_API_AVAILABLE
except ImportError:
    NBA_API_AVAILABLE = False
    NBADataFetcher = None

try:
    from data.apis.nfl_data import NFLDataFetcher, NFL_DATA_AVAILABLE
except ImportError:
    NFL_DATA_AVAILABLE = False
    NFLDataFetcher = None

try:
    from data.apis.mlb_data import MLBDataFetcher, PYBASEBALL_AVAILABLE
except ImportError:
    PYBASEBALL_AVAILABLE = False
    MLBDataFetcher = None

try:
    from data.apis.soccer_data import SoccerDataFetcher, HTTPX_AVAILABLE
    SOCCER_AVAILABLE = HTTPX_AVAILABLE
except ImportError:
    SOCCER_AVAILABLE = False
    SoccerDataFetcher = None


# ============================================================================
# NBA Team Data
# ============================================================================
NBA_TEAMS = [
    {"abbr": "ATL", "name": "Atlanta Hawks", "city": "Atlanta", "conference": "Eastern", "division": "Southeast"},
    {"abbr": "BOS", "name": "Boston Celtics", "city": "Boston", "conference": "Eastern", "division": "Atlantic"},
    {"abbr": "BKN", "name": "Brooklyn Nets", "city": "Brooklyn", "conference": "Eastern", "division": "Atlantic"},
    {"abbr": "CHA", "name": "Charlotte Hornets", "city": "Charlotte", "conference": "Eastern", "division": "Southeast"},
    {"abbr": "CHI", "name": "Chicago Bulls", "city": "Chicago", "conference": "Eastern", "division": "Central"},
    {"abbr": "CLE", "name": "Cleveland Cavaliers", "city": "Cleveland", "conference": "Eastern", "division": "Central"},
    {"abbr": "DAL", "name": "Dallas Mavericks", "city": "Dallas", "conference": "Western", "division": "Southwest"},
    {"abbr": "DEN", "name": "Denver Nuggets", "city": "Denver", "conference": "Western", "division": "Northwest"},
    {"abbr": "DET", "name": "Detroit Pistons", "city": "Detroit", "conference": "Eastern", "division": "Central"},
    {"abbr": "GSW", "name": "Golden State Warriors", "city": "San Francisco", "conference": "Western", "division": "Pacific"},
    {"abbr": "HOU", "name": "Houston Rockets", "city": "Houston", "conference": "Western", "division": "Southwest"},
    {"abbr": "IND", "name": "Indiana Pacers", "city": "Indianapolis", "conference": "Eastern", "division": "Central"},
    {"abbr": "LAC", "name": "Los Angeles Clippers", "city": "Los Angeles", "conference": "Western", "division": "Pacific"},
    {"abbr": "LAL", "name": "Los Angeles Lakers", "city": "Los Angeles", "conference": "Western", "division": "Pacific"},
    {"abbr": "MEM", "name": "Memphis Grizzlies", "city": "Memphis", "conference": "Western", "division": "Southwest"},
    {"abbr": "MIA", "name": "Miami Heat", "city": "Miami", "conference": "Eastern", "division": "Southeast"},
    {"abbr": "MIL", "name": "Milwaukee Bucks", "city": "Milwaukee", "conference": "Eastern", "division": "Central"},
    {"abbr": "MIN", "name": "Minnesota Timberwolves", "city": "Minneapolis", "conference": "Western", "division": "Northwest"},
    {"abbr": "NOP", "name": "New Orleans Pelicans", "city": "New Orleans", "conference": "Western", "division": "Southwest"},
    {"abbr": "NYK", "name": "New York Knicks", "city": "New York", "conference": "Eastern", "division": "Atlantic"},
    {"abbr": "OKC", "name": "Oklahoma City Thunder", "city": "Oklahoma City", "conference": "Western", "division": "Northwest"},
    {"abbr": "ORL", "name": "Orlando Magic", "city": "Orlando", "conference": "Eastern", "division": "Southeast"},
    {"abbr": "PHI", "name": "Philadelphia 76ers", "city": "Philadelphia", "conference": "Eastern", "division": "Atlantic"},
    {"abbr": "PHX", "name": "Phoenix Suns", "city": "Phoenix", "conference": "Western", "division": "Pacific"},
    {"abbr": "POR", "name": "Portland Trail Blazers", "city": "Portland", "conference": "Western", "division": "Northwest"},
    {"abbr": "SAC", "name": "Sacramento Kings", "city": "Sacramento", "conference": "Western", "division": "Pacific"},
    {"abbr": "SAS", "name": "San Antonio Spurs", "city": "San Antonio", "conference": "Western", "division": "Southwest"},
    {"abbr": "TOR", "name": "Toronto Raptors", "city": "Toronto", "conference": "Eastern", "division": "Atlantic"},
    {"abbr": "UTA", "name": "Utah Jazz", "city": "Salt Lake City", "conference": "Western", "division": "Northwest"},
    {"abbr": "WAS", "name": "Washington Wizards", "city": "Washington", "conference": "Eastern", "division": "Southeast"},
]

# ============================================================================
# NFL Team Data
# ============================================================================
NFL_TEAMS = [
    {"abbr": "ARI", "name": "Arizona Cardinals", "city": "Phoenix", "conference": "NFC", "division": "West"},
    {"abbr": "ATL", "name": "Atlanta Falcons", "city": "Atlanta", "conference": "NFC", "division": "South"},
    {"abbr": "BAL", "name": "Baltimore Ravens", "city": "Baltimore", "conference": "AFC", "division": "North"},
    {"abbr": "BUF", "name": "Buffalo Bills", "city": "Buffalo", "conference": "AFC", "division": "East"},
    {"abbr": "CAR", "name": "Carolina Panthers", "city": "Charlotte", "conference": "NFC", "division": "South"},
    {"abbr": "CHI", "name": "Chicago Bears", "city": "Chicago", "conference": "NFC", "division": "North"},
    {"abbr": "CIN", "name": "Cincinnati Bengals", "city": "Cincinnati", "conference": "AFC", "division": "North"},
    {"abbr": "CLE", "name": "Cleveland Browns", "city": "Cleveland", "conference": "AFC", "division": "North"},
    {"abbr": "DAL", "name": "Dallas Cowboys", "city": "Dallas", "conference": "NFC", "division": "East"},
    {"abbr": "DEN", "name": "Denver Broncos", "city": "Denver", "conference": "AFC", "division": "West"},
    {"abbr": "DET", "name": "Detroit Lions", "city": "Detroit", "conference": "NFC", "division": "North"},
    {"abbr": "GB", "name": "Green Bay Packers", "city": "Green Bay", "conference": "NFC", "division": "North"},
    {"abbr": "HOU", "name": "Houston Texans", "city": "Houston", "conference": "AFC", "division": "South"},
    {"abbr": "IND", "name": "Indianapolis Colts", "city": "Indianapolis", "conference": "AFC", "division": "South"},
    {"abbr": "JAX", "name": "Jacksonville Jaguars", "city": "Jacksonville", "conference": "AFC", "division": "South"},
    {"abbr": "KC", "name": "Kansas City Chiefs", "city": "Kansas City", "conference": "AFC", "division": "West"},
    {"abbr": "LAC", "name": "Los Angeles Chargers", "city": "Los Angeles", "conference": "AFC", "division": "West"},
    {"abbr": "LAR", "name": "Los Angeles Rams", "city": "Los Angeles", "conference": "NFC", "division": "West"},
    {"abbr": "LV", "name": "Las Vegas Raiders", "city": "Las Vegas", "conference": "AFC", "division": "West"},
    {"abbr": "MIA", "name": "Miami Dolphins", "city": "Miami", "conference": "AFC", "division": "East"},
    {"abbr": "MIN", "name": "Minnesota Vikings", "city": "Minneapolis", "conference": "NFC", "division": "North"},
    {"abbr": "NE", "name": "New England Patriots", "city": "Foxborough", "conference": "AFC", "division": "East"},
    {"abbr": "NO", "name": "New Orleans Saints", "city": "New Orleans", "conference": "NFC", "division": "South"},
    {"abbr": "NYG", "name": "New York Giants", "city": "East Rutherford", "conference": "NFC", "division": "East"},
    {"abbr": "NYJ", "name": "New York Jets", "city": "East Rutherford", "conference": "AFC", "division": "East"},
    {"abbr": "PHI", "name": "Philadelphia Eagles", "city": "Philadelphia", "conference": "NFC", "division": "East"},
    {"abbr": "PIT", "name": "Pittsburgh Steelers", "city": "Pittsburgh", "conference": "AFC", "division": "North"},
    {"abbr": "SEA", "name": "Seattle Seahawks", "city": "Seattle", "conference": "NFC", "division": "West"},
    {"abbr": "SF", "name": "San Francisco 49ers", "city": "San Francisco", "conference": "NFC", "division": "West"},
    {"abbr": "TB", "name": "Tampa Bay Buccaneers", "city": "Tampa", "conference": "NFC", "division": "South"},
    {"abbr": "TEN", "name": "Tennessee Titans", "city": "Nashville", "conference": "AFC", "division": "South"},
    {"abbr": "WAS", "name": "Washington Commanders", "city": "Landover", "conference": "NFC", "division": "East"},
]

# ============================================================================
# MLB Team Data
# ============================================================================
MLB_TEAMS = [
    {"abbr": "ARI", "name": "Arizona Diamondbacks", "city": "Phoenix", "league": "NL", "division": "West"},
    {"abbr": "ATL", "name": "Atlanta Braves", "city": "Atlanta", "league": "NL", "division": "East"},
    {"abbr": "BAL", "name": "Baltimore Orioles", "city": "Baltimore", "league": "AL", "division": "East"},
    {"abbr": "BOS", "name": "Boston Red Sox", "city": "Boston", "league": "AL", "division": "East"},
    {"abbr": "CHC", "name": "Chicago Cubs", "city": "Chicago", "league": "NL", "division": "Central"},
    {"abbr": "CHW", "name": "Chicago White Sox", "city": "Chicago", "league": "AL", "division": "Central"},
    {"abbr": "CIN", "name": "Cincinnati Reds", "city": "Cincinnati", "league": "NL", "division": "Central"},
    {"abbr": "CLE", "name": "Cleveland Guardians", "city": "Cleveland", "league": "AL", "division": "Central"},
    {"abbr": "COL", "name": "Colorado Rockies", "city": "Denver", "league": "NL", "division": "West"},
    {"abbr": "DET", "name": "Detroit Tigers", "city": "Detroit", "league": "AL", "division": "Central"},
    {"abbr": "HOU", "name": "Houston Astros", "city": "Houston", "league": "AL", "division": "West"},
    {"abbr": "KC", "name": "Kansas City Royals", "city": "Kansas City", "league": "AL", "division": "Central"},
    {"abbr": "LAA", "name": "Los Angeles Angels", "city": "Anaheim", "league": "AL", "division": "West"},
    {"abbr": "LAD", "name": "Los Angeles Dodgers", "city": "Los Angeles", "league": "NL", "division": "West"},
    {"abbr": "MIA", "name": "Miami Marlins", "city": "Miami", "league": "NL", "division": "East"},
    {"abbr": "MIL", "name": "Milwaukee Brewers", "city": "Milwaukee", "league": "NL", "division": "Central"},
    {"abbr": "MIN", "name": "Minnesota Twins", "city": "Minneapolis", "league": "AL", "division": "Central"},
    {"abbr": "NYM", "name": "New York Mets", "city": "New York", "league": "NL", "division": "East"},
    {"abbr": "NYY", "name": "New York Yankees", "city": "New York", "league": "AL", "division": "East"},
    {"abbr": "OAK", "name": "Oakland Athletics", "city": "Oakland", "league": "AL", "division": "West"},
    {"abbr": "PHI", "name": "Philadelphia Phillies", "city": "Philadelphia", "league": "NL", "division": "East"},
    {"abbr": "PIT", "name": "Pittsburgh Pirates", "city": "Pittsburgh", "league": "NL", "division": "Central"},
    {"abbr": "SD", "name": "San Diego Padres", "city": "San Diego", "league": "NL", "division": "West"},
    {"abbr": "SF", "name": "San Francisco Giants", "city": "San Francisco", "league": "NL", "division": "West"},
    {"abbr": "SEA", "name": "Seattle Mariners", "city": "Seattle", "league": "AL", "division": "West"},
    {"abbr": "STL", "name": "St. Louis Cardinals", "city": "St. Louis", "league": "NL", "division": "Central"},
    {"abbr": "TB", "name": "Tampa Bay Rays", "city": "St. Petersburg", "league": "AL", "division": "East"},
    {"abbr": "TEX", "name": "Texas Rangers", "city": "Arlington", "league": "AL", "division": "West"},
    {"abbr": "TOR", "name": "Toronto Blue Jays", "city": "Toronto", "league": "AL", "division": "East"},
    {"abbr": "WSH", "name": "Washington Nationals", "city": "Washington", "league": "NL", "division": "East"},
]

# ============================================================================
# Soccer Team Data (Premier League)
# ============================================================================
EPL_TEAMS = [
    {"abbr": "ARS", "name": "Arsenal", "city": "London", "league": "EPL"},
    {"abbr": "AVL", "name": "Aston Villa", "city": "Birmingham", "league": "EPL"},
    {"abbr": "BOU", "name": "AFC Bournemouth", "city": "Bournemouth", "league": "EPL"},
    {"abbr": "BRE", "name": "Brentford", "city": "London", "league": "EPL"},
    {"abbr": "BHA", "name": "Brighton & Hove Albion", "city": "Brighton", "league": "EPL"},
    {"abbr": "CHE", "name": "Chelsea", "city": "London", "league": "EPL"},
    {"abbr": "CRY", "name": "Crystal Palace", "city": "London", "league": "EPL"},
    {"abbr": "EVE", "name": "Everton", "city": "Liverpool", "league": "EPL"},
    {"abbr": "FUL", "name": "Fulham", "city": "London", "league": "EPL"},
    {"abbr": "IPS", "name": "Ipswich Town", "city": "Ipswich", "league": "EPL"},
    {"abbr": "LEI", "name": "Leicester City", "city": "Leicester", "league": "EPL"},
    {"abbr": "LIV", "name": "Liverpool", "city": "Liverpool", "league": "EPL"},
    {"abbr": "MCI", "name": "Manchester City", "city": "Manchester", "league": "EPL"},
    {"abbr": "MUN", "name": "Manchester United", "city": "Manchester", "league": "EPL"},
    {"abbr": "NEW", "name": "Newcastle United", "city": "Newcastle", "league": "EPL"},
    {"abbr": "NFO", "name": "Nottingham Forest", "city": "Nottingham", "league": "EPL"},
    {"abbr": "SOU", "name": "Southampton", "city": "Southampton", "league": "EPL"},
    {"abbr": "TOT", "name": "Tottenham Hotspur", "city": "London", "league": "EPL"},
    {"abbr": "WHU", "name": "West Ham United", "city": "London", "league": "EPL"},
    {"abbr": "WOL", "name": "Wolverhampton Wanderers", "city": "Wolverhampton", "league": "EPL"},
]


class DataBackfiller:
    """Handles database population for all sports."""

    def __init__(self):
        self.team_cache: Dict[str, Dict[str, int]] = {}  # sport -> abbr -> db_id
        self.player_cache: Dict[str, int] = {}  # external_id -> db_id

    async def seed_teams(self, sport: str):
        """Seed teams for a sport."""
        logger.info(f"Seeding {sport.upper()} teams...")

        if sport == "nba":
            teams_data = NBA_TEAMS
            sport_enum = Sport.NBA
        elif sport == "nfl":
            teams_data = NFL_TEAMS
            sport_enum = Sport.NFL
        elif sport == "mlb":
            teams_data = MLB_TEAMS
            sport_enum = Sport.MLB
        elif sport == "soccer":
            teams_data = EPL_TEAMS
            sport_enum = Sport.SOCCER
        else:
            logger.error(f"Unknown sport: {sport}")
            return

        async with AsyncSessionLocal() as session:
            self.team_cache[sport] = {}

            for team_data in teams_data:
                # Check if team exists
                result = await session.execute(
                    select(Team).where(
                        and_(
                            Team.sport == sport_enum,
                            Team.abbreviation == team_data["abbr"]
                        )
                    )
                )
                existing = result.scalars().first()

                if existing:
                    self.team_cache[sport][team_data["abbr"]] = existing.id
                    logger.debug(f"  Team exists: {team_data['name']}")
                else:
                    new_team = Team(
                        sport=sport_enum,
                        name=team_data["name"],
                        abbreviation=team_data["abbr"],
                        city=team_data["city"],
                        conference=team_data.get("conference") or team_data.get("league"),
                        division=team_data.get("division"),
                        league=team_data.get("league", sport.upper()),
                        is_active=True,
                        external_ids={"abbr": team_data["abbr"]}
                    )
                    session.add(new_team)
                    await session.flush()
                    self.team_cache[sport][team_data["abbr"]] = new_team.id
                    logger.debug(f"  Created team: {team_data['name']}")

            await session.commit()
            logger.info(f"  Seeded {len(teams_data)} {sport.upper()} teams")

    def get_team_id(self, sport: str, abbr: str) -> Optional[int]:
        """Get team database ID from abbreviation."""
        if sport not in self.team_cache:
            return None
        return self.team_cache[sport].get(abbr)

    async def backfill_nba(self, num_seasons: int = 3, include_stats: bool = True):
        """Backfill NBA historical data."""
        if not NBA_API_AVAILABLE:
            logger.error("nba_api not available. Install with: pip install nba_api")
            return

        logger.info(f"Backfilling NBA data for {num_seasons} seasons...")
        await self.seed_teams("nba")

        fetcher = NBADataFetcher()
        current_year = datetime.now().year

        # Determine seasons to fetch
        # NBA season spans two years (e.g., 2024-25)
        if datetime.now().month >= 10:
            latest_season_start = current_year
        else:
            latest_season_start = current_year - 1

        seasons = []
        for i in range(num_seasons):
            year = latest_season_start - i
            season_str = f"{year}-{str(year+1)[-2:]}"
            seasons.append((year, season_str))

        total_games = 0
        total_stats = 0

        async with AsyncSessionLocal() as session:
            for season_year, season_str in seasons:
                logger.info(f"  Processing {season_str} season...")

                try:
                    # Get season games
                    games_df = fetcher.get_season_games(season=season_str)

                    if games_df.empty:
                        logger.warning(f"    No games found for {season_str}")
                        continue

                    # Process each unique game
                    processed_game_ids = set()

                    for _, row in games_df.iterrows():
                        game_id = str(row.get("GAME_ID", ""))
                        if not game_id or game_id in processed_game_ids:
                            continue
                        processed_game_ids.add(game_id)

                        # Check if game exists
                        result = await session.execute(
                            select(Game).where(Game.external_id == game_id)
                        )
                        if result.scalars().first():
                            continue

                        # Parse teams
                        matchup = row.get("MATCHUP", "")
                        team_abbr = row.get("TEAM_ABBREVIATION", "")

                        # Determine home/away from matchup (e.g., "LAL vs. GSW" or "LAL @ GSW")
                        if "@" in matchup:
                            is_away = True
                            parts = matchup.split(" @ ")
                        elif "vs." in matchup:
                            is_away = False
                            parts = matchup.split(" vs. ")
                        else:
                            continue

                        if len(parts) != 2:
                            continue

                        if is_away:
                            away_abbr = parts[0].strip()
                            home_abbr = parts[1].strip()
                        else:
                            home_abbr = parts[0].strip()
                            away_abbr = parts[1].strip()

                        home_team_id = self.get_team_id("nba", home_abbr)
                        away_team_id = self.get_team_id("nba", away_abbr)

                        if not home_team_id or not away_team_id:
                            logger.debug(f"    Could not resolve teams: {home_abbr} vs {away_abbr}")
                            continue

                        # Parse game date
                        game_date_str = row.get("GAME_DATE", "")
                        try:
                            game_date = datetime.strptime(game_date_str, "%Y-%m-%d")
                        except:
                            game_date = datetime.now()

                        # Create game record
                        wl = row.get("WL", "")
                        pts = row.get("PTS")

                        new_game = Game(
                            sport=Sport.NBA,
                            external_id=game_id,
                            season=season_year,
                            season_type="regular" if "Regular" in str(row.get("SEASON_TYPE", "")) else "playoffs",
                            home_team_id=home_team_id,
                            away_team_id=away_team_id,
                            scheduled_time=game_date,
                            status=GameStatus.FINAL,
                        )
                        session.add(new_game)
                        total_games += 1

                        # Commit in batches
                        if total_games % 100 == 0:
                            await session.commit()
                            logger.info(f"    Saved {total_games} games...")

                    await session.commit()
                    logger.info(f"    Season {season_str}: {len(processed_game_ids)} games processed")

                except Exception as e:
                    logger.error(f"    Error processing {season_str}: {e}")
                    await session.rollback()
                    continue

                # Be nice to the API
                await asyncio.sleep(2)

        logger.info(f"NBA backfill complete: {total_games} games")

    async def backfill_nfl(self, num_seasons: int = 3, include_stats: bool = True):
        """Backfill NFL historical data."""
        if not NFL_DATA_AVAILABLE:
            logger.error("nfl_data_py not available. Install with: pip install nfl_data_py")
            return

        logger.info(f"Backfilling NFL data for {num_seasons} seasons...")
        await self.seed_teams("nfl")

        fetcher = NFLDataFetcher()
        current_year = datetime.now().year

        # NFL season is in fall, so use previous year if before September
        if datetime.now().month < 9:
            latest_season = current_year - 1
        else:
            latest_season = current_year

        seasons = list(range(latest_season - num_seasons + 1, latest_season + 1))

        total_games = 0

        async with AsyncSessionLocal() as session:
            for season in seasons:
                logger.info(f"  Processing {season} season...")

                try:
                    games = fetcher.get_game_results([season])

                    if games.empty:
                        logger.warning(f"    No games found for {season}")
                        continue

                    for _, row in games.iterrows():
                        game_id = str(row.get("game_id", ""))
                        if not game_id:
                            continue

                        # Check if game exists
                        result = await session.execute(
                            select(Game).where(Game.external_id == game_id)
                        )
                        if result.scalars().first():
                            continue

                        home_abbr = row.get("home_team", "")
                        away_abbr = row.get("away_team", "")

                        home_team_id = self.get_team_id("nfl", home_abbr)
                        away_team_id = self.get_team_id("nfl", away_abbr)

                        if not home_team_id or not away_team_id:
                            continue

                        # Parse game date
                        game_date_str = row.get("gameday", "")
                        try:
                            game_date = datetime.strptime(str(game_date_str), "%Y-%m-%d")
                        except:
                            game_date = datetime.now()

                        new_game = Game(
                            sport=Sport.NFL,
                            external_id=game_id,
                            season=season,
                            season_type="regular",
                            week=row.get("week"),
                            home_team_id=home_team_id,
                            away_team_id=away_team_id,
                            scheduled_time=game_date,
                            home_score=row.get("home_score"),
                            away_score=row.get("away_score"),
                            status=GameStatus.FINAL if row.get("result") else GameStatus.SCHEDULED,
                        )
                        session.add(new_game)
                        total_games += 1

                        if total_games % 50 == 0:
                            await session.commit()
                            logger.info(f"    Saved {total_games} games...")

                    await session.commit()

                except Exception as e:
                    logger.error(f"    Error processing {season}: {e}")
                    await session.rollback()
                    continue

        logger.info(f"NFL backfill complete: {total_games} games")

    async def backfill_mlb(self, num_seasons: int = 2, include_stats: bool = True):
        """Backfill MLB historical data."""
        if not PYBASEBALL_AVAILABLE:
            logger.error("pybaseball not available. Install with: pip install pybaseball")
            return

        logger.info(f"Backfilling MLB data for {num_seasons} seasons...")
        await self.seed_teams("mlb")

        fetcher = MLBDataFetcher()
        current_year = datetime.now().year

        # MLB season runs April-October
        if datetime.now().month < 4:
            latest_season = current_year - 1
        else:
            latest_season = current_year

        seasons = list(range(latest_season - num_seasons + 1, latest_season + 1))

        total_games = 0

        async with AsyncSessionLocal() as session:
            for season in seasons:
                logger.info(f"  Processing {season} season...")

                try:
                    games = fetcher.get_historical_games([season])

                    if not games:
                        logger.warning(f"    No games found for {season}")
                        continue

                    for game_data in games:
                        # Create unique game ID
                        game_id = f"mlb_{season}_{game_data.get('date')}_{game_data.get('team')}_{game_data.get('opponent')}"

                        # Check if exists
                        result = await session.execute(
                            select(Game).where(Game.external_id == game_id)
                        )
                        if result.scalars().first():
                            continue

                        team_abbr = game_data.get("team", "")
                        opp_abbr = game_data.get("opponent", "").replace("@", "")

                        is_home = game_data.get("home_away") == "home"

                        if is_home:
                            home_abbr = team_abbr
                            away_abbr = opp_abbr
                        else:
                            home_abbr = opp_abbr
                            away_abbr = team_abbr

                        home_team_id = self.get_team_id("mlb", home_abbr)
                        away_team_id = self.get_team_id("mlb", away_abbr)

                        if not home_team_id or not away_team_id:
                            continue

                        # Parse date
                        date_str = game_data.get("date", "")
                        try:
                            game_date = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
                        except:
                            game_date = datetime.now()

                        new_game = Game(
                            sport=Sport.MLB,
                            external_id=game_id,
                            season=season,
                            season_type="regular",
                            home_team_id=home_team_id,
                            away_team_id=away_team_id,
                            scheduled_time=game_date,
                            home_score=game_data.get("runs_scored") if is_home else game_data.get("runs_allowed"),
                            away_score=game_data.get("runs_allowed") if is_home else game_data.get("runs_scored"),
                            status=GameStatus.FINAL,
                        )
                        session.add(new_game)
                        total_games += 1

                        if total_games % 100 == 0:
                            await session.commit()
                            logger.info(f"    Saved {total_games} games...")

                    await session.commit()

                except Exception as e:
                    logger.error(f"    Error processing {season}: {e}")
                    await session.rollback()
                    continue

        logger.info(f"MLB backfill complete: {total_games} games")

    async def backfill_soccer(self, num_seasons: int = 3, include_stats: bool = True):
        """Backfill Soccer historical data."""
        if not SOCCER_AVAILABLE:
            logger.error("Soccer data dependencies not available. Install with: pip install httpx soccerdata")
            return

        logger.info(f"Backfilling Soccer data for {num_seasons} seasons...")
        await self.seed_teams("soccer")

        fetcher = SoccerDataFetcher()
        current_year = datetime.now().year

        # Generate season codes
        seasons = []
        for i in range(num_seasons):
            year = current_year - i - 1
            season_code = f"{str(year)[-2:]}{str(year + 1)[-2:]}"
            seasons.append(season_code)

        total_games = 0

        async with AsyncSessionLocal() as session:
            for season in seasons:
                logger.info(f"  Processing {season} season...")

                try:
                    matches_df = fetcher.fetch_football_data_season("premier_league", season)

                    if matches_df.empty:
                        logger.warning(f"    No matches found for {season}")
                        continue

                    for _, row in matches_df.iterrows():
                        # Create unique game ID
                        date_str = str(row.get("date", ""))[:10] if row.get("date") else ""
                        home_team = row.get("home_team", "")
                        away_team = row.get("away_team", "")

                        game_id = f"epl_{season}_{date_str}_{home_team}_{away_team}".replace(" ", "_")

                        # Check if exists
                        result = await session.execute(
                            select(Game).where(Game.external_id == game_id)
                        )
                        if result.scalars().first():
                            continue

                        # For soccer, we need to match team names to our seeded teams
                        # This is simplified - a real implementation would need fuzzy matching
                        home_team_id = None
                        away_team_id = None

                        for abbr, tid in self.team_cache.get("soccer", {}).items():
                            # Simple name matching
                            result = await session.execute(select(Team).where(Team.id == tid))
                            team = result.scalars().first()
                            if team and team.name and home_team and team.name.lower() in home_team.lower():
                                home_team_id = tid
                            if team and team.name and away_team and team.name.lower() in away_team.lower():
                                away_team_id = tid

                        if not home_team_id or not away_team_id:
                            continue

                        # Parse date
                        try:
                            game_date = row.get("date")
                            if not isinstance(game_date, datetime):
                                game_date = datetime.strptime(str(game_date)[:10], "%Y-%m-%d")
                        except:
                            game_date = datetime.now()

                        new_game = Game(
                            sport=Sport.SOCCER,
                            external_id=game_id,
                            season=int(f"20{season[:2]}"),
                            season_type="regular",
                            home_team_id=home_team_id,
                            away_team_id=away_team_id,
                            scheduled_time=game_date,
                            home_score=row.get("home_goals"),
                            away_score=row.get("away_goals"),
                            status=GameStatus.FINAL,
                        )
                        session.add(new_game)
                        total_games += 1

                        if total_games % 50 == 0:
                            await session.commit()
                            logger.info(f"    Saved {total_games} games...")

                    await session.commit()

                except Exception as e:
                    logger.error(f"    Error processing {season}: {e}")
                    await session.rollback()
                    continue

        logger.info(f"Soccer backfill complete: {total_games} games")

    async def run(self, sports: List[str], num_seasons: int, include_stats: bool):
        """Run backfill for specified sports."""
        logger.info("=" * 60)
        logger.info("Sports Prediction Platform - Data Backfill")
        logger.info("=" * 60)

        for sport in sports:
            logger.info(f"\n{'='*40}")
            logger.info(f"Processing: {sport.upper()}")
            logger.info(f"{'='*40}")

            if sport == "nba":
                await self.backfill_nba(num_seasons, include_stats)
            elif sport == "nfl":
                await self.backfill_nfl(num_seasons, include_stats)
            elif sport == "mlb":
                await self.backfill_mlb(num_seasons, include_stats)
            elif sport == "soccer":
                await self.backfill_soccer(num_seasons, include_stats)
            else:
                logger.warning(f"Unknown sport: {sport}")

        logger.info("\n" + "=" * 60)
        logger.info("Backfill Complete!")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Backfill sports data into database")
    parser.add_argument(
        "--sport",
        type=str,
        default="all",
        help="Sport to backfill (nba, nfl, mlb, soccer, all)"
    )
    parser.add_argument(
        "--seasons",
        type=int,
        default=3,
        help="Number of seasons to backfill (default: 3)"
    )
    parser.add_argument(
        "--skip-stats",
        action="store_true",
        help="Skip player stats (faster, less data)"
    )

    args = parser.parse_args()

    if args.sport == "all":
        sports = ["nba", "nfl", "mlb", "soccer"]
    else:
        sports = [args.sport.lower()]

    backfiller = DataBackfiller()

    try:
        asyncio.run(backfiller.run(sports, args.seasons, not args.skip_stats))
    except KeyboardInterrupt:
        logger.warning("\nBackfill interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
