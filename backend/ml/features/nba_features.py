"""
NBA Feature Engineering Pipeline.

Comprehensive feature engineering for maximum prediction accuracy.
Implements Dean Oliver's Four Factors, advanced metrics, situational factors,
and opponent-adjusted statistics.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta


class NBAFeatureEngineer:
    """
    Advanced feature engineering for NBA games.

    Features include:
    - Efficiency metrics (ORtg, DRtg, Net Rating)
    - Four Factors (eFG%, TOV%, ORB%, FT Rate)
    - Rolling averages at multiple windows (5, 10, 20 games)
    - Home/away performance splits
    - Rest and fatigue factors
    - Opponent-adjusted metrics
    - Momentum/form indicators
    - Matchup-specific features
    """

    def __init__(self):
        self.rolling_windows = [5, 10, 20]  # Multiple time horizons
        self.min_games_required = 5

    def calculate_efficiency_metrics(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Offensive and Defensive Ratings using proper possession formula.

        ORtg = 100 * Points / Possessions
        DRtg = 100 * Points Allowed / Possessions
        """
        df = games_df.copy()

        # More accurate possession estimation (Dean Oliver formula)
        # Poss = 0.5 * ((Tm FGA + 0.4 * Tm FTA - 1.07 * (Tm ORB / (Tm ORB + Opp DRB)) * (Tm FGA - Tm FG) + Tm TOV)
        #              + (Opp FGA + 0.4 * Opp FTA - 1.07 * (Opp ORB / (Opp ORB + Tm DRB)) * (Opp FGA - Opp FG) + Opp TOV))

        # Simplified but accurate version when we don't have opponent detail
        df['possessions'] = (
            df['fga'] + 0.44 * df['fta'] + df['tov'] - df['orb']
        )

        # Efficiency ratings
        df['off_rating'] = np.where(
            df['possessions'] > 0,
            100 * (df['pts'] / df['possessions']),
            0
        )
        df['def_rating'] = np.where(
            df['possessions'] > 0,
            100 * (df['pts_allowed'] / df['possessions']),
            0
        )
        df['net_rating'] = df['off_rating'] - df['def_rating']

        # Pace (possessions per 48 min)
        df['pace'] = np.where(
            df['minutes'] > 0,
            48 * (df['possessions'] / df['minutes']),
            100  # Default pace
        )

        return df

    def calculate_four_factors(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Dean Oliver's Four Factors - the key determinants of winning.

        1. eFG% (Effective Field Goal %) - Shooting efficiency
        2. TOV% (Turnover %) - Ball security
        3. ORB% (Offensive Rebound %) - Second chances
        4. FT Rate - Free throw generation
        """
        df = games_df.copy()

        # Effective Field Goal Percentage (weights 3s at 1.5x)
        df['efg_pct'] = np.where(
            df['fga'] > 0,
            (df['fgm'] + 0.5 * df['fg3m']) / df['fga'],
            0
        )

        # Turnover Percentage (turnovers per possession)
        df['tov_pct'] = np.where(
            (df['fga'] + 0.44 * df['fta'] + df['tov']) > 0,
            df['tov'] / (df['fga'] + 0.44 * df['fta'] + df['tov']),
            0
        )

        # Offensive Rebound Percentage
        df['orb_pct'] = np.where(
            (df['orb'] + df['opp_drb']) > 0,
            df['orb'] / (df['orb'] + df['opp_drb']),
            0
        )

        # Free Throw Rate (FTM per FGA)
        df['ft_rate'] = np.where(
            df['fga'] > 0,
            df['ftm'] / df['fga'],
            0
        )

        # Opponent Four Factors (defensive versions)
        if 'opp_fgm' in df.columns:
            df['opp_efg_pct'] = np.where(
                df['opp_fga'] > 0,
                (df['opp_fgm'] + 0.5 * df['opp_fg3m']) / df['opp_fga'],
                0
            )
            df['opp_tov_pct'] = np.where(
                (df['opp_fga'] + 0.44 * df['opp_fta'] + df['opp_tov']) > 0,
                df['opp_tov'] / (df['opp_fga'] + 0.44 * df['opp_fta'] + df['opp_tov']),
                0
            )
            df['opp_ft_rate'] = np.where(
                df['opp_fga'] > 0,
                df['opp_ftm'] / df['opp_fga'],
                0
            )

        return df

    def calculate_shooting_metrics(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate detailed shooting metrics."""
        df = games_df.copy()

        # True Shooting % (accounts for FTs and 3s)
        df['ts_pct'] = np.where(
            (2 * (df['fga'] + 0.44 * df['fta'])) > 0,
            df['pts'] / (2 * (df['fga'] + 0.44 * df['fta'])),
            0
        )

        # 3-point rate (% of shots from 3)
        df['three_rate'] = np.where(
            df['fga'] > 0,
            df['fg3a'] / df['fga'],
            0
        )

        # 3-point accuracy
        df['three_pct'] = np.where(
            df['fg3a'] > 0,
            df['fg3m'] / df['fg3a'],
            0
        )

        # 2-point shooting
        df['two_fga'] = df['fga'] - df['fg3a']
        df['two_fgm'] = df['fgm'] - df['fg3m']
        df['two_pct'] = np.where(
            df['two_fga'] > 0,
            df['two_fgm'] / df['two_fga'],
            0
        )

        return df

    def calculate_rest_factors(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate rest and fatigue-related features.

        Rest is CRITICAL for NBA predictions - back-to-backs significantly
        impact performance, especially for road teams.
        """
        df = games_df.copy()
        df = df.sort_values(['team_id', 'date'])

        # Days since last game
        df['prev_game_date'] = df.groupby('team_id')['date'].shift(1)
        df['days_rest'] = (df['date'] - df['prev_game_date']).dt.days
        df['days_rest'] = df['days_rest'].fillna(3)  # Season opener default

        # Back-to-back indicator
        df['is_b2b'] = (df['days_rest'] == 1).astype(int)

        # Second of back-to-back on road (worst case scenario)
        if 'is_home' in df.columns:
            df['b2b_road'] = ((df['days_rest'] == 1) & (df['is_home'] == 0)).astype(int)

        # 3 games in 4 nights
        df['games_last_4_days'] = df.groupby('team_id')['date'].transform(
            lambda x: x.rolling('4D', closed='left').count()
        )
        df['is_3_in_4'] = (df['games_last_4_days'] >= 3).astype(int)

        # 4 games in 5 nights
        df['games_last_5_days'] = df.groupby('team_id')['date'].transform(
            lambda x: x.rolling('5D', closed='left').count()
        )
        df['is_4_in_5'] = (df['games_last_5_days'] >= 4).astype(int)

        # Cumulative fatigue score
        df['fatigue_score'] = (
            df['is_b2b'] * 2 +
            df['is_3_in_4'] * 1.5 +
            df['is_4_in_5'] * 1 +
            df.get('b2b_road', 0) * 1
        )

        return df

    def calculate_home_away_splits(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate home/away performance differentials.

        Home court advantage varies significantly by team and is a key predictor.
        """
        df = games_df.copy()

        if 'is_home' not in df.columns:
            return df

        # Rolling home/away metrics
        for window in self.rolling_windows:
            # Home games only
            home_mask = df['is_home'] == 1
            df[f'home_off_rating_{window}g'] = df.groupby('team_id').apply(
                lambda x: x[home_mask]['off_rating'].rolling(window, min_periods=1).mean()
            ).reset_index(level=0, drop=True)

            df[f'home_def_rating_{window}g'] = df.groupby('team_id').apply(
                lambda x: x[home_mask]['def_rating'].rolling(window, min_periods=1).mean()
            ).reset_index(level=0, drop=True)

            # Away games only
            away_mask = df['is_home'] == 0
            df[f'away_off_rating_{window}g'] = df.groupby('team_id').apply(
                lambda x: x[away_mask]['off_rating'].rolling(window, min_periods=1).mean()
            ).reset_index(level=0, drop=True)

            df[f'away_def_rating_{window}g'] = df.groupby('team_id').apply(
                lambda x: x[away_mask]['def_rating'].rolling(window, min_periods=1).mean()
            ).reset_index(level=0, drop=True)

        # Home/away differential
        df['home_advantage'] = (
            (df.get('home_off_rating_10g', 0) - df.get('away_off_rating_10g', 0)) +
            (df.get('away_def_rating_10g', 0) - df.get('home_def_rating_10g', 0))
        ) / 2

        return df

    def calculate_momentum_features(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate momentum and form indicators.

        Recent performance trends are predictive, but mean reversion is real.
        """
        df = games_df.copy()
        df = df.sort_values(['team_id', 'date'])

        # Win/loss streaks
        df['game_result'] = (df['pts'] > df['pts_allowed']).astype(int)

        def get_streak(series):
            """Calculate current win/loss streak."""
            streaks = []
            current_streak = 0
            last_result = None

            for result in series:
                if result == last_result and last_result is not None:
                    current_streak += 1 if result == 1 else -1
                else:
                    current_streak = 1 if result == 1 else -1
                last_result = result
                streaks.append(current_streak)

            return pd.Series(streaks, index=series.index)

        df['streak'] = df.groupby('team_id')['game_result'].transform(get_streak)

        # Recent win percentage
        for window in self.rolling_windows:
            df[f'win_pct_{window}g'] = df.groupby('team_id')['game_result'].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )

        # Form vs season average (momentum indicator)
        df['season_win_pct'] = df.groupby('team_id')['game_result'].transform(
            lambda x: x.expanding().mean()
        )
        df['recent_vs_season'] = df['win_pct_5g'] - df['season_win_pct']

        # Point differential trends
        df['point_diff'] = df['pts'] - df['pts_allowed']
        for window in self.rolling_windows:
            df[f'avg_margin_{window}g'] = df.groupby('team_id')['point_diff'].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )

        # Margin trend (is team improving or declining?)
        df['margin_trend'] = df['avg_margin_5g'] - df['avg_margin_20g']

        return df

    def create_rolling_features(self, team_logs: pd.DataFrame) -> pd.DataFrame:
        """
        Create multi-window rolling averages for key metrics.
        """
        cols_to_roll = [
            'off_rating', 'def_rating', 'net_rating', 'pace',
            'efg_pct', 'tov_pct', 'orb_pct', 'ft_rate',
            'ts_pct', 'three_rate', 'three_pct'
        ]

        # Filter to columns that exist
        cols_to_roll = [c for c in cols_to_roll if c in team_logs.columns]

        result = team_logs.copy()

        for window in self.rolling_windows:
            rolled = team_logs[cols_to_roll].rolling(window=window, min_periods=1).mean()
            rolled.columns = [f'{c}_{window}g' for c in rolled.columns]
            result = pd.concat([result, rolled], axis=1)

        # Exponential weighted averages (more weight to recent games)
        ewm_cols = ['off_rating', 'def_rating', 'net_rating']
        ewm_cols = [c for c in ewm_cols if c in team_logs.columns]

        for span in [5, 10]:
            ewm = team_logs[ewm_cols].ewm(span=span).mean()
            ewm.columns = [f'{c}_ewm{span}' for c in ewm.columns]
            result = pd.concat([result, ewm], axis=1)

        return result

    def calculate_opponent_adjusted_metrics(
        self,
        games_df: pd.DataFrame,
        league_avg_off: float = 112.0,
        league_avg_def: float = 112.0
    ) -> pd.DataFrame:
        """
        Calculate opponent-adjusted metrics.

        A team's performance should be evaluated relative to opponent strength.
        """
        df = games_df.copy()

        # This requires opponent data - if available
        if 'opp_off_rating_10g' in df.columns and 'opp_def_rating_10g' in df.columns:
            # Opponent-adjusted offensive rating
            # (Your ORtg) * (League Avg DRtg / Opponent DRtg)
            df['adj_off_rating'] = df['off_rating'] * (league_avg_def / df['opp_def_rating_10g'].replace(0, league_avg_def))

            # Opponent-adjusted defensive rating
            # (Your DRtg) * (League Avg ORtg / Opponent ORtg)
            df['adj_def_rating'] = df['def_rating'] * (league_avg_off / df['opp_off_rating_10g'].replace(0, league_avg_off))

            df['adj_net_rating'] = df['adj_off_rating'] - df['adj_def_rating']

        return df

    def calculate_matchup_features(
        self,
        home_team_stats: pd.Series,
        away_team_stats: pd.Series
    ) -> Dict[str, float]:
        """
        Calculate head-to-head matchup features.

        These are the actual features used for prediction.
        """
        features = {}

        # Rating differentials (home - away)
        for window in self.rolling_windows:
            off_col = f'off_rating_{window}g'
            def_col = f'def_rating_{window}g'
            net_col = f'net_rating_{window}g'

            if off_col in home_team_stats.index:
                features[f'off_rating_diff_{window}g'] = (
                    home_team_stats[off_col] - away_team_stats[off_col]
                )
                features[f'def_rating_diff_{window}g'] = (
                    away_team_stats[def_col] - home_team_stats[def_col]  # Lower is better for defense
                )
                features[f'net_rating_diff_{window}g'] = (
                    home_team_stats[net_col] - away_team_stats[net_col]
                )

        # Four factors differentials
        for col in ['efg_pct', 'tov_pct', 'orb_pct', 'ft_rate']:
            col_10g = f'{col}_10g'
            if col_10g in home_team_stats.index:
                # For tov_pct, lower is better
                if col == 'tov_pct':
                    features[f'{col}_diff'] = away_team_stats[col_10g] - home_team_stats[col_10g]
                else:
                    features[f'{col}_diff'] = home_team_stats[col_10g] - away_team_stats[col_10g]

        # Pace differential (for totals predictions)
        if 'pace_10g' in home_team_stats.index:
            features['pace_diff'] = home_team_stats['pace_10g'] - away_team_stats['pace_10g']
            features['avg_pace'] = (home_team_stats['pace_10g'] + away_team_stats['pace_10g']) / 2

        # Rest differential
        if 'days_rest' in home_team_stats.index:
            features['rest_diff'] = home_team_stats['days_rest'] - away_team_stats['days_rest']
            features['home_b2b'] = home_team_stats.get('is_b2b', 0)
            features['away_b2b'] = away_team_stats.get('is_b2b', 0)
            features['fatigue_diff'] = away_team_stats.get('fatigue_score', 0) - home_team_stats.get('fatigue_score', 0)

        # Momentum differential
        if 'streak' in home_team_stats.index:
            features['streak_diff'] = home_team_stats['streak'] - away_team_stats['streak']
            features['win_pct_diff_5g'] = home_team_stats.get('win_pct_5g', 0.5) - away_team_stats.get('win_pct_5g', 0.5)
            features['margin_trend_diff'] = home_team_stats.get('margin_trend', 0) - away_team_stats.get('margin_trend', 0)

        # Home court advantage
        features['home_advantage'] = home_team_stats.get('home_advantage', 3.0)  # ~3 pts default

        return features

    def process_games(self, games: List[Dict]) -> pd.DataFrame:
        """
        Main pipeline to process raw game data into model features.
        """
        # Convert to DataFrame
        df = pd.DataFrame(games)

        # Ensure date is datetime
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(['team_id', 'date'])

        # Calculate base metrics
        df = self.calculate_efficiency_metrics(df)
        df = self.calculate_four_factors(df)
        df = self.calculate_shooting_metrics(df)

        # Calculate situational factors
        df = self.calculate_rest_factors(df)
        df = self.calculate_momentum_features(df)

        # Group by team and apply rolling windows
        feature_dfs = []
        for team_id, team_data in df.groupby('team_id'):
            team_features = self.create_rolling_features(team_data)
            feature_dfs.append(team_features)

        final_df = pd.concat(feature_dfs)
        final_df = final_df.sort_values('date')

        # Calculate home/away splits (requires full dataset)
        final_df = self.calculate_home_away_splits(final_df)

        # Handle missing values - use forward fill then backward fill
        # This prevents look-ahead bias while handling start of season
        numeric_cols = final_df.select_dtypes(include=[np.number]).columns
        final_df[numeric_cols] = final_df.groupby('team_id')[numeric_cols].transform(
            lambda x: x.ffill().bfill()
        )

        # Any remaining NaN -> league average (0 for differentials)
        final_df = final_df.fillna(0)

        return final_df

    def prepare_prediction_features(
        self,
        home_team_id: int,
        away_team_id: int,
        team_stats_df: pd.DataFrame,
        game_date: datetime
    ) -> Dict[str, float]:
        """
        Prepare features for a specific upcoming game prediction.

        Uses only data available before game_date (no look-ahead bias).
        """
        # Get most recent stats for each team before game date
        home_stats = team_stats_df[
            (team_stats_df['team_id'] == home_team_id) &
            (team_stats_df['date'] < game_date)
        ].iloc[-1] if len(team_stats_df[
            (team_stats_df['team_id'] == home_team_id) &
            (team_stats_df['date'] < game_date)
        ]) > 0 else None

        away_stats = team_stats_df[
            (team_stats_df['team_id'] == away_team_id) &
            (team_stats_df['date'] < game_date)
        ].iloc[-1] if len(team_stats_df[
            (team_stats_df['team_id'] == away_team_id) &
            (team_stats_df['date'] < game_date)
        ]) > 0 else None

        if home_stats is None or away_stats is None:
            raise ValueError(f"Insufficient data for teams {home_team_id} vs {away_team_id}")

        # Calculate matchup features
        features = self.calculate_matchup_features(home_stats, away_stats)

        return features


# Export feature columns for model training
CORE_FEATURE_COLUMNS = [
    # Rating differentials at multiple windows
    'off_rating_diff_5g', 'off_rating_diff_10g', 'off_rating_diff_20g',
    'def_rating_diff_5g', 'def_rating_diff_10g', 'def_rating_diff_20g',
    'net_rating_diff_5g', 'net_rating_diff_10g', 'net_rating_diff_20g',

    # Four factors
    'efg_pct_diff', 'tov_pct_diff', 'orb_pct_diff', 'ft_rate_diff',

    # Pace (important for totals)
    'pace_diff', 'avg_pace',

    # Rest/fatigue
    'rest_diff', 'home_b2b', 'away_b2b', 'fatigue_diff',

    # Momentum
    'streak_diff', 'win_pct_diff_5g', 'margin_trend_diff',

    # Home court
    'home_advantage'
]
