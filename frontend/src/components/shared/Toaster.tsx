import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import { X } from 'lucide-react'

interface Toast {
  id: string
  title: string
  description?: string
  type: 'success' | 'error' | 'info' | 'warning'
}

// Simple toast state management
const toastListeners: Set<(toasts: Toast[]) => void> = new Set()
let toasts: Toast[] = []

export function toast(toast: Omit<Toast, 'id'>) {
  const id = Math.random().toString(36).slice(2)
  const newToast = { ...toast, id }
  toasts = [...toasts, newToast]
  toastListeners.forEach((listener) => listener(toasts))

  // Auto dismiss after 5 seconds
  setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id)
    toastListeners.forEach((listener) => listener(toasts))
  }, 5000)
}

export function Toaster() {
  const [localToasts, setLocalToasts] = useState<Toast[]>([])

  useEffect(() => {
    toastListeners.add(setLocalToasts)
    return () => {
      toastListeners.delete(setLocalToasts)
    }
  }, [])

  const dismiss = (id: string) => {
    toasts = toasts.filter((t) => t.id !== id)
    toastListeners.forEach((listener) => listener(toasts))
  }

  if (localToasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80">
      {localToasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            'flex items-start gap-3 p-4 rounded-lg shadow-lg border',
            t.type === 'success' && 'bg-green-500/10 border-green-500/20 text-green-500',
            t.type === 'error' && 'bg-red-500/10 border-red-500/20 text-red-500',
            t.type === 'warning' && 'bg-yellow-500/10 border-yellow-500/20 text-yellow-500',
            t.type === 'info' && 'bg-blue-500/10 border-blue-500/20 text-blue-500'
          )}
        >
          <div className="flex-1">
            <p className="font-medium">{t.title}</p>
            {t.description && (
              <p className="text-sm opacity-80 mt-1">{t.description}</p>
            )}
          </div>
          <button
            onClick={() => dismiss(t.id)}
            className="p-1 hover:bg-white/10 rounded"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  )
}
