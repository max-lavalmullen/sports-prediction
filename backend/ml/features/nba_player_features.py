"""
NBA Player Feature Engineering Pipeline.

Transforms raw player game logs into predictive features for prop betting.
Includes rolling averages, usage metrics, consistency scores, and defense-vs-position adjustments.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime

class NBAPlayerFeatureEngineer:
    """
    Feature engineering for NBA Player Props.
    
    Generates features for:
    - Points, Rebounds, Assists, Threes, Steals, Blocks
    - Usage Rate & Efficiency
    - Consistency (Standard Deviation of performance)
    - Matchup specific adjustments (Defense vs Position)
    """

    def __init__(self):
        self.rolling_windows = [5, 10, 20]
        # Key stats we want to predict
        self.target_stats = ['pts', 'reb', 'ast', 'fg3m', 'stl', 'blk', 'tov']
        
    def calculate_advanced_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate per-game advanced metrics.
        
        Note: Exact Usage Rate requires team totals, here we use an approximation
        or assume pre-calculated/provided values if available.
        For now, we focus on efficiency and volume metrics.
        """
        # Effective Field Goal %
        df['efg_pct'] = np.where(
            df['fga'] > 0,
            (df['fgm'] + 0.5 * df['fg3m']) / df['fga'],
            0
        )
        
        # True Shooting % approximation (0.44 coeff for FTA)
        # TS% = Pts / (2 * (FGA + 0.44 * FTA))
        df['ts_pct'] = np.where(
            (2 * (df['fga'] + 0.44 * df['fta'])) > 0,
            df['pts'] / (2 * (df['fga'] + 0.44 * df['fta'])),
            0
        )
        
        # Game Score (Hollinger) - rough measure of single game productivity
        # PTS + 0.4 * FG - 0.7 * FGA - 0.4*(FTA - FTM) + 0.7 * ORB + 0.3 * DRB + STL + 0.7 * AST + 0.7 * BLK - 0.4 * PF - TOV
        df['game_score'] = (
            df['pts'] + 0.4 * df['fgm'] - 0.7 * df['fga'] - 
            0.4 * (df['fta'] - df['ftm']) + 0.7 * df['oreb'] + 
            0.3 * df['dreb'] + df['stl'] + 0.7 * df['ast'] + 
            0.7 * df['blk'] - 0.4 * df['pf'] - df['tov']
        )
        
        return df

    def create_rolling_features(self, player_logs: pd.DataFrame) -> pd.DataFrame:
        """
        Create rolling averages and consistency metrics for a single player.
        """
        df = player_logs.sort_values('date').copy()
        
        # Stats to roll
        base_stats = self.target_stats + ['min', 'fga', 'fg3a', 'fta', 'game_score', 'plus_minus']
        
        for window in self.rolling_windows:
            # Simple Moving Average
            rolled = df[base_stats].rolling(window=window, min_periods=1)
            
            # Averages
            means = rolled.mean().add_suffix(f'_{window}g')
            df = pd.concat([df, means], axis=1)
            
            # Consistency (Standard Deviation)
            # Valuable for props: High variance players are risky for 'Under' bets, good for 'Ladder' bets
            stds = rolled.std().add_suffix(f'_std_{window}g')
            df = pd.concat([df, stds], axis=1)
            
            # Floor/Ceiling (Min/Max in window)
            df[f'pts_min_{window}g'] = rolled['pts'].min()
            df[f'pts_max_{window}g'] = rolled['pts'].max()

        # Exponential Weighted Moving Average (EWMA) - weighs recent games more
        # Span=5 roughly correlates to last 3-4 games heavy weighting
        ewma_cols = ['pts', 'reb', 'ast', 'min', 'game_score']
        ewma = df[ewma_cols].ewm(span=5).mean().add_suffix('_ewma_5')
        df = pd.concat([df, ewma], axis=1)

        return df

    def calculate_rest_days(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate days since last game."""
        df['prev_game_date'] = df['date'].shift(1)
        df['days_rest'] = (df['date'] - df['prev_game_date']).dt.days
        df['days_rest'] = df['days_rest'].fillna(3) # Default to fully rested
        
        # Cap rest at 7 days to avoid skewing outliers (all-star break, injury return)
        df['days_rest'] = df['days_rest'].clip(upper=7)
        return df

    def calculate_defense_vs_position(self, df: pd.DataFrame, league_logs: pd.DataFrame) -> pd.DataFrame:
        """
        Add features for Opponent Rank vs Position.
        
        This requires the full league dataset to calculate how well the opponent
        defends this player's position compared to league average.
        """
        # This is a placeholder for the complex logic of:
        # 1. Determine player's primary position (G, F, C)
        # 2. Aggregate stats allowed by opponent to that position
        # 3. Calculate rank/percentile
        
        # For now, we will assume these features are injected or we just return the df
        # Real implementation would compute 'opp_rank_pts', 'opp_rank_reb', etc.
        return df

    def process_player_logs(self, logs: List[Dict]) -> pd.DataFrame:
        """
        Main pipeline to process raw player logs.
        """
        if not logs:
            return pd.DataFrame()

        df = pd.DataFrame(logs)
        df['date'] = pd.to_datetime(df['date'])
        
        # Calculate derived per-game stats
        df = self.calculate_advanced_stats(df)
        
        # Group by player and apply rolling windows
        player_dfs = []
        for player_id, player_data in df.groupby('player_id'):
            # Calculate rest days
            player_data = self.calculate_rest_days(player_data)
            
            # Calculate rolling features
            player_data = self.create_rolling_features(player_data)
            
            player_dfs.append(player_data)
            
        if not player_dfs:
            return pd.DataFrame()
            
        final_df = pd.concat(player_dfs)
        final_df = final_df.sort_values(['date', 'player_id'])
        
        # Fill NaN (first games of season)
        final_df = final_df.fillna(0)
        
        return final_df

    def prepare_prediction_features(
        self,
        player_id: int,
        player_history_df: pd.DataFrame,
        game_date: datetime,
        opponent_team_id: int
    ) -> Dict[str, float]:
        """
        Prepare feature vector for a specific prediction.
        """
        # Get player's history strictly before the game date
        history = player_history_df[
            (player_history_df['player_id'] == player_id) & 
            (player_history_df['date'] < game_date)
        ]
        
        if history.empty:
            return {}
            
        # Get most recent row (contains the rolling averages up to that point)
        recent_stats = history.iloc[-1]
        
        features = {}
        
        # Extract rolling features
        for col in recent_stats.index:
            if any(x in col for x in ['_5g', '_10g', '_20g', '_ewma']):
                features[col] = float(recent_stats[col])
        
        # Add basic info
        features['days_rest'] = (game_date - recent_stats['date']).days
        features['is_home'] = 1 # Placeholder, needs schedule lookup
        
        return features

feature_engineer = NBAPlayerFeatureEngineer()
