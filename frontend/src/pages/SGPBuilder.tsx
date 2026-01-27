import { useState } from 'react'
import { usePredictions } from '@/hooks/usePredictions'
import { useCalculateSGP } from '@/hooks/useSGP'
import { formatPercent, formatOdds, sportDisplayName, formatEdge } from '@/lib/utils'
import type { GameWithPredictions, SGPLeg, Prediction, MoneylinePrediction, SpreadPrediction, TotalPrediction } from '@/types'
import {
  Calculator,
  Plus,
  Trash2,
  ArrowRight,
  TrendingUp,
  Check,
  AlertCircle
} from 'lucide-react'
import { cn } from '@/lib/utils'

export default function SGPBuilder() {
  const [selectedGame, setSelectedGame] = useState<GameWithPredictions | null>(null)
  const [selectedLegs, setSelectedLegs] = useState<SGPLeg[]>([])
  const [marketOdds, setMarketOdds] = useState<string>('')
  
  const { data: games, isLoading: gamesLoading } = usePredictions({
    // Fetch upcoming games for all sports
  })

  const calculateMutation = useCalculateSGP()

  const handleAddLeg = (leg: SGPLeg) => {
    if (selectedLegs.length >= 10) return
    if (selectedLegs.some(l => l.type === leg.type && l.description === leg.description)) return
    setSelectedLegs([...selectedLegs, leg])
    calculateMutation.reset()
  }

  const handleRemoveLeg = (index: number) => {
    const newLegs = [...selectedLegs]
    newLegs.splice(index, 1)
    setSelectedLegs(newLegs)
    calculateMutation.reset()
  }

  const handleCalculate = () => {
    if (!selectedGame || selectedLegs.length < 2) return

    const odds = parseInt(marketOdds)
    
    calculateMutation.mutate({
      sport: selectedGame.sport,
      gameId: selectedGame.id.toString(),
      legs: selectedLegs,
      marketOddsAmerican: !isNaN(odds) ? odds : undefined
    })
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      {/* Left Column: Game Selection & Legs */}
      <div className="lg:col-span-2 space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2">SGP Builder</h1>
          <p className="text-muted-foreground">
            Build correlated parlays and discover true probabilities.
          </p>
        </div>

        {/* Game Selector */}
        <div className="bg-card/50 rounded-2xl border border-border/50 overflow-hidden">
          <div className="p-4 border-b border-border/50 bg-muted/20">
            <h3 className="font-semibold">1. Select a Game</h3>
          </div>
          <div className="p-4">
             {gamesLoading ? (
               <div className="space-y-2">
                 {[1,2,3].map(i => <div key={i} className="skeleton h-12 w-full rounded-lg" />)}
               </div>
             ) : (
               <select 
                 className="select select-bordered w-full"
                 onChange={(e) => {
                    const game = games?.find(g => g.id.toString() === e.target.value)
                    setSelectedGame(game || null)
                    setSelectedLegs([])
                    calculateMutation.reset()
                 }}
                 value={selectedGame?.id || ''}
               >
                 <option value="">Choose a matchup...</option>
                 {games?.map(game => (
                   <option key={game.id} value={game.id}>
                     {sportDisplayName(game.sport)}: {game.awayTeam.name} @ {game.homeTeam.name}
                   </option>
                 ))}
               </select>
             )}
          </div>
        </div>

        {/* Available Legs */}
        {selectedGame && (
          <div className="bg-card/50 rounded-2xl border border-border/50 overflow-hidden animate-in fade-in slide-in-from-bottom-4">
             <div className="p-4 border-b border-border/50 bg-muted/20">
              <h3 className="font-semibold">2. Add Legs</h3>
            </div>
            <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* Moneyline Options */}
              {selectedGame.predictions.moneyline && (
                <>
                  <LegButton 
                    label={`${selectedGame.homeTeam.name} ML`}
                    subLabel={`Win Prob: ${formatPercent((selectedGame.predictions.moneyline.prediction as MoneylinePrediction).homeProb)}`}
                    onClick={() => handleAddLeg({
                      type: 'moneyline_home', // Simplified type
                      prob: (selectedGame.predictions.moneyline!.prediction as MoneylinePrediction).homeProb,
                      description: `${selectedGame.homeTeam.name} Moneyline`
                    })}
                  />
                  <LegButton 
                    label={`${selectedGame.awayTeam.name} ML`}
                    subLabel={`Win Prob: ${formatPercent((selectedGame.predictions.moneyline.prediction as MoneylinePrediction).awayProb)}`}
                    onClick={() => handleAddLeg({
                      type: 'moneyline_away',
                      prob: (selectedGame.predictions.moneyline!.prediction as MoneylinePrediction).awayProb,
                      description: `${selectedGame.awayTeam.name} Moneyline`
                    })}
                  />
                </>
              )}

              {/* Spread Options */}
              {selectedGame.predictions.spread && (
                <>
                   <LegButton 
                    label={`${selectedGame.homeTeam.name} ${formatSpread((selectedGame.predictions.spread.prediction as SpreadPrediction).predictedSpread)}`}
                    subLabel={`Cover Prob: ${formatPercent((selectedGame.predictions.spread.prediction as SpreadPrediction).homeCoverProb)}`}
                    onClick={() => handleAddLeg({
                      type: 'spread_home',
                      prob: (selectedGame.predictions.spread!.prediction as SpreadPrediction).homeCoverProb,
                      description: `${selectedGame.homeTeam.name} ${formatSpread((selectedGame.predictions.spread!.prediction as SpreadPrediction).predictedSpread)}`
                    })}
                  />
                   {/* We assume symmetric prob for away spread for now if not explicit */}
                   <LegButton 
                    label={`${selectedGame.awayTeam.name} ${formatSpread(-(selectedGame.predictions.spread.prediction as SpreadPrediction).predictedSpread)}`}
                    subLabel={`Cover Prob: ${formatPercent(1 - (selectedGame.predictions.spread.prediction as SpreadPrediction).homeCoverProb - (selectedGame.predictions.spread.prediction as SpreadPrediction).pushProb)}`}
                    onClick={() => handleAddLeg({
                      type: 'spread_away',
                      prob: 1 - (selectedGame.predictions.spread!.prediction as SpreadPrediction).homeCoverProb - (selectedGame.predictions.spread!.prediction as SpreadPrediction).pushProb,
                      description: `${selectedGame.awayTeam.name} ${formatSpread(-(selectedGame.predictions.spread!.prediction as SpreadPrediction).predictedSpread)}`
                    })}
                  />
                </>
              )}
              
               {/* Total Options */}
               {selectedGame.predictions.total && (
                <>
                  <LegButton 
                    label={`Over ${(selectedGame.predictions.total.prediction as TotalPrediction).predictedTotal}`}
                    subLabel={`Prob: ${formatPercent((selectedGame.predictions.total.prediction as TotalPrediction).overProb)}`}
                    onClick={() => handleAddLeg({
                      type: 'total_over',
                      prob: (selectedGame.predictions.total!.prediction as TotalPrediction).overProb,
                      description: `Over ${(selectedGame.predictions.total!.prediction as TotalPrediction).predictedTotal}`
                    })}
                  />
                  <LegButton 
                    label={`Under ${(selectedGame.predictions.total.prediction as TotalPrediction).predictedTotal}`}
                    subLabel={`Prob: ${formatPercent((selectedGame.predictions.total.prediction as TotalPrediction).underProb)}`}
                    onClick={() => handleAddLeg({
                      type: 'total_under',
                      prob: (selectedGame.predictions.total!.prediction as TotalPrediction).underProb,
                      description: `Under ${(selectedGame.predictions.total!.prediction as TotalPrediction).predictedTotal}`
                    })}
                  />
                </>
              )}
              
              {/* Placeholder for props - in real app would map props here */}
              <div className="col-span-full mt-2 p-3 bg-muted/30 rounded-lg text-center text-sm text-muted-foreground border border-dashed border-border">
                 Player props would appear here
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Right Column: Slip & Calculation */}
      <div className="space-y-6">
        <div className="bg-card border border-border rounded-2xl shadow-lg sticky top-6">
          <div className="p-4 border-b border-border flex items-center justify-between bg-muted/20 rounded-t-2xl">
            <h3 className="font-semibold flex items-center gap-2">
              <Calculator className="h-4 w-4" />
              SGP Slip
            </h3>
            <span className="badge badge-neutral">{selectedLegs.length} Legs</span>
          </div>
          
          <div className="p-4 space-y-4">
             {selectedLegs.length === 0 ? (
               <div className="text-center py-8 text-muted-foreground">
                 <p className="text-sm">Select legs to build your parlay</p>
               </div>
             ) : (
               <div className="space-y-2">
                 {selectedLegs.map((leg, idx) => (
                   <div key={idx} className="flex items-center justify-between p-3 bg-muted/30 rounded-lg group">
                     <div>
                       <p className="font-medium text-sm">{leg.description}</p>
                       <p className="text-xs text-muted-foreground">Model Prob: {formatPercent(leg.prob)}</p>
                     </div>
                     <button 
                       onClick={() => handleRemoveLeg(idx)}
                       className="text-muted-foreground hover:text-red-400 transition-colors p-1"
                     >
                       <Trash2 className="h-4 w-4" />
                     </button>
                   </div>
                 ))}
               </div>
             )}
             
             {selectedLegs.length >= 2 && (
               <div className="pt-4 border-t border-border/50 space-y-4">
                 <div>
                   <label className="text-xs font-medium text-muted-foreground mb-1 block">
                     Sportsbook Odds (Optional)
                   </label>
                   <div className="relative">
                     <span className="absolute left-3 top-2.5 text-muted-foreground font-mono text-sm">+</span>
                     <input 
                       type="number" 
                       placeholder="e.g. 450" 
                       className="input input-bordered w-full pl-7"
                       value={marketOdds}
                       onChange={(e) => setMarketOdds(e.target.value)}
                     />
                   </div>
                 </div>
                 
                 <button 
                   className={cn(
                     "btn-primary w-full", 
                     calculateMutation.isPending && "loading"
                   )}
                   onClick={handleCalculate}
                   disabled={calculateMutation.isPending}
                 >
                   Calculate True Probability
                 </button>
               </div>
             )}
             
             {/* Results */}
             {calculateMutation.isSuccess && calculateMutation.data && (
               <div className="mt-4 pt-4 border-t border-border animate-in fade-in zoom-in-95">
                 <div className="text-center mb-4">
                   <p className="text-sm text-muted-foreground mb-1">True Probability</p>
                   <p className="text-3xl font-bold text-primary">
                     {formatPercent(calculateMutation.data.trueProb)}
                   </p>
                   <p className="text-xs text-muted-foreground mt-1">
                     Estimated via Monte Carlo ({calculateMutation.data.individualProbs.length} correlated legs)
                   </p>
                 </div>
                 
                 {calculateMutation.data.ev !== undefined && (
                   <div className="grid grid-cols-2 gap-3">
                     <div className="p-3 bg-muted/30 rounded-lg text-center">
                       <p className="text-xs text-muted-foreground">Edge</p>
                       <p className={cn(
                         "font-bold font-mono",
                         formatEdge(calculateMutation.data.edge || 0).className
                       )}>
                         {formatEdge(calculateMutation.data.edge || 0).text}
                       </p>
                     </div>
                     <div className="p-3 bg-muted/30 rounded-lg text-center">
                       <p className="text-xs text-muted-foreground">EV</p>
                       <p className={cn(
                         "font-bold font-mono",
                         (calculateMutation.data.ev || 0) > 0 ? "text-emerald-400" : "text-red-400"
                       )}>
                         {((calculateMutation.data.ev || 0) * 100).toFixed(1)}%
                       </p>
                     </div>
                   </div>
                 )}
               </div>
             )}
             
             {calculateMutation.isError && (
               <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-start gap-2">
                 <AlertCircle className="h-5 w-5 text-red-400 shrink-0" />
                 <p className="text-sm text-red-400">
                   {calculateMutation.error.message}
                 </p>
               </div>
             )}
          </div>
        </div>
      </div>
    </div>
  )
}

function LegButton({ label, subLabel, onClick }: { label: string, subLabel: string, onClick: () => void }) {
  return (
    <button 
      onClick={onClick}
      className="flex flex-col items-start p-3 rounded-xl border border-border/50 bg-card hover:bg-muted/50 hover:border-primary/50 transition-all text-left group"
    >
      <div className="flex w-full justify-between items-start">
        <span className="font-medium">{label}</span>
        <Plus className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity text-primary" />
      </div>
      <span className="text-xs text-muted-foreground">{subLabel}</span>
    </button>
  )
}

function formatSpread(spread: number) {
  if (spread > 0) return `+${spread}`
  return spread.toString()
}