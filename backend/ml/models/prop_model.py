"""
Player Prop Prediction Model.

Uses XGBoost Regression to predict player statistics (Points, Rebounds, Assists).
"""
import pandas as pd
import numpy as np
import joblib
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

from loguru import logger

class PlayerPropModel:
    """
    Regression model for player props.
    
    Attributes:
        stat_type: The statistic to predict (e.g., 'pts', 'reb', 'ast')
        model: The underlying XGBoost regressor
    """
    
    def __init__(self, stat_type: str = 'pts', model_dir: str = 'ml/saved_models/nba/props'):
        self.stat_type = stat_type
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model = XGBRegressor(
            n_estimators=500,
            learning_rate=0.05,
            max_depth=5,
            subsample=0.8,
            colsample_bytree=0.8,
            objective='reg:squarederror',
            n_jobs=-1,
            early_stopping_rounds=50
        )
        self.feature_names: List[str] = []
        
    def train(self, df: pd.DataFrame, feature_cols: List[str], target_col: str):
        """
        Train the model.
        
        Args:
            df: DataFrame containing features and target
            feature_cols: List of feature column names
            target_col: Name of the target column
        """
        self.feature_names = feature_cols
        
        X = df[feature_cols]
        y = df[target_col]
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Train
        logger.info(f"Training {self.stat_type} model with {len(X_train)} samples...")
        
        eval_set = [(X_train, y_train), (X_test, y_test)]
        self.model.fit(
            X_train, y_train,
            eval_set=eval_set,
            verbose=False
        )
        
        # Evaluate
        preds = self.model.predict(X_test)
        mae = mean_absolute_error(y_test, preds)
        r2 = r2_score(y_test, preds)
        
        logger.info(f"Model {self.stat_type} Results - MAE: {mae:.3f}, R2: {r2:.3f}")
        
        return {"mae": mae, "r2": r2}

    def predict(self, features_df: pd.DataFrame) -> np.ndarray:
        """Generate predictions."""
        if not self.feature_names:
            raise ValueError("Model not trained or loaded")
            
        # Ensure columns match
        for col in self.feature_names:
            if col not in features_df.columns:
                features_df[col] = 0
                
        return self.model.predict(features_df[self.feature_names])

    def save(self):
        """Save model to disk."""
        path = self.model_dir / f"prop_model_{self.stat_type}.joblib"
        joblib.dump({
            'model': self.model,
            'feature_names': self.feature_names,
            'stat_type': self.stat_type
        }, path)
        logger.info(f"Saved model to {path}")

    def load(self):
        """Load model from disk."""
        path = self.model_dir / f"prop_model_{self.stat_type}.joblib"
        if not path.exists():
            logger.warning(f"No model found at {path}")
            return False
            
        data = joblib.load(path)
        self.model = data['model']
        self.feature_names = data['feature_names']
        self.stat_type = data['stat_type']
        logger.info(f"Loaded model from {path}")
        return True
