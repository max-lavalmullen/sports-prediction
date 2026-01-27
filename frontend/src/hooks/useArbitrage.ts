import { useQuery } from '@tanstack/react-query'
import type { ArbitrageOpportunity, Sport } from '@/types'

const API_URL = import.meta.env.VITE_API_URL || ''

async function fetchArbitrageOpportunities(sport: Sport, options: {
  includeArbs?: boolean
  includeMiddles?: boolean
  includeLowHold?: boolean
  maxHold?: number
} = {}): Promise<ArbitrageOpportunity[]> {
  const searchParams = new URLSearchParams()
  if (options.includeArbs !== undefined) searchParams.set('include_arbs', options.includeArbs.toString())
  if (options.includeMiddles !== undefined) searchParams.set('include_middles', options.includeMiddles.toString())
  if (options.includeLowHold !== undefined) searchParams.set('include_low_hold', options.includeLowHold.toString())
  if (options.maxHold !== undefined) searchParams.set('max_hold', options.maxHold.toString())

  const response = await fetch(`${API_URL}/api/v1/arb/${sport}?${searchParams}`)

  if (!response.ok) {
    throw new Error('Failed to fetch arbitrage opportunities')
  }

  const data = await response.json()
  
  // Map snake_case to camelCase
  return data.map((opp: any) => ({
    gameId: opp.game_id,
    sport: opp.sport,
    homeTeam: opp.home_team,
    awayTeam: opp.away_team,
    marketType: opp.market_type,
    opportunityType: opp.opportunity_type,
    book1: opp.book1,
    selection1: opp.selection1,
    odds1: opp.odds1,
    line1: opp.line1,
    book2: opp.book2,
    selection2: opp.selection2,
    odds2: opp.odds2,
    line2: opp.line2,
    book3: opp.book3,
    selection3: opp.selection3,
    odds3: opp.odds3,
    profitPct: opp.profit_pct,
    stake1Pct: opp.stake1_pct,
    stake2Pct: opp.stake2_pct,
    stake3Pct: opp.stake3_pct,
    middleSize: opp.middle_size,
    combinedHold: opp.combined_hold,
    detectedAt: opp.detected_at
  }))
}

export function useArbitrage(sport: Sport, options = {}) {
  return useQuery({
    queryKey: ['arbitrage', sport, options],
    queryFn: () => fetchArbitrageOpportunities(sport, options),
    refetchInterval: 10000, // Refetch every 10 seconds for arbs
  })
}
