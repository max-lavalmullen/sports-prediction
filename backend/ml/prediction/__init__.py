"""
Prediction module for sports betting.

Provides unified prediction services across all sports.
"""

from .prediction_service import (
    PredictionService,
    Prediction,
    prediction_service,
    get_predictions,
    get_value_bets,
)

__all__ = [
    "PredictionService",
    "Prediction",
    "prediction_service",
    "get_predictions",
    "get_value_bets",
]
