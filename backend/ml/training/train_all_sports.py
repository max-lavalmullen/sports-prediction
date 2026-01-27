"""
Comprehensive Model Training Script for All Sports.

This script trains prediction models for NFL, NBA, MLB, and Soccer using
historical data and walk-forward cross-validation.

Usage:
    python -m ml.training.train_all_sports --sports nba nfl --tune
    python -m ml.training.train_all_sports --sports all
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
from loguru import logger
import pandas as pd
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ml.training.trainer import ModelTrainer, WalkForwardSplit
from ml.features.nba_features import NBAFeatureEngineer, CORE_FEATURE_COLUMNS as NBA_FEATURES
from ml.features.nfl_features import NFLFeatureEngineer, NFL_CORE_FEATURES as NFL_FEATURES
from ml.features.mlb_features import MLBFeatureEngineer, MLB_CORE_FEATURES as MLB_FEATURES
from ml.features.soccer_features import SoccerFeatureEngineer, SOCCER_CORE_FEATURES


class SportModelTrainer:
    """
    Unified trainer for all sports models.

    Handles:
    - Data loading and preprocessing
    - Feature engineering
    - Model training with walk-forward CV
    - Hyperparameter tuning (optional)
    - Model saving and evaluation reporting
    """

    SPORT_CONFIGS = {
        'nba': {
            'feature_engineer': NBAFeatureEngineer,
            'feature_columns': [
                'home_pts', 'home_fg_pct', 'home_fg3_pct', 'home_reb',
                'home_ast', 'home_tov', 'home_plus_minus'
            ],
            'target_col': 'home_win',
            'date_col': 'date',
            'data_path': 'data/nba',
            'min_seasons': 3,
        },
        'nfl': {
            'feature_engineer': NFLFeatureEngineer,
            'feature_columns': [
                'spread_line', 'total_line', 'home_moneyline', 'away_moneyline'
            ],
            'target_col': 'home_win',
            'date_col': 'date',
            'data_path': 'data/nfl',
            'min_seasons': 3,
        },
        'mlb': {
            'feature_engineer': MLBFeatureEngineer,
            'feature_columns': [
                'home_runs', 'home_runs_allowed'
            ],
            'target_col': 'home_win',
            'date_col': 'date',
            'data_path': 'data/mlb',
            'min_seasons': 3,
        },
        'soccer': {
            'feature_engineer': SoccerFeatureEngineer,
            'feature_columns': SOCCER_CORE_FEATURES,
            'target_col': 'home_win',
            'date_col': 'date',
            'data_path': 'data/soccer',
            'min_seasons': 2,
        },
    }

    def __init__(
        self,
        base_path: str = ".",
        model_save_path: str = "ml/saved_models"
    ):
        """
        Initialize the trainer.

        Args:
            base_path: Base path for data files
            model_save_path: Path to save trained models
        """
        self.base_path = Path(base_path)
        self.model_save_path = Path(model_save_path)
        self.model_save_path.mkdir(parents=True, exist_ok=True)
        self.results: Dict[str, Any] = {}

    def load_data(self, sport: str) -> Optional[pd.DataFrame]:
        """
        Load historical data for a sport.

        Args:
            sport: Sport name

        Returns:
            DataFrame with historical game data
        """
        config = self.SPORT_CONFIGS.get(sport)
        if not config:
            logger.error(f"Unknown sport: {sport}")
            return None

        # Try multiple possible data locations
        possible_paths = [
            # Historical data directory (most likely location)
            self.base_path / "data" / "historical" / f"{sport}_historical_games.csv",
            # Sport-specific directory
            self.base_path / config['data_path'] / f"{sport}_games.parquet",
            self.base_path / config['data_path'] / f"{sport}_games.csv",
            # Alternative naming
            self.base_path / "data" / "historical" / f"{sport}_games.csv",
        ]

        for path in possible_paths:
            if path.exists():
                logger.info(f"Loading {sport} data from {path}")
                if path.suffix == '.parquet':
                    return pd.read_parquet(path)
                else:
                    return pd.read_csv(path)

        logger.warning(f"No data file found for {sport}. Searched paths: {[str(p) for p in possible_paths]}")
        return None

    def prepare_features(
        self,
        sport: str,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Apply feature engineering for a sport.

        Args:
            sport: Sport name
            data: Raw game data

        Returns:
            DataFrame with engineered features
        """
        config = self.SPORT_CONFIGS[sport]
        logger.info(f"Engineering features for {sport}... (input shape: {data.shape})")

        # Standardize column names based on sport
        data = self._standardize_columns(sport, data)

        # For NFL, data is already at matchup level with home_win
        if sport == 'nfl':
            return self._prepare_nfl_features(data)

        # For NBA/MLB, data is team-level game logs - need to create matchups
        return self._prepare_team_log_features(sport, data)

    def _standardize_columns(self, sport: str, data: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names from historical data formats."""
        data = data.copy()

        if sport == 'nba':
            # NBA uses GAME_DATE, GAME_ID, MATCHUP, WL, PTS, etc.
            rename_map = {
                'GAME_DATE': 'date',
                'GAME_ID': 'game_id',
                'TEAM_ABBREVIATION': 'team',
                'TEAM_NAME': 'team_name',
                'PTS': 'pts',
                'FG_PCT': 'fg_pct',
                'FG3_PCT': 'fg3_pct',
                'FT_PCT': 'ft_pct',
                'REB': 'reb',
                'AST': 'ast',
                'STL': 'stl',
                'BLK': 'blk',
                'TOV': 'tov',
                'PLUS_MINUS': 'plus_minus',
            }
            data = data.rename(columns={k: v for k, v in rename_map.items() if k in data.columns})

            # Parse home/away from MATCHUP column (e.g., "BKN vs. NYK" = home, "BKN @ NYK" = away)
            if 'MATCHUP' in data.columns:
                data['is_home'] = data['MATCHUP'].str.contains(' vs. ').astype(int)
                data['opponent'] = data['MATCHUP'].apply(
                    lambda x: x.split(' vs. ')[-1] if ' vs. ' in str(x) else x.split(' @ ')[-1] if ' @ ' in str(x) else ''
                )

        elif sport == 'nfl':
            # NFL data is already matchup-level
            rename_map = {
                'gameday': 'date',
            }
            data = data.rename(columns={k: v for k, v in rename_map.items() if k in data.columns})

            # Create home_win from scores
            if 'home_score' in data.columns and 'away_score' in data.columns:
                data['home_win'] = (data['home_score'] > data['away_score']).astype(int)

        elif sport == 'mlb':
            # MLB uses Date, Tm, Home_Away, R, RA, etc.
            rename_map = {
                'Date': 'date',
                'Tm': 'team',
                'Opp': 'opponent',
                'R': 'runs_scored',
                'RA': 'runs_allowed',
            }
            data = data.rename(columns={k: v for k, v in rename_map.items() if k in data.columns})

            # Parse home/away
            if 'Home_Away' in data.columns:
                data['is_home'] = (data['Home_Away'] == 'Home').astype(int)

        return data

    def _prepare_nfl_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare NFL features from matchup-level data."""
        logger.info("Preparing NFL matchup features...")

        # NFL data already has home_team, away_team, scores, and betting lines
        # Create simple features from the available data
        featured = data.copy()

        # Remove rows with missing scores (future games)
        featured = featured.dropna(subset=['home_score', 'away_score'])

        # Simple features from betting lines
        if 'spread_line' in featured.columns:
            featured['spread_line'] = featured['spread_line'].fillna(0)
        if 'total_line' in featured.columns:
            featured['total_line'] = featured['total_line'].fillna(45)

        # Point differential
        featured['point_diff'] = featured['home_score'] - featured['away_score']
        featured['total_points'] = featured['home_score'] + featured['away_score']

        # Ensure date column exists
        if 'date' not in featured.columns and 'gameday' in featured.columns:
            featured['date'] = featured['gameday']

        logger.info(f"NFL features prepared: {len(featured)} games")
        return featured

    def _prepare_team_log_features(self, sport: str, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare features from team-level game logs (NBA, MLB)."""
        logger.info(f"Preparing {sport} features from team logs...")

        # Group by game_id to create matchups
        if 'game_id' not in data.columns:
            # Create game_id from date and teams
            data['game_id'] = data.apply(
                lambda r: f"{r.get('date', '')}_{r.get('team', '')}",
                axis=1
            )

        matchups = []

        # For NBA, games appear twice (once per team)
        if sport == 'nba':
            # Group home games
            home_games = data[data['is_home'] == 1].copy() if 'is_home' in data.columns else data.copy()

            for _, row in home_games.iterrows():
                matchup = {
                    'date': row.get('date'),
                    'game_id': row.get('game_id'),
                    'home_team': row.get('team'),
                    'away_team': row.get('opponent'),
                    # Use WL column for target
                    'home_win': 1 if row.get('WL') == 'W' else 0,
                    # Features
                    'home_pts': row.get('pts', 0),
                    'home_fg_pct': row.get('fg_pct', 0),
                    'home_fg3_pct': row.get('fg3_pct', 0),
                    'home_reb': row.get('reb', 0),
                    'home_ast': row.get('ast', 0),
                    'home_tov': row.get('tov', 0),
                    'home_plus_minus': row.get('plus_minus', 0),
                }
                matchups.append(matchup)

        elif sport == 'mlb':
            # Group home games
            home_games = data[data['is_home'] == 1].copy() if 'is_home' in data.columns else data.copy()

            for _, row in home_games.iterrows():
                matchup = {
                    'date': row.get('date'),
                    'home_team': row.get('team'),
                    'away_team': row.get('opponent'),
                    'home_win': 1 if row.get('W/L') == 'W' else 0,
                    # Features
                    'home_runs': row.get('runs_scored', 0),
                    'home_runs_allowed': row.get('runs_allowed', 0),
                }
                matchups.append(matchup)

        if matchups:
            featured = pd.DataFrame(matchups)
            logger.info(f"{sport} features prepared: {len(featured)} matchups")
            return featured
        else:
            logger.warning(f"No matchups created for {sport}")
            return pd.DataFrame()

    def create_matchup_dataset(
        self,
        sport: str,
        team_logs: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Create matchup-level dataset from team game logs.

        For each game, creates features comparing home vs away team stats.
        """
        config = self.SPORT_CONFIGS[sport]
        engineer_class = config['feature_engineer']
        engineer = engineer_class()

        matchups = []
        date_col = config['date_col']

        # Group games by game_id or date+teams
        if 'game_id' in team_logs.columns:
            game_groups = team_logs.groupby('game_id')
        else:
            # Create synthetic game_id from date and teams
            team_logs['game_id'] = team_logs.apply(
                lambda r: f"{r.get(date_col)}_{r.get('home_team', '')}_{r.get('away_team', '')}",
                axis=1
            )
            game_groups = team_logs.groupby('game_id')

        for game_id, game_data in game_groups:
            if len(game_data) < 2:
                continue

            home_row = game_data[game_data.get('is_home', 1) == 1]
            away_row = game_data[game_data.get('is_home', 1) == 0]

            if len(home_row) == 0 or len(away_row) == 0:
                continue

            home_stats = home_row.iloc[0]
            away_stats = away_row.iloc[0]

            # Calculate matchup features
            if hasattr(engineer, 'calculate_matchup_features'):
                matchup_features = engineer.calculate_matchup_features(home_stats, away_stats)
            else:
                matchup_features = {}

            # Add metadata
            matchup_features['game_id'] = game_id
            matchup_features['date'] = home_stats.get(date_col)
            matchup_features['home_team'] = home_stats.get('team')
            matchup_features['away_team'] = away_stats.get('team')

            # Add target
            if 'home_win' in home_stats:
                matchup_features['home_win'] = home_stats['home_win']
            elif 'goals_for' in home_stats and 'goals_against' in home_stats:
                matchup_features['home_win'] = int(home_stats['goals_for'] > home_stats['goals_against'])

            matchups.append(matchup_features)

        return pd.DataFrame(matchups)

    def train_sport(
        self,
        sport: str,
        model_type: str = "xgb",
        tune_hyperparams: bool = False,
        n_tune_trials: int = 50,
        task: str = "classification"
    ) -> Dict[str, Any]:
        """
        Train model for a specific sport.

        Args:
            sport: Sport name
            model_type: Model architecture ('xgb', 'ensemble', 'stacked')
            tune_hyperparams: Whether to tune hyperparameters
            n_tune_trials: Number of Optuna trials
            task: 'classification' or 'regression'

        Returns:
            Training results dictionary
        """
        logger.info(f"=" * 60)
        logger.info(f"Training {sport.upper()} model ({model_type}, {task})")
        logger.info(f"=" * 60)

        # Load data
        data = self.load_data(sport)
        if data is None or data.empty:
            logger.error(f"No data available for {sport}")
            return {'error': 'No data available'}

        logger.info(f"Loaded {len(data)} records")

        # Feature engineering
        featured_data = self.prepare_features(sport, data)

        # Create matchup dataset if needed
        config = self.SPORT_CONFIGS[sport]
        feature_cols = config['feature_columns']

        # Check if we have matchup features or need to create them
        available_features = [c for c in feature_cols if c in featured_data.columns]

        if len(available_features) < len(feature_cols) * 0.5:
            logger.info("Creating matchup dataset from team logs...")
            featured_data = self.create_matchup_dataset(sport, featured_data)

        # Filter to available features - use configured features if available, otherwise use all numeric columns
        available_features = [c for c in feature_cols if c in featured_data.columns]

        # If not enough configured features available, use all numeric columns except target/date
        if len(available_features) < 2:
            logger.info("Using all available numeric features...")
            target_col = config['target_col']
            date_col = config['date_col']
            exclude_cols = {target_col, date_col, 'game_id', 'home_team', 'away_team'}
            available_features = [
                c for c in featured_data.columns
                if c not in exclude_cols and featured_data[c].dtype in ['int64', 'float64']
            ]

        logger.info(f"Using {len(available_features)} features: {available_features}")

        if len(available_features) < 2:
            logger.error(f"Insufficient features for {sport}")
            return {'error': 'Insufficient features'}

        # Prepare training data
        target_col = config['target_col']
        date_col = config['date_col']

        if target_col not in featured_data.columns:
            logger.error(f"Target column '{target_col}' not found")
            return {'error': f'Target column {target_col} not found'}

        # Select columns for training
        train_cols = available_features + [target_col, date_col]
        train_data = featured_data[train_cols].dropna()

        logger.info(f"Training data: {len(train_data)} samples")

        if len(train_data) < 100:
            logger.error(f"Training set too small ({len(train_data)} samples). Need at least 100.")
            return {'error': f'Training set too small: {len(train_data)} samples'}

        if len(train_data) < 500:
            logger.warning(f"Small training set ({len(train_data)} samples). Results may be unreliable.")

        # Initialize trainer
        trainer = ModelTrainer(
            sport=sport,
            model_type=model_type,
            task=task
        )

        # Train model
        results = trainer.train(
            data=train_data,
            target_col=target_col,
            date_col=date_col,
            tune_first=tune_hyperparams,
            n_tune_trials=n_tune_trials
        )

        # Log results
        logger.info(f"\n{sport.upper()} Training Results:")
        logger.info(f"  CV Aggregate: {results.get('cv_results', {}).get('aggregate', {})}")
        logger.info(f"  Final Metrics: {results.get('final_metrics', {})}")
        logger.info(f"  Model saved to: {results.get('model_path', 'N/A')}")

        # Store results
        self.results[sport] = results

        return results

    def train_all(
        self,
        sports: Optional[List[str]] = None,
        model_type: str = "xgb",
        tune_hyperparams: bool = False,
        tasks: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Train models for all specified sports.

        Args:
            sports: List of sports to train (default: all)
            model_type: Model architecture
            tune_hyperparams: Whether to tune hyperparameters
            tasks: Dict mapping sport to task type

        Returns:
            Results for all sports
        """
        if sports is None or sports == ['all']:
            sports = list(self.SPORT_CONFIGS.keys())

        tasks = tasks or {}

        all_results = {}

        for sport in sports:
            task = tasks.get(sport, 'classification')
            try:
                results = self.train_sport(
                    sport=sport,
                    model_type=model_type,
                    tune_hyperparams=tune_hyperparams,
                    task=task
                )
                all_results[sport] = results
            except Exception as e:
                logger.error(f"Error training {sport}: {e}")
                all_results[sport] = {'error': str(e)}

        # Save summary
        self._save_training_summary(all_results)

        return all_results

    def _save_training_summary(self, results: Dict[str, Any]):
        """Save training summary to JSON."""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'results': {}
        }

        for sport, result in results.items():
            if 'error' in result:
                summary['results'][sport] = {'error': result['error']}
            else:
                summary['results'][sport] = {
                    'model_path': result.get('model_path'),
                    'cv_aggregate': result.get('cv_results', {}).get('aggregate', {}),
                    'final_metrics': result.get('final_metrics', {}),
                }

        summary_path = self.model_save_path / 'training_summary.json'
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        logger.info(f"Training summary saved to {summary_path}")


def main():
    """Main entry point for training script."""
    parser = argparse.ArgumentParser(description="Train sports prediction models")

    parser.add_argument(
        '--sports',
        nargs='+',
        default=['all'],
        help='Sports to train (nba, nfl, mlb, soccer, or all)'
    )
    parser.add_argument(
        '--model-type',
        choices=['xgb', 'ensemble', 'stacked'],
        default='xgb',
        help='Model architecture'
    )
    parser.add_argument(
        '--tune',
        action='store_true',
        help='Enable hyperparameter tuning with Optuna'
    )
    parser.add_argument(
        '--tune-trials',
        type=int,
        default=50,
        help='Number of Optuna trials'
    )
    parser.add_argument(
        '--base-path',
        type=str,
        default='.',
        help='Base path for data files'
    )
    parser.add_argument(
        '--save-path',
        type=str,
        default='ml/saved_models',
        help='Path to save models'
    )

    args = parser.parse_args()

    # Setup logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO"
    )
    logger.add(
        "training_{time}.log",
        rotation="100 MB",
        level="DEBUG"
    )

    logger.info("Starting model training...")
    logger.info(f"Sports: {args.sports}")
    logger.info(f"Model type: {args.model_type}")
    logger.info(f"Hyperparameter tuning: {args.tune}")

    # Initialize trainer
    trainer = SportModelTrainer(
        base_path=args.base_path,
        model_save_path=args.save_path
    )

    # Train models
    results = trainer.train_all(
        sports=args.sports,
        model_type=args.model_type,
        tune_hyperparams=args.tune
    )

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("TRAINING COMPLETE")
    logger.info("=" * 60)

    for sport, result in results.items():
        if 'error' in result:
            logger.error(f"{sport.upper()}: FAILED - {result['error']}")
        else:
            agg = result.get('cv_results', {}).get('aggregate', {})
            auc = agg.get('auc', 'N/A')
            logger.info(f"{sport.upper()}: AUC={auc:.4f}" if isinstance(auc, float) else f"{sport.upper()}: {auc}")


if __name__ == '__main__':
    main()
