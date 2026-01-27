import { useState } from 'react'
import { useBets, useBetStats } from '@/hooks/useBetting'
import { formatCurrency, formatPercent, formatOdds } from '@/lib/utils'
import { Plus, Filter, Download } from 'lucide-react'

export default function BetTracker() {
  const [showAddBet, setShowAddBet] = useState(false)
  const { data: bets, isLoading } = useBets({ limit: 50 })
  const { data: stats } = useBetStats()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Bet Tracker</h1>
          <p className="text-muted-foreground">
            Track your bets and analyze performance
          </p>
        </div>
        <div className="flex gap-2">
          <button className="flex items-center gap-2 px-4 py-2 rounded-md border border-border hover:bg-muted">
            <Filter className="h-4 w-4" />
            Filter
          </button>
          <button className="flex items-center gap-2 px-4 py-2 rounded-md border border-border hover:bg-muted">
            <Download className="h-4 w-4" />
            Export
          </button>
          <button
            onClick={() => setShowAddBet(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md"
          >
            <Plus className="h-4 w-4" />
            Add Bet
          </button>
        </div>
      </div>

      {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <StatCard label="Total P/L" value={formatCurrency(stats.totalProfit)} isPositive={stats.totalProfit >= 0} />
          <StatCard label="ROI" value={formatPercent(stats.roi)} isPositive={stats.roi >= 0} />
          <StatCard label="Win Rate" value={formatPercent(stats.winRate)} />
          <StatCard label="Total Bets" value={stats.totalBets.toString()} />
          <StatCard label="Pending" value={stats.pendingBets.toString()} />
          <StatCard label="Avg CLV" value={stats.avgClv ? formatPercent(stats.avgClv) : 'N/A'} />
        </div>
      )}

      {/* Bet History Table */}
      <div className="bg-card rounded-lg border border-border">
        <div className="px-6 py-4 border-b border-border">
          <h2 className="font-semibold">Recent Bets</h2>
        </div>

        {isLoading ? (
          <div className="p-6 text-center text-muted-foreground">Loading...</div>
        ) : bets && bets.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="text-left px-4 py-3">Date</th>
                  <th className="text-left px-4 py-3">Selection</th>
                  <th className="text-left px-4 py-3">Type</th>
                  <th className="text-right px-4 py-3">Odds</th>
                  <th className="text-right px-4 py-3">Stake</th>
                  <th className="text-right px-4 py-3">Result</th>
                  <th className="text-right px-4 py-3">P/L</th>
                </tr>
              </thead>
              <tbody>
                {bets.map((bet) => (
                  <tr key={bet.id} className="border-b border-border hover:bg-muted/50">
                    <td className="px-4 py-3">
                      {new Date(bet.placedAt).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 font-medium">{bet.selection}</td>
                    <td className="px-4 py-3 text-muted-foreground capitalize">
                      {bet.betType.replace('_', ' ')}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {formatOdds(bet.oddsAmerican)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {formatCurrency(bet.stake)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          bet.result === 'win'
                            ? 'bg-green-500/10 text-green-500'
                            : bet.result === 'loss'
                            ? 'bg-red-500/10 text-red-500'
                            : bet.result === 'push'
                            ? 'bg-yellow-500/10 text-yellow-500'
                            : 'bg-muted text-muted-foreground'
                        }`}
                      >
                        {bet.result.toUpperCase()}
                      </span>
                    </td>
                    <td
                      className={`px-4 py-3 text-right font-medium ${
                        (bet.profitLoss ?? 0) >= 0 ? 'text-green-500' : 'text-red-500'
                      }`}
                    >
                      {bet.profitLoss !== undefined
                        ? formatCurrency(bet.profitLoss)
                        : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-6 text-center text-muted-foreground">
            No bets recorded yet. Add your first bet to start tracking.
          </div>
        )}
      </div>

      {/* Add Bet Modal */}
      {showAddBet && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-card rounded-lg border border-border p-6 w-full max-w-md">
            <h2 className="font-semibold text-lg mb-4">Add New Bet</h2>
            <form className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Selection</label>
                <input
                  type="text"
                  placeholder="e.g., Lakers -4.5"
                  className="w-full px-3 py-2 rounded-md border border-border bg-background"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Bet Type</label>
                  <select className="w-full px-3 py-2 rounded-md border border-border bg-background">
                    <option value="spread">Spread</option>
                    <option value="moneyline">Moneyline</option>
                    <option value="total">Total</option>
                    <option value="player_prop">Player Prop</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Odds</label>
                  <input
                    type="number"
                    placeholder="-110"
                    className="w-full px-3 py-2 rounded-md border border-border bg-background"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Stake</label>
                  <input
                    type="number"
                    placeholder="100"
                    className="w-full px-3 py-2 rounded-md border border-border bg-background"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Sportsbook</label>
                  <select className="w-full px-3 py-2 rounded-md border border-border bg-background">
                    <option value="">Select...</option>
                    <option value="draftkings">DraftKings</option>
                    <option value="fanduel">FanDuel</option>
                    <option value="betmgm">BetMGM</option>
                    <option value="caesars">Caesars</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setShowAddBet(false)}
                  className="px-4 py-2 rounded-md border border-border hover:bg-muted"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-md"
                >
                  Add Bet
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({
  label,
  value,
  isPositive,
}: {
  label: string
  value: string
  isPositive?: boolean
}) {
  return (
    <div className="bg-card rounded-lg border border-border p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p
        className={`text-xl font-bold ${
          isPositive !== undefined
            ? isPositive
              ? 'text-green-500'
              : 'text-red-500'
            : ''
        }`}
      >
        {value}
      </p>
    </div>
  )
}
