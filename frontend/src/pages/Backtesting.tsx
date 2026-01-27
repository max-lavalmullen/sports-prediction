import { useState } from 'react'
import { formatCurrency, formatPercent } from '@/lib/utils'
import { useBacktest } from '@/hooks/useBacktest'
import type { Sport, BetType } from '@/types'
import {
  Play,
  History,
  TrendingUp,
  TrendingDown,
  Target,
  Calendar,
  DollarSign,
  Percent,
  AlertCircle
} from 'lucide-react'
import { cn } from '@/lib/utils'

// Mapping for UI labels to API values
const sportMapping: Record<string, Sport> = {
  'Basketball': 'nba',
  'Football': 'nfl',
  'Baseball': 'mlb',
  'Soccer': 'soccer'
}

const betTypeMapping: Record<string, BetType> = {
  'Spread': 'spread',
  'Total': 'total',
  'Moneyline': 'moneyline',
  'Props': 'player_prop'
}

export default function Backtesting() {
  const [selectedSports, setSelectedSports] = useState<string[]>(['Basketball'])
  const [selectedBetTypes, setSelectedBetTypes] = useState<string[]>(['Moneyline']) // Default to ML as it's implemented in backtest service
  const [minEdge, setMinEdge] = useState(3)
  const [kellyFraction, setKellyFraction] = useState(0.25)
  const [startDate, setStartDate] = useState('2023-01-01')
  const [endDate, setEndDate] = useState('2023-12-31')
  const [initialBankroll, setInitialBankroll] = useState(10000)

  const backtestMutation = useBacktest()
  const result = backtestMutation.data

  const toggleSelection = (item: string, selected: string[], setSelected: (v: string[]) => void) => {
    if (selected.includes(item)) {
      setSelected(selected.filter(s => s !== item))
    } else {
      setSelected([...selected, item])
    }
  }

  const handleRunBacktest = () => {
    backtestMutation.mutate({
      strategy: {
        sports: selectedSports.map(s => sportMapping[s]),
        betTypes: selectedBetTypes.map(t => betTypeMapping[t]),
        minEdge: minEdge / 100, // Convert to decimal
        minConfidence: 0,
        kellyFraction: kellyFraction,
        maxStakePct: 0.05
      },
      start_date: startDate,
      end_date: endDate,
      initial_bankroll: initialBankroll
    })
  }

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Strategy Configuration */}
        <div className="bg-card/50 rounded-2xl border border-border/50 overflow-hidden">
          <div className="flex items-center gap-3 px-6 py-4 border-b border-border/50">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-500/15">
              <History className="h-4 w-4 text-blue-400" />
            </div>
            <div>
              <h3 className="font-semibold">Strategy Setup</h3>
              <p className="text-xs text-muted-foreground">Configure your backtest parameters</p>
            </div>
          </div>

          <div className="p-6 space-y-6">
            {/* Sports selection */}
            <div>
              <label className="block text-sm font-medium mb-3">Markets</label>
              <div className="flex flex-wrap gap-2">
                {Object.keys(sportMapping).map((sport) => (
                  <button
                    key={sport}
                    onClick={() => toggleSelection(sport, selectedSports, setSelectedSports)}
                    className={cn(
                      'px-3 py-1.5 text-sm rounded-full transition-all duration-200',
                      selectedSports.includes(sport)
                        ? 'bg-primary/15 text-primary border border-primary/30'
                        : 'bg-muted/50 text-muted-foreground border border-transparent hover:bg-muted'
                    )}
                  >
                    {sport}
                  </button>
                ))}
              </div>
            </div>

            {/* Bet types */}
            <div>
              <label className="block text-sm font-medium mb-3">Position Types</label>
              <div className="flex flex-wrap gap-2">
                {Object.keys(betTypeMapping).map((type) => (
                  <button
                    key={type}
                    onClick={() => toggleSelection(type, selectedBetTypes, setSelectedBetTypes)}
                    className={cn(
                      'px-3 py-1.5 text-sm rounded-full transition-all duration-200',
                      selectedBetTypes.includes(type)
                        ? 'bg-primary/15 text-primary border border-primary/30'
                        : 'bg-muted/50 text-muted-foreground border border-transparent hover:bg-muted'
                    )}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>

            {/* Minimum Edge */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="text-sm font-medium">Minimum Edge</label>
                <span className="text-sm font-mono text-primary">{minEdge}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="10"
                step="0.5"
                value={minEdge}
                onChange={(e) => setMinEdge(Number(e.target.value))}
                className="w-full h-2 bg-muted rounded-full appearance-none cursor-pointer accent-primary"
              />
              <div className="flex justify-between text-xs text-muted-foreground mt-2">
                <span>0%</span>
                <span>5%</span>
                <span>10%</span>
              </div>
            </div>

            {/* Kelly Fraction */}
            <div>
              <label className="block text-sm font-medium mb-3">Position Sizing</label>
              <div className="relative">
                <select 
                  className="select h-11 w-full"
                  value={kellyFraction}
                  onChange={(e) => setKellyFraction(parseFloat(e.target.value))}
                >
                  <option value="0.125">Eighth Kelly (Very Conservative)</option>
                  <option value="0.25">Quarter Kelly (Conservative)</option>
                  <option value="0.5">Half Kelly (Moderate)</option>
                  <option value="1">Full Kelly (Aggressive)</option>
                </select>
              </div>
            </div>

            {/* Date Range */}
            <div>
              <label className="block text-sm font-medium mb-3">Time Period</label>
              <div className="grid grid-cols-2 gap-3">
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                  <input
                    type="date"
                    className="input pl-10 h-11 w-full"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                  />
                </div>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                  <input
                    type="date"
                    className="input pl-10 h-11 w-full"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                  />
                </div>
              </div>
            </div>

            {/* Initial Bankroll */}
            <div>
              <label className="block text-sm font-medium mb-3">Starting Capital</label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                <input
                  type="number"
                  value={initialBankroll}
                  onChange={(e) => setInitialBankroll(Number(e.target.value))}
                  className="input pl-10 h-11 w-full"
                />
              </div>
            </div>

            {/* Run button */}
            <button
              onClick={handleRunBacktest}
              disabled={backtestMutation.isPending}
              className="btn-primary btn-lg w-full"
            >
              {backtestMutation.isPending ? (
                 <>
                   <span className="loading loading-spinner loading-sm mr-2"></span>
                   Running Analysis...
                 </>
              ) : (
                 <>
                   <Play className="h-4 w-4 mr-2" />
                   Run Backtest
                 </>
              )}
            </button>
            
            {backtestMutation.isError && (
               <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-start gap-2">
                 <AlertCircle className="h-5 w-5 text-red-400 shrink-0" />
                 <p className="text-sm text-red-400">
                   {backtestMutation.error.message}
                 </p>
               </div>
            )}
          </div>
        </div>

        {/* Results */}
        <div className="lg:col-span-2 space-y-6">
          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <ResultCard
              label="Total ROI"
              value={result ? formatPercent(result.roi) : "---"}
              positive={result ? result.roi >= 0 : undefined}
              icon={Percent}
              accent="emerald"
            />
            <ResultCard
              label="Success Rate"
              value={result ? formatPercent(result.winRate) : "---"}
              icon={Target}
              accent="blue"
            />
            <ResultCard
              label="Total Profit"
              value={result ? formatCurrency(result.totalProfit) : "---"}
              positive={result ? result.totalProfit >= 0 : undefined}
              icon={DollarSign}
              accent={result && result.totalProfit < 0 ? "red" : "emerald"}
            />
            <ResultCard
              label="Total Bets"
              value={result ? result.totalBets.toString() : "---"}
              icon={History}
              accent="violet"
            />
          </div>

          {/* Equity Curve */}
          <div className="bg-card/50 rounded-2xl border border-border/50 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border/50">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-emerald-500/15">
                  <TrendingUp className="h-4 w-4 text-emerald-400" />
                </div>
                <div>
                  <h3 className="font-semibold">Performance Curve</h3>
                  <p className="text-xs text-muted-foreground">Bankroll growth over time</p>
                </div>
              </div>
            </div>
            <div className="p-6">
              {result?.equityCurve && result.equityCurve.length > 0 ? (
                 <div className="h-64 flex items-end justify-between gap-1">
                    {/* Simple bar chart visualization for now */}
                    {result.equityCurve.map((point, i) => {
                       const max = Math.max(...result.equityCurve.map(p => p.bankroll));
                       const min = Math.min(...result.equityCurve.map(p => p.bankroll));
                       const range = max - min || 1;
                       const height = ((point.bankroll - min) / range) * 80 + 10;
                       
                       return (
                          <div 
                             key={i} 
                             className="bg-emerald-500/50 w-full hover:bg-emerald-400 transition-colors rounded-t-sm relative group"
                             style={{ height: `${height}%` }}
                          >
                             <div className="opacity-0 group-hover:opacity-100 absolute bottom-full mb-2 left-1/2 -translate-x-1/2 bg-popover text-popover-foreground text-xs p-2 rounded shadow-lg whitespace-nowrap z-10 pointer-events-none">
                                {point.date}: {formatCurrency(point.bankroll)}
                             </div>
                          </div>
                       )
                    })}
                 </div>
              ) : (
                <div className="h-64 flex items-center justify-center bg-muted/30 rounded-xl border border-dashed border-border">
                  <div className="text-center">
                    <TrendingUp className="h-8 w-8 text-muted-foreground/50 mx-auto mb-2" />
                    <p className="text-muted-foreground text-sm">Run a backtest to visualize performance</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ResultCard({
  label,
  value,
  positive,
  icon: Icon,
  accent,
}: {
  label: string
  value: string
  positive?: boolean
  icon: React.ComponentType<{ className?: string }>
  accent: 'emerald' | 'blue' | 'red' | 'violet' | 'amber'
}) {
  const accentStyles = {
    emerald: 'bg-emerald-500/15 border-emerald-500/20 text-emerald-400',
    blue: 'bg-blue-500/15 border-blue-500/20 text-blue-400',
    red: 'bg-red-500/15 border-red-500/20 text-red-400',
    violet: 'bg-violet-500/15 border-violet-500/20 text-violet-400',
    amber: 'bg-amber-500/15 border-amber-500/20 text-amber-400',
  }

  return (
    <div className="stat-card">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground mb-1">{label}</p>
          <p className={cn(
            'text-2xl font-bold tracking-tight',
            positive === true && 'text-emerald-400',
            positive === false && 'text-red-400'
          )}>
            {value}
          </p>
        </div>
        <div className={cn(
          'flex items-center justify-center w-10 h-10 rounded-xl border',
          accentStyles[accent]
        )}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  )
}
