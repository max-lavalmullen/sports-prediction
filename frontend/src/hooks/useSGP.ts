import { useMutation } from '@tanstack/react-query'
import type { SGPRequest, SGPResponse } from '@/types'

const API_URL = import.meta.env.VITE_API_URL || ''

async function calculateSGP(request: SGPRequest): Promise<SGPResponse> {
  const response = await fetch(`${API_URL}/api/v1/sgp/calculate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to calculate SGP')
  }

  const data = await response.json()
  
  // Map snake_case to camelCase
  return {
    trueProb: data.true_prob,
    impliedProb: data.implied_prob,
    edge: data.edge,
    ev: data.ev,
    marketOddsAmerican: data.market_odds_american,
    marketOddsDecimal: data.market_odds_decimal,
    legsCount: data.legs_count,
    individualProbs: data.individual_probs
  }
}

export function useCalculateSGP() {
  return useMutation({
    mutationFn: calculateSGP
  })
}
