"""
Base Model Interface.
"""
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from typing import Dict, Any

class BaseModel(ABC):
    """Abstract base class for all sports prediction models."""

    @abstractmethod
    def train(self, X_train: pd.DataFrame, y_train: pd.Series, **kwargs):
        """Train the model."""
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions."""
        pass

    @abstractmethod
    def save(self, path: str):
        """Save model artifacts."""
        pass

    @abstractmethod
    def load(self, path: str):
        """Load model artifacts."""
        pass
