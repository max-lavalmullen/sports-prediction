import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Sport, BetType } from '@/types'

interface SettingsState {
  // Display preferences
  oddsFormat: 'american' | 'decimal'
  theme: 'light' | 'dark' | 'system'
  defaultSport: Sport | 'all'

  // Alert preferences
  alertsEnabled: boolean
  alertMinEdge: number
  alertSports: Sport[]
  alertBetTypes: BetType[]

  // Bankroll settings
  bankroll: number
  defaultKellyFraction: number
  maxStakePercent: number

  // API keys (stored locally)
  oddsApiKey: string

  // Actions
  setOddsFormat: (format: 'american' | 'decimal') => void
  setTheme: (theme: 'light' | 'dark' | 'system') => void
  setDefaultSport: (sport: Sport | 'all') => void
  setAlertsEnabled: (enabled: boolean) => void
  setAlertMinEdge: (edge: number) => void
  setAlertSports: (sports: Sport[]) => void
  setAlertBetTypes: (types: BetType[]) => void
  setBankroll: (amount: number) => void
  setDefaultKellyFraction: (fraction: number) => void
  setMaxStakePercent: (percent: number) => void
  setOddsApiKey: (key: string) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      // Default values
      oddsFormat: 'american',
      theme: 'dark',
      defaultSport: 'all',

      alertsEnabled: true,
      alertMinEdge: 0.03,
      alertSports: [],
      alertBetTypes: [],

      bankroll: 10000,
      defaultKellyFraction: 0.25,
      maxStakePercent: 0.05,

      oddsApiKey: '',

      // Actions
      setOddsFormat: (format) => set({ oddsFormat: format }),
      setTheme: (theme) => set({ theme }),
      setDefaultSport: (sport) => set({ defaultSport: sport }),
      setAlertsEnabled: (enabled) => set({ alertsEnabled: enabled }),
      setAlertMinEdge: (edge) => set({ alertMinEdge: edge }),
      setAlertSports: (sports) => set({ alertSports: sports }),
      setAlertBetTypes: (types) => set({ alertBetTypes: types }),
      setBankroll: (amount) => set({ bankroll: amount }),
      setDefaultKellyFraction: (fraction) => set({ defaultKellyFraction: fraction }),
      setMaxStakePercent: (percent) => set({ maxStakePercent: percent }),
      setOddsApiKey: (key) => set({ oddsApiKey: key }),
    }),
    {
      name: 'sports-prediction-settings',
    }
  )
)
