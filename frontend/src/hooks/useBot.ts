import { useQuery } from '@tanstack/react-query'
import type { BotStatus } from '@/types'

const API_URL = import.meta.env.VITE_API_URL || ''

async function fetchBotStatus(botId: string = 'paper_default'): Promise<BotStatus> {
  const response = await fetch(`${API_URL}/api/v1/bot/status?bot_id=${botId}`)
  
  if (!response.ok) {
    throw new Error('Failed to fetch bot status')
  }

  const data = await response.json()
  
  // Map snake_case to camelCase
  return {
    botId: data.bot_id,
    botType: data.bot_type,
    isActive: data.is_active,
    balance: data.balance,
    activeBetsCount: data.active_bets_count
  }
}

async function fetchBotLogs(botId: string = 'paper_default', limit: number = 50) {
    // Placeholder - matches API response structure which is currently empty list
    const response = await fetch(`${API_URL}/api/v1/bot/logs?bot_id=${botId}&limit=${limit}`)
    if (!response.ok) throw new Error('Failed to fetch logs')
    return await response.json()
}

export function useBotStatus(botId?: string) {
  return useQuery({
    queryKey: ['botStatus', botId],
    queryFn: () => fetchBotStatus(botId),
    refetchInterval: 5000,
  })
}

export function useBotLogs(botId?: string) {
    return useQuery({
        queryKey: ['botLogs', botId],
        queryFn: () => fetchBotLogs(botId),
        refetchInterval: 10000,
    })
}
