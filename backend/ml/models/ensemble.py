"""
Ensemble Model for Sports Prediction.

Combines multiple diverse models to improve prediction accuracy and reliability.
Research shows ensemble methods consistently outperform single models for
sports betting, especially when combining fundamentally different algorithms.
"""
import numpy as np
import pandas as pd
import joblib
from typing import Dict, Any, Optional, List, Tuple
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
import xgboost as xgb
import warnings

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    warnings.warn("LightGBM not installed. Install with: pip install lightgbm")

from ml.models.base_model import BaseModel


class EnsembleModel(BaseModel):
    """
    Ensemble combining multiple models with learned weights.

    Models included:
    1. XGBoost - Gradient boosting (handles non-linear patterns)
    2. LightGBM - Fast gradient boosting (different splits)
    3. Logistic Regression - Linear baseline (regularizes ensemble)
    4. Neural Network - Can capture complex interactions (optional)

    The final prediction is a weighted average, with weights learned
    via cross-validation to minimize log loss.
    """

    def __init__(
        self,
        task: str = "classification",
        use_lightgbm: bool = True,
        use_neural_net: bool = False
    ):
        """
        Initialize ensemble.

        Args:
            task: "classification" or "regression"
            use_lightgbm: Include LightGBM if available
            use_neural_net: Include neural network (requires tensorflow)
        """
        self.task = task
        self.use_lightgbm = use_lightgbm and HAS_LIGHTGBM
        self.use_neural_net = use_neural_net
        self.models: Dict[str, Any] = {}
        self.weights: Dict[str, float] = {}
        self.calibrator = None
        self.feature_names = None
        self.is_trained = False

    def _create_models(self) -> Dict[str, Any]:
        """Create the base models for the ensemble."""
        models = {}

        # XGBoost
        if self.task == "classification":
            models['xgb'] = xgb.XGBClassifier(
                objective='binary:logistic',
                max_depth=4,
                learning_rate=0.03,
                n_estimators=500,
                subsample=0.7,
                colsample_bytree=0.7,
                min_child_weight=10,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
                n_jobs=-1,
                use_label_encoder=False,
                eval_metric='logloss'
            )
        else:
            models['xgb'] = xgb.XGBRegressor(
                objective='reg:squarederror',
                max_depth=4,
                learning_rate=0.03,
                n_estimators=500,
                subsample=0.7,
                colsample_bytree=0.7,
                min_child_weight=10,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
                n_jobs=-1
            )

        # LightGBM (if available)
        if self.use_lightgbm:
            if self.task == "classification":
                models['lgb'] = lgb.LGBMClassifier(
                    objective='binary',
                    max_depth=4,
                    learning_rate=0.03,
                    n_estimators=500,
                    subsample=0.7,
                    colsample_bytree=0.7,
                    min_child_samples=20,
                    reg_alpha=0.1,
                    reg_lambda=1.0,
                    random_state=43,  # Different seed
                    n_jobs=-1,
                    verbose=-1
                )
            else:
                models['lgb'] = lgb.LGBMRegressor(
                    objective='regression',
                    max_depth=4,
                    learning_rate=0.03,
                    n_estimators=500,
                    subsample=0.7,
                    colsample_bytree=0.7,
                    min_child_samples=20,
                    reg_alpha=0.1,
                    reg_lambda=1.0,
                    random_state=43,
                    n_jobs=-1,
                    verbose=-1
                )

        # Linear model (provides regularization/smoothing to ensemble)
        if self.task == "classification":
            models['linear'] = LogisticRegression(
                C=0.1,  # Strong regularization
                max_iter=1000,
                random_state=44,
                n_jobs=-1
            )
        else:
            models['linear'] = Ridge(
                alpha=1.0,
                random_state=44
            )

        return models

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        optimize_weights: bool = True,
        **kwargs
    ):
        """
        Train all models in the ensemble.

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features (for weight optimization)
            y_val: Validation labels
            optimize_weights: Whether to learn optimal weights via validation
        """
        self.feature_names = list(X_train.columns)
        self.models = self._create_models()

        # Train each model
        for name, model in self.models.items():
            if name in ['xgb', 'lgb'] and X_val is not None:
                # Use early stopping for boosting models
                model.fit(
                    X_train, y_train,
                    eval_set=[(X_val, y_val)],
                    early_stopping_rounds=50,
                    verbose=False
                )
            else:
                model.fit(X_train, y_train)

        # Optimize ensemble weights
        if optimize_weights and X_val is not None and y_val is not None:
            self._optimize_weights(X_val, y_val)
        else:
            # Equal weights as default
            n_models = len(self.models)
            self.weights = {name: 1.0 / n_models for name in self.models}

        # Calibrate final ensemble probabilities
        if self.task == "classification":
            self._calibrate_ensemble(X_train, y_train)

        self.is_trained = True

    def _optimize_weights(self, X_val: pd.DataFrame, y_val: pd.Series):
        """
        Optimize ensemble weights to minimize validation loss.

        Uses constrained optimization to find weights that minimize log loss
        while ensuring weights sum to 1 and are non-negative.
        """
        from scipy.optimize import minimize

        # Get predictions from each model
        model_preds = {}
        for name, model in self.models.items():
            if self.task == "classification":
                model_preds[name] = model.predict_proba(X_val)[:, 1]
            else:
                model_preds[name] = model.predict(X_val)

        model_names = list(model_preds.keys())
        pred_matrix = np.column_stack([model_preds[n] for n in model_names])

        def loss_function(weights):
            """Calculate loss for given weights."""
            weighted_pred = np.dot(pred_matrix, weights)

            if self.task == "classification":
                # Log loss
                eps = 1e-15
                weighted_pred = np.clip(weighted_pred, eps, 1 - eps)
                return -np.mean(
                    y_val * np.log(weighted_pred) +
                    (1 - y_val) * np.log(1 - weighted_pred)
                )
            else:
                # MSE
                return np.mean((weighted_pred - y_val) ** 2)

        # Constraints: weights sum to 1
        constraints = {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}

        # Bounds: weights between 0 and 1
        bounds = [(0, 1) for _ in model_names]

        # Initial guess: equal weights
        n_models = len(model_names)
        initial_weights = np.ones(n_models) / n_models

        # Optimize
        result = minimize(
            loss_function,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        # Store optimized weights
        self.weights = {name: w for name, w in zip(model_names, result.x)}

    def _calibrate_ensemble(self, X: pd.DataFrame, y: pd.Series):
        """Calibrate ensemble probabilities."""
        from sklearn.model_selection import cross_val_predict

        # Get ensemble predictions via cross-validation
        raw_preds = self._get_raw_predictions(X)

        # Fit isotonic calibrator
        self.calibrator = IsotonicRegression(out_of_bounds='clip')
        self.calibrator.fit(raw_preds, y)

    def _get_raw_predictions(self, X: pd.DataFrame) -> np.ndarray:
        """Get weighted predictions from all models (uncalibrated)."""
        predictions = np.zeros(len(X))

        for name, model in self.models.items():
            weight = self.weights.get(name, 0)
            if weight > 0:
                if self.task == "classification":
                    pred = model.predict_proba(X)[:, 1]
                else:
                    pred = model.predict(X)
                predictions += weight * pred

        return predictions

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Get calibrated ensemble predictions.

        Returns probabilities for classification, point estimates for regression.
        """
        if not self.is_trained:
            raise ValueError("Ensemble not trained")

        raw_preds = self._get_raw_predictions(X)

        if self.task == "classification" and self.calibrator is not None:
            return self.calibrator.transform(raw_preds)

        return raw_preds

    def predict_individual(self, X: pd.DataFrame) -> Dict[str, np.ndarray]:
        """
        Get predictions from each individual model.

        Useful for analyzing model agreement.
        """
        if not self.is_trained:
            raise ValueError("Ensemble not trained")

        predictions = {}
        for name, model in self.models.items():
            if self.task == "classification":
                predictions[name] = model.predict_proba(X)[:, 1]
            else:
                predictions[name] = model.predict(X)

        return predictions

    def get_model_agreement(self, X: pd.DataFrame) -> np.ndarray:
        """
        Calculate model agreement score (0-1).

        Higher values indicate models agree more, which typically
        correlates with more reliable predictions.
        """
        individual_preds = self.predict_individual(X)
        pred_matrix = np.column_stack(list(individual_preds.values()))

        # Agreement = 1 - normalized standard deviation
        pred_std = np.std(pred_matrix, axis=1)
        max_std = 0.5 if self.task == "classification" else pred_std.max()

        agreement = 1 - (pred_std / max_std)
        return np.clip(agreement, 0, 1)

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get aggregated feature importance across models.

        Weighted by model weights in ensemble.
        """
        if not self.is_trained:
            raise ValueError("Ensemble not trained")

        importance_sum = {}

        for name, model in self.models.items():
            weight = self.weights.get(name, 0)
            if weight == 0:
                continue

            # Get importance from this model
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
            elif hasattr(model, 'coef_'):
                importances = np.abs(model.coef_).flatten()
            else:
                continue

            # Aggregate
            for i, imp in enumerate(importances):
                if i < len(self.feature_names):
                    feat_name = self.feature_names[i]
                    importance_sum[feat_name] = importance_sum.get(feat_name, 0) + weight * imp

        # Normalize
        total = sum(importance_sum.values()) or 1
        return {k: v / total for k, v in sorted(
            importance_sum.items(),
            key=lambda x: x[1],
            reverse=True
        )}

    def save(self, path: str):
        """Save ensemble to disk."""
        save_dict = {
            'models': self.models,
            'weights': self.weights,
            'calibrator': self.calibrator,
            'feature_names': self.feature_names,
            'task': self.task,
            'is_trained': self.is_trained
        }
        joblib.dump(save_dict, path)

    def load(self, path: str):
        """Load ensemble from disk."""
        save_dict = joblib.load(path)
        self.models = save_dict['models']
        self.weights = save_dict['weights']
        self.calibrator = save_dict.get('calibrator')
        self.feature_names = save_dict.get('feature_names')
        self.task = save_dict.get('task', 'classification')
        self.is_trained = save_dict.get('is_trained', False)


class StackedEnsemble(BaseModel):
    """
    Two-level stacked ensemble for maximum accuracy.

    Level 1: Multiple diverse base models
    Level 2: Meta-learner that combines base model predictions

    This is more powerful than simple averaging but requires more data
    to avoid overfitting.
    """

    def __init__(
        self,
        task: str = "classification",
        meta_learner: str = "logistic"
    ):
        self.task = task
        self.meta_learner_type = meta_learner
        self.base_models: Dict[str, Any] = {}
        self.meta_model = None
        self.feature_names = None
        self.is_trained = False

    def _create_base_models(self) -> Dict[str, Any]:
        """Create diverse base models."""
        models = {}

        # XGBoost with different configurations
        if self.task == "classification":
            models['xgb_deep'] = xgb.XGBClassifier(
                max_depth=6, learning_rate=0.05, n_estimators=300,
                random_state=42, n_jobs=-1, use_label_encoder=False
            )
            models['xgb_shallow'] = xgb.XGBClassifier(
                max_depth=3, learning_rate=0.02, n_estimators=800,
                random_state=43, n_jobs=-1, use_label_encoder=False
            )
        else:
            models['xgb_deep'] = xgb.XGBRegressor(
                max_depth=6, learning_rate=0.05, n_estimators=300,
                random_state=42, n_jobs=-1
            )
            models['xgb_shallow'] = xgb.XGBRegressor(
                max_depth=3, learning_rate=0.02, n_estimators=800,
                random_state=43, n_jobs=-1
            )

        # LightGBM variants
        if HAS_LIGHTGBM:
            if self.task == "classification":
                models['lgb'] = lgb.LGBMClassifier(
                    max_depth=4, learning_rate=0.03, n_estimators=500,
                    random_state=44, n_jobs=-1, verbose=-1
                )
            else:
                models['lgb'] = lgb.LGBMRegressor(
                    max_depth=4, learning_rate=0.03, n_estimators=500,
                    random_state=44, n_jobs=-1, verbose=-1
                )

        # Linear model
        if self.task == "classification":
            models['linear'] = LogisticRegression(C=0.1, max_iter=1000, random_state=45)
        else:
            models['linear'] = Ridge(alpha=1.0, random_state=45)

        return models

    def _create_meta_learner(self):
        """Create the meta-learner model."""
        if self.meta_learner_type == "logistic":
            if self.task == "classification":
                return LogisticRegression(C=1.0, max_iter=1000)
            else:
                return Ridge(alpha=0.1)
        elif self.meta_learner_type == "xgb":
            if self.task == "classification":
                return xgb.XGBClassifier(
                    max_depth=3, n_estimators=100, learning_rate=0.1,
                    use_label_encoder=False
                )
            else:
                return xgb.XGBRegressor(max_depth=3, n_estimators=100, learning_rate=0.1)
        else:
            raise ValueError(f"Unknown meta learner: {self.meta_learner_type}")

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        **kwargs
    ):
        """
        Train stacked ensemble using out-of-fold predictions.

        This prevents information leakage to the meta-learner.
        """
        from sklearn.model_selection import KFold

        self.feature_names = list(X_train.columns)
        self.base_models = self._create_base_models()

        # Generate out-of-fold predictions for meta-learner training
        n_folds = 5
        kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)

        oof_predictions = {name: np.zeros(len(X_train)) for name in self.base_models}

        for fold_idx, (train_idx, val_idx) in enumerate(kf.split(X_train)):
            X_fold_train = X_train.iloc[train_idx]
            y_fold_train = y_train.iloc[train_idx]
            X_fold_val = X_train.iloc[val_idx]

            for name, model in self.base_models.items():
                # Clone model for this fold
                model_clone = type(model)(**model.get_params())
                model_clone.fit(X_fold_train, y_fold_train)

                if self.task == "classification":
                    oof_predictions[name][val_idx] = model_clone.predict_proba(X_fold_val)[:, 1]
                else:
                    oof_predictions[name][val_idx] = model_clone.predict(X_fold_val)

        # Train base models on full training data
        for name, model in self.base_models.items():
            model.fit(X_train, y_train)

        # Create meta-features from OOF predictions
        meta_features = np.column_stack(list(oof_predictions.values()))

        # Train meta-learner
        self.meta_model = self._create_meta_learner()
        self.meta_model.fit(meta_features, y_train)

        self.is_trained = True

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Get stacked ensemble predictions."""
        if not self.is_trained:
            raise ValueError("Ensemble not trained")

        # Get base model predictions
        base_preds = []
        for name, model in self.base_models.items():
            if self.task == "classification":
                base_preds.append(model.predict_proba(X)[:, 1])
            else:
                base_preds.append(model.predict(X))

        # Stack into meta-features
        meta_features = np.column_stack(base_preds)

        # Get meta-learner prediction
        if self.task == "classification":
            return self.meta_model.predict_proba(meta_features)[:, 1]
        else:
            return self.meta_model.predict(meta_features)

    def save(self, path: str):
        """Save stacked ensemble."""
        save_dict = {
            'base_models': self.base_models,
            'meta_model': self.meta_model,
            'feature_names': self.feature_names,
            'task': self.task,
            'is_trained': self.is_trained
        }
        joblib.dump(save_dict, path)

    def load(self, path: str):
        """Load stacked ensemble."""
        save_dict = joblib.load(path)
        self.base_models = save_dict['base_models']
        self.meta_model = save_dict['meta_model']
        self.feature_names = save_dict.get('feature_names')
        self.task = save_dict.get('task', 'classification')
        self.is_trained = save_dict.get('is_trained', False)
