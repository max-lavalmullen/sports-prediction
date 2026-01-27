import { useEffect, useRef, useState, useCallback } from 'react'

interface UseWebSocketOptions {
  url: string
  onMessage?: (data: unknown) => void
  onOpen?: () => void
  onClose?: () => void
  onError?: (error: Event) => void
  reconnectAttempts?: number
  reconnectInterval?: number
}

interface WebSocketState {
  isConnected: boolean
  lastMessage: unknown | null
  error: Event | null
}

export function useWebSocket({
  url,
  onMessage,
  onOpen,
  onClose,
  onError,
  reconnectAttempts = 5,
  reconnectInterval = 3000,
}: UseWebSocketOptions) {
  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    lastMessage: null,
    error: null,
  })

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectCountRef = useRef(0)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>()
  const mountedRef = useRef(true)

  // Use refs for callbacks to avoid dependency issues
  const onMessageRef = useRef(onMessage)
  const onOpenRef = useRef(onOpen)
  const onCloseRef = useRef(onClose)
  const onErrorRef = useRef(onError)

  // Update refs when callbacks change
  useEffect(() => {
    onMessageRef.current = onMessage
    onOpenRef.current = onOpen
    onCloseRef.current = onClose
    onErrorRef.current = onError
  }, [onMessage, onOpen, onClose, onError])

  const connect = useCallback(() => {
    if (!mountedRef.current) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return

    try {
      const ws = new WebSocket(url)

      ws.onopen = () => {
        if (!mountedRef.current) {
          ws.close()
          return
        }
        setState((prev) => ({ ...prev, isConnected: true, error: null }))
        reconnectCountRef.current = 0
        onOpenRef.current?.()
      }

      ws.onmessage = (event) => {
        if (!mountedRef.current) return
        try {
          const data = JSON.parse(event.data)
          setState((prev) => ({ ...prev, lastMessage: data }))
          onMessageRef.current?.(data)
        } catch {
          setState((prev) => ({ ...prev, lastMessage: event.data }))
          onMessageRef.current?.(event.data)
        }
      }

      ws.onclose = () => {
        if (!mountedRef.current) return
        setState((prev) => ({ ...prev, isConnected: false }))
        onCloseRef.current?.()

        // Attempt reconnection
        if (mountedRef.current && reconnectCountRef.current < reconnectAttempts) {
          reconnectCountRef.current++
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, reconnectInterval)
        }
      }

      ws.onerror = (error) => {
        if (!mountedRef.current) return
        setState((prev) => ({ ...prev, error }))
        onErrorRef.current?.(error)
      }

      wsRef.current = ws
    } catch (err) {
      console.error('WebSocket connection error:', err)
    }
  }, [url, reconnectAttempts, reconnectInterval])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    reconnectCountRef.current = reconnectAttempts
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [reconnectAttempts])

  const sendMessage = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    connect()

    return () => {
      mountedRef.current = false
      disconnect()
    }
  }, []) // Empty deps - only run on mount/unmount

  return {
    ...state,
    sendMessage,
    connect,
    disconnect,
  }
}
