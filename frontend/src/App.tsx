import { Routes, Route } from 'react-router-dom'
import { Toaster } from '@/components/shared/Toaster'
import Layout from '@/components/shared/Layout'
import Dashboard from '@/pages/Dashboard'
import Backtesting from '@/pages/Backtesting'
import Analytics from '@/pages/Analytics'
import BetTracker from '@/pages/BetTracker'
import Simulation from '@/pages/Simulation'
import Settings from '@/pages/Settings'
import Arbitrage from '@/pages/Arbitrage'
import SGPBuilder from '@/pages/SGPBuilder'
import BotDashboard from '@/pages/BotDashboard'

function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="arbitrage" element={<Arbitrage />} />
          <Route path="sgp" element={<SGPBuilder />} />
          <Route path="backtesting" element={<Backtesting />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="analytics/team/:teamId" element={<Analytics />} />
          <Route path="analytics/player/:playerId" element={<Analytics />} />
          <Route path="bets" element={<BetTracker />} />
          <Route path="simulation" element={<Simulation />} />
          <Route path="bot" element={<BotDashboard />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
      <Toaster />
    </>
  )
}

export default App
