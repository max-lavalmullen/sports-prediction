import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { formatCurrency, formatPercent } from '@/lib/utils'
import {
  Play,
  FlaskConical,
  TrendingUp,
  Shield,
  DollarSign,
  BarChart3,
  Info,
  Loader2,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface SimulationResult {
  n_simulations: number
  n_bets: number
  median_final_bankroll: number
  p5_final_bankroll: number
  p25_final_bankroll: number
  p75_final_bankroll: number
  p95_final_bankroll: number
  probability_of_profit: number
  probability_of_ruin: number
  probability_of_halving: number
  expected_roi: number
  expected_profit: number
}

export default function Simulation() {
  const [simulations, setSimulations] = useState(10000)
  const [betsPerSim, setBetsPerSim] = useState(1000)
  const [winRate, setWinRate] = useState(54)
  const [bankroll, setBankroll] = useState(10000)
  const [avgOdds, setAvgOdds] = useState(-110)
  const [kellyFraction, setKellyFraction] = useState(0.25)

  const simulationMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch(`${API_URL}/api/v1/backtest/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          n_simulations: simulations,
          n_bets: betsPerSim,
          initial_bankroll: bankroll,
          win_rate: winRate / 100,
          avg_odds: avgOdds,
          kelly_fraction: kellyFraction,
        }),
      })
      if (!response.ok) throw new Error('Simulation failed')
      return response.json() as Promise<SimulationResult>
    },
  })

  const result = simulationMutation.data

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Configuration */}
        <div className="bg-card/50 rounded-2xl border border-border/50 overflow-hidden">
          <div className="flex items-center gap-3 px-6 py-4 border-b border-border/50">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-violet-500/15">
              <FlaskConical className="h-4 w-4 text-violet-400" />
            </div>
            <div>
              <h3 className="font-semibold">Parameters</h3>
              <p className="text-xs text-muted-foreground">Configure Monte Carlo simulation</p>
            </div>
          </div>

          <div className="p-6 space-y-6">
            {/* Number of Simulations */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="text-sm font-medium">Simulations</label>
                <span className="text-sm font-mono text-primary">{simulations.toLocaleString()}</span>
              </div>
              <input
                type="range"
                min="1000"
                max="50000"
                step="1000"
                value={simulations}
                onChange={(e) => setSimulations(Number(e.target.value))}
                className="w-full h-2 bg-muted rounded-full appearance-none cursor-pointer accent-primary"
              />
              <p className="text-xs text-muted-foreground mt-2">
                More simulations = more accurate projections
              </p>
            </div>

            {/* Bets per Simulation */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="text-sm font-medium">Positions per Path</label>
                <span className="text-sm font-mono text-primary">{betsPerSim.toLocaleString()}</span>
              </div>
              <input
                type="range"
                min="100"
                max="5000"
                step="100"
                value={betsPerSim}
                onChange={(e) => setBetsPerSim(Number(e.target.value))}
                className="w-full h-2 bg-muted rounded-full appearance-none cursor-pointer accent-primary"
              />
            </div>

            {/* Initial Bankroll */}
            <div>
              <label className="block text-sm font-medium mb-3">Starting Capital</label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                <input
                  type="number"
                  value={bankroll}
                  onChange={(e) => setBankroll(Number(e.target.value))}
                  className="input pl-10 h-11"
                />
              </div>
            </div>

            {/* Expected Win Rate */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="text-sm font-medium">Expected Win Rate</label>
                <span className="text-sm font-mono text-primary">{winRate}%</span>
              </div>
              <input
                type="range"
                min="48"
                max="65"
                step="0.5"
                value={winRate}
                onChange={(e) => setWinRate(Number(e.target.value))}
                className="w-full h-2 bg-muted rounded-full appearance-none cursor-pointer accent-primary"
              />
              <div className="flex justify-between text-xs text-muted-foreground mt-2">
                <span>Break-even</span>
                <span>Elite</span>
              </div>
            </div>

            {/* Average Odds */}
            <div>
              <label className="block text-sm font-medium mb-3">Average Odds</label>
              <div className="relative">
                <input
                  type="number"
                  value={avgOdds}
                  onChange={(e) => setAvgOdds(Number(e.target.value))}
                  className="input h-11"
                />
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                Standard -110 implies 4.55% vig
              </p>
            </div>

            {/* Kelly Fraction */}
            <div>
              <label className="block text-sm font-medium mb-3">Position Sizing</label>
              <select
                className="select h-11"
                value={kellyFraction}
                onChange={(e) => setKellyFraction(Number(e.target.value))}
              >
                <option value="0.25">Quarter Kelly (Conservative)</option>
                <option value="0.5">Half Kelly (Moderate)</option>
                <option value="1">Full Kelly (Aggressive)</option>
              </select>
            </div>

            {/* Run button */}
            <button
              onClick={() => simulationMutation.mutate()}
              disabled={simulationMutation.isPending}
              className="btn-primary btn-lg w-full"
            >
              {simulationMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Play className="h-4 w-4 mr-2" />
              )}
              {simulationMutation.isPending ? 'Running Simulation...' : 'Run Simulation'}
            </button>
          </div>
        </div>

        {/* Results */}
        <div className="lg:col-span-2 space-y-6">
          {/* Outcome Distribution */}
          <div className="bg-card/50 rounded-2xl border border-border/50 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border/50">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-500/15">
                  <BarChart3 className="h-4 w-4 text-blue-400" />
                </div>
                <div>
                  <h3 className="font-semibold">Projected Outcomes</h3>
                  <p className="text-xs text-muted-foreground">Distribution of final bankroll values</p>
                </div>
              </div>
            </div>

            <div className="p-6">
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="text-center p-4 rounded-xl bg-red-500/10 border border-red-500/20">
                  <p className="text-xs text-red-400/80 mb-1">Worst Case (5%)</p>
                  <p className="text-xl font-bold text-red-400">
                    {result ? formatCurrency(result.p5_final_bankroll) : '--'}
                  </p>
                </div>
                <div className="text-center p-4 rounded-xl bg-blue-500/10 border border-blue-500/20">
                  <p className="text-xs text-blue-400/80 mb-1">Expected (Median)</p>
                  <p className="text-xl font-bold text-blue-400">
                    {result ? formatCurrency(result.median_final_bankroll) : '--'}
                  </p>
                </div>
                <div className="text-center p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                  <p className="text-xs text-emerald-400/80 mb-1">Best Case (95%)</p>
                  <p className="text-xl font-bold text-emerald-400">
                    {result ? formatCurrency(result.p95_final_bankroll) : '--'}
                  </p>
                </div>
              </div>

              <div className="h-48 flex items-center justify-center bg-muted/30 rounded-xl border border-dashed border-border">
                <div className="text-center">
                  <BarChart3 className="h-8 w-8 text-muted-foreground/50 mx-auto mb-2" />
                  <p className="text-muted-foreground text-sm">
                    {result
                      ? `Simulated ${result.n_simulations.toLocaleString()} paths with ${result.n_bets.toLocaleString()} bets each`
                      : 'Run simulation to see distribution'}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Risk Metrics */}
          <div className="bg-card/50 rounded-2xl border border-border/50 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border/50">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-amber-500/15">
                  <Shield className="h-4 w-4 text-amber-400" />
                </div>
                <div>
                  <h3 className="font-semibold">Risk Analysis</h3>
                  <p className="text-xs text-muted-foreground">Probability of various outcomes</p>
                </div>
              </div>
            </div>

            <div className="p-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <RiskMetric
                  label="Profit Probability"
                  value={result ? formatPercent(result.probability_of_profit) : '--'}
                  description="Chance of ending in profit"
                  type="positive"
                />
                <RiskMetric
                  label="Risk of Ruin"
                  value={result ? formatPercent(result.probability_of_ruin) : '--'}
                  description="Chance of losing everything"
                  type={result && result.probability_of_ruin < 0.01 ? 'positive' : 'negative'}
                />
                <RiskMetric
                  label="50% Drawdown Risk"
                  value={result ? formatPercent(result.probability_of_halving) : '--'}
                  description="Chance of losing half"
                  type={result && result.probability_of_halving < 0.05 ? 'positive' : 'warning'}
                />
                <RiskMetric
                  label="Expected ROI"
                  value={result ? (result.expected_roi >= 0 ? '+' : '') + formatPercent(result.expected_roi) : '--'}
                  description="Mean projected return"
                  type={result && result.expected_roi >= 0 ? 'positive' : 'negative'}
                />
              </div>
            </div>
          </div>

          {/* Percentile Paths */}
          <div className="bg-card/50 rounded-2xl border border-border/50 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border/50">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-emerald-500/15">
                  <TrendingUp className="h-4 w-4 text-emerald-400" />
                </div>
                <div>
                  <h3 className="font-semibold">Growth Trajectories</h3>
                  <p className="text-xs text-muted-foreground">Bankroll paths by percentile</p>
                </div>
              </div>
            </div>

            <div className="p-6">
              <div className="h-64 flex items-center justify-center bg-muted/30 rounded-xl border border-dashed border-border">
                <div className="text-center">
                  <TrendingUp className="h-8 w-8 text-muted-foreground/50 mx-auto mb-2" />
                  <p className="text-muted-foreground text-sm">Trajectory visualization will appear here</p>
                </div>
              </div>

              <div className="flex justify-center gap-8 mt-4">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-400" />
                  <span className="text-sm text-muted-foreground">5th percentile</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-blue-400" />
                  <span className="text-sm text-muted-foreground">Median</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-emerald-400" />
                  <span className="text-sm text-muted-foreground">95th percentile</span>
                </div>
              </div>
            </div>
          </div>

          {/* Info callout */}
          <div className="flex items-start gap-3 p-4 rounded-xl bg-blue-500/10 border border-blue-500/20">
            <Info className="h-5 w-5 text-blue-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-blue-100">
                Monte Carlo simulations help understand the range of possible outcomes given your strategy parameters.
                Results assume consistent edge and proper bankroll management.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function RiskMetric({
  label,
  value,
  description,
  type,
}: {
  label: string
  value: string
  description: string
  type: 'positive' | 'negative' | 'warning' | 'neutral'
}) {
  const styles = {
    positive: 'text-emerald-400',
    negative: 'text-red-400',
    warning: 'text-amber-400',
    neutral: 'text-foreground',
  }

  return (
    <div className="p-4 rounded-xl bg-muted/30 border border-border/50">
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      <p className={cn('text-xl font-bold', styles[type])}>{value}</p>
      <p className="text-xs text-muted-foreground/70 mt-1">{description}</p>
    </div>
  )
}
