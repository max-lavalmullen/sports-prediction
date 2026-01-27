import { useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Search,
  TrendingUp,
  Flame,
  Snowflake,
  BarChart3,
  ArrowUpRight,
  ChevronRight,
  Filter,
  AlertCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const sportOptions = [
  { value: 'all', label: 'All Sports' },
  { value: 'nba', label: 'Basketball' },
  { value: 'nfl', label: 'Football' },
  { value: 'mlb', label: 'Baseball' },
  { value: 'soccer', label: 'Soccer' },
]

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface TrendData {
  name: string
  record: string
  roi: number
  sample_size: number
}

export default function Analytics() {
  const { teamId, playerId } = useParams()
  const [searchParams] = useSearchParams()
  const gameId = searchParams.get('game')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSport, setSelectedSport] = useState('all')

  // Fetch trends data
  const { data: trendsData } = useQuery({
    queryKey: ['trends', selectedSport],
    queryFn: async () => {
      const sport = selectedSport === 'all' ? 'nba' : selectedSport
      const response = await fetch(`${API_URL}/api/v1/analytics/trends?sport=${sport.toUpperCase()}`)
      if (!response.ok) return null
      return response.json()
    },
  })

  const trends: TrendData[] = trendsData?.trends || []
  const hasRealData = false // Will be true once we have historical game results

  // Fetch game details if gameId is provided
  const { data: gameData, isLoading: gameLoading } = useQuery({
    queryKey: ['game', gameId],
    queryFn: async () => {
      const response = await fetch(`${API_URL}/api/v1/predictions/game/${gameId}`)
      if (!response.ok) throw new Error('Failed to fetch game')
      return response.json()
    },
    enabled: !!gameId,
  })

  // If viewing a specific game, show game details
  if (gameId && gameData) {
    const game = gameData.game
    return (
      <div className="space-y-8">
        <div className="bg-card/50 rounded-2xl border border-border/50 overflow-hidden">
          <div className="px-6 py-4 border-b border-border/50">
            <h2 className="text-xl font-bold">
              {game?.away_team} @ {game?.home_team}
            </h2>
            <p className="text-muted-foreground text-sm mt-1">
              {game?.sport?.toUpperCase()} • {new Date(game?.scheduled_time).toLocaleString()}
            </p>
          </div>

          <div className="p-6 space-y-6">
            {/* Game Info */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-muted/30 rounded-xl p-4">
                <p className="text-sm text-muted-foreground mb-1">Status</p>
                <p className="font-semibold capitalize">{game?.status}</p>
              </div>
              <div className="bg-muted/30 rounded-xl p-4">
                <p className="text-sm text-muted-foreground mb-1">Venue</p>
                <p className="font-semibold">{game?.venue || 'TBD'}</p>
              </div>
            </div>

            {/* Predictions */}
            <div>
              <h3 className="font-semibold mb-4">Model Predictions</h3>
              {Object.keys(gameData.predictions || {}).length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {Object.entries(gameData.predictions).map(([type, pred]: [string, any]) => (
                    <div key={type} className="bg-muted/30 rounded-xl p-4">
                      <p className="text-sm text-muted-foreground mb-2 capitalize">{type}</p>
                      <div className="space-y-1">
                        {pred.prediction && Object.entries(pred.prediction).map(([key, value]: [string, any]) => (
                          <div key={key} className="flex justify-between">
                            <span className="text-sm">{key.replace(/([A-Z])/g, ' $1').trim()}</span>
                            <span className="font-mono text-sm">
                              {typeof value === 'number' ? (value * 100).toFixed(1) + '%' : value}
                            </span>
                          </div>
                        ))}
                        {pred.edge && (
                          <div className="flex justify-between pt-2 border-t border-border/50 mt-2">
                            <span className="text-sm text-emerald-400">Edge</span>
                            <span className="font-mono text-sm text-emerald-400">
                              +{(pred.edge * 100).toFixed(1)}%
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground">No predictions generated yet for this game.</p>
              )}
            </div>

            {/* Value Bets */}
            {gameData.value_bets && gameData.value_bets.length > 0 && (
              <div>
                <h3 className="font-semibold mb-4">Value Bets</h3>
                <div className="space-y-2">
                  {gameData.value_bets.map((bet: any, i: number) => (
                    <div key={i} className="flex items-center justify-between bg-emerald-500/10 rounded-lg p-3">
                      <span className="capitalize">{bet.type}</span>
                      <span className="font-mono text-emerald-400">+{(bet.edge * 100).toFixed(1)}% edge</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  if (gameId && gameLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Search and filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search teams or players..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input pl-11 h-12"
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <select
            value={selectedSport}
            onChange={(e) => setSelectedSport(e.target.value)}
            className="select pl-11 h-12 min-w-[160px]"
          >
            {sportOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Data collection notice */}
      {!hasRealData && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
          <AlertCircle className="h-5 w-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-amber-100 font-medium">Collecting Historical Data</p>
            <p className="text-sm text-amber-200/70 mt-1">
              Analytics and trends will become available as game results are collected.
              The system is actively tracking upcoming games and odds.
            </p>
          </div>
        </div>
      )}

      {/* Quick insights grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <InsightCard
          title="Top Against the Spread"
          subtitle="Last 10 games"
          icon={TrendingUp}
          accent="emerald"
          items={hasRealData ? [] : [
            { name: 'Data collecting...', value: '--', positive: true },
          ]}
        />

        <InsightCard
          title="Over Performers"
          subtitle="Totals last 10"
          icon={ArrowUpRight}
          accent="blue"
          items={hasRealData ? [] : [
            { name: 'Data collecting...', value: '--', positive: true },
          ]}
        />

        <InsightCard
          title="Hot Performers"
          subtitle="Player props on fire"
          icon={Flame}
          accent="amber"
          items={hasRealData ? [] : [
            { name: 'Data collecting...', value: '--', positive: true },
          ]}
        />

        <InsightCard
          title="Cold Performers"
          subtitle="Trending under"
          icon={Snowflake}
          accent="blue"
          items={hasRealData ? [] : [
            { name: 'Data collecting...', value: '--', positive: false },
          ]}
        />
      </div>

      {/* Profitable trends */}
      <div className="bg-card/50 rounded-2xl border border-border/50 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border/50">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-violet-500/15">
              <BarChart3 className="h-4 w-4 text-violet-400" />
            </div>
            <div>
              <h3 className="font-semibold">Profitable Trends</h3>
              <p className="text-xs text-muted-foreground">Patterns with positive ROI over 30 days</p>
            </div>
          </div>
          <span className="badge badge-neutral">Last 30 days</span>
        </div>

        {hasRealData && trends.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/50">
                  <th className="table-header text-left px-6 py-4">Trend Description</th>
                  <th className="table-header text-right px-6 py-4">Record</th>
                  <th className="table-header text-right px-6 py-4">ROI</th>
                  <th className="table-header text-right px-6 py-4">Sample</th>
                  <th className="table-header px-6 py-4"></th>
                </tr>
              </thead>
              <tbody>
                {trends.map((item, i) => (
                  <tr key={i} className="table-row group cursor-pointer">
                    <td className="px-6 py-4">
                      <span className="font-medium">{item.name}</span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span className="font-mono font-medium">{item.record}</span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span className={cn(
                        'font-mono font-semibold',
                        item.roi > 0 ? 'text-emerald-400' : 'text-red-400'
                      )}>
                        {item.roi > 0 ? '+' : ''}{(item.roi * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span className="text-muted-foreground">{item.sample_size} games</span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <ChevronRight className="h-4 w-4 text-muted-foreground/50 group-hover:text-foreground transition-colors inline-block" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center">
            <BarChart3 className="h-8 w-8 text-muted-foreground/50 mx-auto mb-3" />
            <p className="text-muted-foreground">
              Profitable trends will appear here once enough game results are collected.
            </p>
            <p className="text-sm text-muted-foreground/70 mt-1">
              The system is tracking {selectedSport === 'all' ? 'all sports' : selectedSport.toUpperCase()} games and will analyze patterns over time.
            </p>
          </div>
        )}
      </div>

      {/* Team/Player Detail Panel */}
      {(teamId || playerId) && (
        <div className="bg-card/50 rounded-2xl border border-border/50 p-6">
          <h3 className="font-semibold mb-4">
            {teamId ? `Team Analysis` : `Player Analysis`}
          </h3>
          <p className="text-muted-foreground">
            Detailed analytics and historical performance data would appear here.
          </p>
        </div>
      )}
    </div>
  )
}

function InsightCard({
  title,
  subtitle,
  icon: Icon,
  accent,
  items,
}: {
  title: string
  subtitle: string
  icon: React.ComponentType<{ className?: string }>
  accent: 'emerald' | 'blue' | 'violet' | 'amber'
  items: { name: string; value: string; positive: boolean }[]
}) {
  const accentStyles = {
    emerald: {
      bg: 'bg-emerald-500/15',
      text: 'text-emerald-400',
      border: 'border-emerald-500/20',
    },
    blue: {
      bg: 'bg-blue-500/15',
      text: 'text-blue-400',
      border: 'border-blue-500/20',
    },
    violet: {
      bg: 'bg-violet-500/15',
      text: 'text-violet-400',
      border: 'border-violet-500/20',
    },
    amber: {
      bg: 'bg-amber-500/15',
      text: 'text-amber-400',
      border: 'border-amber-500/20',
    },
  }

  const styles = accentStyles[accent]

  return (
    <div className="bg-card/50 rounded-2xl border border-border/50 overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border/50">
        <div className={cn(
          'flex items-center justify-center w-8 h-8 rounded-lg',
          styles.bg
        )}>
          <Icon className={cn('h-4 w-4', styles.text)} />
        </div>
        <div>
          <h3 className="font-semibold text-sm">{title}</h3>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
      </div>
      <div className="p-4 space-y-3">
        {items.map((item, i) => (
          <div
            key={i}
            className="flex items-center justify-between group cursor-pointer hover:bg-muted/30 -mx-2 px-2 py-1.5 rounded-lg transition-colors"
          >
            <span className="text-sm truncate">{item.name}</span>
            <span className={cn(
              'font-mono text-sm font-medium',
              item.positive ? 'text-emerald-400' : 'text-red-400'
            )}>
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}