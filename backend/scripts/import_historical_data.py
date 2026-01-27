#!/usr/bin/env python3
"""
Historical Data Import Script.

Fetches historical game data for all sports and saves to CSV
for model training.

Usage:
    python scripts/import_historical_data.py --sport nba --seasons 2022 2023 2024
    python scripts/import_historical_data.py --sport all --seasons 2022 2023 2024
    python scripts/import_historical_data.py --sport nfl --seasons 2023 2024 --include-pbp
"""

import argparse
import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


def import_nba_data(seasons: list, output_dir: Path, include_box_scores: bool = False) -> pd.DataFrame:
    """Import NBA historical data."""
    from data.apis.nba_data import NBADataFetcher, NBA_API_AVAILABLE

    if not NBA_API_AVAILABLE:
        logger.error("nba_api package not available")
        return pd.DataFrame()

    logger.info(f"Importing NBA data for seasons: {seasons}")
    nba = NBADataFetcher()

    all_games = []

    for season_year in seasons:
        # NBA season format: "2023-24"
        season_str = f"{season_year}-{str(season_year + 1)[-2:]}"
        logger.info(f"Fetching NBA season {season_str}...")

        try:
            games = nba.get_season_games(season=season_str)
            if not games.empty:
                games['season'] = season_str
                all_games.append(games)
                logger.info(f"  Found {len(games)} games")
        except Exception as e:
            logger.error(f"  Error fetching {season_str}: {e}")

    if not all_games:
        logger.warning("No NBA data fetched")
        return pd.DataFrame()

    combined = pd.concat(all_games, ignore_index=True)

    # Save to CSV
    output_file = output_dir / "nba_historical_games.csv"
    combined.to_csv(output_file, index=False)
    logger.success(f"Saved {len(combined)} NBA games to {output_file}")

    # Also fetch standings for each season
    standings_data = []
    for season_year in seasons:
        season_str = f"{season_year}-{str(season_year + 1)[-2:]}"
        try:
            standings = nba.get_standings(season=season_str)
            if not standings.empty:
                standings['season'] = season_str
                standings_data.append(standings)
        except Exception as e:
            logger.warning(f"Could not fetch standings for {season_str}: {e}")

    if standings_data:
        standings_combined = pd.concat(standings_data, ignore_index=True)
        standings_file = output_dir / "nba_standings.csv"
        standings_combined.to_csv(standings_file, index=False)
        logger.success(f"Saved standings to {standings_file}")

    return combined


def import_nfl_data(seasons: list, output_dir: Path, include_pbp: bool = False) -> pd.DataFrame:
    """Import NFL historical data."""
    from data.apis.nfl_data import NFLDataFetcher, NFL_DATA_AVAILABLE

    if not NFL_DATA_AVAILABLE:
        logger.error("nfl_data_py package not available")
        return pd.DataFrame()

    logger.info(f"Importing NFL data for seasons: {seasons}")
    nfl = NFLDataFetcher()

    # Get game results
    logger.info("Fetching game results...")
    games = nfl.get_game_results(seasons)

    if not games.empty:
        output_file = output_dir / "nfl_historical_games.csv"
        games.to_csv(output_file, index=False)
        logger.success(f"Saved {len(games)} NFL games to {output_file}")

    # Get team stats
    logger.info("Calculating team stats from PBP data...")
    team_stats = nfl.get_team_stats(seasons)

    if not team_stats.empty:
        stats_file = output_dir / "nfl_team_stats.csv"
        team_stats.to_csv(stats_file, index=False)
        logger.success(f"Saved team stats to {stats_file}")

    # Get betting lines
    logger.info("Fetching betting lines...")
    lines = nfl.get_betting_lines(seasons)

    if not lines.empty:
        lines_file = output_dir / "nfl_betting_lines.csv"
        lines.to_csv(lines_file, index=False)
        logger.success(f"Saved betting lines to {lines_file}")

    # Get weekly player stats
    logger.info("Fetching weekly player stats...")
    weekly = nfl.get_weekly_stats(seasons)

    if not weekly.empty:
        weekly_file = output_dir / "nfl_weekly_player_stats.csv"
        weekly.to_csv(weekly_file, index=False)
        logger.success(f"Saved {len(weekly)} player stat rows to {weekly_file}")

    # Optionally get full PBP data (large!)
    if include_pbp:
        logger.info("Fetching play-by-play data (this may take a while)...")
        pbp = nfl.get_play_by_play(seasons)

        if not pbp.empty:
            pbp_file = output_dir / "nfl_play_by_play.parquet"
            pbp.to_parquet(pbp_file, index=False)
            logger.success(f"Saved {len(pbp)} plays to {pbp_file}")

    return games


def import_mlb_data(seasons: list, output_dir: Path) -> pd.DataFrame:
    """Import MLB historical data."""
    from data.apis.mlb_data import MLBDataFetcher, PYBASEBALL_AVAILABLE

    if not PYBASEBALL_AVAILABLE:
        logger.error("pybaseball package not available")
        return pd.DataFrame()

    logger.info(f"Importing MLB data for seasons: {seasons}")
    mlb = MLBDataFetcher()

    all_games = []

    for season in seasons:
        logger.info(f"Fetching MLB {season} game results...")
        try:
            games = mlb.get_game_results(season)
            if not games.empty:
                games['season'] = season
                all_games.append(games)
                logger.info(f"  Found {len(games)} games")
        except Exception as e:
            logger.error(f"  Error fetching {season}: {e}")

    if not all_games:
        logger.warning("No MLB data fetched")
        return pd.DataFrame()

    combined = pd.concat(all_games, ignore_index=True)

    output_file = output_dir / "mlb_historical_games.csv"
    combined.to_csv(output_file, index=False)
    logger.success(f"Saved {len(combined)} MLB games to {output_file}")

    # Get team batting stats
    logger.info("Fetching team batting stats...")
    batting_data = []
    for season in seasons:
        try:
            batting = mlb.get_team_batting(season)
            if not batting.empty:
                batting['season'] = season
                batting_data.append(batting)
        except Exception as e:
            logger.warning(f"Could not fetch batting for {season}: {e}")

    if batting_data:
        batting_combined = pd.concat(batting_data, ignore_index=True)
        batting_file = output_dir / "mlb_team_batting.csv"
        batting_combined.to_csv(batting_file, index=False)
        logger.success(f"Saved team batting to {batting_file}")

    # Get team pitching stats
    logger.info("Fetching team pitching stats...")
    pitching_data = []
    for season in seasons:
        try:
            pitching = mlb.get_team_pitching(season)
            if not pitching.empty:
                pitching['season'] = season
                pitching_data.append(pitching)
        except Exception as e:
            logger.warning(f"Could not fetch pitching for {season}: {e}")

    if pitching_data:
        pitching_combined = pd.concat(pitching_data, ignore_index=True)
        pitching_file = output_dir / "mlb_team_pitching.csv"
        pitching_combined.to_csv(pitching_file, index=False)
        logger.success(f"Saved team pitching to {pitching_file}")

    return combined


def main():
    parser = argparse.ArgumentParser(description="Import historical sports data for model training")
    parser.add_argument(
        "--sport",
        choices=["nba", "nfl", "mlb", "all"],
        default="all",
        help="Sport to import data for"
    )
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=[2022, 2023, 2024],
        help="Seasons to import (years)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./data/historical",
        help="Output directory for CSV files"
    )
    parser.add_argument(
        "--include-pbp",
        action="store_true",
        help="Include NFL play-by-play data (large file)"
    )

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Output directory: {output_dir.absolute()}")
    logger.info(f"Seasons: {args.seasons}")

    start_time = datetime.now()

    if args.sport in ["nba", "all"]:
        import_nba_data(args.seasons, output_dir)

    if args.sport in ["nfl", "all"]:
        import_nfl_data(args.seasons, output_dir, include_pbp=args.include_pbp)

    if args.sport in ["mlb", "all"]:
        import_mlb_data(args.seasons, output_dir)

    elapsed = datetime.now() - start_time
    logger.info(f"Import completed in {elapsed}")

    # List all created files
    logger.info("\nCreated files:")
    for f in sorted(output_dir.glob("*")):
        size_mb = f.stat().st_size / (1024 * 1024)
        logger.info(f"  {f.name}: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
