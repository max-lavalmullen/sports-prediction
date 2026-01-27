"""
Elo Rating System for Sports Prediction.

Elo ratings are a powerful baseline that often performs surprisingly well.
Many professional sports bettors use Elo as a core component of their models.

Key advantages:
- Simple and interpretable
- Naturally handles strength of schedule
- No overfitting to small samples
- Works well out-of-the-box with minimal tuning
- Provides calibrated win probabilities

This implementation includes:
- Sport-specific K-factors
- Home advantage adjustment
- Margin of victory incorporation
- Season reset/carryover
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json


class EloRating:
    """
    Elo rating system optimized for sports betting.

    The Elo system was originally designed for chess but adapts well to
    team sports. Each team has a rating that updates after each game
    based on the result vs expectation.
    """

    def __init__(
        self,
        k_factor: float = 20.0,
        home_advantage: float = 100.0,
        initial_rating: float = 1500.0,
        season_carryover: float = 0.75,
        use_margin: bool = True,
        margin_multiplier: float = 0.0075
    ):
        """
        Initialize Elo rating system.

        Args:
            k_factor: How much ratings change after each game (higher = more reactive)
            home_advantage: Elo points added for home team
            initial_rating: Starting rating for new teams
            season_carryover: How much of rating to carry over between seasons (0-1)
            use_margin: Whether to adjust updates based on margin of victory
            margin_multiplier: How much margin affects K-factor
        """
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.season_carryover = season_carryover
        self.use_margin = use_margin
        self.margin_multiplier = margin_multiplier

        self.ratings: Dict[str, float] = {}
        self.rating_history: List[Dict] = []

    def get_rating(self, team: str) -> float:
        """Get current rating for a team."""
        return self.ratings.get(team, self.initial_rating)

    def _expected_score(
        self,
        rating_a: float,
        rating_b: float,
        home_advantage: float = 0
    ) -> float:
        """
        Calculate expected probability of team A winning.

        Uses the standard Elo formula:
        E = 1 / (1 + 10^((Rb - Ra - HFA) / 400))
        """
        diff = rating_b - rating_a - home_advantage
        return 1 / (1 + 10 ** (diff / 400))

    def _margin_multiplier(self, margin: float, elo_diff: float) -> float:
        """
        Calculate multiplier based on margin of victory.

        Larger wins should result in larger rating changes, but with
        diminishing returns to prevent extreme swings.

        Uses FiveThirtyEight's formula for NFL/NBA.
        """
        if not self.use_margin:
            return 1.0

        # Prevent extreme multipliers
        margin = abs(margin)

        # Log-based diminishing returns
        # Autocorrelation adjustment: favorites that win big shouldn't
        # get as much credit as underdogs that win big
        if elo_diff > 0:  # Favorite won
            adjustment = 2.2 / ((elo_diff * 0.001) + 2.2)
        else:  # Underdog won
            adjustment = 1.0

        multiplier = np.log(margin + 1) * self.margin_multiplier * 100 * adjustment

        return max(0.5, min(multiplier + 1, 3.0))  # Clamp between 0.5x and 3x

    def update(
        self,
        home_team: str,
        away_team: str,
        home_score: int,
        away_score: int,
        date: Optional[datetime] = None
    ) -> Tuple[float, float]:
        """
        Update ratings after a game.

        Args:
            home_team: Home team identifier
            away_team: Away team identifier
            home_score: Home team score
            away_score: Away team score
            date: Game date (for history tracking)

        Returns:
            Tuple of (new_home_rating, new_away_rating)
        """
        # Get current ratings
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Calculate expected win probability for home team
        expected_home = self._expected_score(
            home_rating,
            away_rating,
            self.home_advantage
        )

        # Actual result (1 for home win, 0 for away win, 0.5 for tie)
        if home_score > away_score:
            actual_home = 1.0
        elif home_score < away_score:
            actual_home = 0.0
        else:
            actual_home = 0.5

        # Margin-adjusted K-factor
        margin = home_score - away_score
        elo_diff = home_rating + self.home_advantage - away_rating
        k_mult = self._margin_multiplier(margin, elo_diff)
        effective_k = self.k_factor * k_mult

        # Update ratings
        rating_change = effective_k * (actual_home - expected_home)
        new_home_rating = home_rating + rating_change
        new_away_rating = away_rating - rating_change

        self.ratings[home_team] = new_home_rating
        self.ratings[away_team] = new_away_rating

        # Track history
        if date:
            self.rating_history.append({
                'date': date,
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'home_rating_before': home_rating,
                'away_rating_before': away_rating,
                'home_rating_after': new_home_rating,
                'away_rating_after': new_away_rating,
                'expected_home_prob': expected_home,
                'actual_result': actual_home,
                'rating_change': rating_change
            })

        return new_home_rating, new_away_rating

    def predict_win_probability(
        self,
        home_team: str,
        away_team: str,
        neutral_site: bool = False
    ) -> float:
        """
        Predict probability of home team winning.

        Args:
            home_team: Home team identifier
            away_team: Away team identifier
            neutral_site: Whether game is at neutral venue

        Returns:
            Probability of home team winning (0-1)
        """
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        hfa = 0 if neutral_site else self.home_advantage

        return self._expected_score(home_rating, away_rating, hfa)

    def predict_spread(
        self,
        home_team: str,
        away_team: str,
        neutral_site: bool = False,
        points_per_elo: float = 0.04
    ) -> float:
        """
        Predict point spread (home team perspective).

        Negative = home team favored.

        Args:
            home_team: Home team identifier
            away_team: Away team identifier
            neutral_site: Whether at neutral venue
            points_per_elo: Conversion factor (sport-specific)

        Returns:
            Predicted spread (negative = home favored)
        """
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        hfa = 0 if neutral_site else self.home_advantage

        elo_diff = home_rating + hfa - away_rating
        spread = -elo_diff * points_per_elo

        return spread

    def new_season(self):
        """
        Apply season carryover to all ratings.

        Regresses ratings toward the mean to account for roster changes,
        player development, and other offseason factors.
        """
        for team in self.ratings:
            old_rating = self.ratings[team]
            new_rating = (
                self.season_carryover * old_rating +
                (1 - self.season_carryover) * self.initial_rating
            )
            self.ratings[team] = new_rating

    def process_season(
        self,
        games: pd.DataFrame,
        home_team_col: str = 'home_team',
        away_team_col: str = 'away_team',
        home_score_col: str = 'home_score',
        away_score_col: str = 'away_score',
        date_col: str = 'date'
    ) -> pd.DataFrame:
        """
        Process a full season of games and return predictions.

        Args:
            games: DataFrame with game data
            *_col: Column name mappings

        Returns:
            DataFrame with Elo predictions added
        """
        games = games.sort_values(date_col).copy()

        predictions = []
        for idx, row in games.iterrows():
            # Get pre-game prediction
            pred_prob = self.predict_win_probability(
                row[home_team_col],
                row[away_team_col]
            )
            pred_spread = self.predict_spread(
                row[home_team_col],
                row[away_team_col]
            )

            home_rating = self.get_rating(row[home_team_col])
            away_rating = self.get_rating(row[away_team_col])

            predictions.append({
                'elo_home_prob': pred_prob,
                'elo_spread': pred_spread,
                'elo_home_rating': home_rating,
                'elo_away_rating': away_rating,
                'elo_diff': home_rating - away_rating
            })

            # Update ratings with result
            self.update(
                row[home_team_col],
                row[away_team_col],
                row[home_score_col],
                row[away_score_col],
                row[date_col]
            )

        pred_df = pd.DataFrame(predictions, index=games.index)
        return pd.concat([games, pred_df], axis=1)

    def get_rankings(self) -> pd.DataFrame:
        """Get current team rankings."""
        rankings = pd.DataFrame([
            {'team': team, 'rating': rating}
            for team, rating in self.ratings.items()
        ])
        return rankings.sort_values('rating', ascending=False).reset_index(drop=True)

    def save(self, path: str):
        """Save ratings to file."""
        data = {
            'ratings': self.ratings,
            'params': {
                'k_factor': self.k_factor,
                'home_advantage': self.home_advantage,
                'initial_rating': self.initial_rating,
                'season_carryover': self.season_carryover,
                'use_margin': self.use_margin,
                'margin_multiplier': self.margin_multiplier
            },
            'history': self.rating_history[-1000:]  # Keep last 1000 games
        }
        with open(path, 'w') as f:
            json.dump(data, f, default=str)

    def load(self, path: str):
        """Load ratings from file."""
        with open(path, 'r') as f:
            data = json.load(f)

        self.ratings = data['ratings']
        params = data.get('params', {})
        self.k_factor = params.get('k_factor', self.k_factor)
        self.home_advantage = params.get('home_advantage', self.home_advantage)
        self.rating_history = data.get('history', [])


class SportEloConfig:
    """Pre-configured Elo settings for different sports."""

    @staticmethod
    def nba() -> EloRating:
        """NBA-optimized Elo settings."""
        return EloRating(
            k_factor=20.0,
            home_advantage=100.0,  # ~3.5 points
            initial_rating=1500.0,
            season_carryover=0.75,
            use_margin=True,
            margin_multiplier=0.0075
        )

    @staticmethod
    def nfl() -> EloRating:
        """NFL-optimized Elo settings."""
        return EloRating(
            k_factor=20.0,
            home_advantage=65.0,  # ~2.5 points
            initial_rating=1500.0,
            season_carryover=0.5,  # More regression due to short season
            use_margin=True,
            margin_multiplier=0.008
        )

    @staticmethod
    def mlb() -> EloRating:
        """MLB-optimized Elo settings."""
        return EloRating(
            k_factor=4.0,  # Lower due to high game volume
            home_advantage=24.0,  # ~54% home win rate
            initial_rating=1500.0,
            season_carryover=0.5,
            use_margin=False  # Runs don't translate as cleanly
        )

    @staticmethod
    def nhl() -> EloRating:
        """NHL-optimized Elo settings."""
        return EloRating(
            k_factor=8.0,
            home_advantage=50.0,  # ~54% home win rate
            initial_rating=1500.0,
            season_carryover=0.6,
            use_margin=True,
            margin_multiplier=0.01
        )

    @staticmethod
    def soccer() -> EloRating:
        """Soccer/Football-optimized Elo settings."""
        return EloRating(
            k_factor=32.0,  # Higher due to fewer games
            home_advantage=100.0,
            initial_rating=1500.0,
            season_carryover=0.8,
            use_margin=True,
            margin_multiplier=0.005
        )


class EloFeatureGenerator:
    """
    Generate Elo-based features for ML models.

    Elo features are excellent inputs to ML models because they:
    - Capture relative team strength
    - Are pre-normalized
    - Implicitly handle strength of schedule
    """

    def __init__(self, sport: str = 'nba'):
        """Initialize with sport-specific Elo."""
        sport_configs = {
            'nba': SportEloConfig.nba,
            'nfl': SportEloConfig.nfl,
            'mlb': SportEloConfig.mlb,
            'nhl': SportEloConfig.nhl,
            'soccer': SportEloConfig.soccer
        }

        if sport.lower() in sport_configs:
            self.elo = sport_configs[sport.lower()]()
        else:
            self.elo = EloRating()

    def generate_features(
        self,
        games: pd.DataFrame,
        home_team_col: str = 'home_team',
        away_team_col: str = 'away_team',
        home_score_col: str = 'home_score',
        away_score_col: str = 'away_score',
        date_col: str = 'date'
    ) -> pd.DataFrame:
        """
        Generate Elo features for games.

        Features generated:
        - elo_home_rating: Home team's Elo rating
        - elo_away_rating: Away team's Elo rating
        - elo_diff: Rating difference (home - away)
        - elo_home_prob: Win probability based on Elo
        - elo_spread: Predicted spread
        """
        result_df = self.elo.process_season(
            games,
            home_team_col,
            away_team_col,
            home_score_col,
            away_score_col,
            date_col
        )

        return result_df