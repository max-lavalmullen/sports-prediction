# Sports Prediction Platform - System Architecture

## Executive Summary

A comprehensive, real-time sports prediction system covering NFL, NBA, MLB, and Soccer (EPL+) with predictions for moneylines, spreads, totals, player props, and same-game parlay correlations. Built for both profitable betting edge detection and research/analysis.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA INGESTION LAYER                                │
├─────────────────┬─────────────────┬─────────────────┬──────────────────────────┤
│   Odds APIs     │  Stats APIs     │  News Pipeline  │   Scraping Workers       │
│  (WebSocket)    │  (REST/Batch)   │  (NLP/Streaming)│   (Playwright/BS4)       │
│  - OpticOdds    │  - Sportradar   │  - Twitter/X    │   - ESPN                 │
│  - Unabated     │  - StatsBomb    │  - Reddit       │   - Team sites           │
│  - The Odds API │  - Free APIs    │  - News APIs    │   - Injury reports       │
└────────┬────────┴────────┬────────┴────────┬────────┴─────────────┬────────────┘
         │                 │                 │                      │
         ▼                 ▼                 ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           MESSAGE QUEUE (Redis Streams)                          │
│                    Real-time event streaming & job orchestration                 │
└─────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA STORAGE LAYER                                  │
├──────────────────────────┬──────────────────────────┬───────────────────────────┤
│     PostgreSQL +         │        Redis             │      Object Storage       │
│     TimescaleDB          │     (Hot Cache)          │      (Model Artifacts)    │
│  - Historical data       │  - Live odds             │  - Trained models         │
│  - Player stats          │  - Session state         │  - Feature stores         │
│  - Game results          │  - Predictions cache     │  - Backtest results       │
│  - Odds history (hyper)  │  - Real-time alerts      │  - Raw scraped data       │
└──────────────────────────┴──────────────────────────┴───────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           FEATURE ENGINEERING LAYER                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Sport-Specific Feature Pipelines:                                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │     NFL      │ │     NBA      │ │     MLB      │ │   Soccer     │            │
│  │  - EPA/play  │ │  - Pace adj  │ │  - wOBA      │ │  - xG/xA     │            │
│  │  - DVOA      │ │  - ORtg/DRtg │ │  - FIP/ERA   │ │  - xGChain   │            │
│  │  - Success%  │ │  - PIE       │ │  - wRC+      │ │  - PPDA      │            │
│  │  - Air yards │ │  - USG%      │ │  - Barrel%   │ │  - xT        │            │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘            │
│                                                                                  │
│  Cross-Sport Features: Rolling averages, opponent adjustments, rest days,        │
│  travel distance, weather, venue effects, referee/umpire tendencies             │
└─────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ML MODEL LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    ENSEMBLE ARCHITECTURE                                 │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │    │
│  │  │  Specialized Models (Per Sport)                                  │    │    │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                │    │    │
│  │  │  │NFL Model│ │NBA Model│ │MLB Model│ │Soccer   │                │    │    │
│  │  │  │XGBoost+ │ │LightGBM+│ │CatBoost+│ │XGBoost+ │                │    │    │
│  │  │  │Transformer│NN       │ │NN       │ │CNN-LSTM │                │    │    │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘                │    │    │
│  │  └─────────────────────────────────────────────────────────────────┘    │    │
│  │                              ▼                                           │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │    │
│  │  │  Unified Multi-Sport Model                                       │    │    │
│  │  │  - Shared embedding layer for cross-sport patterns              │    │    │
│  │  │  - Sport-specific output heads                                   │    │    │
│  │  │  - Transfer learning between similar sports                      │    │    │
│  │  └─────────────────────────────────────────────────────────────────┘    │    │
│  │                              ▼                                           │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │    │
│  │  │  Meta-Learner (Stacked Ensemble)                                 │    │    │
│  │  │  - MLP combining all model outputs                               │    │    │
│  │  │  - Calibrated probability outputs                                │    │    │
│  │  │  - Confidence intervals via conformal prediction                 │    │    │
│  │  └─────────────────────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  Prediction Types:                                                               │
│  ├── Game Outcomes (Win/Lose/Draw probabilities)                                │
│  ├── Spread Predictions (margin + confidence intervals)                         │
│  ├── Totals Predictions (combined score distribution)                           │
│  ├── Player Props (individual stat projections)                                 │
│  └── SGP Correlations (copula-based dependency modeling)                        │
└─────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API LAYER (FastAPI)                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  REST Endpoints:                    WebSocket Endpoints:                         │
│  - GET /predictions/{sport}         - /ws/live-odds                             │
│  - GET /players/{id}/props          - /ws/predictions                           │
│  - GET /backtest/run                - /ws/alerts                                │
│  - GET /analytics/{team}            - /ws/simulation                            │
│  - POST /bets/track                                                             │
│  - GET /bankroll/stats                                                          │
└─────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React + TypeScript)                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  Live Dashboard │  │  Backtesting    │  │  Analytics      │                  │
│  │  - Odds grid    │  │  - Strategy     │  │  - Team pages   │                  │
│  │  - Value alerts │  │    builder      │  │  - Player cards │                  │
│  │  - Model vs line│  │  - ROI charts   │  │  - Trend graphs │                  │
│  │  - Confidence   │  │  - Drawdown     │  │  - Comparisons  │                  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                  │
│                                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  Bet Tracker    │  │  Simulation     │  │  Settings       │                  │
│  │  - Log bets     │  │  - Monte Carlo  │  │  - API keys     │                  │
│  │  - P/L charts   │  │  - Accuracy     │  │  - Notifications│                  │
│  │  - Kelly sizing │  │    over time    │  │  - Model config │                  │
│  │  - Performance  │  │  - What-if      │  │  - Data sources │                  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                  │
│                                                                                  │
│  UI Framework: React 18 + TypeScript + TanStack Query + Zustand                 │
│  Charts: Recharts + D3.js for custom visualizations                             │
│  Components: shadcn/ui + Tailwind CSS                                           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Sources

### 2.1 Odds Data (Real-Time)

| Provider | Type | Coverage | Cost | Latency |
|----------|------|----------|------|---------|
| [OpticOdds](https://opticodds.com/) | WebSocket | 200+ books, all sports | $$$ | <1s |
| [Unabated API](https://unabated.com/get-unabated-api) | WebSocket | 25+ books, props | $$ | <1s |
| [The Odds API](https://the-odds-api.com/) | REST | 15+ books, major markets | $ | 5-10s |
| [OddsJam](https://oddsjam.com/odds-api) | WebSocket | Props, alternates | $$$ | <1s |

**Recommendation**: Start with The Odds API (affordable), upgrade to OpticOdds/Unabated for live betting edge.

### 2.2 Statistics Data

| Provider | Sports | Data Quality | Cost |
|----------|--------|--------------|------|
| Sportradar | All | Professional-grade | $$$$$ (Enterprise) |
| StatsBomb | Soccer | Best-in-class event data | $$$ |
| [SportsDataIO](https://sportsdata.io/) | All | Good, play-by-play | $$ |
| nflfastR/nflverse | NFL | Excellent, free | Free |
| NBA API (unofficial) | NBA | Play-by-play | Free |
| pybaseball | MLB | Statcast data | Free |
| FBref | Soccer | Advanced stats | Free (scrape) |

### 2.3 News & Injury Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    NEWS AGGREGATION PIPELINE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Sources:                                                        │
│  ├── Official injury reports (team sites, league APIs)          │
│  ├── Beat reporter Twitter/X accounts (curated list)            │
│  ├── Reddit (r/nfl, r/nba, r/baseball, r/soccer)               │
│  ├── News APIs (NewsAPI, Google News)                           │
│  └── Rotowire/Rotoworld (injury news)                           │
│                                                                  │
│  NLP Pipeline:                                                   │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │
│  │ Ingest   │──▶│   NER    │──▶│ Classify │──▶│ Extract  │     │
│  │ Stream   │   │ (Player, │   │ (Injury  │   │ (Status, │     │
│  │          │   │  Team)   │   │  Type)   │   │  Impact) │     │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘     │
│                                                                  │
│  Models: Fine-tuned RoBERTa for sports NER + classification     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. ML Model Architecture

### 3.1 Sport-Specific Models

#### NFL Model
```python
# Key features
features = [
    # Efficiency metrics
    'off_epa_per_play', 'def_epa_per_play', 'success_rate',
    'explosive_play_rate', 'turnover_margin',

    # Passing
    'cpoe', 'air_yards_share', 'adot', 'pressure_rate',

    # Rushing
    'rush_epa', 'yards_before_contact', 'stuff_rate',

    # Situational
    'red_zone_td_rate', 'third_down_rate', 'fourth_down_aggression',

    # Context
    'rest_days', 'travel_distance', 'dome_vs_outdoor',
    'temperature', 'wind_speed', 'elevation'
]

# Model: XGBoost + Transformer ensemble
# XGBoost handles tabular features
# Transformer processes play sequence embeddings
```

#### NBA Model
```python
features = [
    # Team efficiency (pace-adjusted per 100 possessions)
    'off_rating', 'def_rating', 'net_rating',
    'pace', 'true_shooting_pct',

    # Four factors
    'efg_pct', 'tov_pct', 'orb_pct', 'ft_rate',

    # Advanced
    'assist_rate', 'three_point_rate', 'rim_frequency',
    'mid_range_frequency', 'transition_frequency',

    # Opponent-adjusted
    'sos_adj_off_rating', 'sos_adj_def_rating',

    # Context
    'back_to_back', 'days_rest', 'travel_miles',
    'altitude_change', 'home_court_strength'
]

# Model: LightGBM + Graph Neural Network
# GNN captures player interaction patterns
```

#### MLB Model
```python
features = [
    # Pitcher
    'fip', 'xfip', 'siera', 'k_rate', 'bb_rate',
    'gb_rate', 'hr_fb_rate', 'stuff_plus', 'location_plus',

    # Batter
    'woba', 'xwoba', 'wrc_plus', 'barrel_rate',
    'hard_hit_rate', 'chase_rate', 'whiff_rate',

    # Matchup
    'pitcher_vs_handedness', 'batter_vs_pitch_type',
    'park_factor', 'umpire_k_rate', 'umpire_zone_size',

    # Context
    'days_rest_pitcher', 'bullpen_usage_last_3',
    'temperature', 'humidity', 'wind_direction'
]

# Model: CatBoost (handles categoricals well) + Neural Net
```

#### Soccer Model
```python
features = [
    # Expected metrics
    'xg', 'xga', 'xg_diff', 'npxg',
    'xa', 'xg_chain', 'xg_buildup',

    # Possession
    'possession_pct', 'ppda', 'oppda',
    'deep_completions', 'progressive_passes',

    # Defensive
    'tackles_won', 'interceptions', 'blocks',
    'clearances', 'pressures', 'pressure_success',

    # Set pieces
    'corner_xg', 'freekick_xg', 'penalty_xg',

    # Context
    'fixture_congestion', 'travel_distance',
    'league_position', 'recent_form_xg'
]

# Model: XGBoost + CNN-LSTM for sequence patterns
```

### 3.2 Player Props Model

```python
class PlayerPropsModel:
    """
    Predicts individual player statistics with uncertainty.
    Uses quantile regression for full distribution.
    """

    def __init__(self):
        self.quantiles = [0.1, 0.25, 0.5, 0.75, 0.9]

    def features(self, player_id, game_context):
        return {
            # Historical performance
            'season_avg': ...,
            'last_5_avg': ...,
            'last_10_avg': ...,
            'home_away_split': ...,

            # Matchup
            'opponent_defense_rank': ...,
            'opponent_pace': ...,
            'position_matchup_score': ...,

            # Team context
            'teammate_injury_boost': ...,  # More usage if star out
            'projected_game_script': ...,   # Blowout = fewer minutes
            'vegas_total': ...,             # Higher total = more stats

            # Prop-specific
            'market_line': ...,
            'historical_over_rate': ...
        }

    def predict(self, features):
        # Returns full distribution
        return {
            'p10': model.predict(features, quantile=0.1),
            'p25': model.predict(features, quantile=0.25),
            'median': model.predict(features, quantile=0.5),
            'p75': model.predict(features, quantile=0.75),
            'p90': model.predict(features, quantile=0.9),
            'mean': model.predict(features, quantile='mean'),
            'std': calculate_std_from_quantiles(...)
        }
```

### 3.3 Same-Game Parlay Correlation Model

```python
class SGPCorrelationModel:
    """
    Models correlations between outcomes in the same game.
    Uses copulas to capture dependency structures.
    """

    def __init__(self):
        # Correlation matrices per game type
        self.correlation_pairs = [
            ('player_points', 'team_total'),
            ('player_rebounds', 'game_pace'),
            ('qb_passing_yards', 'team_spread'),
            ('pitcher_strikeouts', 'game_under'),
        ]

    def estimate_correlation(self, outcome_a, outcome_b, game_context):
        """
        Estimate correlation coefficient between two outcomes.
        Positive correlation = both likely to hit together.
        """
        # Historical co-occurrence analysis
        # Conditional probability modeling
        # Copula fitting for tail dependencies
        pass

    def price_parlay(self, legs: List[Bet], correlations: Matrix):
        """
        Calculate fair odds for correlated parlay.
        Compare to book price to find edge.
        """
        # Adjust naive multiplication by correlation factor
        naive_prob = prod([leg.probability for leg in legs])
        adjusted_prob = apply_copula_adjustment(naive_prob, correlations)
        return adjusted_prob
```

### 3.4 Ensemble Meta-Learner

```python
class MetaLearner:
    """
    Stacked ensemble combining all model outputs.
    Trained on out-of-fold predictions.
    """

    def __init__(self):
        self.base_models = {
            'sport_specific': SportSpecificEnsemble(),
            'unified': UnifiedMultiSportModel(),
            'player_props': PlayerPropsModel(),
            'market_signals': MarketModel(),  # Uses odds movement
        }
        self.meta_model = CalibratedMLP()

    def predict(self, game):
        # Get predictions from all base models
        base_predictions = {
            name: model.predict(game)
            for name, model in self.base_models.items()
        }

        # Stack and predict
        stacked_features = self.stack(base_predictions)

        # Calibrated probability output
        probs = self.meta_model.predict_proba(stacked_features)

        # Conformal prediction for confidence intervals
        intervals = self.conformal_predictor.predict(stacked_features)

        return {
            'probabilities': probs,
            'confidence_intervals': intervals,
            'model_agreement': self.calculate_agreement(base_predictions),
            'feature_importance': self.explain(stacked_features)
        }
```

---

## 4. Database Schema

### 4.1 Core Tables (PostgreSQL)

```sql
-- Teams
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    sport VARCHAR(10) NOT NULL,
    name VARCHAR(100) NOT NULL,
    abbreviation VARCHAR(10),
    league VARCHAR(50),
    conference VARCHAR(50),
    division VARCHAR(50),
    venue_id INTEGER REFERENCES venues(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Players
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    sport VARCHAR(10) NOT NULL,
    name VARCHAR(100) NOT NULL,
    team_id INTEGER REFERENCES teams(id),
    position VARCHAR(20),
    jersey_number INTEGER,
    birth_date DATE,
    height_inches INTEGER,
    weight_lbs INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    external_ids JSONB,  -- {espn_id, sportradar_id, etc}
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Games
CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    sport VARCHAR(10) NOT NULL,
    external_id VARCHAR(50),
    home_team_id INTEGER REFERENCES teams(id),
    away_team_id INTEGER REFERENCES teams(id),
    scheduled_time TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) DEFAULT 'scheduled',
    home_score INTEGER,
    away_score INTEGER,
    venue_id INTEGER REFERENCES venues(id),
    weather_conditions JSONB,
    officials JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Player Stats (per game)
CREATE TABLE player_game_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id),
    game_id INTEGER REFERENCES games(id),
    stats JSONB NOT NULL,  -- Sport-specific stats
    minutes_played DECIMAL(5,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(player_id, game_id)
);

-- Predictions
CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id),
    prediction_type VARCHAR(50) NOT NULL,  -- moneyline, spread, total, prop
    model_version VARCHAR(50) NOT NULL,
    prediction JSONB NOT NULL,  -- {home_prob, away_prob, spread, etc}
    confidence JSONB,  -- {lower, upper, confidence_level}
    feature_importance JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bets (tracking)
CREATE TABLE bets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    game_id INTEGER REFERENCES games(id),
    prediction_id INTEGER REFERENCES predictions(id),
    bet_type VARCHAR(50) NOT NULL,
    selection VARCHAR(100) NOT NULL,
    odds_american INTEGER NOT NULL,
    odds_decimal DECIMAL(6,3) NOT NULL,
    stake DECIMAL(10,2) NOT NULL,
    potential_payout DECIMAL(10,2) NOT NULL,
    result VARCHAR(20),  -- win, loss, push, pending
    profit_loss DECIMAL(10,2),
    sportsbook VARCHAR(50),
    placed_at TIMESTAMPTZ DEFAULT NOW(),
    settled_at TIMESTAMPTZ
);
```

### 4.2 Time-Series Tables (TimescaleDB)

```sql
-- Odds history (hypertable)
CREATE TABLE odds_history (
    time TIMESTAMPTZ NOT NULL,
    game_id INTEGER NOT NULL,
    sportsbook VARCHAR(50) NOT NULL,
    market_type VARCHAR(50) NOT NULL,  -- moneyline, spread, total
    selection VARCHAR(50) NOT NULL,    -- home, away, over, under
    odds_american INTEGER,
    odds_decimal DECIMAL(6,3),
    line DECIMAL(5,2),  -- spread or total line
    PRIMARY KEY (time, game_id, sportsbook, market_type, selection)
);

SELECT create_hypertable('odds_history', 'time');

-- Create continuous aggregates for analysis
CREATE MATERIALIZED VIEW odds_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    game_id,
    market_type,
    selection,
    AVG(odds_decimal) as avg_odds,
    MIN(odds_decimal) as min_odds,
    MAX(odds_decimal) as max_odds,
    COUNT(DISTINCT sportsbook) as num_books
FROM odds_history
GROUP BY bucket, game_id, market_type, selection;

-- Player props odds
CREATE TABLE prop_odds_history (
    time TIMESTAMPTZ NOT NULL,
    game_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    sportsbook VARCHAR(50) NOT NULL,
    prop_type VARCHAR(50) NOT NULL,  -- points, rebounds, assists, etc
    line DECIMAL(5,2) NOT NULL,
    over_odds INTEGER,
    under_odds INTEGER,
    PRIMARY KEY (time, game_id, player_id, sportsbook, prop_type)
);

SELECT create_hypertable('prop_odds_history', 'time');
```

---

## 5. API Design

### 5.1 REST Endpoints

```yaml
# Predictions
GET /api/v1/predictions
  ?sport=nba
  &date=2024-01-15
  &type=spread,total,moneyline

GET /api/v1/predictions/{game_id}
  Response: {
    game: {...},
    predictions: {
      moneyline: {home_prob: 0.62, away_prob: 0.38, confidence: [0.58, 0.66]},
      spread: {predicted: -4.5, confidence: [-7.5, -1.5]},
      total: {predicted: 218.5, confidence: [212, 225]}
    },
    value_bets: [...],
    model_explanation: {...}
  }

# Player Props
GET /api/v1/props/{player_id}
  ?game_id=123
  Response: {
    player: {...},
    props: [
      {type: 'points', projection: {p10: 15, median: 22, p90: 31}, line: 23.5, edge: -0.02},
      {type: 'rebounds', projection: {...}, line: 7.5, edge: 0.08}
    ]
  }

# Backtesting
POST /api/v1/backtest
  Body: {
    strategy: {
      sport: 'nba',
      bet_types: ['spread'],
      min_edge: 0.03,
      kelly_fraction: 0.25
    },
    date_range: {start: '2023-01-01', end: '2024-01-01'}
  }
  Response: {
    summary: {roi: 0.08, total_bets: 342, win_rate: 0.54},
    equity_curve: [...],
    monthly_breakdown: [...],
    max_drawdown: 0.12
  }

# Bet Tracking
POST /api/v1/bets
  Body: {game_id, bet_type, selection, odds, stake, sportsbook}

GET /api/v1/bets/stats
  Response: {
    total_profit: 2340.50,
    roi: 0.067,
    by_sport: {...},
    by_bet_type: {...},
    recent_form: [...]
  }

# Analytics
GET /api/v1/analytics/teams/{team_id}
GET /api/v1/analytics/players/{player_id}
GET /api/v1/analytics/matchups/{game_id}
```

### 5.2 WebSocket Endpoints

```typescript
// Live odds stream
ws://localhost:8000/ws/odds
  -> Subscribe: {sports: ['nba', 'nfl'], markets: ['spread', 'total']}
  <- Updates: {game_id, sportsbook, market, odds, timestamp}

// Real-time predictions
ws://localhost:8000/ws/predictions
  -> Subscribe: {games: [123, 456]}
  <- Updates: {game_id, prediction_type, new_prediction, confidence}

// Value alerts
ws://localhost:8000/ws/alerts
  -> Subscribe: {min_edge: 0.03, sports: ['nba']}
  <- Alert: {game_id, bet_type, edge: 0.045, odds, expires_in: 30}
```

---

## 6. Frontend Architecture

### 6.1 Tech Stack

```
React 18 + TypeScript
├── State Management: Zustand (simple) + TanStack Query (server state)
├── Routing: React Router v6
├── UI Components: shadcn/ui + Tailwind CSS
├── Charts: Recharts + D3.js (custom)
├── Real-time: Native WebSocket + custom hooks
├── Forms: React Hook Form + Zod validation
└── Build: Vite
```

### 6.2 Component Structure

```
src/
├── components/
│   ├── dashboard/
│   │   ├── LiveOddsGrid.tsx       # Real-time odds comparison
│   │   ├── ValueAlerts.tsx        # Edge notifications
│   │   ├── PredictionCard.tsx     # Model vs line display
│   │   └── ConfidenceMeter.tsx    # Probability visualization
│   │
│   ├── backtesting/
│   │   ├── StrategyBuilder.tsx    # Configure backtest params
│   │   ├── EquityCurve.tsx        # P/L over time chart
│   │   ├── DrawdownChart.tsx      # Risk visualization
│   │   └── ResultsTable.tsx       # Detailed bet history
│   │
│   ├── analytics/
│   │   ├── TeamProfile.tsx        # Team stats dashboard
│   │   ├── PlayerCard.tsx         # Player analysis
│   │   ├── MatchupAnalysis.tsx    # H2H comparison
│   │   └── TrendCharts.tsx        # Rolling performance
│   │
│   ├── betting/
│   │   ├── BetSlip.tsx            # Track new bets
│   │   ├── BetHistory.tsx         # Past bets table
│   │   ├── BankrollStats.tsx      # P/L, ROI, Kelly
│   │   └── PerformanceCharts.tsx  # Results visualization
│   │
│   ├── simulation/
│   │   ├── MonteCarloSim.tsx      # Run simulations
│   │   ├── AccuracyTracker.tsx    # Model accuracy over time
│   │   └── WhatIfAnalysis.tsx     # Scenario testing
│   │
│   └── shared/
│       ├── ProbabilityDist.tsx    # Distribution visualization
│       ├── OddsDisplay.tsx        # American/Decimal toggle
│       ├── SportSelector.tsx      # Multi-sport nav
│       └── DatePicker.tsx         # Game date selection
│
├── hooks/
│   ├── useWebSocket.ts            # Real-time connection
│   ├── usePredictions.ts          # TanStack Query wrappers
│   ├── useOdds.ts
│   └── useBetting.ts
│
├── stores/
│   ├── settingsStore.ts           # User preferences
│   ├── betSlipStore.ts            # Current selections
│   └── alertStore.ts              # Notification state
│
└── pages/
    ├── Dashboard.tsx
    ├── Backtesting.tsx
    ├── Analytics.tsx
    ├── BetTracker.tsx
    ├── Simulation.tsx
    └── Settings.tsx
```

### 6.3 Key UI Components

#### Probability Distribution Display
```typescript
interface ProbabilityDisplayProps {
  prediction: {
    probability: number;
    confidence_interval: [number, number];
    ev: number;  // Expected value in units
  };
  marketOdds: number;
  displayMode: 'distribution' | 'stars' | 'ev' | 'all';
}

// Shows:
// - Bell curve with confidence interval shading
// - Star rating (1-5) based on edge size
// - EV in units (+0.5u, -0.2u)
// - All three combined for power users
```

#### Live Odds Grid
```typescript
// Real-time updating grid showing:
// - Model prediction vs current line
// - Edge calculation (model prob - implied prob)
// - Odds from multiple sportsbooks
// - Best available odds highlighted
// - Historical line movement sparkline
```

---

## 7. Training Pipeline

### 7.1 MLOps Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     TRAINING PIPELINE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Data Preparation                                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ - Feature engineering with time-based splits             │   │
│  │ - No data leakage (strict temporal cutoffs)              │   │
│  │ - Walk-forward validation setup                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ▼                                      │
│  2. Model Training                                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ - Local: M4 Pro for XGBoost/LightGBM                     │   │
│  │ - Cloud GPU: Neural networks, transformers                │   │
│  │ - Hyperparameter tuning: Optuna                          │   │
│  │ - Cross-validation: TimeSeriesSplit                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ▼                                      │
│  3. Model Evaluation                                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ - Accuracy metrics (AUC, Brier score)                    │   │
│  │ - Calibration (reliability diagrams)                     │   │
│  │ - Profitability (ROI on historical odds)                 │   │
│  │ - Comparison to closing line value (CLV)                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ▼                                      │
│  4. Model Registry                                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ - Version control with MLflow                            │   │
│  │ - A/B testing framework                                  │   │
│  │ - Rollback capability                                    │   │
│  │ - Performance monitoring                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Retraining Schedule

| Component | Frequency | Trigger |
|-----------|-----------|---------|
| Base models | Weekly | End of week games |
| Player embeddings | Daily | After daily games |
| Calibration layer | Daily | With new outcomes |
| Full retrain | Monthly | Significant drift detected |
| Emergency retrain | As needed | Major roster changes, injuries |

---

## 8. Backtesting Framework

### 8.1 Core Principles

```python
class BacktestEngine:
    """
    Proper backtesting with no data leakage.
    """

    def __init__(self, config: BacktestConfig):
        self.config = config

    def run(self, strategy: Strategy, data: DataFrame) -> BacktestResults:
        results = []

        # Walk-forward simulation
        for date in self.get_betting_dates(data):
            # 1. Get model predictions (trained only on past data)
            predictions = self.get_predictions(date, lookback_only=True)

            # 2. Get odds available at decision time (not closing)
            available_odds = self.get_odds_at_time(date, time='decision')

            # 3. Apply strategy to identify bets
            bets = strategy.select_bets(predictions, available_odds)

            # 4. Apply stake sizing (Kelly, flat, etc)
            bets = strategy.size_bets(bets, self.current_bankroll)

            # 5. Record hypothetical bets
            for bet in bets:
                results.append({
                    'date': date,
                    'bet': bet,
                    'odds_used': bet.odds,
                    'closing_odds': self.get_closing_odds(bet),
                    'result': self.get_result(bet),
                    'profit': self.calculate_profit(bet)
                })

            # 6. Update bankroll
            self.update_bankroll(results[-len(bets):])

        return BacktestResults(results)

    def calculate_metrics(self, results: BacktestResults) -> dict:
        return {
            'total_bets': len(results),
            'win_rate': results.wins / results.total,
            'roi': results.profit / results.total_staked,
            'yield': results.profit / results.total_risked,
            'max_drawdown': self.calculate_drawdown(results),
            'sharpe_ratio': self.calculate_sharpe(results),
            'clv': self.calculate_closing_line_value(results),
            'by_sport': self.breakdown_by_sport(results),
            'by_bet_type': self.breakdown_by_type(results),
            'monthly_returns': self.monthly_breakdown(results),
            'equity_curve': self.generate_equity_curve(results)
        }
```

### 8.2 Simulation Engine

```python
class MonteCarloSimulator:
    """
    Simulate future performance with uncertainty.
    """

    def simulate(
        self,
        strategy: Strategy,
        n_simulations: int = 10000,
        n_bets: int = 1000
    ) -> SimulationResults:

        outcomes = []

        for _ in range(n_simulations):
            bankroll = self.initial_bankroll

            for _ in range(n_bets):
                # Sample bet from historical distribution
                bet = self.sample_bet(strategy)

                # Simulate outcome based on edge and variance
                outcome = self.simulate_outcome(bet)

                # Update bankroll
                bankroll = self.update(bankroll, bet, outcome)

            outcomes.append(bankroll)

        return SimulationResults(
            median_outcome=np.median(outcomes),
            p5_outcome=np.percentile(outcomes, 5),
            p95_outcome=np.percentile(outcomes, 95),
            probability_of_ruin=sum(o <= 0 for o in outcomes) / len(outcomes),
            distribution=outcomes
        )
```

---

## 9. Deployment Architecture

### 9.1 Local Development (Phase 1)

```
┌─────────────────────────────────────────────────────────────────┐
│                     LOCAL DEVELOPMENT                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Docker Compose Stack:                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  PostgreSQL  │  │    Redis     │  │   Backend    │           │
│  │  TimescaleDB │  │   (Cache)    │  │   (FastAPI)  │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Frontend   │  │  ML Worker   │  │   Scheduler  │           │
│  │   (React)    │  │  (Training)  │  │   (Celery)   │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                  │
│  Local ports:                                                    │
│  - Frontend: http://localhost:3000                              │
│  - API: http://localhost:8000                                   │
│  - WebSocket: ws://localhost:8000/ws                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 Cloud Migration (Phase 2)

```
When ready to scale:
├── AWS / GCP / DigitalOcean
├── Kubernetes for orchestration
├── Managed PostgreSQL (RDS / Cloud SQL)
├── Managed Redis (ElastiCache / Memorystore)
├── GPU instances for training (spot/preemptible)
└── CDN for frontend (CloudFront / Cloud CDN)
```

---

## 10. Project Structure

```
sports-prediction-platform/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── predictions.py
│   │   │   │   ├── props.py
│   │   │   │   ├── backtest.py
│   │   │   │   ├── bets.py
│   │   │   │   └── analytics.py
│   │   │   └── websocket/
│   │   │       ├── odds.py
│   │   │       └── alerts.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── security.py
│   │   ├── models/
│   │   │   ├── game.py
│   │   │   ├── player.py
│   │   │   ├── prediction.py
│   │   │   └── bet.py
│   │   └── services/
│   │       ├── prediction_service.py
│   │       ├── odds_service.py
│   │       └── backtest_service.py
│   ├── ml/
│   │   ├── features/
│   │   │   ├── nfl_features.py
│   │   │   ├── nba_features.py
│   │   │   ├── mlb_features.py
│   │   │   └── soccer_features.py
│   │   ├── models/
│   │   │   ├── base_model.py
│   │   │   ├── ensemble.py
│   │   │   ├── player_props.py
│   │   │   └── sgp_correlation.py
│   │   ├── training/
│   │   │   ├── trainer.py
│   │   │   ├── evaluation.py
│   │   │   └── calibration.py
│   │   └── inference/
│   │       └── predictor.py
│   ├── data/
│   │   ├── scrapers/
│   │   ├── apis/
│   │   └── processors/
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── stores/
│   │   ├── pages/
│   │   ├── lib/
│   │   └── types/
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
└── README.md
```

---

## 11. Key Research Sources

### Academic Papers
- [Systematic Review of ML in Sports Betting](https://arxiv.org/html/2410.21484v1) - Comprehensive overview of techniques
- [Deep Learning for Sports Prediction](https://pmc.ncbi.nlm.nih.gov/articles/PMC12453701/) - CNN+Transformer hybrid approach
- [Model Calibration vs Accuracy](https://www.sciencedirect.com/science/article/pii/S266682702400015X) - Why calibration matters more
- [Stacked Ensemble for NBA](https://www.nature.com/articles/s41598-025-13657-1) - MLP meta-learner approach

### Data Sources
- [The Odds API](https://the-odds-api.com/) - Affordable real-time odds
- [OpticOdds](https://opticodds.com/) - Professional-grade streaming
- [Unabated API](https://unabated.com/get-unabated-api) - WebSocket props/live

### Tutorials & Guides
- [Building Sports Analytics Website](https://medium.com/@neilpierre24/a-guide-to-building-your-own-full-stack-sports-analytics-website-a9247cb3b99f) - Full-stack approach
- [Backtesting Sports Betting](https://medium.com/systematic-sports/backtesting-a-sports-betting-strategy-283833a5eca3) - Proper validation
- [Sports Betting Python Package](https://github.com/georgedouzas/sports-betting) - Open source tools

---

## 12. Security & Compliance

### 12.1 Data Security
- **API Key Management**: All external API keys (Odds API, Sportradar) stored in environment variables, never in code.
- **User Data**: Passwords hashed with bcrypt. Session tokens (JWT) with short expiry.
- **Encryption**: TLS for all data in transit. At-rest encryption for database volumes (Phase 2).

### 12.2 Operational Security
- **Rate Limiting**: Redis-backed rate limiter on API endpoints to prevent abuse.
- **Input Validation**: Strict Pydantic models for all incoming data to prevent injection attacks.
- **Sandboxing**: Model execution environments isolated to prevent arbitrary code execution from pickled models.

## 13. Responsible Gaming

The platform is designed for analysis and entertainment.
- **Bankroll Protection**: Built-in limits on max bet size suggestions (e.g., max 5% Kelly).
- **Reality Checks**: Optional notifications for time spent or potential losses.
- **Disclaimer**: Clear labeling that predictions are probabilistic and not guaranteed.
- **No Direct Betting**: The platform tracks bets but does *not* execute them on sportsbooks directly (compliance safe harbor).

---

## 14. Next Steps

1. **Set up development environment** (Docker, databases)
2. **Implement data ingestion** (start with free APIs)
3. **Build feature engineering pipelines** (one sport at a time)
4. **Train initial models** (XGBoost baseline)
5. **Create basic API** (predictions endpoint)
6. **Build MVP frontend** (odds grid + predictions)
7. **Add backtesting** (validate before betting real money)
8. **Iterate and improve** (add sports, models, features)