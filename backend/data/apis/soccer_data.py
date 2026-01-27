"""
Soccer Data Fetcher.

Fetches historical match data, team stats, and expected goals (xG) data
from multiple free sources:
- football-data.co.uk (historical results with betting odds)
- FBref/StatsBomb (advanced stats via soccerdata)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
import io
from loguru import logger

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx not installed. Some soccer data fetching may be unavailable.")

# Try to import soccerdata for FBref access
try:
    import soccerdata as sd
    SOCCERDATA_AVAILABLE = True
except ImportError:
    SOCCERDATA_AVAILABLE = False
    logger.warning("soccerdata not installed. FBref/xG data will be unavailable.")


class SoccerDataFetcher:
    """
    Fetches soccer data from multiple free sources.

    Primary sources:
    - football-data.co.uk: Historical match results with betting odds
    - FBref (via soccerdata): Advanced stats including xG
    """

    # League codes for football-data.co.uk
    FOOTBALL_DATA_LEAGUES = {
        "premier_league": "E0",
        "championship": "E1",
        "league_one": "E2",
        "league_two": "E3",
        "la_liga": "SP1",
        "bundesliga": "D1",
        "serie_a": "I1",
        "ligue_1": "F1",
        "eredivisie": "N1",
        "primeira_liga": "P1",
    }

    # League codes for soccerdata/FBref
    FBREF_LEAGUES = {
        "premier_league": "ENG-Premier League",
        "la_liga": "ESP-La Liga",
        "bundesliga": "GER-Bundesliga",
        "serie_a": "ITA-Serie A",
        "ligue_1": "FRA-Ligue 1",
    }

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize the fetcher.

        Args:
            data_dir: Directory to cache downloaded data
        """
        self.data_dir = Path(data_dir) if data_dir else Path("data/soccer")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._fbref_cache: Dict[str, pd.DataFrame] = {}

    def get_football_data_url(self, league: str, season: str) -> str:
        """
        Get URL for football-data.co.uk CSV.

        Args:
            league: League key (e.g., 'premier_league')
            season: Season string (e.g., '2324' for 2023-24)
        """
        league_code = self.FOOTBALL_DATA_LEAGUES.get(league, league)
        return f"https://www.football-data.co.uk/mmz4281/{season}/{league_code}.csv"

    def fetch_football_data_season(
        self,
        league: str = "premier_league",
        season: str = "2324"
    ) -> pd.DataFrame:
        """
        Fetch a season of match data from football-data.co.uk.

        Args:
            league: League key (e.g., 'premier_league', 'la_liga')
            season: Season code (e.g., '2324' for 2023-24, '2223' for 2022-23)

        Returns:
            DataFrame with match results and betting odds
        """
        if not HTTPX_AVAILABLE:
            logger.error("httpx required for fetching football-data.co.uk")
            return pd.DataFrame()

        url = self.get_football_data_url(league, season)

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url)
                response.raise_for_status()

            # Parse CSV
            df = pd.read_csv(io.StringIO(response.text), encoding='utf-8', on_bad_lines='skip')

            # Standardize column names
            df = self._standardize_football_data_columns(df)

            # Add metadata
            df['league'] = league
            df['season'] = season

            logger.info(f"Fetched {len(df)} matches for {league} {season}")
            return df

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {league} {season}: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching {league} {season}: {e}")
            return pd.DataFrame()

    def _standardize_football_data_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names from football-data.co.uk."""
        column_mapping = {
            'Div': 'division',
            'Date': 'date',
            'Time': 'time',
            'HomeTeam': 'home_team',
            'AwayTeam': 'away_team',
            'FTHG': 'home_goals',
            'FTAG': 'away_goals',
            'FTR': 'result',  # H/D/A
            'HTHG': 'ht_home_goals',
            'HTAG': 'ht_away_goals',
            'HTR': 'ht_result',
            'HS': 'home_shots',
            'AS': 'away_shots',
            'HST': 'home_shots_target',
            'AST': 'away_shots_target',
            'HF': 'home_fouls',
            'AF': 'away_fouls',
            'HC': 'home_corners',
            'AC': 'away_corners',
            'HY': 'home_yellow',
            'AY': 'away_yellow',
            'HR': 'home_red',
            'AR': 'away_red',
            # Betting odds (Bet365)
            'B365H': 'odds_home',
            'B365D': 'odds_draw',
            'B365A': 'odds_away',
            # Market odds
            'AvgH': 'avg_odds_home',
            'AvgD': 'avg_odds_draw',
            'AvgA': 'avg_odds_away',
            # Over/Under
            'BbAv>2.5': 'avg_odds_over_2_5',
            'BbAv<2.5': 'avg_odds_under_2_5',
            # Asian Handicap
            'BbAHh': 'asian_handicap_line',
            'BbAvAHH': 'avg_ah_home',
            'BbAvAHA': 'avg_ah_away',
        }

        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

        # Parse date
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')

        return df

    def fetch_multiple_seasons(
        self,
        league: str = "premier_league",
        seasons: Optional[List[str]] = None,
        start_season: int = 2018
    ) -> pd.DataFrame:
        """
        Fetch multiple seasons of data.

        Args:
            league: League key
            seasons: List of season codes, or None to auto-generate from start_season
            start_season: Start year if seasons not provided

        Returns:
            Combined DataFrame
        """
        if seasons is None:
            # Generate season codes from start_season to current
            current_year = datetime.now().year
            seasons = []
            for year in range(start_season, current_year + 1):
                season_code = f"{str(year)[-2:]}{str(year + 1)[-2:]}"
                seasons.append(season_code)

        all_data = []
        for season in seasons:
            df = self.fetch_football_data_season(league, season)
            if not df.empty:
                all_data.append(df)

        if not all_data:
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)
        combined = combined.sort_values('date').reset_index(drop=True)

        logger.info(f"Combined {len(combined)} matches from {len(all_data)} seasons")
        return combined

    def fetch_fbref_data(
        self,
        league: str = "premier_league",
        season: str = "2023-2024"
    ) -> pd.DataFrame:
        """
        Fetch match data from FBref including xG.

        Args:
            league: League key
            season: Season string (e.g., '2023-2024')

        Returns:
            DataFrame with match data including xG
        """
        if not SOCCERDATA_AVAILABLE:
            logger.error("soccerdata package required for FBref data")
            return pd.DataFrame()

        fbref_league = self.FBREF_LEAGUES.get(league)
        if not fbref_league:
            logger.error(f"League {league} not supported for FBref")
            return pd.DataFrame()

        cache_key = f"{league}_{season}"
        if cache_key in self._fbref_cache:
            return self._fbref_cache[cache_key]

        try:
            fbref = sd.FBref(leagues=fbref_league, seasons=season)
            schedule = fbref.read_schedule()

            if schedule.empty:
                return pd.DataFrame()

            # Flatten multi-index if present
            if isinstance(schedule.columns, pd.MultiIndex):
                schedule.columns = ['_'.join(col).strip() for col in schedule.columns.values]

            # Standardize
            schedule = self._standardize_fbref_columns(schedule)
            schedule['league'] = league
            schedule['season'] = season

            self._fbref_cache[cache_key] = schedule

            logger.info(f"Fetched {len(schedule)} matches from FBref for {league} {season}")
            return schedule

        except Exception as e:
            logger.error(f"Error fetching FBref data: {e}")
            return pd.DataFrame()

    def _standardize_fbref_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize FBref column names."""
        # FBref column names vary, so we try multiple patterns
        column_mapping = {}

        for col in df.columns:
            col_lower = col.lower()
            if 'home' in col_lower and 'xg' in col_lower:
                column_mapping[col] = 'home_xg'
            elif 'away' in col_lower and 'xg' in col_lower:
                column_mapping[col] = 'away_xg'
            elif col_lower in ['home', 'home_team']:
                column_mapping[col] = 'home_team'
            elif col_lower in ['away', 'away_team']:
                column_mapping[col] = 'away_team'
            elif col_lower == 'date':
                column_mapping[col] = 'date'
            elif col_lower in ['score', 'result']:
                column_mapping[col] = 'score'

        df = df.rename(columns=column_mapping)

        # Parse score into goals
        if 'score' in df.columns:
            try:
                scores = df['score'].str.split('–|–|-', expand=True)
                if len(scores.columns) >= 2:
                    df['home_goals'] = pd.to_numeric(scores[0], errors='coerce')
                    df['away_goals'] = pd.to_numeric(scores[1], errors='coerce')
            except Exception:
                pass

        return df

    def get_team_form(
        self,
        matches_df: pd.DataFrame,
        team: str,
        n_matches: int = 5
    ) -> pd.DataFrame:
        """
        Get recent form for a team.

        Args:
            matches_df: DataFrame with match data
            team: Team name
            n_matches: Number of recent matches

        Returns:
            DataFrame with team's recent matches
        """
        home_matches = matches_df[matches_df['home_team'] == team].copy()
        home_matches['is_home'] = 1
        home_matches['team'] = team
        home_matches['opponent'] = home_matches['away_team']
        home_matches['goals_for'] = home_matches['home_goals']
        home_matches['goals_against'] = home_matches['away_goals']

        away_matches = matches_df[matches_df['away_team'] == team].copy()
        away_matches['is_home'] = 0
        away_matches['team'] = team
        away_matches['opponent'] = away_matches['home_team']
        away_matches['goals_for'] = away_matches['away_goals']
        away_matches['goals_against'] = away_matches['home_goals']

        all_matches = pd.concat([home_matches, away_matches])
        all_matches = all_matches.sort_values('date', ascending=False)

        return all_matches.head(n_matches)

    def prepare_team_game_logs(
        self,
        matches_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Convert match data to team game logs format for feature engineering.

        Args:
            matches_df: DataFrame with match data

        Returns:
            DataFrame with one row per team per game
        """
        all_logs = []

        for _, match in matches_df.iterrows():
            # Home team record
            home_log = {
                'date': match.get('date'),
                'team': match.get('home_team'),
                'opponent': match.get('away_team'),
                'is_home': 1,
                'goals_for': match.get('home_goals'),
                'goals_against': match.get('away_goals'),
                'shots': match.get('home_shots'),
                'shots_on_target': match.get('home_shots_target'),
                'shots_against': match.get('away_shots'),
                'shots_on_target_against': match.get('away_shots_target'),
                'corners': match.get('home_corners'),
                'fouls': match.get('home_fouls'),
                'xg': match.get('home_xg'),
                'xga': match.get('away_xg'),
                'league': match.get('league'),
                'season': match.get('season'),
            }

            # Away team record
            away_log = {
                'date': match.get('date'),
                'team': match.get('away_team'),
                'opponent': match.get('home_team'),
                'is_home': 0,
                'goals_for': match.get('away_goals'),
                'goals_against': match.get('home_goals'),
                'shots': match.get('away_shots'),
                'shots_on_target': match.get('away_shots_target'),
                'shots_against': match.get('home_shots'),
                'shots_on_target_against': match.get('home_shots_target'),
                'corners': match.get('away_corners'),
                'fouls': match.get('away_fouls'),
                'xg': match.get('away_xg'),
                'xga': match.get('home_xg'),
                'league': match.get('league'),
                'season': match.get('season'),
            }

            all_logs.extend([home_log, away_log])

        df = pd.DataFrame(all_logs)
        df = df.sort_values(['team', 'date']).reset_index(drop=True)

        # Convert to numeric
        numeric_cols = ['goals_for', 'goals_against', 'shots', 'shots_on_target',
                       'shots_against', 'shots_on_target_against', 'corners',
                       'fouls', 'xg', 'xga']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    def get_historical_data(
        self,
        leagues: Optional[List[str]] = None,
        start_season: int = 2018
    ) -> pd.DataFrame:
        """
        Get historical data for multiple leagues.

        Args:
            leagues: List of league keys (default: top 5 leagues)
            start_season: Starting season year

        Returns:
            Combined DataFrame with all matches
        """
        if leagues is None:
            leagues = ["premier_league", "la_liga", "bundesliga", "serie_a", "ligue_1"]

        all_data = []

        for league in leagues:
            df = self.fetch_multiple_seasons(league, start_season=start_season)
            if not df.empty:
                all_data.append(df)

        if not all_data:
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)
        combined = combined.sort_values('date').reset_index(drop=True)

        logger.info(f"Total: {len(combined)} matches across {len(leagues)} leagues")
        return combined

    def get_upcoming_fixtures(self, league: str = "premier_league") -> pd.DataFrame:
        """
        Get upcoming fixtures (requires live API or scraping).

        For now, returns empty - this will be implemented in task #2 (live data).
        """
        logger.info("Upcoming fixtures will be available after live data API integration")
        return pd.DataFrame()

    def merge_with_xg(
        self,
        basic_df: pd.DataFrame,
        xg_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge basic match data with xG data from FBref.

        Args:
            basic_df: DataFrame from football-data.co.uk
            xg_df: DataFrame from FBref with xG

        Returns:
            Merged DataFrame
        """
        if basic_df.empty or xg_df.empty:
            return basic_df

        # Standardize team names for matching
        # This is tricky because sources use different names
        # For now, try to match on date + home team

        merged = basic_df.copy()

        # Create lookup from xG data
        if 'home_xg' in xg_df.columns and 'date' in xg_df.columns:
            xg_lookup = xg_df.set_index(['date', 'home_team'])[['home_xg', 'away_xg']].to_dict('index')

            def get_xg(row):
                key = (row['date'], row['home_team'])
                if key in xg_lookup:
                    return xg_lookup[key].get('home_xg'), xg_lookup[key].get('away_xg')
                return None, None

            merged[['home_xg', 'away_xg']] = merged.apply(
                lambda r: pd.Series(get_xg(r)), axis=1
            )

        return merged

    def save_data(self, df: pd.DataFrame, filename: str) -> Path:
        """Save DataFrame to parquet file."""
        filepath = self.data_dir / f"{filename}.parquet"
        df.to_parquet(filepath, index=False)
        logger.info(f"Saved data to {filepath}")
        return filepath

    def load_data(self, filename: str) -> pd.DataFrame:
        """Load DataFrame from parquet file."""
        filepath = self.data_dir / f"{filename}.parquet"
        if filepath.exists():
            return pd.read_parquet(filepath)
        return pd.DataFrame()


def fetch_all_soccer_data(start_season: int = 2018) -> Dict[str, pd.DataFrame]:
    """
    Convenience function to fetch all available soccer data.

    Args:
        start_season: Starting season year

    Returns:
        Dict with 'matches' and 'team_logs' DataFrames
    """
    fetcher = SoccerDataFetcher()

    # Fetch historical match data
    matches = fetcher.get_historical_data(start_season=start_season)

    if matches.empty:
        logger.warning("No match data fetched")
        return {"matches": pd.DataFrame(), "team_logs": pd.DataFrame()}

    # Convert to team game logs for feature engineering
    team_logs = fetcher.prepare_team_game_logs(matches)

    # Save to disk
    fetcher.save_data(matches, "soccer_matches")
    fetcher.save_data(team_logs, "soccer_team_logs")

    return {
        "matches": matches,
        "team_logs": team_logs
    }
