-- SGP Correlations (learned from data or rule-based)
CREATE TABLE IF NOT EXISTS sgp_correlations (
    id SERIAL PRIMARY KEY,
    sport VARCHAR(50) NOT NULL,
    leg1_type VARCHAR(50) NOT NULL,  -- 'team_spread', 'player_points', 'total_over', etc.
    leg2_type VARCHAR(50) NOT NULL,
    correlation_coefficient FLOAT NOT NULL,  -- -1 to 1
    sample_size INT DEFAULT 0,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(sport, leg1_type, leg2_type)
);

-- Index for fast lookup
CREATE INDEX IF NOT EXISTS idx_sgp_corr_lookup ON sgp_correlations(sport, leg1_type, leg2_type);
