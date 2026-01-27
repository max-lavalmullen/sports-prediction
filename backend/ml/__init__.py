"""
ML Module for Sports Prediction.

This module provides:
- Feature engineering pipelines
- Multiple model architectures (XGBoost, Ensemble, Stacked)
- Elo rating system
- Walk-forward validation training
- Hyperparameter tuning
"""

from ml.models.base_model import BaseModel
from ml.models.xgb_model import XGBModel, XGBSpreadModel, XGBTotalModel
from ml.models.ensemble import EnsembleModel, StackedEnsemble
from ml.models.elo import EloRating, SportEloConfig, EloFeatureGenerator

# Feature engineers
from ml.features.nba_features import NBAFeatureEngineer, CORE_FEATURE_COLUMNS
from ml.features.nfl_features import NFLFeatureEngineer, NFL_CORE_FEATURES
from ml.features.mlb_features import MLBFeatureEngineer, MLB_CORE_FEATURES
from ml.features.soccer_features import SoccerFeatureEngineer, SOCCER_CORE_FEATURES
from ml.features import get_feature_engineer, get_feature_columns

from ml.training.trainer import ModelTrainer, WalkForwardSplit

__all__ = [
    # Base
    'BaseModel',

    # Models
    'XGBModel',
    'XGBSpreadModel',
    'XGBTotalModel',
    'EnsembleModel',
    'StackedEnsemble',

    # Elo
    'EloRating',
    'SportEloConfig',
    'EloFeatureGenerator',

    # Features
    'NBAFeatureEngineer',
    'NFLFeatureEngineer',
    'MLBFeatureEngineer',
    'SoccerFeatureEngineer',
    'CORE_FEATURE_COLUMNS',
    'NFL_CORE_FEATURES',
    'MLB_CORE_FEATURES',
    'SOCCER_CORE_FEATURES',
    'get_feature_engineer',
    'get_feature_columns',

    # Training
    'ModelTrainer',
    'WalkForwardSplit',
]
