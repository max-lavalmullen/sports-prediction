import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePredictions, useValueBets } from '@/hooks/usePredictions'
import { useBetStats } from '@/hooks/useBetting'
import { formatPercent, formatCurrency, formatOdds, formatEdge, sportDisplayName } from '@/lib/utils'
import type { Sport } from '@/types'
import {
  TrendingUp,
  TrendingDown,
  Target,
  DollarSign,
  Activity,
  Sparkles,
  ArrowUpRight,
  Clock,
  Flame,
  ChevronRight,
  AlertCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const sports: (Sport | 'all')[] = ['all', 'nba', 'nfl', 'mlb', 'soccer']

const sportLabels: Record<string, string> = {
  all: 'All Sports',
  nba: 'Basketball',
  nfl: 'Football',
  mlb: 'Baseball',
  soccer: 'Soccer',
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [selectedSport, setSelectedSport] = useState<Sport | 'all'>('all')

  // Don't filter by date - show all upcoming games
  const { data: predictions, isLoading: predictionsLoading } = usePredictions({
    sport: selectedSport === 'all' ? undefined : selectedSport,
    // No date filter - show all upcoming games
  })

  const { data: valueBets, isLoading: valueLoading } = useValueBets({
    sport: selectedSport === 'all' ? undefined : selectedSport,
    minEdge: 0.03,
    limit: 10,
  })

  const { data: betStats } = useBetStats()

  return (
    <div className="space-y-8">
      {/* Sport filter pills */}
      <div className="flex items-center gap-2">
        {sports.map((sport) => (
          <button
            key={sport}
            onClick={() => setSelectedSport(sport)}
            className={cn(
              'px-4 py-2 rounded-full text-sm font-medium transition-all duration-200',
              selectedSport === sport
                ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/25'
                : 'bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
          >
            {sportLabels[sport]}
          </button>
        ))}
      </div>

      {/* Performance metrics */}
      {betStats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Total Returns"
            value={formatCurrency(betStats.totalProfit)}
            trend={betStats.totalProfit >= 0 ? 'up' : 'down'}
            trendValue={betStats.totalProfit >= 0 ? '+12.4% this month' : '-3.2% this month'}
            icon={DollarSign}
            accent="emerald"
          />
          <MetricCard
            label="Return on Investment"
            value={formatPercent(betStats.roi)}
            trend={betStats.roi >= 0 ? 'up' : 'down'}
            trendValue="Lifetime average"
            icon={TrendingUp}
            accent="blue"
          />
          <MetricCard
            label="Success Rate"
            value={formatPercent(betStats.winRate)}
            trend={betStats.winRate >= 0.52 ? 'up' : 'neutral'}
            trendValue={`${betStats.totalBets} total predictions`}
            icon={Target}
            accent="violet"
          />
          <MetricCard
            label="Active Positions"
            value={betStats.totalBets.toString()}
            icon={Activity}
            accent="amber"
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Value opportunities */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-emerald-500/15">
                <Sparkles className="h-4 w-4 text-emerald-400" />
              </div>
              <div>
                <h3 className="font-semibold">Value Opportunities</h3>
                <p className="text-xs text-muted-foreground">Edges detected by our models</p>
              </div>
            </div>
            <span className="badge badge-success">
              <Flame className="h-3 w-3 mr-1" />
              {valueBets?.length || 0} found
            </span>
          </div>

          <div className="bg-card/50 rounded-2xl border border-border/50 overflow-hidden">
            {valueLoading ? (
              <div className="p-8">
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="skeleton h-20 rounded-xl" />
                  ))}
                </div>
              </div>
            ) : valueBets && valueBets.length > 0 ? (
              <div className="divide-y divide-border/50">
                {valueBets.map((bet, i) => {
                  const { text: edgeText, className: edgeClass } = formatEdge(bet.edge)
                  const isHighValue = bet.edge >= 0.05
                  return (
                    <div
                      key={i}
                      className={cn(
                        'group flex items-center justify-between p-4 transition-all duration-200',
                        'hover:bg-muted/30 cursor-pointer',
                        isHighValue && 'bg-emerald-500/5'
                      )}
                    >
                      <div className="flex items-center gap-4">
                        {isHighValue && (
                          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/20">
                            <Flame className="h-5 w-5 text-emerald-400" />
                          </div>
                        )}
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-medium">{bet.selection}</p>
                            {isHighValue && (
                              <span className="badge badge-success text-[10px]">High Value</span>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {bet.predictionType.replace('_', ' ')} prediction
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-6">
                        <div className="text-right">
                          <p className={cn('font-mono font-semibold text-lg', edgeClass)}>
                            {edgeText}
                          </p>
                          <p className="text-xs text-muted-foreground">edge detected</p>
                        </div>
                        <div className="text-right">
                          <p className="font-mono text-sm">
                            {formatOdds(bet.marketOdds)}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {formatPercent(bet.ourProb)} confidence
                          </p>
                        </div>
                        <ChevronRight className="h-5 w-5 text-muted-foreground/50 group-hover:text-foreground transition-colors" />
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <EmptyState
                icon={Sparkles}
                title="No opportunities right now"
                description="Our models are continuously scanning. Check back soon for new value plays."
              />
            )}
          </div>
        </div>

        {/* Today's games */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-500/15">
                <Clock className="h-4 w-4 text-blue-400" />
              </div>
              <div>
                <h3 className="font-semibold">Upcoming Matchups</h3>
                <p className="text-xs text-muted-foreground">Games with predictions</p>
              </div>
            </div>
          </div>

          <div className="bg-card/50 rounded-2xl border border-border/50 overflow-hidden">
            {predictionsLoading ? (
              <div className="p-4 space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="skeleton h-24 rounded-xl" />
                ))}
              </div>
            ) : predictions && predictions.length > 0 ? (
              <div className="divide-y divide-border/50 max-h-[500px] overflow-y-auto">
                {predictions.slice(0, 10).map((game) => (
                  <div
                    key={game.id}
                    className="group p-4 transition-all duration-200 hover:bg-muted/30 cursor-pointer"
                    onClick={() => navigate(`/analytics?game=${game.id}`)}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span className="badge badge-info text-[10px]">
                        {sportDisplayName(game.sport)}
                      </span>
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(game.scheduledTime).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                    <p className="font-medium mb-1">
                      {game.awayTeam.name} <span className="text-muted-foreground">@</span> {game.homeTeam.name}
                    </p>
                    {game.predictions.spread && (
                      <div className="flex items-center justify-between mt-2 pt-2 border-t border-border/30">
                        <span className="text-xs text-muted-foreground">Projected spread</span>
                        <span className="font-mono text-sm">
                          {game.homeTeam.name.split(' ').pop()}{' '}
                          <span className={cn(
                            (game.predictions.spread.prediction as { predictedSpread: number }).predictedSpread > 0
                              ? 'text-emerald-400'
                              : 'text-red-400'
                          )}>
                            {(game.predictions.spread.prediction as { predictedSpread: number }).predictedSpread > 0 ? '+' : ''}
                            {(game.predictions.spread.prediction as { predictedSpread: number }).predictedSpread?.toFixed(1)}
                          </span>
                        </span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={Clock}
                title="No upcoming games"
                description="Check back later for new matchups and predictions."
              />
            )}
          </div>
        </div>
      </div>

      {/* Live alerts section */}
      <div className="bg-card/50 rounded-2xl border border-border/50 overflow-hidden">
        <div className="flex items-center gap-3 px-6 py-4 border-b border-border/50">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-amber-500/15">
            <AlertCircle className="h-4 w-4 text-amber-400" />
          </div>
          <div>
            <h3 className="font-semibold">Live Notifications</h3>
            <p className="text-xs text-muted-foreground">Real-time alerts for line movements and new opportunities</p>
          </div>
        </div>
        <div className="p-8 text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-muted/50 mb-4">
            <AlertCircle className="h-6 w-6 text-muted-foreground" />
          </div>
          <p className="text-muted-foreground mb-4">
            Enable real-time notifications to stay ahead of line movements
          </p>
          <button className="btn-primary btn-md">
            Enable Notifications
          </button>
        </div>
      </div>
    </div>
  )
}

function MetricCard({
  label,
  value,
  trend,
  trendValue,
  icon: Icon,
  accent = 'emerald',
}: {
  label: string
  value: string
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
  icon: React.ComponentType<{ className?: string }>
  accent?: 'emerald' | 'blue' | 'violet' | 'amber'
}) {
  const accentColors = {
    emerald: {
      bg: 'bg-emerald-500/15',
      border: 'border-emerald-500/20',
      text: 'text-emerald-400',
      glow: 'shadow-emerald-500/10',
    },
    blue: {
      bg: 'bg-blue-500/15',
      border: 'border-blue-500/20',
      text: 'text-blue-400',
      glow: 'shadow-blue-500/10',
    },
    violet: {
      bg: 'bg-violet-500/15',
      border: 'border-violet-500/20',
      text: 'text-violet-400',
      glow: 'shadow-violet-500/10',
    },
    amber: {
      bg: 'bg-amber-500/15',
      border: 'border-amber-500/20',
      text: 'text-amber-400',
      glow: 'shadow-amber-500/10',
    },
  }

  const colors = accentColors[accent]

  return (
    <div className={cn(
      'stat-card group',
      trend === 'up' && 'hover:shadow-emerald-500/5',
      trend === 'down' && 'hover:shadow-red-500/5'
    )}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground mb-1">{label}</p>
          <p className={cn(
            'text-2xl font-bold tracking-tight',
            trend === 'up' && 'text-emerald-400',
            trend === 'down' && 'text-red-400'
          )}>
            {value}
          </p>
          {trendValue && (
            <div className="flex items-center gap-1 mt-2">
              {trend === 'up' && <ArrowUpRight className="h-3 w-3 text-emerald-400" />}
              {trend === 'down' && <TrendingDown className="h-3 w-3 text-red-400" />}
              <span className="text-xs text-muted-foreground">{trendValue}</span>
            </div>
          )}
        </div>
        <div className={cn(
          'flex items-center justify-center w-10 h-10 rounded-xl border',
          colors.bg,
          colors.border
        )}>
          <Icon className={cn('h-5 w-5', colors.text)} />
        </div>
      </div>
    </div>
  )
}

function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ComponentType<{ className?: string }>
  title: string
  description: string
}) {
  return (
    <div className="p-8 text-center">
      <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-muted/50 mb-4">
        <Icon className="h-6 w-6 text-muted-foreground" />
      </div>
      <h4 className="font-medium mb-1">{title}</h4>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  )
}