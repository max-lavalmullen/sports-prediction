import { create } from 'zustand'
import type { ValueAlert } from '@/types'

interface AlertState {
  alerts: ValueAlert[]
  unreadCount: number
  isConnected: boolean

  // Actions
  addAlert: (alert: ValueAlert) => void
  removeAlert: (index: number) => void
  clearAlerts: () => void
  markAllRead: () => void
  setConnected: (connected: boolean) => void
}

export const useAlertStore = create<AlertState>((set) => ({
  alerts: [],
  unreadCount: 0,
  isConnected: false,

  addAlert: (alert) =>
    set((state) => ({
      alerts: [alert, ...state.alerts].slice(0, 50), // Keep last 50 alerts
      unreadCount: state.unreadCount + 1,
    })),

  removeAlert: (index) =>
    set((state) => ({
      alerts: state.alerts.filter((_, i) => i !== index),
    })),

  clearAlerts: () => set({ alerts: [], unreadCount: 0 }),

  markAllRead: () => set({ unreadCount: 0 }),

  setConnected: (connected) => set({ isConnected: connected }),
}))
