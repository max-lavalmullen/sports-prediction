"""
Monte Carlo Simulation for Correlated Outcomes.
Used for SGP (Same Game Parlay) true probability estimation.
"""

import numpy as np
from typing import List, Dict, Any, Tuple
from scipy.stats import norm, multivariate_normal


class SGPMonteCarlo:
    """
    Monte Carlo simulator for correlated betting outcomes.
    
    Uses a Gaussian copula to model dependencies between different betting legs.
    """

    def __init__(self, num_simulations: int = 10000):
        self.num_simulations = num_simulations

    def simulate_parlay(
        self, 
        leg_probs: List[float], 
        correlation_matrix: np.ndarray
    ) -> float:
        """
        Estimate the true probability of a parlay hitting.
        
        Args:
            leg_probs: List of individual probabilities for each leg.
            correlation_matrix: NxN matrix of correlations between legs.
            
        Returns:
            Estimated joint probability of all legs hitting.
        """
        n_legs = len(leg_probs)
        if n_legs == 0:
            return 0.0
        if n_legs == 1:
            return leg_probs[0]

        # 1. Generate correlated normal samples
        # Mean 0, Covariance = Correlation matrix (since variances are 1)
        mean = np.zeros(n_legs)
        samples = multivariate_normal.rvs(
            mean=mean, 
            cov=correlation_matrix, 
            size=self.num_simulations
        )
        
        # 2. Convert to uniform distributions [0, 1] using CDF
        uniform_samples = norm.cdf(samples)
        
        # 3. Check which simulations resulted in all legs hitting
        # A leg hits if its uniform sample is less than its individual probability
        # (Assuming prob is P(outcome=True))
        hits = np.all(uniform_samples < np.array(leg_probs), axis=1)
        
        # 4. Return probability (fraction of simulations that hit)
        joint_prob = np.sum(hits) / self.num_simulations
        
        return float(joint_prob)

    def calculate_ev(
        self, 
        true_prob: float, 
        market_odds_decimal: float
    ) -> Dict[str, float]:
        """Calculate Expected Value and Edge."""
        ev = (true_prob * market_odds_decimal) - 1
        implied_prob = 1 / market_odds_decimal
        edge = true_prob - implied_prob
        
        return {
            "ev": ev,
            "edge": edge,
            "true_prob": true_prob,
            "implied_prob": implied_prob
        }
