"""
Unified Prediction Service.

Orchestrates the full prediction pipeline:
1. Load trained models for each sport
2. Fetch today's games from live games service
3. Generate features for each matchup
4. Generate calibrated predictions
5. Combine with odds to find value bets

Usage:
    from ml.prediction.prediction_service import PredictionService

    service = PredictionService()
    predictions = service.get_todays_predictions("nba")
    value_bets = service.find_value_bets("nba", min_edge=0.03)
"""

import os
import json
import joblib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from loguru import logger

# Feature engineers
from ml.features.nba_features import NBAFeatureEngineer
from ml.features.nfl_features import NFLFeatureEngineer
from ml.features.mlb_features import MLBFeatureEngineer
from ml.features.soccer_features import SoccerFeatureEngineer

# Data services
from data.apis.live_games import LiveGamesService, Game
from data.apis.odds_api import OddsService
from data.apis.stats_service import StatsService


@dataclass
class Prediction:
    """A single game prediction."""
    game_id: str
    sport: str
    date: str
    home_team: str
    away_team: str

    # Probabilities
    home_win_prob: float
    away_win_prob: float
    draw_prob: Optional[float] = None  # For soccer

    # Spread/Total predictions (if applicable)
    predicted_spread: Optional[float] = None
    spread_confidence: Optional[float] = None
    predicted_total: Optional[float] = None
    total_confidence: Optional[float] = None

    # Cover probabilities given lines
    home_cover_prob: Optional[float] = None
    over_prob: Optional[float] = None

    # Odds and value
    home_ml_odds: Optional[int] = None
    away_ml_odds: Optional[int] = None
    spread_line: Optional[float] = None
    total_line: Optional[float] = None

    # Value calculations
    home_ml_edge: Optional[float] = None
    away_ml_edge: Optional[float] = None
    home_cover_edge: Optional[float] = None
    over_edge: Optional[float] = None

    # Recommended bet
    recommended_bet: Optional[str] = None
    kelly_fraction: Optional[float] = None

    # Metadata
    model_version: Optional[str] = None
    confidence: Optional[str] = None  # high, medium, low
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "sport": self.sport,
            "date": self.date,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "home_win_prob": self.home_win_prob,
            "away_win_prob": self.away_win_prob,
            "draw_prob": self.draw_prob,
            "predicted_spread": self.predicted_spread,
            "predicted_total": self.predicted_total,
            "home_cover_prob": self.home_cover_prob,
            "over_prob": self.over_prob,
            "home_ml_odds": self.home_ml_odds,
            "away_ml_odds": self.away_ml_odds,
            "spread_line": self.spread_line,
            "total_line": self.total_line,
            "home_ml_edge": self.home_ml_edge,
            "away_ml_edge": self.away_ml_edge,
            "recommended_bet": self.recommended_bet,
            "kelly_fraction": self.kelly_fraction,
            "confidence": self.confidence,
            "generated_at": self.generated_at,
        }


class PredictionService:
    """
    Main prediction service orchestrating the full pipeline.
    """

    SPORT_CONFIGS = {
        'nba': {
            'feature_engineer': NBAFeatureEngineer,
            'model_prefix': 'xgb_classification',
            'has_draw': False,
        },
        'nfl': {
            'feature_engineer': NFLFeatureEngineer,
            'model_prefix': 'xgb_classification',
            'has_draw': False,
        },
        'mlb': {
            'feature_engineer': MLBFeatureEngineer,
            'model_prefix': 'xgb_classification',
            'has_draw': False,
        },
        'soccer': {
            'feature_engineer': SoccerFeatureEngineer,
            'model_prefix': 'xgb_classification',
            'has_draw': True,
        },
    }

    def __init__(
        self,
        model_path: str = "ml/saved_models",
        cache_predictions: bool = True
    ):
        """
        Initialize prediction service.

        Args:
            model_path: Path to saved model files
            cache_predictions: Whether to cache predictions
        """
        self.model_path = Path(model_path)
        self.cache_predictions = cache_predictions

        # Initialize services
        self.live_games = LiveGamesService()
        self.stats_service = StatsService()
        self.odds_service = OddsService()

        # Model cache
        self._models: Dict[str, Any] = {}
        self._feature_engineers: Dict[str, Any] = {}

        # Prediction cache
        self._prediction_cache: Dict[str, Tuple[datetime, List[Prediction]]] = {}

    def load_model(self, sport: str) -> Optional[Any]:
        """
        Load the trained model for a sport.

        Args:
            sport: Sport name

        Returns:
            Loaded model or None
        """
        if sport in self._models:
            return self._models[sport]

        config = self.SPORT_CONFIGS.get(sport)
        if not config:
            logger.error(f"Unknown sport: {sport}")
            return None

        model_dir = self.model_path / sport

        if not model_dir.exists():
            logger.warning(f"No model directory for {sport}: {model_dir}")
            return None

        # Find the latest model file
        model_files = list(model_dir.glob(f"{config['model_prefix']}*.joblib"))

        if not model_files:
            logger.warning(f"No model files found for {sport}")
            return None

        # Sort by modification time (newest first)
        model_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        latest_model = model_files[0]

        try:
            model_data = joblib.load(latest_model)
            self._models[sport] = model_data
            logger.info(f"Loaded {sport} model from {latest_model}")
            return model_data
        except Exception as e:
            logger.error(f"Error loading {sport} model: {e}")
            return None

    def get_feature_engineer(self, sport: str):
        """Get or create feature engineer for a sport."""
        if sport not in self._feature_engineers:
            config = self.SPORT_CONFIGS.get(sport)
            if config:
                self._feature_engineers[sport] = config['feature_engineer']()
        return self._feature_engineers.get(sport)

    def get_todays_games(self, sport: str) -> List[Game]:
        """Get today's games for a sport."""
        return self.live_games.get_todays_games([sport])

    def get_team_recent_stats(
        self,
        sport: str,
        team: str,
        n_games: int = 10
    ) -> pd.Series:
        """
        Get recent stats for a team.

        Args:
            sport: Sport name
            team: Team name/abbreviation
            n_games: Number of recent games

        Returns:
            Series with team's recent stats
        """
        try:
            stats_df = self.stats_service.get_team_stats(sport, team)

            if stats_df.empty:
                return pd.Series()

            # Get the most recent record (should have rolling features)
            return stats_df.iloc[-1]
        except Exception as e:
            logger.error(f"Error getting stats for {team}: {e}")
            return pd.Series()

    def generate_matchup_features(
        self,
        sport: str,
        home_team: str,
        away_team: str
    ) -> Optional[pd.DataFrame]:
        """
        Generate features for a matchup.

        Args:
            sport: Sport name
            home_team: Home team
            away_team: Away team

        Returns:
            DataFrame with features or None
        """
        engineer = self.get_feature_engineer(sport)
        if not engineer:
            return None

        # Get team stats
        home_stats = self.get_team_recent_stats(sport, home_team)
        away_stats = self.get_team_recent_stats(sport, away_team)

        if home_stats.empty or away_stats.empty:
            logger.warning(f"Missing stats for {home_team} vs {away_team}")
            return None

        # Calculate matchup features
        if hasattr(engineer, 'calculate_matchup_features'):
            features = engineer.calculate_matchup_features(home_stats, away_stats)
            return pd.DataFrame([features])

        return None

    def predict_game(
        self,
        sport: str,
        game: Game
    ) -> Optional[Prediction]:
        """
        Generate prediction for a single game.

        Args:
            sport: Sport name
            game: Game object

        Returns:
            Prediction object or None
        """
        model_data = self.load_model(sport)
        if not model_data:
            logger.warning(f"No model available for {sport}")
            return None

        # Get model from loaded data
        if isinstance(model_data, dict):
            model = model_data.get('model')
        else:
            model = model_data

        if not model:
            return None

        # Generate features
        features_df = self.generate_matchup_features(
            sport,
            game.home_team,
            game.away_team
        )

        if features_df is None or features_df.empty:
            logger.warning(f"Could not generate features for {game.home_team} vs {game.away_team}")
            return None

        # Get feature names from model
        feature_names = model_data.get('feature_names', []) if isinstance(model_data, dict) else []

        # Align features with model expectation
        if feature_names:
            # Add missing features with 0
            for col in feature_names:
                if col not in features_df.columns:
                    features_df[col] = 0
            features_df = features_df[feature_names]

        try:
            # Generate prediction
            if hasattr(model, 'predict_proba'):
                probs = model.predict_proba(features_df)
                home_win_prob = probs[0][1]
            elif hasattr(model, 'predict'):
                # Check if model has calibrator
                if isinstance(model_data, dict) and model_data.get('calibrator'):
                    raw_prob = model.predict_proba(features_df)[0][1]
                    home_win_prob = model_data['calibrator'].transform([raw_prob])[0]
                else:
                    home_win_prob = model.predict(features_df)[0]
            else:
                logger.error("Model has no predict method")
                return None

            away_win_prob = 1 - home_win_prob

            # Determine confidence level
            if home_win_prob > 0.65 or home_win_prob < 0.35:
                confidence = "high"
            elif home_win_prob > 0.55 or home_win_prob < 0.45:
                confidence = "medium"
            else:
                confidence = "low"

            prediction = Prediction(
                game_id=game.game_id,
                sport=sport,
                date=game.date,
                home_team=game.home_team,
                away_team=game.away_team,
                home_win_prob=float(home_win_prob),
                away_win_prob=float(away_win_prob),
                spread_line=game.spread_line,
                total_line=game.total_line,
                home_ml_odds=game.home_moneyline,
                away_ml_odds=game.away_moneyline,
                confidence=confidence,
            )

            # Calculate edges if odds available
            prediction = self._add_value_calculations(prediction)

            return prediction

        except Exception as e:
            logger.error(f"Error predicting game: {e}")
            return None

    def _add_value_calculations(self, prediction: Prediction) -> Prediction:
        """Add edge and Kelly calculations to prediction."""

        # Home ML edge
        if prediction.home_ml_odds:
            implied_prob = self._american_to_prob(prediction.home_ml_odds)
            prediction.home_ml_edge = prediction.home_win_prob - implied_prob

        # Away ML edge
        if prediction.away_ml_odds:
            implied_prob = self._american_to_prob(prediction.away_ml_odds)
            prediction.away_ml_edge = prediction.away_win_prob - implied_prob

        # Find best bet
        best_edge = 0
        best_bet = None
        kelly = 0

        if prediction.home_ml_edge and prediction.home_ml_edge > best_edge:
            best_edge = prediction.home_ml_edge
            best_bet = f"Home ML ({prediction.home_team})"
            kelly = self._kelly_criterion(prediction.home_win_prob, prediction.home_ml_odds)

        if prediction.away_ml_edge and prediction.away_ml_edge > best_edge:
            best_edge = prediction.away_ml_edge
            best_bet = f"Away ML ({prediction.away_team})"
            kelly = self._kelly_criterion(prediction.away_win_prob, prediction.away_ml_odds)

        if best_edge >= 0.03:  # Minimum 3% edge
            prediction.recommended_bet = best_bet
            prediction.kelly_fraction = kelly

        return prediction

    def _american_to_prob(self, american_odds: int) -> float:
        """Convert American odds to implied probability."""
        if american_odds > 0:
            return 100 / (american_odds + 100)
        else:
            return abs(american_odds) / (abs(american_odds) + 100)

    def _kelly_criterion(self, prob: float, american_odds: int) -> float:
        """Calculate Kelly criterion fraction."""
        if american_odds > 0:
            b = american_odds / 100
        else:
            b = 100 / abs(american_odds)

        q = 1 - prob
        kelly = (prob * b - q) / b

        # Return quarter Kelly, capped at 5%
        return max(0, min(kelly * 0.25, 0.05))

    def get_todays_predictions(
        self,
        sport: str,
        refresh: bool = False
    ) -> List[Prediction]:
        """
        Get predictions for all of today's games.

        Args:
            sport: Sport name
            refresh: Force refresh even if cached

        Returns:
            List of Prediction objects
        """
        cache_key = f"{sport}_{datetime.now().strftime('%Y-%m-%d')}"

        # Check cache
        if not refresh and cache_key in self._prediction_cache:
            cached_time, predictions = self._prediction_cache[cache_key]
            # Cache valid for 1 hour
            if (datetime.now() - cached_time).seconds < 3600:
                return predictions

        games = self.get_todays_games(sport)

        if not games:
            logger.info(f"No games found for {sport} today")
            return []

        predictions = []

        for game in games:
            if game.status == "final":
                continue  # Skip completed games

            prediction = self.predict_game(sport, game)
            if prediction:
                predictions.append(prediction)

        # Cache results
        if self.cache_predictions:
            self._prediction_cache[cache_key] = (datetime.now(), predictions)

        logger.info(f"Generated {len(predictions)} predictions for {sport}")

        return predictions

    def find_value_bets(
        self,
        sport: str,
        min_edge: float = 0.03,
        min_kelly: float = 0.01
    ) -> List[Dict[str, Any]]:
        """
        Find value betting opportunities.

        Args:
            sport: Sport name
            min_edge: Minimum edge required (default 3%)
            min_kelly: Minimum Kelly fraction (default 1%)

        Returns:
            List of value bet opportunities
        """
        predictions = self.get_todays_predictions(sport)

        value_bets = []

        for pred in predictions:
            # Check home ML
            if pred.home_ml_edge and pred.home_ml_edge >= min_edge:
                kelly = pred.kelly_fraction or 0
                if kelly >= min_kelly:
                    value_bets.append({
                        "game_id": pred.game_id,
                        "game": f"{pred.away_team} @ {pred.home_team}",
                        "bet_type": "Moneyline",
                        "selection": pred.home_team,
                        "odds": pred.home_ml_odds,
                        "model_prob": pred.home_win_prob,
                        "edge": pred.home_ml_edge,
                        "kelly": kelly,
                        "confidence": pred.confidence,
                    })

            # Check away ML
            if pred.away_ml_edge and pred.away_ml_edge >= min_edge:
                kelly = self._kelly_criterion(pred.away_win_prob, pred.away_ml_odds or 100)
                if kelly >= min_kelly:
                    value_bets.append({
                        "game_id": pred.game_id,
                        "game": f"{pred.away_team} @ {pred.home_team}",
                        "bet_type": "Moneyline",
                        "selection": pred.away_team,
                        "odds": pred.away_ml_odds,
                        "model_prob": pred.away_win_prob,
                        "edge": pred.away_ml_edge,
                        "kelly": kelly,
                        "confidence": pred.confidence,
                    })

        # Sort by edge
        value_bets.sort(key=lambda x: x["edge"], reverse=True)

        return value_bets

    def get_predictions_summary(self, sport: str) -> Dict[str, Any]:
        """Get summary of today's predictions."""
        predictions = self.get_todays_predictions(sport)

        if not predictions:
            return {"sport": sport, "games": 0, "message": "No predictions available"}

        summary = {
            "sport": sport,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "games": len(predictions),
            "high_confidence": sum(1 for p in predictions if p.confidence == "high"),
            "value_bets": len(self.find_value_bets(sport)),
            "predictions": [p.to_dict() for p in predictions],
        }

        return summary

    def save_predictions(self, sport: str, output_path: Optional[str] = None):
        """Save predictions to JSON file."""
        predictions = self.get_todays_predictions(sport)

        if not predictions:
            logger.info(f"No predictions to save for {sport}")
            return

        if output_path is None:
            output_dir = Path("predictions")
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / f"{sport}_{datetime.now().strftime('%Y%m%d')}.json"

        data = {
            "sport": sport,
            "generated_at": datetime.now().isoformat(),
            "predictions": [p.to_dict() for p in predictions]
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved {len(predictions)} predictions to {output_path}")


# Singleton instance
prediction_service = PredictionService()


def get_predictions(sport: str) -> List[Dict[str, Any]]:
    """Convenience function to get today's predictions."""
    predictions = prediction_service.get_todays_predictions(sport)
    return [p.to_dict() for p in predictions]


def get_value_bets(sport: str, min_edge: float = 0.03) -> List[Dict[str, Any]]:
    """Convenience function to get value bets."""
    return prediction_service.find_value_bets(sport, min_edge=min_edge)
