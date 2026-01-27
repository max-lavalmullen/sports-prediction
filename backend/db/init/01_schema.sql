-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Teams
CREATE TABLE IF NOT EXISTS teams (
    id SERIAL PRIMARY KEY,
    sport VARCHAR(10) NOT NULL,
    name VARCHAR(100) NOT NULL,
    abbreviation VARCHAR(10),
    league VARCHAR(50),
    conference VARCHAR(50),
    division VARCHAR(50),
    venue_id INTEGER, -- constraint added later if venue table exists, or ignored for now
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Venues (Added this as teams referenced it, though not explicitly in the snippet, it's good practice)
CREATE TABLE IF NOT EXISTS venues (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    city VARCHAR(100),
    state VARCHAR(50),
    country VARCHAR(50),
    capacity INTEGER,
    surface VARCHAR(50)
);

-- Add FK to teams if venues exists (or we can just leave it as integer for now if we don't populate venues immediately)
-- ALTER TABLE teams ADD CONSTRAINT fk_venue FOREIGN KEY (venue_id) REFERENCES venues(id);

-- Players
CREATE TABLE IF NOT EXISTS players (
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
CREATE TABLE IF NOT EXISTS games (
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
CREATE TABLE IF NOT EXISTS player_game_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id),
    game_id INTEGER REFERENCES games(id),
    stats JSONB NOT NULL,  -- Sport-specific stats
    minutes_played DECIMAL(5,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(player_id, game_id)
);

-- Predictions
CREATE TABLE IF NOT EXISTS predictions (
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
CREATE TABLE IF NOT EXISTS bets (
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

-- Time-Series Tables (TimescaleDB)

-- Odds history (hypertable)
CREATE TABLE IF NOT EXISTS odds_history (
    time TIMESTAMPTZ NOT NULL,
    game_id INTEGER NOT NULL,
    sportsbook VARCHAR(50) NOT NULL,
    market_type VARCHAR(50) NOT NULL,  -- moneyline, spread, total
    selection VARCHAR(50) NOT NULL,    -- home, away, over, under
    odds_american INTEGER,
    odds_decimal DECIMAL(6,3),
    line DECIMAL(5,2)  -- spread or total line
    -- PRIMARY KEY is complex in hypertables, usually (time, ...)
);

-- Create hypertable
SELECT create_hypertable('odds_history', 'time', if_not_exists => TRUE);

-- Player props odds
CREATE TABLE IF NOT EXISTS prop_odds_history (
    time TIMESTAMPTZ NOT NULL,
    game_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    sportsbook VARCHAR(50) NOT NULL,
    prop_type VARCHAR(50) NOT NULL,  -- points, rebounds, assists, etc
    line DECIMAL(5,2) NOT NULL,
    over_odds INTEGER,
    under_odds INTEGER
);

SELECT create_hypertable('prop_odds_history', 'time', if_not_exists => TRUE);

-- Continuous aggregates
-- Note: refresh policies would be added here in production

CREATE MATERIALIZED VIEW IF NOT EXISTS odds_hourly
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
