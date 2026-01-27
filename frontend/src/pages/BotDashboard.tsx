import { useState } from 'react'
import { useBotStatus, useBotLogs } from '@/hooks/useBot'
import { formatCurrency } from '@/lib/utils'
import {
  Bot,
  Play,
  Square,
  Activity,
  DollarSign,
  ScrollText,
  AlertCircle
} from 'lucide-react'
import { cn } from '@/lib/utils'

export default function BotDashboard() {
  const [selectedBotId, setSelectedBotId] = useState('paper_default')
  
  const { data: status, isLoading: statusLoading } = useBotStatus(selectedBotId)
  const { data: logs, isLoading: logsLoading } = useBotLogs(selectedBotId)

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Bot Dashboard</h1>
        <p className="text-muted-foreground">
          Monitor and control your automated betting strategies.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Status Card */}
        <div className="lg:col-span-2">
           <div className="bg-card rounded-2xl border border-border shadow-sm p-6 relative overflow-hidden">
             <div className="absolute top-0 right-0 p-4 opacity-5">
               <Bot className="h-40 w-40" />
             </div>
             
             <div className="flex items-center gap-4 mb-6 relative">
               <div className={cn(
                 "w-16 h-16 rounded-2xl flex items-center justify-center shadow-lg",
                 status?.isActive ? "bg-emerald-500 text-white" : "bg-muted text-muted-foreground"
               )}>
                 <Bot className="h-8 w-8" />
               </div>
               <div>
                 <h2 className="text-2xl font-bold">Paper Trading Bot</h2>
                 <div className="flex items-center gap-2 mt-1">
                   <span className={cn(
                     "w-2 h-2 rounded-full animate-pulse",
                     status?.isActive ? "bg-emerald-500" : "bg-red-500"
                   )} />
                   <span className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                     {status?.isActive ? 'Running' : 'Stopped'}
                   </span>
                 </div>
               </div>
             </div>
             
             <div className="grid grid-cols-2 gap-4 relative z-10">
               <div className="bg-background/50 rounded-xl p-4 border border-border/50">
                 <p className="text-sm text-muted-foreground mb-1">Current Balance</p>
                 <p className="text-3xl font-mono font-bold">
                   {status ? formatCurrency(status.balance) : '---'}
                 </p>
               </div>
               <div className="bg-background/50 rounded-xl p-4 border border-border/50">
                 <p className="text-sm text-muted-foreground mb-1">Active Bets</p>
                 <p className="text-3xl font-mono font-bold">
                   {status?.activeBetsCount || 0}
                 </p>
               </div>
             </div>
             
             <div className="mt-6 flex gap-3 relative z-10">
               <button className="btn-primary gap-2">
                 <Play className="h-4 w-4" /> Start Bot
               </button>
               <button className="btn-outline border-red-500/30 text-red-500 hover:bg-red-500/10 gap-2">
                 <Square className="h-4 w-4 fill-current" /> Stop
               </button>
             </div>
           </div>
           
           {/* Recent Activity */}
           <div className="mt-6">
             <h3 className="font-semibold mb-4 flex items-center gap-2">
               <Activity className="h-4 w-4" /> Recent Activity
             </h3>
             
             <div className="bg-card rounded-2xl border border-border shadow-sm overflow-hidden">
               {logsLoading ? (
                 <div className="p-4 space-y-2">
                   {[1,2,3].map(i => <div key={i} className="skeleton h-12 rounded-lg" />)}
                 </div>
               ) : logs && logs.length > 0 ? (
                 <div className="divide-y divide-border/50">
                   {logs.map((log: any) => (
                     <div key={log.id} className="p-4 flex items-center justify-between text-sm">
                       <div>
                         <p className="font-medium">{log.action}</p>
                         <p className="text-xs text-muted-foreground">{new Date(log.timestamp).toLocaleString()}</p>
                       </div>
                       <div className="text-right">
                         <p>{log.message}</p>
                       </div>
                     </div>
                   ))}
                 </div>
               ) : (
                 <div className="p-12 text-center text-muted-foreground">
                   <ScrollText className="h-12 w-12 mx-auto mb-3 opacity-20" />
                   <p>No activity logs found</p>
                 </div>
               )}
             </div>
           </div>
        </div>
        
        {/* Settings/Info */}
        <div className="space-y-6">
           <div className="bg-card rounded-2xl border border-border shadow-sm p-5">
             <h3 className="font-semibold mb-4">Strategy Configuration</h3>
             <div className="space-y-4 text-sm">
               <div className="flex justify-between py-2 border-b border-border/50">
                 <span className="text-muted-foreground">Mode</span>
                 <span className="font-medium">Paper Trading</span>
               </div>
               <div className="flex justify-between py-2 border-b border-border/50">
                 <span className="text-muted-foreground">Min Edge</span>
                 <span className="font-medium">5.0%</span>
               </div>
               <div className="flex justify-between py-2 border-b border-border/50">
                 <span className="text-muted-foreground">Kelly Fraction</span>
                 <span className="font-medium">0.25</span>
               </div>
               <div className="flex justify-between py-2 border-b border-border/50">
                 <span className="text-muted-foreground">Max Stake</span>
                 <span className="font-medium">2.0%</span>
               </div>
               <div className="pt-2">
                 <button className="btn-outline w-full text-xs h-8">Edit Configuration</button>
               </div>
             </div>
           </div>
           
           <div className="bg-blue-500/10 border border-blue-500/20 rounded-2xl p-5">
             <div className="flex gap-3">
               <AlertCircle className="h-5 w-5 text-blue-400 shrink-0 mt-0.5" />
               <div>
                 <h4 className="font-semibold text-blue-400 text-sm">Safety Mode Active</h4>
                 <p className="text-xs text-blue-400/80 mt-1">
                   The bot is running in safety mode. It will only place bets with high confidence and strictly adhere to bankroll management rules.
                 </p>
               </div>
             </div>
           </div>
        </div>
      </div>
    </div>
  )
}
