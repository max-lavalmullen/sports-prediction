"""
Same-Game Parlay (SGP) Service.
Calculates true probabilities for correlated outcomes and suggests high-EV parlays.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from loguru import logger

from app.core.database import get_db_connection
from ml.simulation.monte_carlo import SGPMonteCarlo


class SGPService:
    """
    Service for analyzing Same-Game Parlays.
    """

    def __init__(self):
        self.simulator = SGPMonteCarlo(num_simulations=10000)
        self._correlation_cache = {}

    def get_correlation(self, sport: str, leg1_type: str, leg2_type: str) -> float:
        """Get correlation coefficient between two types of bets."""
        # Check cache
        cache_key = f"{sport}:{leg1_type}:{leg2_type}"
        rev_cache_key = f"{sport}:{leg2_type}:{leg1_type}"
        
        if cache_key in self._correlation_cache:
            return self._correlation_cache[cache_key]
        if rev_cache_key in self._correlation_cache:
            return self._correlation_cache[rev_cache_key]

        # Load from DB
        conn = get_db_connection()
        if not conn:
            return self._get_default_correlation(sport, leg1_type, leg2_type)

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT correlation_coefficient 
                    FROM sgp_correlations 
                    WHERE sport = %s 
                    AND ((leg1_type = %s AND leg2_type = %s) 
                         OR (leg1_type = %s AND leg2_type = %s))
                    """,
                    (sport, leg1_type, leg2_type, leg2_type, leg1_type)
                )
                row = cur.fetchone()
                if row:
                    corr = row[0]
                    self._correlation_cache[cache_key] = corr
                    return corr
        except Exception as e:
            logger.error(f"Error fetching correlation: {e}")
        finally:
            conn.close()

        # Default if not in DB
        return self._get_default_correlation(sport, leg1_type, leg2_type)

    def _get_default_correlation(self, sport: str, leg1_type: str, leg2_type: str) -> float:
        """Rule-based default correlations when data is missing."""
        # NFL Examples
        if sport == "nfl":
            # QB Over Yards + Team Wins (Positive)
            if "pass_yds" in leg1_type and "win" in leg2_type: return 0.35
            # RB Over Yards + Team Wins (Positive)
            if "rush_yds" in leg1_type and "win" in leg2_type: return 0.25
            # Over Total + Favorite Wins (Slightly positive)
            if "total_over" in leg1_type and "fav_win" in leg2_type: return 0.15
            # QB Over Yards + WR Over Yards (High positive)
            if "pass_yds" in leg1_type and "rec_yds" in leg2_type: return 0.6
            
        # NBA Examples
        if sport == "nba":
            # Player Points + Team Wins
            if "points" in leg1_type and "win" in leg2_type: return 0.3
            # High Total + Over Points for star
            if "total_over" in leg1_type and "points" in leg2_type: return 0.2
            # Assists + Points for teammates (Positive)
            if "assists" in leg1_type and "points" in leg2_type: return 0.25

        return 0.0

    def calculate_parlay_probability(
        self, 
        sport: str, 
        legs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate true probability for a list of parlay legs.
        
        Each leg should have:
        - type: str (e.g. 'nba_player_points_over')
        - prob: float (individual win probability from model)
        """
        n_legs = len(legs)
        if n_legs == 0:
            return {"true_prob": 0, "edge": 0}

        # 1. Build correlation matrix
        corr_matrix = np.eye(n_legs)
        for i in range(n_legs):
            for j in range(i + 1, n_legs):
                corr = self.get_correlation(sport, legs[i]['type'], legs[j]['type'])
                corr_matrix[i, j] = corr
                corr_matrix[j, i] = corr

        # 2. Ensure matrix is positive semi-definite (for multivariate_normal)
        # Sometime correlations from different sources can lead to non-PSD matrices
        # We can use a simple adjustment if needed
        eigvals, eigvecs = np.linalg.eigh(corr_matrix)
        eigvals = np.maximum(eigvals, 1e-8)
        corr_matrix = eigvecs @ np.diag(eigvals) @ eigvecs.T
        
        # Rescale to ensure diagonals are 1 (re-normalization)
        d = np.sqrt(np.diag(corr_matrix))
        corr_matrix = corr_matrix / np.outer(d, d)

        # 3. Simulate
        probs = [leg['prob'] for leg in legs]
        true_prob = self.simulator.simulate_parlay(probs, corr_matrix)

        return {
            "true_prob": true_prob,
            "legs": n_legs,
            "individual_probs": probs,
            "correlation_matrix": corr_matrix.tolist()
        }

    def suggest_sgp(
        self, 
        sport: str, 
        game_id: str, 
        available_legs: List[Dict[str, Any]], 
        max_legs: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find high-EV SGP combinations.
        
        Simple version: Look for pairs/triplets with high positive correlation
        and high individual probabilities.
        """
        if not available_legs:
            return []

        suggestions = []
        
        # Sort legs by probability
        sorted_legs = sorted(available_legs, key=lambda x: x.get('prob', 0), reverse=True)
        
        # Try finding pairs with high correlation
        for i in range(min(len(sorted_legs), 10)):
            for j in range(i + 1, min(len(sorted_legs), 10)):
                leg1 = sorted_legs[i]
                leg2 = sorted_legs[j]
                
                corr = self.get_correlation(sport, leg1['type'], leg2['type'])
                
                if corr > 0.15: # Significant positive correlation
                    # Calculate joint prob
                    result = self.calculate_parlay_probability(sport, [leg1, leg2])
                    
                    suggestions.append({
                        "game_id": game_id,
                        "legs": [leg1, leg2],
                        "true_prob": result["true_prob"],
                        "correlation": corr,
                        "combined_description": f"{leg1.get('description', leg1['type'])} + {leg2.get('description', leg2['type'])}"
                    })

        # Sort suggestions by probability (as proxy for EV since we don't have market odds here)
        suggestions.sort(key=lambda x: x['true_prob'], reverse=True)
        
        return suggestions[:5]


# Singleton instance
sgp_service = SGPService()
