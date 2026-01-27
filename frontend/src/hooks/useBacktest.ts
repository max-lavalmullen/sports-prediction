import { useMutation } from '@tanstack/react-query'
import type { BacktestResult, StrategyConfig } from '@/types'

const API_URL = import.meta.env.VITE_API_URL || ''

interface BacktestParams {
  strategy: StrategyConfig
  start_date: string
  end_date: string
  initial_bankroll: number
}

async function runBacktest(params: BacktestParams): Promise<BacktestResult> {
  const response = await fetch(`${API_URL}/api/v1/backtest/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to run backtest')
  }

  const data = await response.json()
  
  // Map snake_case to camelCase
  return {
    totalBets: data.total_bets,
    wins: data.wins,
    losses: data.losses,
    pushes: data.pushes,
    winRate: data.win_rate,
    initialBankroll: data.initial_bankroll,
    finalBankroll: data.final_bankroll,
    totalProfit: data.total_profit,
    totalStaked: data.total_staked,
    roi: data.roi,
    yieldPct: data.yield_pct,
    maxDrawdown: data.max_drawdown,
    maxDrawdownPct: data.max_drawdown_pct,
    sharpeRatio: data.sharpe_ratio,
    avgClv: data.avg_clv,
    clvPositivePct: data.clv_positive_pct,
    bySport: data.by_sport,
    byBetType: data.by_bet_type,
    monthlyReturns: data.monthly_returns,
    equityCurve: data.equity_curve,
    drawdownCurve: data.drawdown_curve
  }
}

export function useBacktest() {
  return useMutation({
    mutationFn: runBacktest
  })
}
