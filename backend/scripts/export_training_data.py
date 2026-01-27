"""
Export historical game data from database to CSV/parquet for ML training.

This script bridges the gap between the database (populated by backfill scripts)
and the ML training pipeline (which expects CSV/parquet files).

Usage:
    python scripts/export_training_data.py --sport all
    python scripts/export_training_data.py --sport nba --format parquet
    python scripts/export_training_data.py --sport nfl --seasons 3
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd
from loguru import logger

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from app.core.database import async_session_maker
from app.models.game import Game, Team, Sport, GameStatus, PlayerGameStats


class TrainingDataExporter:
    """
    Export game data from database to training-ready CSV/parquet files.

    Output format matches what ml/training/train_all_sports.py expects.
    """

    SPORTS = ['nba', 'nfl', 'mlb', 'soccer']

    def __init__(self, output_dir: str = "data/historical"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def export_all(
        self,
        sports: Optional[List[str]] = None,
        format: str = "csv",
        min_date: Optional[str] = None,
        max_date: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Export data for all specified sports.

        Args:
            sports: List of sports to export (default: all)
            format: Output format ('csv' or 'parquet')
            min_date: Minimum date filter (YYYY-MM-DD)
            max_date: Maximum date filter (YYYY-MM-DD)

        Returns:
            Dict mapping sport to output file path
        """
        if sports is None or sports == ['all']:
            sports = self.SPORTS

        results = {}

        for sport in sports:
            try:
                path = await self.export_sport(sport, format, min_date, max_date)
                results[sport] = str(path) if path else None
            except Exception as e:
                logger.error(f"Error exporting {sport}: {e}")
                results[sport] = None

        return results

    async def export_sport(
        self,
        sport: str,
        format: str = "csv",
        min_date: Optional[str] = None,
        max_date: Optional[str] = None
    ) -> Optional[Path]:
        """
        Export training data for a single sport.

        Creates a matchup-level dataset with:
        - Game metadata (date, teams, scores)
        - Target variable (home_win)
        - Sport-specific features
        """
        logger.info(f"Exporting {sport.upper()} training data...")

        sport_enum = Sport(sport.lower())

        async with async_session_maker() as session:
            # Build query
            query = (
                select(Game)
                .options(
                    selectinload(Game.home_team),
                    selectinload(Game.away_team),
                    selectinload(Game.player_stats).selectinload(PlayerGameStats.player)
                )
                .where(
                    and_(
                        Game.sport == sport_enum,
                        Game.status == GameStatus.FINAL,  # Only completed games
                        Game.home_score.isnot(None),
                        Game.away_score.isnot(None)
                    )
                )
                .order_by(Game.scheduled_time)
            )

            # Apply date filters
            if min_date:
                query = query.where(Game.scheduled_time >= datetime.strptime(min_date, "%Y-%m-%d"))
            if max_date:
                query = query.where(Game.scheduled_time <= datetime.strptime(max_date, "%Y-%m-%d"))

            result = await session.execute(query)
            games = result.scalars().all()

        if not games:
            logger.warning(f"No completed games found for {sport}")
            return None

        logger.info(f"Found {len(games)} completed {sport} games")

        # Convert to DataFrame based on sport
        if sport == 'nba':
            df = self._process_nba_games(games)
        elif sport == 'nfl':
            df = self._process_nfl_games(games)
        elif sport == 'mlb':
            df = self._process_mlb_games(games)
        elif sport == 'soccer':
            df = self._process_soccer_games(games)
        else:
            logger.error(f"Unknown sport: {sport}")
            return None

        if df.empty:
            logger.warning(f"No data to export for {sport}")
            return None

        # Save to file
        filename = f"{sport}_historical_games.{format}"
        output_path = self.output_dir / filename

        if format == 'parquet':
            df.to_parquet(output_path, index=False)
        else:
            df.to_csv(output_path, index=False)

        logger.info(f"Exported {len(df)} {sport} games to {output_path}")

        # Print sample statistics
        self._log_data_summary(sport, df)

        return output_path

    def _process_nba_games(self, games: List[Game]) -> pd.DataFrame:
        """
        Process NBA games into training format.

        Creates matchup-level features including aggregated player stats.
        """
        records = []

        for game in games:
            # Base game info
            record = {
                'date': game.scheduled_time.strftime('%Y-%m-%d'),
                'game_id': game.external_id or f"game_{game.id}",
                'season': game.season,
                'home_team': game.home_team.abbreviation if game.home_team else 'UNK',
                'away_team': game.away_team.abbreviation if game.away_team else 'UNK',
                'home_score': game.home_score,
                'away_score': game.away_score,
                'home_win': 1 if game.home_score > game.away_score else 0,
            }

            # Score-based features
            record['total_points'] = game.home_score + game.away_score
            record['point_diff'] = game.home_score - game.away_score

            # Aggregate player stats if available
            home_stats = {'pts': 0, 'reb': 0, 'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'fg_pct': [], 'fg3_pct': []}
            away_stats = {'pts': 0, 'reb': 0, 'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'fg_pct': [], 'fg3_pct': []}

            for ps in game.player_stats:
                if not ps.stats:
                    continue

                is_home = ps.player.team_id == game.home_team_id if ps.player else False
                target_stats = home_stats if is_home else away_stats

                stats = ps.stats
                target_stats['pts'] += stats.get('points', 0) or 0
                target_stats['reb'] += stats.get('rebounds', 0) or 0
                target_stats['ast'] += stats.get('assists', 0) or 0
                target_stats['stl'] += stats.get('steals', 0) or 0
                target_stats['blk'] += stats.get('blocks', 0) or 0
                target_stats['tov'] += stats.get('turnovers', 0) or 0

                if stats.get('fg_pct'):
                    target_stats['fg_pct'].append(stats['fg_pct'])
                if stats.get('fg3_pct'):
                    target_stats['fg3_pct'].append(stats['fg3_pct'])

            # Add aggregated stats to record
            record['home_pts'] = home_stats['pts'] if home_stats['pts'] > 0 else game.home_score
            record['home_reb'] = home_stats['reb']
            record['home_ast'] = home_stats['ast']
            record['home_stl'] = home_stats['stl']
            record['home_blk'] = home_stats['blk']
            record['home_tov'] = home_stats['tov']
            record['home_fg_pct'] = sum(home_stats['fg_pct']) / len(home_stats['fg_pct']) if home_stats['fg_pct'] else 0
            record['home_fg3_pct'] = sum(home_stats['fg3_pct']) / len(home_stats['fg3_pct']) if home_stats['fg3_pct'] else 0
            record['home_plus_minus'] = game.home_score - game.away_score

            record['away_pts'] = away_stats['pts'] if away_stats['pts'] > 0 else game.away_score
            record['away_reb'] = away_stats['reb']
            record['away_ast'] = away_stats['ast']
            record['away_stl'] = away_stats['stl']
            record['away_blk'] = away_stats['blk']
            record['away_tov'] = away_stats['tov']
            record['away_fg_pct'] = sum(away_stats['fg_pct']) / len(away_stats['fg_pct']) if away_stats['fg_pct'] else 0
            record['away_fg3_pct'] = sum(away_stats['fg3_pct']) / len(away_stats['fg3_pct']) if away_stats['fg3_pct'] else 0
            record['away_plus_minus'] = game.away_score - game.home_score

            records.append(record)

        return pd.DataFrame(records)

    def _process_nfl_games(self, games: List[Game]) -> pd.DataFrame:
        """
        Process NFL games into training format.

        NFL data is already matchup-level in the database.
        """
        records = []

        for game in games:
            record = {
                'date': game.scheduled_time.strftime('%Y-%m-%d'),
                'game_id': game.external_id or f"game_{game.id}",
                'season': game.season,
                'week': game.week,
                'home_team': game.home_team.abbreviation if game.home_team else 'UNK',
                'away_team': game.away_team.abbreviation if game.away_team else 'UNK',
                'home_score': game.home_score,
                'away_score': game.away_score,
                'home_win': 1 if game.home_score > game.away_score else 0,
                'total_points': game.home_score + game.away_score,
                'point_diff': game.home_score - game.away_score,
            }

            # Quarter scores if available
            if game.home_score_by_period:
                for i, score in enumerate(game.home_score_by_period[:4], 1):
                    record[f'home_q{i}'] = score
            if game.away_score_by_period:
                for i, score in enumerate(game.away_score_by_period[:4], 1):
                    record[f'away_q{i}'] = score

            # Placeholder betting lines (would come from odds_history)
            record['spread_line'] = 0
            record['total_line'] = 45
            record['home_moneyline'] = -110
            record['away_moneyline'] = -110

            records.append(record)

        return pd.DataFrame(records)

    def _process_mlb_games(self, games: List[Game]) -> pd.DataFrame:
        """
        Process MLB games into training format.
        """
        records = []

        for game in games:
            record = {
                'date': game.scheduled_time.strftime('%Y-%m-%d'),
                'game_id': game.external_id or f"game_{game.id}",
                'season': game.season,
                'home_team': game.home_team.abbreviation if game.home_team else 'UNK',
                'away_team': game.away_team.abbreviation if game.away_team else 'UNK',
                'home_score': game.home_score,
                'away_score': game.away_score,
                'home_win': 1 if game.home_score > game.away_score else 0,
                'total_runs': game.home_score + game.away_score,
                'run_diff': game.home_score - game.away_score,
            }

            # Alias columns for MLB feature engineering
            record['home_runs'] = game.home_score
            record['home_runs_allowed'] = game.away_score
            record['away_runs'] = game.away_score
            record['away_runs_allowed'] = game.home_score

            # Inning scores if available
            if game.home_score_by_period:
                for i, score in enumerate(game.home_score_by_period, 1):
                    record[f'home_inn{i}'] = score
            if game.away_score_by_period:
                for i, score in enumerate(game.away_score_by_period, 1):
                    record[f'away_inn{i}'] = score

            records.append(record)

        return pd.DataFrame(records)

    def _process_soccer_games(self, games: List[Game]) -> pd.DataFrame:
        """
        Process soccer games into training format.
        """
        records = []

        for game in games:
            record = {
                'date': game.scheduled_time.strftime('%Y-%m-%d'),
                'game_id': game.external_id or f"game_{game.id}",
                'season': game.season,
                'home_team': game.home_team.name if game.home_team else 'Unknown',
                'away_team': game.away_team.name if game.away_team else 'Unknown',
                'home_goals': game.home_score,
                'away_goals': game.away_score,
                # Soccer can have draws
                'home_win': 1 if game.home_score > game.away_score else 0,
                'draw': 1 if game.home_score == game.away_score else 0,
                'away_win': 1 if game.away_score > game.home_score else 0,
                'total_goals': game.home_score + game.away_score,
                'goal_diff': game.home_score - game.away_score,
            }

            # Half-time scores if available
            if game.home_score_by_period and len(game.home_score_by_period) >= 2:
                record['home_ht'] = game.home_score_by_period[0]
                record['away_ht'] = game.away_score_by_period[0] if game.away_score_by_period else 0

            records.append(record)

        return pd.DataFrame(records)

    def _log_data_summary(self, sport: str, df: pd.DataFrame):
        """Log summary statistics for exported data."""
        logger.info(f"\n{sport.upper()} Data Summary:")
        logger.info(f"  Total games: {len(df)}")

        if 'date' in df.columns:
            logger.info(f"  Date range: {df['date'].min()} to {df['date'].max()}")

        if 'season' in df.columns:
            logger.info(f"  Seasons: {sorted(df['season'].unique())}")

        if 'home_win' in df.columns:
            home_win_pct = df['home_win'].mean()
            logger.info(f"  Home win rate: {home_win_pct:.1%}")

        # Count unique teams
        if 'home_team' in df.columns:
            all_teams = set(df['home_team'].unique()) | set(df['away_team'].unique())
            logger.info(f"  Unique teams: {len(all_teams)}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Export training data from database")

    parser.add_argument(
        '--sport',
        nargs='+',
        default=['all'],
        help='Sports to export (nba, nfl, mlb, soccer, or all)'
    )
    parser.add_argument(
        '--format',
        choices=['csv', 'parquet'],
        default='csv',
        help='Output format'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/historical',
        help='Output directory'
    )
    parser.add_argument(
        '--min-date',
        type=str,
        help='Minimum date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--max-date',
        type=str,
        help='Maximum date (YYYY-MM-DD)'
    )

    args = parser.parse_args()

    # Setup logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO"
    )

    logger.info("=" * 60)
    logger.info("Training Data Export")
    logger.info("=" * 60)
    logger.info(f"Sports: {args.sport}")
    logger.info(f"Format: {args.format}")
    logger.info(f"Output: {args.output_dir}")

    exporter = TrainingDataExporter(output_dir=args.output_dir)

    results = await exporter.export_all(
        sports=args.sport,
        format=args.format,
        min_date=args.min_date,
        max_date=args.max_date
    )

    logger.info("\n" + "=" * 60)
    logger.info("Export Complete")
    logger.info("=" * 60)

    for sport, path in results.items():
        if path:
            logger.info(f"  {sport.upper()}: {path}")
        else:
            logger.warning(f"  {sport.upper()}: No data exported")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExport cancelled.")
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise
