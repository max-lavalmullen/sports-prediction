import { Outlet, NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  BarChart3,
  History,
  Wallet,
  FlaskConical,
  Settings,
  Bell,
  Zap,
  ChevronRight,
  Radio,
  Scale,
  Calculator,
  Bot
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAlertStore } from '@/stores/alertStore'

const navigation = [
  {
    name: 'Overview',
    href: '/',
    icon: LayoutDashboard,
    description: 'Live predictions & value bets'
  },
  {
    name: 'Arbitrage',
    href: '/arbitrage',
    icon: Scale,
    description: 'Guaranteed profit scanner'
  },
  {
    name: 'Insights',
    href: '/analytics',
    icon: BarChart3,
    description: 'Team & player analytics'
  },
  {
    name: 'SGP Builder',
    href: '/sgp',
    icon: Calculator,
    description: 'Correlation engine'
  },
  {
    name: 'Backtest',
    href: '/backtesting',
    icon: History,
    description: 'Historical performance'
  },
  {
    name: 'Portfolio',
    href: '/bets',
    icon: Wallet,
    description: 'Track your positions'
  },
  {
    name: 'Simulate',
    href: '/simulation',
    icon: FlaskConical,
    description: 'Monte Carlo projections'
  },
  {
    name: 'Bot',
    href: '/bot',
    icon: Bot,
    description: 'Automated strategies'
  },
]

const pageTitle: Record<string, { title: string; subtitle: string }> = {
  '/': { title: 'Overview', subtitle: 'Live predictions and market opportunities' },
  '/arbitrage': { title: 'Arbitrage', subtitle: 'Scanner for risk-free opportunities' },
  '/analytics': { title: 'Insights', subtitle: 'Deep analytics and performance trends' },
  '/sgp': { title: 'SGP Builder', subtitle: 'Build correlated parlays with true odds' },
  '/backtesting': { title: 'Backtest', subtitle: 'Validate strategies with historical data' },
  '/bets': { title: 'Portfolio', subtitle: 'Track and manage your positions' },
  '/simulation': { title: 'Simulate', subtitle: 'Project outcomes with Monte Carlo analysis' },
  '/bot': { title: 'Bot Dashboard', subtitle: 'Manage automated trading strategies' },
  '/settings': { title: 'Settings', subtitle: 'Configure your preferences' },
}

export default function Layout() {
  const { unreadCount, isConnected } = useAlertStore()
  const location = useLocation()
  const currentPage = pageTitle[location.pathname] || { title: 'Edge', subtitle: '' }

  return (
    <div className="min-h-screen bg-background">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-50 w-72 bg-card/50 backdrop-blur-xl border-r border-border/50">
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-5 border-b border-border/50">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-blue-600 shadow-lg shadow-emerald-500/25">
            <Zap className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="font-semibold text-lg tracking-tight">Edge</h1>
            <p className="text-xs text-muted-foreground">Sports Intelligence</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-1">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href
            return (
              <NavLink
                key={item.name}
                to={item.href}
                className={cn(
                  'group flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
                )}
              >
                <div className={cn(
                  'flex items-center justify-center w-9 h-9 rounded-lg transition-colors',
                  isActive
                    ? 'bg-primary/15'
                    : 'bg-muted/50 group-hover:bg-muted'
                )}>
                  <item.icon className={cn(
                    'h-[18px] w-[18px]',
                    isActive ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground'
                  )} />
                </div>
                <div className="flex-1 min-w-0">
                  <span className="block truncate">{item.name}</span>
                  <span className={cn(
                    'block text-xs truncate transition-colors',
                    isActive ? 'text-primary/70' : 'text-muted-foreground/70'
                  )}>
                    {item.description}
                  </span>
                </div>
                {isActive && (
                  <ChevronRight className="h-4 w-4 text-primary/50" />
                )}
              </NavLink>
            )
          })}
        </nav>

        {/* Settings link */}
        <div className="absolute bottom-20 left-4 right-4">
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
              )
            }
          >
            <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-muted/50">
              <Settings className="h-[18px] w-[18px]" />
            </div>
            <span>Settings</span>
          </NavLink>
        </div>

        {/* Connection status */}
        <div className="absolute bottom-4 left-4 right-4">
          <div className={cn(
            'flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all',
            isConnected
              ? 'bg-emerald-500/10 border border-emerald-500/20'
              : 'bg-red-500/10 border border-red-500/20'
          )}>
            <div className="relative">
              <Radio className={cn(
                'h-4 w-4',
                isConnected ? 'text-emerald-400' : 'text-red-400'
              )} />
              {isConnected && (
                <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              )}
            </div>
            <div className="flex-1">
              <span className={cn(
                'font-medium',
                isConnected ? 'text-emerald-400' : 'text-red-400'
              )}>
                {isConnected ? 'Connected' : 'Offline'}
              </span>
              <span className="block text-xs text-muted-foreground">
                {isConnected ? 'Receiving live data' : 'Reconnecting...'}
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="pl-72">
        {/* Header */}
        <header className="sticky top-0 z-40 flex items-center justify-between px-8 py-4 bg-background/80 backdrop-blur-xl border-b border-border/50">
          <div>
            <h2 className="text-xl font-semibold tracking-tight">{currentPage.title}</h2>
            <p className="text-sm text-muted-foreground">{currentPage.subtitle}</p>
          </div>

          <div className="flex items-center gap-3">
            {/* Alerts button */}
            <button className={cn(
              'relative flex items-center gap-2 px-4 py-2 rounded-xl transition-all duration-200',
              unreadCount > 0
                ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/15'
                : 'bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground'
            )}>
              <Bell className="h-4 w-4" />
              <span className="text-sm font-medium">Alerts</span>
              {unreadCount > 0 && (
                <span className="flex items-center justify-center min-w-[20px] h-5 px-1.5 text-xs font-bold text-amber-900 bg-amber-400 rounded-full">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="p-8">
          <div className="animate-fade-in">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}