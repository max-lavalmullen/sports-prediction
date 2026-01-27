import { useEffect } from 'react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useAlertStore } from '@/stores/alertStore'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const { setConnected, addAlert } = useAlertStore()

  const { isConnected } = useWebSocket({
    url: `${WS_URL}/ws/alerts`,
    onOpen: () => {
      setConnected(true)
    },
    onClose: () => {
      setConnected(false)
    },
    onMessage: (data) => {
      if (data && typeof data === 'object' && 'type' in data) {
        const message = data as { type: string; [key: string]: unknown }
        if (message.type === 'value_alert') {
          addAlert(message as never)
        }
      }
    },
    reconnectAttempts: 10,
    reconnectInterval: 5000,
  })

  useEffect(() => {
    setConnected(isConnected)
  }, [isConnected, setConnected])

  return <>{children}</>
}