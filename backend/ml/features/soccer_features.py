"""
Soccer Feature Engineering Pipeline.

Comprehensive feature engineering for soccer match predictions using
expected goals (xG), possession metrics, and situational factors.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class SoccerFeatureEngineer:
    """
    Advanced feature engineering for soccer matches.

    Features include:
    - Expected Goals (xG) metrics
    - Goals and clean sheet rates
    - Possession and passing metrics
    - Shot quality metrics
    - Form and momentum indicators
    - Home/away splits
    - Rest and fixture congestion
    - League table position effects
    """

    def __init__(self):
        self.rolling_windows = [5, 10, 20]  # Typical form windows
        self.min_games_required = 5

    def calculate_goal_metrics(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate goal-based metrics."""
        df = games_df.copy()

        # Goal difference
        df['goal_diff'] = df['goals_for'] - df['goals_against']

        # Goals per game
        df['goals_per_game'] = df['goals_for']
        df['goals_conceded_per_game'] = df['goals_against']

        # Clean sheet
        df['clean_sheet'] = (df['goals_against'] == 0).astype(int)

        # Failed to score
        df['failed_to_score'] = (df['goals_for'] == 0).astype(int)

        # Both teams scored
        df['btts'] = (
            (df['goals_for'] > 0) & (df['goals_against'] > 0)
        ).astype(int)

        # Over/Under thresholds
        total_goals = df['goals_for'] + df['goals_against']
        df['over_1_5'] = (total_goals > 1.5).astype(int)
        df['over_2_5'] = (total_goals > 2.5).astype(int)
        df['over_3_5'] = (total_goals > 3.5).astype(int)

        return df

    def calculate_xg_metrics(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate expected goals (xG) based metrics.

        xG is the gold standard for measuring chance quality.
        """
        df = games_df.copy()

        # If xG data available
        if 'xg' in df.columns and 'xga' in df.columns:
            # xG differential
            df['xg_diff'] = df['xg'] - df['xga']

            # xG overperformance (goals - xG)
            df['xg_overperformance'] = df['goals_for'] - df['xg']
            df['xga_overperformance'] = df['goals_against'] - df['xga']

            # xG per shot (shot quality)
            if 'shots' in df.columns:
                df['xg_per_shot'] = np.where(
                    df['shots'] > 0,
                    df['xg'] / df['shots'],
                    0
                )

        return df

    def calculate_shot_metrics(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate shot-based metrics."""
        df = games_df.copy()

        if 'shots' in df.columns:
            # Shots on target ratio
            if 'shots_on_target' in df.columns:
                df['shot_accuracy'] = np.where(
                    df['shots'] > 0,
                    df['shots_on_target'] / df['shots'],
                    0
                )

            # Conversion rate
            df['conversion_rate'] = np.where(
                df['shots'] > 0,
                df['goals_for'] / df['shots'],
                0
            )

        # Defensive shot metrics
        if 'shots_against' in df.columns:
            df['shots_conceded'] = df['shots_against']

            if 'shots_on_target_against' in df.columns:
                df['shot_save_rate'] = np.where(
                    df['shots_on_target_against'] > 0,
                    1 - (df['goals_against'] / df['shots_on_target_against']),
                    0
                )

        return df

    def calculate_possession_metrics(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate possession and passing metrics."""
        df = games_df.copy()

        if 'possession' in df.columns:
            # Possession differential (vs opponent's 100 - our possession)
            df['possession_diff'] = df['possession'] - 50

        if 'passes' in df.columns and 'passes_completed' in df.columns:
            df['pass_accuracy'] = np.where(
                df['passes'] > 0,
                df['passes_completed'] / df['passes'],
                0
            )

        return df

    def calculate_rest_factors(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate rest and fixture congestion factors.

        European competitions create significant fixture congestion.
        """
        df = games_df.copy()
        df = df.sort_values(['team', 'date'])

        # Days since last game
        df['prev_game_date'] = df.groupby('team')['date'].shift(1)
        df['days_rest'] = (pd.to_datetime(df['date']) - pd.to_datetime(df['prev_game_date'])).dt.days
        df['days_rest'] = df['days_rest'].fillna(7)

        # Short turnaround (midweek game)
        df['short_rest'] = (df['days_rest'] <= 3).astype(int)

        # Long rest (international break)
        df['long_rest'] = (df['days_rest'] >= 10).astype(int)

        # Games in last 14 days (fixture congestion)
        df['games_last_14'] = df.groupby('team')['date'].transform(
            lambda x: x.rolling('14D', closed='left').count()
        )

        # Fixture congestion indicator
        df['fixture_congestion'] = (df['games_last_14'] >= 4).astype(int)

        return df

    def calculate_home_away_splits(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate home/away form."""
        df = games_df.copy()

        if 'is_home' not in df.columns:
            df['is_home'] = 1  # Default to home

        # Rolling home/away metrics
        for window in self.rolling_windows:
            for col in ['goal_diff', 'goals_per_game', 'goals_conceded_per_game', 'clean_sheet']:
                if col in df.columns:
                    df[f'home_{col}_{window}g'] = df.groupby('team').apply(
                        lambda x: x[x['is_home'] == 1][col].rolling(window, min_periods=1).mean()
                    ).reset_index(level=0, drop=True)

                    df[f'away_{col}_{window}g'] = df.groupby('team').apply(
                        lambda x: x[x['is_home'] == 0][col].rolling(window, min_periods=1).mean()
                    ).reset_index(level=0, drop=True)

        # Home advantage calculation
        home_gd = df.get(f'home_goal_diff_{self.rolling_windows[1]}g', 0)
        away_gd = df.get(f'away_goal_diff_{self.rolling_windows[1]}g', 0)
        df['home_advantage'] = (home_gd - away_gd) / 2 if isinstance(home_gd, (int, float)) else 0

        return df

    def calculate_momentum_features(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate form and momentum indicators."""
        df = games_df.copy()
        df = df.sort_values(['team', 'date'])

        # Points from match (W=3, D=1, L=0)
        df['win'] = (df['goals_for'] > df['goals_against']).astype(int)
        df['draw'] = (df['goals_for'] == df['goals_against']).astype(int)
        df['loss'] = (df['goals_for'] < df['goals_against']).astype(int)
        df['points'] = df['win'] * 3 + df['draw']

        # Rolling points per game (form)
        for window in self.rolling_windows:
            df[f'ppg_{window}g'] = df.groupby('team')['points'].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )

        # Win percentage
        for window in self.rolling_windows:
            df[f'win_pct_{window}g'] = df.groupby('team')['win'].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )

        # Unbeaten streak / losing streak
        def get_form_streak(series):
            """Calculate current unbeaten/losing streak."""
            streaks = []
            current = 0
            for points in series:
                if points > 0:  # Win or draw
                    current = max(1, current + 1)
                else:  # Loss
                    current = min(-1, current - 1) if current <= 0 else -1
                streaks.append(current)
            return pd.Series(streaks, index=series.index)

        df['form_streak'] = df.groupby('team')['points'].transform(get_form_streak)

        # Goal difference trend
        for window in self.rolling_windows:
            df[f'avg_gd_{window}g'] = df.groupby('team')['goal_diff'].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )

        df['gd_trend'] = (
            df.get(f'avg_gd_{self.rolling_windows[0]}g', 0) -
            df.get(f'avg_gd_{self.rolling_windows[-1]}g', 0)
        )

        return df

    def calculate_table_position(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate league table position effects."""
        df = games_df.copy()

        # If table position available
        if 'table_position' in df.columns:
            df['is_top_4'] = (df['table_position'] <= 4).astype(int)
            df['is_relegation'] = (df['table_position'] >= 18).astype(int)
            df['is_mid_table'] = (
                (df['table_position'] > 6) & (df['table_position'] < 15)
            ).astype(int)

        return df

    def create_rolling_features(self, team_games: pd.DataFrame) -> pd.DataFrame:
        """Create rolling averages for key metrics."""
        cols_to_roll = [
            'goal_diff', 'goals_per_game', 'goals_conceded_per_game',
            'xg_diff', 'xg', 'xga', 'xg_per_shot',
            'clean_sheet', 'btts', 'over_2_5',
            'conversion_rate', 'shot_accuracy'
        ]

        cols_to_roll = [c for c in cols_to_roll if c in team_games.columns]

        result = team_games.copy()

        for window in self.rolling_windows:
            rolled = team_games[cols_to_roll].rolling(window=window, min_periods=1).mean()
            rolled.columns = [f'{c}_{window}g' for c in rolled.columns]
            result = pd.concat([result, rolled], axis=1)

        # Exponential weighted
        ewm_cols = ['goal_diff', 'goals_per_game', 'goals_conceded_per_game']
        ewm_cols = [c for c in ewm_cols if c in team_games.columns]

        for span in [5, 10]:
            ewm = team_games[ewm_cols].ewm(span=span).mean()
            ewm.columns = [f'{c}_ewm{span}' for c in ewm.columns]
            result = pd.concat([result, ewm], axis=1)

        return result

    def calculate_matchup_features(
        self,
        home_team_stats: pd.Series,
        away_team_stats: pd.Series
    ) -> Dict[str, float]:
        """Calculate matchup-specific features."""
        features = {}

        # Goal metrics differentials
        for window in self.rolling_windows:
            gd_col = f'goal_diff_{window}g'
            if gd_col in home_team_stats.index:
                features[f'gd_diff_{window}g'] = (
                    home_team_stats[gd_col] - away_team_stats[gd_col]
                )

        # Goals scored/conceded
        gs_col = f'goals_per_game_{self.rolling_windows[1]}g'
        gc_col = f'goals_conceded_per_game_{self.rolling_windows[1]}g'
        if gs_col in home_team_stats.index:
            features['home_goals_per_game'] = home_team_stats[gs_col]
            features['away_goals_per_game'] = away_team_stats[gs_col]
            features['home_goals_conceded'] = home_team_stats[gc_col]
            features['away_goals_conceded'] = away_team_stats[gc_col]

            # Expected total goals
            features['expected_total'] = (
                home_team_stats[gs_col] + away_team_stats[gs_col] +
                home_team_stats[gc_col] + away_team_stats[gc_col]
            ) / 2

        # xG differential (if available)
        xg_col = f'xg_diff_{self.rolling_windows[1]}g'
        if xg_col in home_team_stats.index:
            features['xg_diff_diff'] = (
                home_team_stats[xg_col] - away_team_stats[xg_col]
            )

        # Clean sheet rates
        cs_col = f'clean_sheet_{self.rolling_windows[1]}g'
        if cs_col in home_team_stats.index:
            features['home_clean_sheet_rate'] = home_team_stats[cs_col]
            features['away_clean_sheet_rate'] = away_team_stats[cs_col]

        # BTTS rate
        btts_col = f'btts_{self.rolling_windows[1]}g'
        if btts_col in home_team_stats.index:
            features['btts_likelihood'] = (
                home_team_stats[btts_col] + away_team_stats[btts_col]
            ) / 2

        # Over 2.5 rate
        o25_col = f'over_2_5_{self.rolling_windows[1]}g'
        if o25_col in home_team_stats.index:
            features['over_2_5_likelihood'] = (
                home_team_stats[o25_col] + away_team_stats[o25_col]
            ) / 2

        # Form (points per game)
        ppg_col = f'ppg_{self.rolling_windows[1]}g'
        if ppg_col in home_team_stats.index:
            features['ppg_diff'] = (
                home_team_stats[ppg_col] - away_team_stats[ppg_col]
            )

        # Rest factors
        features['rest_diff'] = (
            home_team_stats.get('days_rest', 7) - away_team_stats.get('days_rest', 7)
        )
        features['home_short_rest'] = home_team_stats.get('short_rest', 0)
        features['away_short_rest'] = away_team_stats.get('short_rest', 0)
        features['home_congestion'] = home_team_stats.get('fixture_congestion', 0)
        features['away_congestion'] = away_team_stats.get('fixture_congestion', 0)

        # Momentum
        features['form_streak_diff'] = (
            home_team_stats.get('form_streak', 0) - away_team_stats.get('form_streak', 0)
        )
        wp_col = f'win_pct_{self.rolling_windows[1]}g'
        if wp_col in home_team_stats.index:
            features['win_pct_diff'] = (
                home_team_stats[wp_col] - away_team_stats[wp_col]
            )

        # Home advantage (typically worth ~0.4 goals in soccer)
        features['home_advantage'] = home_team_stats.get('home_advantage', 0.4)

        return features

    def process_games(self, games: List[Dict]) -> pd.DataFrame:
        """Main pipeline to process raw game data."""
        df = pd.DataFrame(games)

        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(['team', 'date'] if 'date' in df.columns else 'team')

        # Calculate base metrics
        df = self.calculate_goal_metrics(df)
        df = self.calculate_xg_metrics(df)
        df = self.calculate_shot_metrics(df)
        df = self.calculate_possession_metrics(df)

        # Situational factors
        df = self.calculate_rest_factors(df)
        df = self.calculate_momentum_features(df)
        df = self.calculate_table_position(df)

        # Rolling features
        feature_dfs = []
        for team, team_data in df.groupby('team'):
            team_features = self.create_rolling_features(team_data)
            feature_dfs.append(team_features)

        final_df = pd.concat(feature_dfs)
        if 'date' in final_df.columns:
            final_df = final_df.sort_values('date')

        # Home/away splits
        final_df = self.calculate_home_away_splits(final_df)

        # Fill missing
        numeric_cols = final_df.select_dtypes(include=[np.number]).columns
        final_df[numeric_cols] = final_df.groupby('team')[numeric_cols].transform(
            lambda x: x.ffill().bfill()
        )
        final_df = final_df.fillna(0)

        return final_df


# Feature columns for model training
SOCCER_CORE_FEATURES = [
    # Goal differentials
    'gd_diff_5g', 'gd_diff_10g', 'gd_diff_20g',

    # Goals scored/conceded
    'home_goals_per_game', 'away_goals_per_game',
    'home_goals_conceded', 'away_goals_conceded',
    'expected_total',

    # xG
    'xg_diff_diff',

    # Clean sheets / BTTS / Over
    'home_clean_sheet_rate', 'away_clean_sheet_rate',
    'btts_likelihood', 'over_2_5_likelihood',

    # Form
    'ppg_diff', 'form_streak_diff', 'win_pct_diff',

    # Rest
    'rest_diff', 'home_short_rest', 'away_short_rest',
    'home_congestion', 'away_congestion',

    # Home field
    'home_advantage',
]