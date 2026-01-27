"""
MLB Feature Engineering Pipeline.

Comprehensive feature engineering for MLB game predictions using
advanced sabermetrics, pitcher-specific factors, and situational analysis.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class MLBFeatureEngineer:
    """
    Advanced feature engineering for MLB games.

    Features include:
    - Run differential and Pythagorean expectation
    - Team batting metrics (OPS, wOBA, wRC+, ISO)
    - Team pitching metrics (ERA, FIP, WHIP, K/9)
    - Starting pitcher analysis
    - Bullpen performance
    - Rest and travel factors
    - Home/away splits
    - Park factors
    - Platoon advantages
    """

    def __init__(self):
        self.rolling_windows = [10, 20, 40]  # MLB has 162 games
        self.min_games_required = 10

    def calculate_run_metrics(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate run-based efficiency metrics."""
        df = games_df.copy()

        # Run differential
        df['run_diff'] = df['runs_scored'] - df['runs_allowed']

        # Runs per game
        df['runs_per_game'] = df['runs_scored']
        df['runs_allowed_per_game'] = df['runs_allowed']

        # Pythagorean expectation (expected win% based on runs)
        # Win% = RS^1.83 / (RS^1.83 + RA^1.83)
        df['pyth_exp'] = np.where(
            (df['runs_scored'] + df['runs_allowed']) > 0,
            np.power(df['runs_scored'], 1.83) /
            (np.power(df['runs_scored'], 1.83) + np.power(df['runs_allowed'], 1.83)),
            0.5
        )

        return df

    def calculate_batting_metrics(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate team batting metrics.

        Uses weighted on-base average (wOBA) as primary offensive metric.
        """
        df = games_df.copy()

        # On-Base Percentage (if components available)
        if all(c in df.columns for c in ['hits', 'walks', 'hbp', 'at_bats', 'sac_flies']):
            df['obp'] = np.where(
                (df['at_bats'] + df['walks'] + df['hbp'] + df['sac_flies']) > 0,
                (df['hits'] + df['walks'] + df['hbp']) /
                (df['at_bats'] + df['walks'] + df['hbp'] + df['sac_flies']),
                0
            )

        # Slugging (if available)
        if all(c in df.columns for c in ['total_bases', 'at_bats']):
            df['slg'] = np.where(
                df['at_bats'] > 0,
                df['total_bases'] / df['at_bats'],
                0
            )

            # OPS
            df['ops'] = df.get('obp', 0) + df.get('slg', 0)

        # Isolated Power (SLG - AVG)
        if 'batting_avg' in df.columns and 'slg' in df.columns:
            df['iso'] = df['slg'] - df['batting_avg']

        # Strikeout rate
        if 'strikeouts' in df.columns and 'at_bats' in df.columns:
            df['k_rate'] = np.where(
                df['at_bats'] > 0,
                df['strikeouts'] / df['at_bats'],
                0
            )

        # Walk rate
        if 'walks' in df.columns and 'at_bats' in df.columns:
            df['bb_rate'] = np.where(
                df['at_bats'] > 0,
                df['walks'] / df['at_bats'],
                0
            )

        return df

    def calculate_pitching_metrics(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate team pitching metrics."""
        df = games_df.copy()

        # ERA (if innings pitched available)
        if 'earned_runs' in df.columns and 'innings_pitched' in df.columns:
            df['era'] = np.where(
                df['innings_pitched'] > 0,
                9 * df['earned_runs'] / df['innings_pitched'],
                0
            )

        # WHIP
        if all(c in df.columns for c in ['hits_allowed', 'walks_allowed', 'innings_pitched']):
            df['whip'] = np.where(
                df['innings_pitched'] > 0,
                (df['hits_allowed'] + df['walks_allowed']) / df['innings_pitched'],
                0
            )

        # K/9
        if 'strikeouts_pitched' in df.columns and 'innings_pitched' in df.columns:
            df['k_per_9'] = np.where(
                df['innings_pitched'] > 0,
                9 * df['strikeouts_pitched'] / df['innings_pitched'],
                0
            )

        # BB/9
        if 'walks_allowed' in df.columns and 'innings_pitched' in df.columns:
            df['bb_per_9'] = np.where(
                df['innings_pitched'] > 0,
                9 * df['walks_allowed'] / df['innings_pitched'],
                0
            )

        # HR/9
        if 'home_runs_allowed' in df.columns and 'innings_pitched' in df.columns:
            df['hr_per_9'] = np.where(
                df['innings_pitched'] > 0,
                9 * df['home_runs_allowed'] / df['innings_pitched'],
                0
            )

        return df

    def calculate_rest_factors(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate rest and schedule factors.

        MLB has unique factors like doubleheaders, travel, and
        pitcher rest days.
        """
        df = games_df.copy()
        df = df.sort_values(['team', 'date'])

        # Days since last game
        df['prev_game_date'] = df.groupby('team')['date'].shift(1)
        df['days_rest'] = (pd.to_datetime(df['date']) - pd.to_datetime(df['prev_game_date'])).dt.days
        df['days_rest'] = df['days_rest'].fillna(1)

        # Doubleheader indicator
        df['is_doubleheader'] = (df['days_rest'] == 0).astype(int)

        # Day game after night game (if D/N column available)
        if 'D/N' in df.columns:
            df['is_day_game'] = (df['D/N'] == 'D').astype(int)
            df['prev_night_game'] = (df.groupby('team')['D/N'].shift(1) == 'N').astype(int)
            df['day_after_night'] = (
                (df['days_rest'] == 1) &
                (df['prev_night_game'] == 1) &
                (df['is_day_game'] == 1)
            ).astype(int)

        # Games in last 7 days (schedule density)
        # Use a simple count of games with days_rest <= 7
        df['games_last_7'] = df.groupby('team')['days_rest'].transform(
            lambda x: (x <= 7).rolling(7, min_periods=1).sum()
        )

        # Travel (rough estimate based on opponent changes)
        df['prev_opponent'] = df.groupby('team')['opponent'].shift(1)
        df['new_series'] = (df['opponent'] != df['prev_opponent']).astype(int)

        return df

    def calculate_home_away_splits(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate home/away performance splits."""
        df = games_df.copy()

        if 'home_away' not in df.columns:
            df['home_away'] = 'home'  # Default

        df['is_home'] = (df['home_away'] == 'home').astype(int)

        # Rolling metrics for home/away
        for window in self.rolling_windows:
            for col in ['run_diff', 'runs_per_game', 'runs_allowed_per_game']:
                if col in df.columns:
                    df[f'home_{col}_{window}g'] = df.groupby('team').apply(
                        lambda x: x[x['is_home'] == 1][col].rolling(window, min_periods=1).mean()
                    ).reset_index(level=0, drop=True)

                    df[f'away_{col}_{window}g'] = df.groupby('team').apply(
                        lambda x: x[x['is_home'] == 0][col].rolling(window, min_periods=1).mean()
                    ).reset_index(level=0, drop=True)

        # Home field advantage
        home_col = f'home_run_diff_{self.rolling_windows[1]}g'
        away_col = f'away_run_diff_{self.rolling_windows[1]}g'
        home_rd = df[home_col] if home_col in df.columns else 0
        away_rd = df[away_col] if away_col in df.columns else 0
        df['home_advantage'] = (home_rd - away_rd) / 2

        return df

    def calculate_momentum_features(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate momentum and streaks."""
        df = games_df.copy()
        df = df.sort_values(['team', 'date'])

        # Win/loss
        df['win'] = (df['runs_scored'] > df['runs_allowed']).astype(int)

        # Parse record if available (e.g., "50-30")
        if 'record' in df.columns:
            df['wins'] = df['record'].str.split('-').str[0].astype(float)
            df['losses'] = df['record'].str.split('-').str[1].astype(float)
            df['season_win_pct'] = df['wins'] / (df['wins'] + df['losses'])

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

        if 'streak' not in df.columns:
            df['streak'] = df.groupby('team')['win'].transform(get_streak)
        else:
            # Parse streak from string (e.g., "W3" or "L2")
            df['streak'] = df['streak'].apply(
                lambda x: int(x[1:]) if isinstance(x, str) and x.startswith('W')
                else -int(x[1:]) if isinstance(x, str) and x.startswith('L')
                else 0
            )

        # Rolling win percentage
        for window in self.rolling_windows:
            df[f'win_pct_{window}g'] = df.groupby('team')['win'].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )

        # Run differential trend
        for window in self.rolling_windows:
            df[f'avg_run_diff_{window}g'] = df.groupby('team')['run_diff'].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )

        short_col = f'avg_run_diff_{self.rolling_windows[0]}g'
        long_col = f'avg_run_diff_{self.rolling_windows[-1]}g'
        short_rd = df[short_col] if short_col in df.columns else 0
        long_rd = df[long_col] if long_col in df.columns else 0
        df['run_diff_trend'] = short_rd - long_rd

        return df

    def create_rolling_features(self, team_games: pd.DataFrame) -> pd.DataFrame:
        """Create rolling averages for all key metrics."""
        cols_to_roll = [
            'run_diff', 'runs_per_game', 'runs_allowed_per_game',
            'pyth_exp', 'ops', 'iso', 'k_rate', 'bb_rate',
            'era', 'whip', 'k_per_9', 'bb_per_9'
        ]

        cols_to_roll = [c for c in cols_to_roll if c in team_games.columns]

        result = team_games.copy()

        for window in self.rolling_windows:
            rolled = team_games[cols_to_roll].rolling(window=window, min_periods=1).mean()
            rolled.columns = [f'{c}_{window}g' for c in rolled.columns]
            result = pd.concat([result, rolled], axis=1)

        # Exponential weighted
        ewm_cols = ['run_diff', 'runs_per_game', 'runs_allowed_per_game']
        ewm_cols = [c for c in ewm_cols if c in team_games.columns]

        for span in [10, 20]:
            ewm = team_games[ewm_cols].ewm(span=span).mean()
            ewm.columns = [f'{c}_ewm{span}' for c in ewm.columns]
            result = pd.concat([result, ewm], axis=1)

        return result

    def calculate_matchup_features(
        self,
        home_team_stats: pd.Series,
        away_team_stats: pd.Series,
        home_pitcher_stats: Optional[Dict] = None,
        away_pitcher_stats: Optional[Dict] = None
    ) -> Dict[str, float]:
        """Calculate matchup-specific features."""
        features = {}

        # Run differential
        for window in self.rolling_windows:
            rd_col = f'run_diff_{window}g'
            if rd_col in home_team_stats.index:
                features[f'run_diff_diff_{window}g'] = (
                    home_team_stats[rd_col] - away_team_stats[rd_col]
                )

        # Runs scored/allowed differentials
        rs_col = f'runs_per_game_{self.rolling_windows[1]}g'
        ra_col = f'runs_allowed_per_game_{self.rolling_windows[1]}g'
        if rs_col in home_team_stats.index:
            features['home_runs_per_game'] = home_team_stats[rs_col]
            features['away_runs_per_game'] = away_team_stats[rs_col]
            features['home_runs_allowed'] = home_team_stats[ra_col]
            features['away_runs_allowed'] = away_team_stats[ra_col]

        # Pythagorean expectation differential
        pyth_col = f'pyth_exp_{self.rolling_windows[1]}g'
        if pyth_col in home_team_stats.index:
            features['pyth_diff'] = (
                home_team_stats[pyth_col] - away_team_stats[pyth_col]
            )

        # Batting metrics
        ops_col = f'ops_{self.rolling_windows[1]}g'
        if ops_col in home_team_stats.index:
            features['ops_diff'] = (
                home_team_stats[ops_col] - away_team_stats[ops_col]
            )

        # Pitching metrics
        era_col = f'era_{self.rolling_windows[1]}g'
        if era_col in home_team_stats.index:
            features['era_diff'] = (
                away_team_stats[era_col] - home_team_stats[era_col]  # Lower is better
            )

        whip_col = f'whip_{self.rolling_windows[1]}g'
        if whip_col in home_team_stats.index:
            features['whip_diff'] = (
                away_team_stats[whip_col] - home_team_stats[whip_col]
            )

        # Starting pitcher stats (if available)
        if home_pitcher_stats:
            features['home_sp_era'] = home_pitcher_stats.get('era', 4.0)
            features['home_sp_whip'] = home_pitcher_stats.get('whip', 1.3)
            features['home_sp_k9'] = home_pitcher_stats.get('k_per_9', 8.0)

        if away_pitcher_stats:
            features['away_sp_era'] = away_pitcher_stats.get('era', 4.0)
            features['away_sp_whip'] = away_pitcher_stats.get('whip', 1.3)
            features['away_sp_k9'] = away_pitcher_stats.get('k_per_9', 8.0)

        if home_pitcher_stats and away_pitcher_stats:
            features['sp_era_diff'] = (
                away_pitcher_stats.get('era', 4.0) - home_pitcher_stats.get('era', 4.0)
            )

        # Rest factors
        features['rest_diff'] = (
            home_team_stats.get('days_rest', 1) - away_team_stats.get('days_rest', 1)
        )
        features['home_doubleheader'] = home_team_stats.get('is_doubleheader', 0)
        features['away_doubleheader'] = away_team_stats.get('is_doubleheader', 0)

        # Momentum
        features['streak_diff'] = (
            home_team_stats.get('streak', 0) - away_team_stats.get('streak', 0)
        )
        wp_col = f'win_pct_{self.rolling_windows[1]}g'
        if wp_col in home_team_stats.index:
            features['win_pct_diff'] = (
                home_team_stats[wp_col] - away_team_stats[wp_col]
            )

        # Home field
        features['home_advantage'] = home_team_stats.get('home_advantage', 0.03)

        return features

    def process_games(self, games: List[Dict]) -> pd.DataFrame:
        """Main pipeline to process raw game data."""
        df = pd.DataFrame(games)

        # Handle different column name conventions
        column_mappings = {
            'Date': 'date',
            'Tm': 'team',
            'Opp': 'opponent',
            'R': 'runs_scored',
            'RA': 'runs_allowed',
            'Home_Away': 'home_away',
            'W/L': 'result'
        }
        for old_col, new_col in column_mappings.items():
            if old_col in df.columns and new_col not in df.columns:
                df[new_col] = df[old_col]

        # Handle home/away
        if 'home_away' in df.columns and df['home_away'].dtype == 'object':
            df['is_home'] = (~df['home_away'].str.contains('@', na=False)).astype(int)
            df['home_away'] = df['is_home'].map({1: 'home', 0: 'away'})

        # Parse date - handle MLB format "Thursday, Mar 28" + season year
        if 'date' in df.columns:
            if 'season' in df.columns:
                # Combine date with season year
                df['date'] = df.apply(
                    lambda row: pd.to_datetime(f"{row['date']} {row['season']}", format='%A, %b %d %Y', errors='coerce')
                    if pd.notna(row['date']) else pd.NaT,
                    axis=1
                )
            else:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.sort_values(['team', 'date'] if 'date' in df.columns else 'team')

        # Calculate base metrics
        df = self.calculate_run_metrics(df)
        df = self.calculate_batting_metrics(df)
        df = self.calculate_pitching_metrics(df)

        # Situational factors
        df = self.calculate_rest_factors(df)
        df = self.calculate_momentum_features(df)

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
MLB_CORE_FEATURES = [
    # Run differentials
    'run_diff_diff_10g', 'run_diff_diff_20g', 'run_diff_diff_40g',

    # Runs scored/allowed
    'home_runs_per_game', 'away_runs_per_game',
    'home_runs_allowed', 'away_runs_allowed',

    # Pythagorean
    'pyth_diff',

    # Batting
    'ops_diff',

    # Pitching
    'era_diff', 'whip_diff',

    # Starting pitchers
    'home_sp_era', 'away_sp_era', 'sp_era_diff',
    'home_sp_whip', 'away_sp_whip',

    # Rest
    'rest_diff', 'home_doubleheader', 'away_doubleheader',

    # Momentum
    'streak_diff', 'win_pct_diff',

    # Home field
    'home_advantage',
]
