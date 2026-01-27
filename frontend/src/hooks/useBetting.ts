import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { Bet, BetStats, BetResult, BetType } from '@/types'

const API_URL = import.meta.env.VITE_API_URL || ''

interface BetCreateParams {
  gameId?: number
  predictionId?: number
  betType: BetType
  selection: string
  oddsAmerican: number
  line?: number
  stake: number
  sportsbook?: string
  modelProbability?: number
  modelEdge?: number
  notes?: string
  tags?: string[]
}

interface BetUpdateParams {
  result: BetResult
  actualResult?: number
  closingLine?: number
}

interface BetsQueryParams {
  result?: BetResult
  betType?: BetType
  startDate?: string
  endDate?: string
  limit?: number
  offset?: number
}

async function createBet(params: BetCreateParams): Promise<Bet> {
  const response = await fetch(`${API_URL}/api/v1/bets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      game_id: params.gameId,
      prediction_id: params.predictionId,
      bet_type: params.betType,
      selection: params.selection,
      odds_american: params.oddsAmerican,
      line: params.line,
      stake: params.stake,
      sportsbook: params.sportsbook,
      model_probability: params.modelProbability,
      model_edge: params.modelEdge,
      notes: params.notes,
      tags: params.tags,
    }),
  })

  if (!response.ok) {
    throw new Error('Failed to create bet')
  }

  return response.json()
}

async function updateBet(betId: number, params: BetUpdateParams): Promise<Bet> {
  const response = await fetch(`${API_URL}/api/v1/bets/${betId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      result: params.result,
      actual_result: params.actualResult,
      closing_line: params.closingLine,
    }),
  })

  if (!response.ok) {
    throw new Error('Failed to update bet')
  }

  return response.json()
}

async function fetchBets(params: BetsQueryParams = {}): Promise<Bet[]> {
  const searchParams = new URLSearchParams()

  if (params.result) searchParams.set('result', params.result)
  if (params.betType) searchParams.set('bet_type', params.betType)
  if (params.startDate) searchParams.set('start_date', params.startDate)
  if (params.endDate) searchParams.set('end_date', params.endDate)
  if (params.limit) searchParams.set('limit', params.limit.toString())
  if (params.offset) searchParams.set('offset', params.offset.toString())

  const response = await fetch(`${API_URL}/api/v1/bets?${searchParams}`)

  if (!response.ok) {
    throw new Error('Failed to fetch bets')
  }

  const data = await response.json()

  // Map snake_case from API to camelCase for frontend
  return data.map((bet: any) => ({
    id: bet.id,
    gameId: bet.game_id,
    betType: bet.bet_type,
    selection: bet.selection,
    oddsAmerican: bet.odds_american,
    oddsDecimal: bet.odds_decimal,
    line: bet.line,
    stake: bet.stake,
    potentialPayout: bet.potential_payout,
    result: bet.result,
    profitLoss: bet.profit_loss,
    sportsbook: bet.sportsbook,
    placedAt: bet.placed_at,
    settledAt: bet.settled_at,
    modelEdge: bet.model_edge,
    clv: bet.clv,
    tags: bet.tags,
  }))
}

async function fetchBetStats(params: {
  startDate?: string
  endDate?: string
} = {}): Promise<BetStats> {
  const searchParams = new URLSearchParams()

  if (params.startDate) searchParams.set('start_date', params.startDate)
  if (params.endDate) searchParams.set('end_date', params.endDate)

  const response = await fetch(`${API_URL}/api/v1/bets/stats?${searchParams}`)

  if (!response.ok) {
    throw new Error('Failed to fetch bet stats')
  }

  const data = await response.json()
  
  // Map snake_case from API to camelCase for frontend
  return {
    totalBets: data.total_bets,
    pendingBets: data.pending_bets,
    wins: data.wins,
    losses: data.losses,
    pushes: data.pushes,
    winRate: data.win_rate,
    totalStaked: data.total_staked,
    totalProfit: data.total_profit,
    roi: data.roi,
    averageOdds: data.average_odds,
    avgClv: data.avg_clv,
    bySport: data.by_sport,
    byBetType: data.by_bet_type,
  }
}

async function calculateKelly(params: {
  probability: number
  oddsAmerican: number
  bankroll: number
  kellyFraction: number
}): Promise<{
  recommendation: string
  edge: number
  recommendedStake: number
  expectedValue: number
}> {
  const searchParams = new URLSearchParams({
    probability: params.probability.toString(),
    odds_american: params.oddsAmerican.toString(),
    bankroll: params.bankroll.toString(),
    kelly_fraction: params.kellyFraction.toString(),
  })

  const response = await fetch(`${API_URL}/api/v1/bets/kelly?${searchParams}`)

  if (!response.ok) {
    throw new Error('Failed to calculate Kelly')
  }

  return response.json()
}

export function useBets(params: BetsQueryParams = {}) {
  return useQuery({
    queryKey: ['bets', params],
    queryFn: () => fetchBets(params),
  })
}

export function useBetStats(params: { startDate?: string; endDate?: string } = {}) {
  return useQuery({
    queryKey: ['betStats', params],
    queryFn: () => fetchBetStats(params),
  })
}

export function useCreateBet() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createBet,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bets'] })
      queryClient.invalidateQueries({ queryKey: ['betStats'] })
    },
  })
}

export function useUpdateBet() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ betId, params }: { betId: number; params: BetUpdateParams }) =>
      updateBet(betId, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bets'] })
      queryClient.invalidateQueries({ queryKey: ['betStats'] })
    },
  })
}

export function useKellyCalculator() {
  return useMutation({
    mutationFn: calculateKelly,
  })
}
