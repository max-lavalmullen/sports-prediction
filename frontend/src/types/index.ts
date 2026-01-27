// Core types for the sports prediction platform

export type Sport = 'nfl' | 'nba' | 'mlb' | 'soccer' | 'ncaaf' | 'ncaab'

export type BetType = 'moneyline' | 'spread' | 'total' | 'player_prop' | 'parlay'

export type BetResult = 'pending' | 'win' | 'loss' | 'push' | 'cancelled'

// Game types
export interface Team {
  id: number
  name: string
  abbreviation: string
  sport: Sport
  league: string
  logoUrl?: string
  primaryColor?: string
}

export interface Game {
  id: number
  sport: Sport
  homeTeam: Team
  awayTeam: Team
  scheduledTime: string
  status: 'scheduled' | 'in_progress' | 'final' | 'postponed'
  homeScore?: number
  awayScore?: number
  venue?: string
}

// Prediction types
export interface ConfidenceInterval {
  lower: number
  upper: number
  confidenceLevel: number
}

export interface MoneylinePrediction {
  homeProb: number
  awayProb: number
  drawProb?: number
}

export interface SpreadPrediction {
  predictedSpread: number
  homeCoverProb: number
  pushProb: number
}

export interface TotalPrediction {
  predictedTotal: number
  overProb: number
  underProb: number
}

export interface Prediction {
  gameId: number
  predictionType: BetType
  prediction: MoneylinePrediction | SpreadPrediction | TotalPrediction
  confidence?: ConfidenceInterval
  edge?: number
  expectedValue?: number
  modelAgreement?: number
  featureImportance?: Record<string, number>
  createdAt: string
}

export interface GameWithPredictions extends Game {
  predictions: {
    moneyline?: Prediction
    spread?: Prediction
    total?: Prediction
  }
}

// Odds types
export interface OddsOutcome {
  name: string
  price: number
  point?: number
}

export interface Market {
  key: string
  outcomes: OddsOutcome[]
}

export interface BookmakerOdds {
  sportsbook: string
  markets: Market[]
  lastUpdate: string
}

export interface GameOdds {
  gameId: number
  homeTeam: string
  awayTeam: string
  bookmakers: BookmakerOdds[]
}

// Bet tracking types
export interface Bet {
  id: number
  gameId?: number
  betType: BetType
  selection: string
  oddsAmerican: number
  oddsDecimal: number
  line?: number
  stake: number
  potentialPayout: number
  result: BetResult
  profitLoss?: number
  sportsbook?: string
  placedAt: string
  settledAt?: string
  modelEdge?: number
  clv?: number
  tags?: string[]
}

export interface BetStats {
  totalBets: number
  pendingBets: number
  wins: number
  losses: number
  pushes: number
  winRate: number
  totalStaked: number
  totalProfit: number
  roi: number
  averageOdds: number
  avgClv?: number
  bySport: Record<Sport, { bets: number; roi: number }>
  byBetType: Record<BetType, { bets: number; roi: number }>
}

// Player props types
export interface PropProjection {
  p10: number
  p25: number
  median: number
  p75: number
  p90: number
  mean: number
  std: number
}

export interface PlayerPropPrediction {
  playerId: number
  playerName: string
  propType: string
  projection: PropProjection
  marketLine?: number
  overProb: number
  underProb: number
  overEdge?: number
  underEdge?: number
  overEv?: number
  underEv?: number
  recommendation?: 'over' | 'under'
}

// Backtest types
export interface StrategyConfig {
  sports: Sport[]
  betTypes: BetType[]
  minEdge: number
  minConfidence: number
  kellyFraction: number
  maxStakePct: number
  flatStake?: number
}

export interface BacktestResult {
  totalBets: number
  wins: number
  losses: number
  pushes: number
  winRate: number
  initialBankroll: number
  finalBankroll: number
  totalProfit: number
  totalStaked: number
  roi: number
  yieldPct: number
  maxDrawdown: number
  maxDrawdownPct: number
  sharpeRatio?: number
  avgClv: number
  clvPositivePct: number
  bySport: Record<Sport, { bets: number; roi: number }>
  byBetType: Record<BetType, { bets: number; roi: number }>
  monthlyReturns: Array<{ month: string; profit: number; roi: number }>
  equityCurve: Array<{ date: string; bankroll: number; cumulativePl: number }>
  drawdownCurve: Array<{ date: string; drawdownPct: number }>
}

// Simulation types
export interface SimulationResult {
  nSimulations: number
  nBets: number
  medianFinalBankroll: number
  p5FinalBankroll: number
  p25FinalBankroll: number
  p75FinalBankroll: number
  p95FinalBankroll: number
  probabilityOfProfit: number
  probabilityOfRuin: number
  probabilityOfHalving: number
  expectedRoi: number
  expectedProfit: number
  finalBankrollDistribution: number[]
}

// WebSocket message types
export interface OddsUpdate {
  type: 'odds_update'
  sport: Sport
  gameId: number
  homeTeam: string
  awayTeam: string
  bookmakers: BookmakerOdds[]
  timestamp: string
}

export interface ValueAlert {
  type: 'value_alert'
  gameId: number
  sport: Sport
  betType: BetType
  selection: string
  edge: number
  expectedValue: number
  odds: number
  expiresIn?: number
}

// Arbitrage Types
export interface ArbitrageOpportunity {
  gameId: string
  sport: Sport
  homeTeam: string
  awayTeam: string
  marketType: string
  opportunityType: 'arbitrage' | 'middle' | 'low_hold'
  book1: string
  selection1: string
  odds1: number
  line1?: number
  book2: string
  selection2: string
  odds2: number
  line2?: number
  book3?: string
  selection3?: string
  odds3?: number
  profitPct: number
  stake1Pct: number
  stake2Pct: number
  stake3Pct?: number
  middleSize?: number
  combinedHold?: number
  detectedAt: string
}

// SGP Types
export interface SGPLeg {
  type: string
  prob: number
  description?: string
}

export interface SGPRequest {
  sport: string
  gameId: string
  legs: SGPLeg[]
  marketOddsAmerican?: number
  marketOddsDecimal?: number
}

export interface SGPResponse {
  trueProb: number
  impliedProb?: number
  edge?: number
  ev?: number
  marketOddsAmerican?: number
  marketOddsDecimal?: number
  legsCount: number
  individualProbs: number[]
}

// Bot Types
export interface BotStatus {
  botId: string
  botType: string
  isActive: boolean
  balance: number
  activeBetsCount: number
}