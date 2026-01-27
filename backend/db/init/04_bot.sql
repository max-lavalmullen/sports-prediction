-- Bot Execution Log
CREATE TABLE IF NOT EXISTS bot_executions (
    id VARCHAR(50) PRIMARY KEY, -- Use UUID string
    strategy_id INT NOT NULL,
    bot_type VARCHAR(50) NOT NULL,  -- 'paper', 'betfair', etc.
    bot_id VARCHAR(50) DEFAULT 'default',
    game_id INT REFERENCES games(id),
    prediction_id INT REFERENCES predictions(id),
    selection VARCHAR(100),
    action VARCHAR(20) NOT NULL,  -- 'place', 'skip', 'cancel'
    status VARCHAR(20) DEFAULT 'pending', -- 'placed', 'settled', 'cancelled'
    stake FLOAT,
    odds FLOAT,
    pnl FLOAT,
    current_balance FLOAT,
    reason TEXT,
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    settled_at TIMESTAMPTZ
);

-- Index for bot lookups
CREATE INDEX IF NOT EXISTS idx_bot_status ON bot_executions(bot_id, status);
