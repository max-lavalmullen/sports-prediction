"""
Advanced Model Training Pipeline.

Implements proper time-series cross-validation (walk-forward validation),
hyperparameter tuning with Optuna, and comprehensive model evaluation.

For sports prediction, avoiding data leakage is CRITICAL. Standard k-fold
cross-validation is invalid because it uses future data to predict the past.
Walk-forward validation respects temporal ordering.
"""
import pandas as pd
import numpy as np
from sklearn.metrics import (
    log_loss, roc_auc_score, brier_score_loss,
    mean_squared_error, mean_absolute_error, r2_score
)
from datetime import datetime
import os
from typing import Dict, Any, List, Optional, Tuple, Type
from loguru import logger
import warnings

try:
    import optuna
    from optuna.samplers import TPESampler
    HAS_OPTUNA = True
except ImportError:
    HAS_OPTUNA = False
    warnings.warn("Optuna not installed. Install with: pip install optuna")

from ml.models.base_model import BaseModel
from ml.models.xgb_model import XGBModel, XGBSpreadModel, XGBTotalModel
from ml.models.ensemble import EnsembleModel, StackedEnsemble
from app.core.config import settings


class WalkForwardSplit:
    """
    Time-series cross-validation with expanding or rolling window.

    Walk-forward validation:
    - Train on data up to time T
    - Test on data from T to T+gap
    - Expand training window (or roll it forward)
    - Repeat

    This mimics real-world deployment where you can only use past data.
    """

    def __init__(
        self,
        n_splits: int = 5,
        test_size: int = None,
        min_train_size: int = None,
        gap: int = 0,
        expanding: bool = True
    ):
        """
        Args:
            n_splits: Number of train/test splits
            test_size: Size of each test set (in samples)
            min_train_size: Minimum training samples before first split
            gap: Number of samples to skip between train and test (prevents leakage)
            expanding: If True, training window expands. If False, it rolls.
        """
        self.n_splits = n_splits
        self.test_size = test_size
        self.min_train_size = min_train_size
        self.gap = gap
        self.expanding = expanding

    def split(self, X: pd.DataFrame, y=None, groups=None):
        """
        Generate train/test indices for walk-forward validation.

        Yields:
            Tuple of (train_indices, test_indices)
        """
        n_samples = len(X)

        # Calculate test size if not specified
        if self.test_size is None:
            self.test_size = n_samples // (self.n_splits + 1)

        # Calculate minimum training size
        if self.min_train_size is None:
            self.min_train_size = self.test_size * 2

        # Generate splits
        test_starts = []
        current_pos = self.min_train_size + self.gap

        for i in range(self.n_splits):
            if current_pos + self.test_size > n_samples:
                break
            test_starts.append(current_pos)
            current_pos += self.test_size

        for test_start in test_starts:
            test_end = min(test_start + self.test_size, n_samples)

            if self.expanding:
                # Training uses all data up to gap before test
                train_end = test_start - self.gap
                train_indices = np.arange(0, train_end)
            else:
                # Rolling window of fixed size
                window_size = self.min_train_size
                train_start = max(0, test_start - self.gap - window_size)
                train_end = test_start - self.gap
                train_indices = np.arange(train_start, train_end)

            test_indices = np.arange(test_start, test_end)

            yield train_indices, test_indices

    def get_n_splits(self):
        return self.n_splits


class ModelTrainer:
    """
    Comprehensive training pipeline with:
    - Walk-forward cross-validation
    - Hyperparameter tuning (Optuna)
    - Multiple model types
    - Calibration and evaluation
    """

    def __init__(
        self,
        sport: str,
        model_type: str = "ensemble",
        task: str = "classification"
    ):
        """
        Args:
            sport: Sport name (e.g., 'nba', 'nfl')
            model_type: Model architecture ('xgb', 'ensemble', 'stacked')
            task: 'classification' (win/loss) or 'regression' (spread/total)
        """
        self.sport = sport
        self.model_type = model_type
        self.task = task
        self.model = None
        self.save_dir = os.path.join(settings.MODEL_PATH, sport)
        os.makedirs(self.save_dir, exist_ok=True)

    def _create_model(self, params: Optional[Dict] = None) -> BaseModel:
        """Create model instance based on configuration."""
        if self.model_type == "xgb":
            if self.task == "classification":
                return XGBModel(params=params, task="classification")
            elif self.task == "spread":
                return XGBSpreadModel(params=params)
            else:
                return XGBTotalModel(params=params)

        elif self.model_type == "ensemble":
            return EnsembleModel(task=self.task)

        elif self.model_type == "stacked":
            return StackedEnsemble(task=self.task)

        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

    def walk_forward_cv(
        self,
        data: pd.DataFrame,
        target_col: str,
        date_col: str = 'date',
        n_splits: int = 5,
        gap: int = 0
    ) -> Dict[str, Any]:
        """
        Perform walk-forward cross-validation.

        This is the PROPER way to evaluate sports prediction models.

        Returns:
            Dictionary with fold metrics and aggregated performance
        """
        logger.info(f"Starting walk-forward CV with {n_splits} splits...")

        # Ensure sorted by date
        data = data.sort_values(date_col).reset_index(drop=True)

        # Prepare features and target
        feature_cols = [c for c in data.columns if c not in [target_col, date_col]]
        X = data[feature_cols]
        y = data[target_col]

        # Create walk-forward splitter
        splitter = WalkForwardSplit(
            n_splits=n_splits,
            gap=gap,
            expanding=True
        )

        # Track metrics across folds
        fold_results = []
        all_predictions = []
        all_actuals = []

        for fold_idx, (train_idx, test_idx) in enumerate(splitter.split(X)):
            logger.info(f"Fold {fold_idx + 1}/{n_splits}: "
                       f"Train size={len(train_idx)}, Test size={len(test_idx)}")

            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

            # Create and train model for this fold
            model = self._create_model()
            model.train(X_train, y_train, X_val=X_test, y_val=y_test)

            # Get predictions
            predictions = model.predict(X_test)

            # Calculate metrics
            fold_metrics = self._calculate_metrics(y_test, predictions)
            fold_metrics['fold'] = fold_idx + 1
            fold_metrics['train_size'] = len(train_idx)
            fold_metrics['test_size'] = len(test_idx)
            fold_metrics['test_start_date'] = data.iloc[test_idx[0]][date_col]
            fold_metrics['test_end_date'] = data.iloc[test_idx[-1]][date_col]

            fold_results.append(fold_metrics)

            all_predictions.extend(predictions)
            all_actuals.extend(y_test)

            logger.info(f"Fold {fold_idx + 1} metrics: {fold_metrics}")

        # Aggregate metrics
        aggregate_metrics = self._calculate_metrics(
            np.array(all_actuals),
            np.array(all_predictions)
        )

        # Calculate metric variance across folds
        metric_names = ['auc', 'log_loss', 'brier_score'] if self.task == "classification" else ['rmse', 'mae', 'r2']

        for metric in metric_names:
            values = [f[metric] for f in fold_results if metric in f]
            if values:
                aggregate_metrics[f'{metric}_std'] = np.std(values)
                aggregate_metrics[f'{metric}_min'] = np.min(values)
                aggregate_metrics[f'{metric}_max'] = np.max(values)

        return {
            'fold_results': fold_results,
            'aggregate': aggregate_metrics,
            'predictions': all_predictions,
            'actuals': all_actuals
        }

    def _calculate_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict[str, float]:
        """Calculate evaluation metrics."""
        metrics = {}

        if self.task == "classification":
            # Classification metrics
            metrics['auc'] = roc_auc_score(y_true, y_pred)
            metrics['log_loss'] = log_loss(y_true, y_pred)
            metrics['brier_score'] = brier_score_loss(y_true, y_pred)

            # Accuracy at different thresholds
            metrics['accuracy_50'] = np.mean((y_pred > 0.5) == y_true)

            # Calibration (how close predictions are to actual win rates)
            for threshold in [0.55, 0.60, 0.65, 0.70]:
                mask = y_pred >= threshold
                if mask.sum() > 0:
                    metrics[f'actual_winrate_{int(threshold*100)}'] = y_true[mask].mean()
                    metrics[f'n_predictions_{int(threshold*100)}'] = mask.sum()

        else:
            # Regression metrics
            metrics['rmse'] = np.sqrt(mean_squared_error(y_true, y_pred))
            metrics['mae'] = mean_absolute_error(y_true, y_pred)
            metrics['r2'] = r2_score(y_true, y_pred)

        return metrics

    def tune_hyperparameters(
        self,
        data: pd.DataFrame,
        target_col: str,
        date_col: str = 'date',
        n_trials: int = 50,
        n_cv_splits: int = 3
    ) -> Dict[str, Any]:
        """
        Tune hyperparameters using Optuna with walk-forward validation.

        Returns:
            Best parameters and study results
        """
        if not HAS_OPTUNA:
            raise ImportError("Optuna required for hyperparameter tuning")

        logger.info(f"Starting hyperparameter tuning with {n_trials} trials...")

        data = data.sort_values(date_col).reset_index(drop=True)
        feature_cols = [c for c in data.columns if c not in [target_col, date_col]]
        X = data[feature_cols]
        y = data[target_col]

        def objective(trial):
            # Define hyperparameter search space
            params = {
                'max_depth': trial.suggest_int('max_depth', 2, 6),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.1, log=True),
                'n_estimators': trial.suggest_int('n_estimators', 200, 1000),
                'subsample': trial.suggest_float('subsample', 0.6, 0.9),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 0.9),
                'min_child_weight': trial.suggest_int('min_child_weight', 5, 50),
                'reg_alpha': trial.suggest_float('reg_alpha', 0.01, 1.0, log=True),
                'reg_lambda': trial.suggest_float('reg_lambda', 0.1, 10.0, log=True),
            }

            # Walk-forward CV
            splitter = WalkForwardSplit(n_splits=n_cv_splits, expanding=True)
            scores = []

            for train_idx, test_idx in splitter.split(X):
                X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
                y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

                model = XGBModel(params=params, task=self.task)
                model.train(X_train, y_train, X_val=X_test, y_val=y_test)
                preds = model.predict(X_test)

                if self.task == "classification":
                    score = log_loss(y_test, preds)  # Minimize
                else:
                    score = mean_squared_error(y_test, preds)  # Minimize

                scores.append(score)

            return np.mean(scores)

        # Create and run study
        study = optuna.create_study(
            direction='minimize',
            sampler=TPESampler(seed=42)
        )
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

        logger.info(f"Best parameters: {study.best_params}")
        logger.info(f"Best score: {study.best_value:.4f}")

        return {
            'best_params': study.best_params,
            'best_score': study.best_value,
            'n_trials': n_trials,
            'study': study
        }

    def train(
        self,
        data: pd.DataFrame,
        target_col: str,
        date_col: str = 'date',
        tune_first: bool = False,
        n_tune_trials: int = 30
    ) -> Dict[str, Any]:
        """
        Full training pipeline.

        Args:
            data: Training data with features and target
            target_col: Name of target column
            date_col: Name of date column
            tune_first: Whether to tune hyperparameters first
            n_tune_trials: Number of Optuna trials if tuning

        Returns:
            Training results including metrics and model path
        """
        logger.info(f"Starting training for {self.sport} ({self.model_type})...")

        # Sort by date
        data = data.sort_values(date_col).reset_index(drop=True)

        # Optional hyperparameter tuning
        best_params = None
        if tune_first and HAS_OPTUNA and self.model_type == 'xgb':
            tune_results = self.tune_hyperparameters(
                data, target_col, date_col,
                n_trials=n_tune_trials
            )
            best_params = tune_results['best_params']

        # Walk-forward CV to get unbiased performance estimate
        cv_results = self.walk_forward_cv(data, target_col, date_col)
        logger.info(f"CV Results: {cv_results['aggregate']}")

        # Train final model on all data
        feature_cols = [c for c in data.columns if c not in [target_col, date_col]]
        X = data[feature_cols]
        y = data[target_col]

        # Use last portion as validation for early stopping
        split_idx = int(len(data) * 0.85)
        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

        self.model = self._create_model(params=best_params)
        self.model.train(X_train, y_train, X_val=X_val, y_val=y_val)

        # Final evaluation on held-out validation set
        final_preds = self.model.predict(X_val)
        final_metrics = self._calculate_metrics(y_val, final_preds)

        logger.info(f"Final model metrics: {final_metrics}")

        # Save model
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.model_type}_{self.task}_{timestamp}.joblib"
        path = os.path.join(self.save_dir, filename)
        self.model.save(path)
        logger.info(f"Model saved to {path}")

        return {
            'cv_results': cv_results,
            'final_metrics': final_metrics,
            'best_params': best_params,
            'model_path': path,
            'feature_importance': self.model.get_feature_importance() if hasattr(self.model, 'get_feature_importance') else None
        }

    def backtest(
        self,
        data: pd.DataFrame,
        target_col: str,
        date_col: str = 'date',
        odds_col: str = 'odds',
        min_edge: float = 0.03,
        kelly_fraction: float = 0.25
    ) -> Dict[str, Any]:
        """
        Backtest betting strategy using walk-forward approach.

        Simulates actual betting performance with proper temporal ordering.

        Returns:
            Backtesting results including ROI, profit, and bet history
        """
        logger.info("Starting backtest...")

        data = data.sort_values(date_col).reset_index(drop=True)
        feature_cols = [c for c in data.columns if c not in [target_col, date_col, odds_col]]

        splitter = WalkForwardSplit(n_splits=10, expanding=True)

        all_bets = []
        bankroll = 10000
        initial_bankroll = bankroll

        for train_idx, test_idx in splitter.split(data):
            X_train = data.iloc[train_idx][feature_cols]
            y_train = data.iloc[train_idx][target_col]
            X_test = data.iloc[test_idx][feature_cols]

            model = self._create_model()
            model.train(X_train, y_train)
            predictions = model.predict(X_test)

            for i, idx in enumerate(test_idx):
                row = data.iloc[idx]
                pred_prob = predictions[i]

                # Calculate implied probability from odds
                if odds_col in data.columns:
                    odds = row[odds_col]
                    if odds > 0:
                        implied_prob = 100 / (odds + 100)
                    else:
                        implied_prob = abs(odds) / (abs(odds) + 100)
                else:
                    implied_prob = 0.5

                edge = pred_prob - implied_prob

                if edge >= min_edge:
                    # Kelly criterion for bet sizing
                    if odds > 0:
                        b = odds / 100
                    else:
                        b = 100 / abs(odds)

                    kelly = (pred_prob * b - (1 - pred_prob)) / b
                    stake = bankroll * kelly * kelly_fraction
                    stake = min(stake, bankroll * 0.05)  # Max 5% of bankroll

                    # Determine outcome
                    actual = row[target_col]
                    if actual == 1:  # Win
                        profit = stake * b
                    else:
                        profit = -stake

                    bankroll += profit

                    all_bets.append({
                        'date': row[date_col],
                        'pred_prob': pred_prob,
                        'implied_prob': implied_prob,
                        'edge': edge,
                        'stake': stake,
                        'outcome': actual,
                        'profit': profit,
                        'bankroll': bankroll
                    })

        # Calculate results
        if all_bets:
            bets_df = pd.DataFrame(all_bets)
            total_staked = bets_df['stake'].sum()
            total_profit = bets_df['profit'].sum()
            wins = bets_df[bets_df['outcome'] == 1]

            results = {
                'total_bets': len(all_bets),
                'wins': len(wins),
                'losses': len(all_bets) - len(wins),
                'win_rate': len(wins) / len(all_bets),
                'total_staked': total_staked,
                'total_profit': total_profit,
                'roi': total_profit / total_staked if total_staked > 0 else 0,
                'final_bankroll': bankroll,
                'bankroll_growth': (bankroll - initial_bankroll) / initial_bankroll,
                'avg_edge': bets_df['edge'].mean(),
                'bets': all_bets
            }
        else:
            results = {
                'total_bets': 0,
                'message': 'No bets met edge threshold'
            }

        logger.info(f"Backtest complete: {results.get('total_bets', 0)} bets, "
                   f"ROI: {results.get('roi', 0):.2%}")

        return results