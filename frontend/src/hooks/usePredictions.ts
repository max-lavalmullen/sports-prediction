import { useQuery } from '@tanstack/react-query'
import type { Sport, GameWithPredictions, Prediction } from '@/types'

const API_URL = import.meta.env.VITE_API_URL || ''

interface PredictionsParams {
  sport?: Sport
  date?: string
  predictionTypes?: string
  minEdge?: number
}

async function fetchPredictions(params: PredictionsParams): Promise<GameWithPredictions[]> {
  const searchParams = new URLSearchParams()

  if (params.sport) searchParams.set('sport', params.sport)
  if (params.date) searchParams.set('date', params.date)
  if (params.predictionTypes) searchParams.set('prediction_types', params.predictionTypes)
  if (params.minEdge) searchParams.set('min_edge', params.minEdge.toString())

  const response = await fetch(`${API_URL}/api/v1/predictions?${searchParams}`)

  if (!response.ok) {
    throw new Error('Failed to fetch predictions')
  }

  const data = await response.json()

  // Map response to match frontend types
  return data.map((game: any) => ({
    ...game,
    // API returns camelCase keys (via Pydantic alias) but string values for teams
    // Map string names to Team objects expected by frontend
    homeTeam: typeof game.homeTeam === 'string' ? { name: game.homeTeam, id: 0, abbreviation: '', sport: game.sport, league: '' } : game.homeTeam,
    awayTeam: typeof game.awayTeam === 'string' ? { name: game.awayTeam, id: 0, abbreviation: '', sport: game.sport, league: '' } : game.awayTeam,
  }))
}

async function fetchGamePrediction(gameId: number): Promise<{
  game: GameWithPredictions
  predictions: Record<string, Prediction>
  valueBets: Array<{ type: string; edge: number; ev: number }>
}> {
  const response = await fetch(`${API_URL}/api/v1/predictions/${gameId}`)

  if (!response.ok) {
    throw new Error('Failed to fetch game prediction')
  }

  const data = await response.json()
  
  // Map manual dict response from API to camelCase
  const game = {
    id: data.game.id,
    sport: data.game.sport,
    scheduledTime: data.game.scheduled_time,
    status: data.game.status,
    venue: data.game.venue,
    // Map string teams to objects
    homeTeam: { name: data.game.home_team, id: 0, abbreviation: '', sport: data.game.sport, league: '' },
    awayTeam: { name: data.game.away_team, id: 0, abbreviation: '', sport: data.game.sport, league: '' },
    predictions: data.predictions // Predictions structure matches fairly well
  } as unknown as GameWithPredictions

  return {
    game,
    predictions: data.predictions,
    valueBets: data.value_bets
  }
}

async function fetchValueBets(params: {
  sport?: Sport
  minEdge?: number
  minEv?: number
  limit?: number
}): Promise<Array<{
  gameId: number
  predictionType: string
  selection: string
  edge: number
  ev: number
  ourProb: number
  marketOdds: number
}>> {
  const searchParams = new URLSearchParams()

  if (params.sport) searchParams.set('sport', params.sport)
  if (params.minEdge) searchParams.set('min_edge', params.minEdge.toString())
  if (params.minEv) searchParams.set('min_ev', params.minEv.toString())
  if (params.limit) searchParams.set('limit', params.limit.toString())

  const response = await fetch(`${API_URL}/api/v1/predictions/value?${searchParams}`)

  if (!response.ok) {
    throw new Error('Failed to fetch value bets')
  }

  const data = await response.json()

  // Map snake_case API response to camelCase
  return data.map((bet: any) => ({
    gameId: bet.game_id,
    predictionType: bet.prediction_type, // Map snake_case value key
    selection: bet.selection,
    edge: bet.edge,
    ev: bet.ev,
    ourProb: bet.our_prob,
    marketOdds: bet.market_odds,
    marketLine: bet.market_line,
    modelAgreement: bet.model_agreement,
    confidence: bet.confidence
  }))
}

export function usePredictions(params: PredictionsParams = {}) {
  return useQuery({
    queryKey: ['predictions', params],
    queryFn: () => fetchPredictions(params),
    refetchInterval: 60000, // Refetch every minute
  })
}

export function useGamePrediction(gameId: number) {
  return useQuery({
    queryKey: ['prediction', gameId],
    queryFn: () => fetchGamePrediction(gameId),
    enabled: !!gameId,
  })
}

export function useValueBets(params: Parameters<typeof fetchValueBets>[0] = {}) {
  return useQuery({
    queryKey: ['valueBets', params],
    queryFn: () => fetchValueBets(params),
    refetchInterval: 30000, // Refetch every 30 seconds
  })
}
