-- Arbitrage History
CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(50) NOT NULL, -- The Odds API event ID
    sport VARCHAR(50) NOT NULL,
    market_type VARCHAR(50) NOT NULL, -- h2h, spreads, totals
    opportunity_type VARCHAR(50) NOT NULL, -- arbitrage, middle, low_hold
    
    book1 VARCHAR(50) NOT NULL,
    selection1 VARCHAR(100) NOT NULL,
    odds1_american INTEGER,
    odds1_decimal FLOAT NOT NULL,
    line1 FLOAT,
    
    book2 VARCHAR(50) NOT NULL,
    selection2 VARCHAR(100) NOT NULL,
    odds2_american INTEGER,
    odds2_decimal FLOAT NOT NULL,
    line2 FLOAT,
    
    -- Side 3 (for 3-way markets like soccer draw)
    book3 VARCHAR(50),
    selection3 VARCHAR(100),
    odds3_american INTEGER,
    odds3_decimal FLOAT,
    
    profit_pct FLOAT NOT NULL,
    stake1_pct FLOAT,
    stake2_pct FLOAT,
    stake3_pct FLOAT,
    middle_size FLOAT,
    combined_hold FLOAT,
    
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    
    UNIQUE(game_id, market_type, book1, book2, book3, selection1, selection2, selection3, line1, line2)
);

-- Index for active arbs
CREATE INDEX IF NOT EXISTS idx_active_arbs ON arbitrage_opportunities(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_arb_game_id ON arbitrage_opportunities(game_id);
