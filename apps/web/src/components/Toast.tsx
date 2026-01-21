import React, { useEffect } from 'react'
import { CheckCircle, AlertCircle, X } from 'lucide-react'

interface ToastProps {
  id: string
  message: string
  type: 'success' | 'error'
  onClose: (id: string) => void
}

export const Toast = ({ id, message, type, onClose }: ToastProps) => {
  useEffect(() => {
    const timer = setTimeout(() => onClose(id), 5000)
    return () => clearTimeout(timer)
  }, [id, onClose])

  const bgColor = type === 'success' ? 'bg-green-50' : 'bg-red-50'
  const borderColor = type === 'success' ? 'border-green-200' : 'border-red-200'
  const textColor = type === 'success' ? 'text-green-800' : 'text-red-800'
  const Icon = type === 'success' ? CheckCircle : AlertCircle

  return (
    <div className={`${bgColor} border ${borderColor} rounded-lg p-4 flex items-start gap-3`}>
      <Icon className={`w-5 h-5 flex-shrink-0 ${textColor}`} />
      <p className={`text-sm font-medium ${textColor}`}>{message}</p>
      <button
        onClick={() => onClose(id)}
        className={`ml-auto flex-shrink-0 ${textColor} hover:opacity-75`}
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}

export const ToastContainer = ({
  toasts,
  onClose,
}: {
  toasts: ToastProps[]
  onClose: (id: string) => void
}) => {
  return (
    <div className="fixed bottom-4 right-4 space-y-2 z-50">
      {toasts.map((toast) => (
        <Toast key={toast.id} {...toast} onClose={onClose} />
      ))}
    </div>
  )
}

export const useToast = () => {
  const [toasts, setToasts] = React.useState<ToastProps[]>([])

  const addToast = (message: string, type: 'success' | 'error' = 'success') => {
    const id = Date.now().toString()
    setToasts((prev) => [...prev, { id, message, type, onClose: () => {} }])
  }

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  return {
    toasts: toasts.map((t) => ({ ...t, onClose: removeToast })),
    addToast,
    removeToast,
  }
}
