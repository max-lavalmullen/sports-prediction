import { useState } from 'react'
import { useArbitrage } from '@/hooks/useArbitrage'
import { formatPercent, formatOdds, sportDisplayName } from '@/lib/utils'
import type { Sport } from '@/types'
import {
  RefreshCw,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
  DollarSign,
  Percent,
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

export default function Arbitrage() {
  const [selectedSport, setSelectedSport] = useState<Sport | 'all'>('all')
  const [showMiddles, setShowMiddles] = useState(true)

  // We can't query 'all' directly based on the hook, so we default to 'nba' if 'all' is selected for now
  // or we need to modify the hook/API to accept 'all'. 
  // For this prototype, let's just use 'nba' default or fetch all individually if 'all' selected.
  // Actually, let's stick to single sport selection for simplicity or pick the first one.
  const sportToQuery = selectedSport === 'all' ? 'nba' : selectedSport

  const { data: opportunities, isLoading, refetch } = useArbitrage(sportToQuery, {
    includeArbs: true,
    includeMiddles: showMiddles,
    includeLowHold: false,
  })

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2">Arbitrage Scanner</h1>
          <p className="text-muted-foreground">
            Find guaranteed profit opportunities and middle bets across sportsbooks.
          </p>
        </div>
        <button 
          onClick={() => refetch()}
          className="btn-outline btn-sm gap-2"
        >
          <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center justify-between bg-card/50 p-4 rounded-xl border border-border/50">
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
        
        <div className="flex items-center gap-4">
           <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
            <input 
              type="checkbox" 
              checked={showMiddles}
              onChange={(e) => setShowMiddles(e.target.checked)}
              className="checkbox checkbox-primary checkbox-sm" 
            />
            Show Middles
          </label>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="stat-card">
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/20">
              <DollarSign className="h-5 w-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Arb Opportunities</p>
              <p className="text-2xl font-bold">
                {opportunities?.filter(o => o.opportunityType === 'arbitrage').length || 0}
              </p>
            </div>
          </div>
        </div>
        
        <div className="stat-card">
           <div className="flex items-center gap-4">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-blue-500/15 border border-blue-500/20">
              <TargetIcon className="h-5 w-5 text-blue-400" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Middle Opportunities</p>
              <p className="text-2xl font-bold">
                {opportunities?.filter(o => o.opportunityType === 'middle').length || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="stat-card">
           <div className="flex items-center gap-4">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-violet-500/15 border border-violet-500/20">
              <Percent className="h-5 w-5 text-violet-400" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Max Profit</p>
              <p className="text-2xl font-bold text-emerald-400">
                 {opportunities?.length ? formatPercent(Math.max(...opportunities.map(o => o.profitPct))/100) : '0.00%'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Opportunities List */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton h-32 rounded-xl" />
            ))}
          </div>
        ) : opportunities && opportunities.length > 0 ? (
          opportunities.map((opp, idx) => (
            <div 
              key={`${opp.gameId}-${idx}`}
              className={cn(
                "group relative overflow-hidden bg-card/50 hover:bg-card border border-border/50 rounded-2xl transition-all duration-300",
                opp.opportunityType === 'arbitrage' 
                  ? "hover:shadow-lg hover:shadow-emerald-500/5 hover:border-emerald-500/30"
                  : "hover:shadow-lg hover:shadow-blue-500/5 hover:border-blue-500/30"
              )}
            >
               {/* Left accent bar */}
               <div className={cn(
                "absolute left-0 top-0 bottom-0 w-1",
                opp.opportunityType === 'arbitrage' ? "bg-emerald-500" : "bg-blue-500"
              )} />

              <div className="p-6">
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={cn(
                        "badge text-[10px] font-bold uppercase tracking-wider",
                        opp.opportunityType === 'arbitrage' 
                          ? "badge-success" 
                          : "badge-info"
                      )}>
                        {opp.opportunityType}
                      </span>
                      <span className="text-xs text-muted-foreground font-mono">
                        {sportDisplayName(opp.sport)} • {opp.marketType.toUpperCase()}
                      </span>
                    </div>
                    <h3 className="text-lg font-semibold">
                      {opp.awayTeam} <span className="text-muted-foreground">@</span> {opp.homeTeam}
                    </h3>
                  </div>

                  <div className="text-right">
                    <p className={cn(
                      "text-2xl font-mono font-bold",
                      opp.profitPct > 0 ? "text-emerald-400" : "text-blue-400"
                    )}>
                      {formatPercent(opp.profitPct / 100)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {opp.opportunityType === 'arbitrage' ? 'Guaranteed Profit' : 'Middle Potential'}
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {/* Side 1 */}
                  <div className="p-4 rounded-xl bg-muted/30 border border-border/50">
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-semibold text-sm">{opp.book1}</span>
                      <span className="font-mono font-bold text-lg">{formatOdds(opp.odds1)}</span>
                    </div>
                    <div className="flex justify-between items-center text-sm text-muted-foreground">
                       <span>{opp.selection1}</span>
                       <span>{(opp.stake1Pct).toFixed(1)}% stake</span>
                    </div>
                  </div>

                  {/* Side 2 */}
                  <div className="p-4 rounded-xl bg-muted/30 border border-border/50">
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-semibold text-sm">{opp.book2}</span>
                      <span className="font-mono font-bold text-lg">{formatOdds(opp.odds2)}</span>
                    </div>
                    <div className="flex justify-between items-center text-sm text-muted-foreground">
                       <span>{opp.selection2}</span>
                       <span>{(opp.stake2Pct).toFixed(1)}% stake</span>
                    </div>
                  </div>

                  {/* Side 3 (if exists) */}
                  {opp.book3 && (
                    <div className="p-4 rounded-xl bg-muted/30 border border-border/50">
                      <div className="flex justify-between items-center mb-2">
                        <span className="font-semibold text-sm">{opp.book3}</span>
                         <span className="font-mono font-bold text-lg">{formatOdds(opp.odds3 || 0)}</span>
                      </div>
                      <div className="flex justify-between items-center text-sm text-muted-foreground">
                        <span>{opp.selection3}</span>
                        <span>{(opp.stake3Pct || 0).toFixed(1)}% stake</span>
                      </div>
                    </div>
                  )}
                  
                  {/* Action Button */}
                  <div className={cn(
                    "flex items-center justify-center",
                    opp.book3 ? "lg:col-span-3" : "md:col-span-2 lg:col-span-1"
                  )}>
                     <button className="btn-primary w-full h-full min-h-[60px] md:min-h-[auto] rounded-xl flex flex-col items-center justify-center gap-1">
                        <span className="font-semibold">Calculate Stakes</span>
                        <span className="text-xs opacity-80">Optimize your bet sizing</span>
                     </button>
                  </div>
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="p-12 text-center bg-card/50 rounded-2xl border border-border/50">
             <div className="inline-flex items-center justify-center w-16 h-16 rounded-3xl bg-muted/50 mb-6">
                <AlertTriangle className="h-8 w-8 text-muted-foreground" />
             </div>
             <h3 className="text-xl font-semibold mb-2">No opportunities found</h3>
             <p className="text-muted-foreground max-w-md mx-auto">
               We couldn't find any arbitrage or middle bets for {sportLabels[sportToQuery]} right now. 
               These opportunities are fleeting, so check back often or enable alerts.
             </p>
          </div>
        )}
      </div>
    </div>
  )
}

function TargetIcon({ className }: { className?: string }) {
  return (
    <svg 
      className={className} 
      xmlns="http://www.w3.org/2000/svg" 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      strokeWidth="2" 
      strokeLinecap="round" 
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  )
}
