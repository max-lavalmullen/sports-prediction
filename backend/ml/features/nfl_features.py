"""
NFL Feature Engineering Pipeline.

Comprehensive feature engineering for NFL game predictions using
EPA-based analytics, success rate metrics, and situational factors.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class NFLFeatureEngineer:
    """
    Advanced feature engineering for NFL games.

    Features include:
    - EPA (Expected Points Added) metrics
    - Success rate by play type
    - DVOA-style opponent adjustments
    - Rest and schedule factors
    - Home/away splits
    - Weather impacts
    - Turnover differential
    - Red zone efficiency
    """

    def __init__(self):
        self.rolling_windows = [3, 5, 10]  # Fewer games in NFL season
        self.min_games_required = 3

    def calculate_epa_metrics(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate EPA-based efficiency metrics.

        EPA (Expected Points Added) is the gold standard for NFL analytics.
        """
        df = games_df.copy()

        # EPA per play (if available)
        if 'total_plays' in df.columns and 'total_epa' in df.columns:
            df['epa_per_play'] = np.where(
                df['total_plays'] > 0,
                df['total_epa'] / df['total_plays'],
                0
            )
        else:
            # Calculate approximate EPA from score if raw EPA not available
            df['epa_per_play'] = 0

        # Pass EPA
        if 'pass_epa' in df.columns:
            df['pass_epa_per_play'] = np.where(
                df['pass_plays'] > 0,
                df['pass_epa'] / df['pass_plays'],
                0
            )

        # Rush EPA
        if 'rush_epa' in df.columns:
            df['rush_epa_per_play'] = np.where(
                df['rush_plays'] > 0,
                df['rush_epa'] / df['rush_plays'],
                0
            )

        # Defensive EPA (opponent's EPA against us)
        if 'opp_total_epa' in df.columns:
            df['def_epa_per_play'] = np.where(
                df['opp_total_plays'] > 0,
                df['opp_total_epa'] / df['opp_total_plays'],
                0
            )

        return df

    def calculate_success_rate(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate success rate metrics.

        A play is "successful" if it gains:
        - 40% of yards to go on 1st down
        - 60% of yards to go on 2nd down
        - 100% of yards to go on 3rd/4th down
        """
        df = games_df.copy()

        # Overall success rate
        if 'successful_plays' in df.columns:
            df['success_rate'] = np.where(
                df['total_plays'] > 0,
                df['successful_plays'] / df['total_plays'],
                0
            )

        # Pass success rate
        if 'pass_success' in df.columns:
            df['pass_success_rate'] = np.where(
                df['pass_plays'] > 0,
                df['pass_success'] / df['pass_plays'],
                0
            )

        # Rush success rate
        if 'rush_success' in df.columns:
            df['rush_success_rate'] = np.where(
                df['rush_plays'] > 0,
                df['rush_success'] / df['rush_plays'],
                0
            )

        return df

    def calculate_scoring_metrics(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate scoring efficiency metrics."""
        df = games_df.copy()

        # Points per drive
        if 'drives' in df.columns:
            df['pts_per_drive'] = np.where(
                df['drives'] > 0,
                df['pts'] / df['drives'],
                0
            )

        # Red zone efficiency
        if 'red_zone_attempts' in df.columns and 'red_zone_scores' in df.columns:
            df['red_zone_pct'] = np.where(
                df['red_zone_attempts'] > 0,
                df['red_zone_scores'] / df['red_zone_attempts'],
                0
            )

        # Third down efficiency
        if 'third_down_attempts' in df.columns and 'third_down_conversions' in df.columns:
            df['third_down_pct'] = np.where(
                df['third_down_attempts'] > 0,
                df['third_down_conversions'] / df['third_down_attempts'],
                0
            )

        return df

    def calculate_turnover_metrics(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate turnover-related metrics."""
        df = games_df.copy()

        # Turnover differential
        interceptions = df['interceptions'] if 'interceptions' in df.columns else 0
        fumbles_lost = df['fumbles_lost'] if 'fumbles_lost' in df.columns else 0
        opp_interceptions = df['opp_interceptions'] if 'opp_interceptions' in df.columns else 0
        opp_fumbles = df['opp_fumbles_lost'] if 'opp_fumbles_lost' in df.columns else 0

        turnovers_lost = interceptions + fumbles_lost
        turnovers_gained = opp_interceptions + opp_fumbles
        df['turnover_diff'] = turnovers_gained - turnovers_lost

        # Turnover-worthy plays (interceptions + fumbles lost)
        df['turnovers'] = turnovers_lost

        # Giveaway rate
        if 'total_plays' in df.columns:
            df['turnover_rate'] = np.where(
                df['total_plays'] > 0,
                turnovers_lost / df['total_plays'],
                0
            )

        return df

    def calculate_rest_factors(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate rest and schedule-related factors.

        Short weeks (Thursday games) significantly impact NFL performance.
        """
        df = games_df.copy()
        df = df.sort_values(['team', 'week'])

        # Days rest (default 7 for typical Sunday-Sunday)
        df['prev_game_date'] = df.groupby('team')['date'].shift(1)
        df['days_rest'] = (pd.to_datetime(df['date']) - pd.to_datetime(df['prev_game_date'])).dt.days
        df['days_rest'] = df['days_rest'].fillna(10)  # Week 1 / bye week

        # Short week (Thursday game after Sunday)
        df['short_week'] = (df['days_rest'] <= 4).astype(int)

        # Long rest (after bye week)
        df['long_rest'] = (df['days_rest'] >= 10).astype(int)

        # Coming off bye
        df['post_bye'] = (df['days_rest'] >= 13).astype(int)

        # Monday night game into short week (worst case)
        df['mnf_to_thursday'] = (
            (df['days_rest'] <= 3) &
            (df.groupby('team')['date'].shift(1).dt.dayofweek == 0)  # Monday
        ).astype(int)

        return df

    def calculate_home_away_splits(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate home/away performance differentials."""
        df = games_df.copy()

        if 'is_home' not in df.columns:
            # Infer from game data
            if 'home_team' in df.columns:
                df['is_home'] = (df['home_team'] == df['team']).astype(int)
            else:
                df['is_home'] = 0

        # Rolling metrics for home/away
        for window in self.rolling_windows:
            # Home performance
            df[f'home_epa_{window}g'] = df.groupby('team').apply(
                lambda x: x[x['is_home'] == 1]['epa_per_play'].rolling(window, min_periods=1).mean()
            ).reset_index(level=0, drop=True) if 'epa_per_play' in df.columns else 0

            df[f'away_epa_{window}g'] = df.groupby('team').apply(
                lambda x: x[x['is_home'] == 0]['epa_per_play'].rolling(window, min_periods=1).mean()
            ).reset_index(level=0, drop=True) if 'epa_per_play' in df.columns else 0

        # Home field advantage (NFL average is ~2.5 points)
        home_epa_col = f'home_epa_{self.rolling_windows[1]}g'
        away_epa_col = f'away_epa_{self.rolling_windows[1]}g'
        home_epa = df[home_epa_col] if home_epa_col in df.columns else 0
        away_epa = df[away_epa_col] if away_epa_col in df.columns else 0
        df['home_advantage'] = home_epa - away_epa

        return df

    def calculate_weather_factors(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate weather-related factors.

        Weather significantly impacts NFL games, especially passing.
        """
        df = games_df.copy()

        # Dome game indicator
        if 'roof' in df.columns:
            df['is_dome'] = df['roof'].isin(['dome', 'closed']).astype(int)
        else:
            df['is_dome'] = 0

        # Surface type
        if 'surface' in df.columns:
            df['is_grass'] = (df['surface'] == 'grass').astype(int)
        else:
            df['is_grass'] = 0

        # Temperature factor (if available)
        if 'temp' in df.columns:
            df['cold_game'] = (df['temp'] < 32).astype(int)
            df['hot_game'] = (df['temp'] > 85).astype(int)

        # Wind factor (if available)
        if 'wind' in df.columns:
            df['high_wind'] = (df['wind'] > 15).astype(int)

        return df

    def calculate_momentum_features(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate momentum and form indicators."""
        df = games_df.copy()
        df = df.sort_values(['team', 'week'])

        # Win/loss
        df['win'] = (df['pts'] > df['pts_allowed']).astype(int)

        # Streak
        def get_streak(series):
            streaks = []
            current = 0
            last = None
            for val in series:
                if val == last and last is not None:
                    current += 1 if val == 1 else -1
                else:
                    current = 1 if val == 1 else -1
                last = val
                streaks.append(current)
            return pd.Series(streaks, index=series.index)

        df['streak'] = df.groupby('team')['win'].transform(get_streak)

        # Rolling win percentage
        for window in self.rolling_windows:
            df[f'win_pct_{window}g'] = df.groupby('team')['win'].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )

        # ATS (Against the Spread) performance
        if 'spread_line' in df.columns:
            df['covered'] = (
                (df['pts'] - df['pts_allowed']) > -df['spread_line']
            ).astype(int)

            for window in self.rolling_windows:
                df[f'ats_pct_{window}g'] = df.groupby('team')['covered'].transform(
                    lambda x: x.rolling(window, min_periods=1).mean()
                )

        # Point differential trend
        df['point_diff'] = df['pts'] - df['pts_allowed']
        for window in self.rolling_windows:
            df[f'avg_margin_{window}g'] = df.groupby('team')['point_diff'].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )

        short_col = f'avg_margin_{self.rolling_windows[0]}g'
        long_col = f'avg_margin_{self.rolling_windows[-1]}g'
        short_margin = df[short_col] if short_col in df.columns else 0
        long_margin = df[long_col] if long_col in df.columns else 0
        df['margin_trend'] = short_margin - long_margin

        return df

    def create_rolling_features(self, team_games: pd.DataFrame) -> pd.DataFrame:
        """Create rolling averages for key metrics."""
        cols_to_roll = [
            'epa_per_play', 'success_rate', 'pass_epa_per_play', 'rush_epa_per_play',
            'pts_per_drive', 'red_zone_pct', 'third_down_pct',
            'turnover_diff', 'turnover_rate'
        ]

        cols_to_roll = [c for c in cols_to_roll if c in team_games.columns]

        result = team_games.copy()

        for window in self.rolling_windows:
            rolled = team_games[cols_to_roll].rolling(window=window, min_periods=1).mean()
            rolled.columns = [f'{c}_{window}g' for c in rolled.columns]
            result = pd.concat([result, rolled], axis=1)

        # Exponential weighted averages
        ewm_cols = ['epa_per_play', 'success_rate']
        ewm_cols = [c for c in ewm_cols if c in team_games.columns]

        for span in [3, 5]:
            ewm = team_games[ewm_cols].ewm(span=span).mean()
            ewm.columns = [f'{c}_ewm{span}' for c in ewm.columns]
            result = pd.concat([result, ewm], axis=1)

        return result

    def calculate_matchup_features(
        self,
        home_team_stats: pd.Series,
        away_team_stats: pd.Series
    ) -> Dict[str, float]:
        """Calculate matchup-specific features for prediction."""
        features = {}

        # EPA differentials
        for window in self.rolling_windows:
            epa_col = f'epa_per_play_{window}g'
            if epa_col in home_team_stats.index:
                features[f'epa_diff_{window}g'] = (
                    home_team_stats[epa_col] - away_team_stats[epa_col]
                )

        # Success rate differential
        sr_col = f'success_rate_{self.rolling_windows[1]}g'
        if sr_col in home_team_stats.index:
            features['success_rate_diff'] = (
                home_team_stats[sr_col] - away_team_stats[sr_col]
            )

        # Pass/Rush EPA balance
        pass_col = f'pass_epa_per_play_{self.rolling_windows[1]}g'
        rush_col = f'rush_epa_per_play_{self.rolling_windows[1]}g'
        if pass_col in home_team_stats.index and rush_col in home_team_stats.index:
            features['home_pass_epa'] = home_team_stats[pass_col]
            features['home_rush_epa'] = home_team_stats[rush_col]
            features['away_pass_epa'] = away_team_stats[pass_col]
            features['away_rush_epa'] = away_team_stats[rush_col]

        # Turnover differential
        to_col = f'turnover_diff_{self.rolling_windows[1]}g'
        if to_col in home_team_stats.index:
            features['turnover_diff_diff'] = (
                home_team_stats[to_col] - away_team_stats[to_col]
            )

        # Rest factors
        features['rest_diff'] = (
            home_team_stats.get('days_rest', 7) - away_team_stats.get('days_rest', 7)
        )
        features['home_short_week'] = home_team_stats.get('short_week', 0)
        features['away_short_week'] = away_team_stats.get('short_week', 0)
        features['home_post_bye'] = home_team_stats.get('post_bye', 0)
        features['away_post_bye'] = away_team_stats.get('post_bye', 0)

        # Momentum
        features['streak_diff'] = (
            home_team_stats.get('streak', 0) - away_team_stats.get('streak', 0)
        )
        wp_col = f'win_pct_{self.rolling_windows[1]}g'
        if wp_col in home_team_stats.index:
            features['win_pct_diff'] = (
                home_team_stats[wp_col] - away_team_stats[wp_col]
            )

        # Home field advantage
        features['home_advantage'] = home_team_stats.get('home_advantage', 0.05)

        # Weather (if available)
        features['is_dome'] = home_team_stats.get('is_dome', 0)

        return features

    def process_games(self, games: List[Dict]) -> pd.DataFrame:
        """Main pipeline to process raw game data into features."""
        df = pd.DataFrame(games)

        # Handle different date column names
        if 'date' not in df.columns and 'gameday' in df.columns:
            df['date'] = df['gameday']
        df['date'] = pd.to_datetime(df['date'])

        # Ensure team column exists
        if 'team' not in df.columns:
            # Create team-level records from game-level data
            home_df = df.copy()
            home_df['team'] = home_df['home_team']
            home_df['opponent'] = home_df['away_team']
            home_df['is_home'] = True
            home_df['pts'] = home_df['home_score'] if 'home_score' in home_df.columns else 0
            home_df['pts_allowed'] = home_df['away_score'] if 'away_score' in home_df.columns else 0

            away_df = df.copy()
            away_df['team'] = away_df['away_team']
            away_df['opponent'] = away_df['home_team']
            away_df['is_home'] = False
            away_df['pts'] = away_df['away_score'] if 'away_score' in away_df.columns else 0
            away_df['pts_allowed'] = away_df['home_score'] if 'home_score' in away_df.columns else 0

            df = pd.concat([home_df, away_df], ignore_index=True)

        df = df.sort_values(['team', 'week'])

        # Calculate base metrics
        df = self.calculate_epa_metrics(df)
        df = self.calculate_success_rate(df)
        df = self.calculate_scoring_metrics(df)
        df = self.calculate_turnover_metrics(df)

        # Situational factors
        df = self.calculate_rest_factors(df)
        df = self.calculate_weather_factors(df)
        df = self.calculate_momentum_features(df)

        # Rolling features by team
        feature_dfs = []
        for team, team_data in df.groupby('team'):
            team_features = self.create_rolling_features(team_data)
            feature_dfs.append(team_features)

        final_df = pd.concat(feature_dfs)
        final_df = final_df.sort_values(['week', 'date'])

        # Home/away splits
        final_df = self.calculate_home_away_splits(final_df)

        # Fill missing values
        numeric_cols = final_df.select_dtypes(include=[np.number]).columns
        final_df[numeric_cols] = final_df.groupby('team')[numeric_cols].transform(
            lambda x: x.ffill().bfill()
        )
        final_df = final_df.fillna(0)

        return final_df


# Feature columns for model training
NFL_CORE_FEATURES = [
    # EPA differentials
    'epa_diff_3g', 'epa_diff_5g', 'epa_diff_10g',
    'success_rate_diff',

    # Pass/Rush balance
    'home_pass_epa', 'home_rush_epa',
    'away_pass_epa', 'away_rush_epa',

    # Turnovers
    'turnover_diff_diff',

    # Rest/Schedule
    'rest_diff', 'home_short_week', 'away_short_week',
    'home_post_bye', 'away_post_bye',

    # Momentum
    'streak_diff', 'win_pct_diff',

    # Home field
    'home_advantage', 'is_dome',
]