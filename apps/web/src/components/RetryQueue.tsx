import { useState, useEffect } from 'react'
import { AlertCircle, CheckCircle, RefreshCw, Edit2 } from 'lucide-react'

interface RetryQueueItem {
  id: string
  file_id: string
  error_type: string
  error_message: string
  processing_attempt: number
  last_retry_at?: string
  manual_notes?: string
  status: 'pending_review' | 'processing' | 'resolved' | 'archived'
  resolved_at?: string
  created_at: string
}

export const RetryQueue = () => {
  const [items, setItems] = useState<RetryQueueItem[]>([])
  const [selectedStatus, setSelectedStatus] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editNotes, setEditNotes] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchRetryQueue()
    const interval = setInterval(fetchRetryQueue, 10000)
    return () => clearInterval(interval)
  }, [selectedStatus])

  const fetchRetryQueue = async () => {
    try {
      const url = new URL('/api/metadata/retry-queue', window.location.origin)
      if (selectedStatus) {
        url.searchParams.append('status_filter', selectedStatus)
      }
      const response = await fetch(url.toString())
      if (!response.ok) throw new Error('Failed to fetch retry queue')
      const data = await response.json()
      setItems(data.items)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const handleRetry = async (itemId: string) => {
    try {
      const response = await fetch(`/api/metadata/retry-queue/${itemId}/retry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: editNotes })
      })
      if (!response.ok) throw new Error('Failed to retry item')
      await fetchRetryQueue()
      setEditingId(null)
      setEditNotes('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    }
  }


  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending_review':
        return 'bg-yellow-50 border-yellow-200'
      case 'processing':
        return 'bg-blue-50 border-blue-200'
      case 'resolved':
        return 'bg-green-50 border-green-200'
      case 'archived':
        return 'bg-gray-50 border-gray-200'
      default:
        return 'bg-gray-50 border-gray-200'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'resolved':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'processing':
        return <RefreshCw className="w-5 h-5 text-blue-500 animate-spin" />
      case 'pending_review':
        return <AlertCircle className="w-5 h-5 text-yellow-500" />
      default:
        return <AlertCircle className="w-5 h-5 text-gray-400" />
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-gray-500">Loading retry queue...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Retry Queue</h1>
        <p className="text-gray-600 mt-2">Manage failed mappings and processing errors</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500" />
          <span className="text-red-700">{error}</span>
        </div>
      )}

      <div className="flex gap-2">
        {['pending_review', 'processing', 'resolved', 'archived'].map(status => (
          <button
            key={status}
            onClick={() => setSelectedStatus(selectedStatus === status ? null : status)}
            className={`px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
              selectedStatus === status
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {status.replace('_', ' ').charAt(0).toUpperCase() + status.slice(1).replace('_', ' ')}
          </button>
        ))}
      </div>

      <div className="space-y-4">
        {items.length === 0 ? (
          <div className="text-center py-8 text-gray-500">No items in retry queue</div>
        ) : (
          items.map(item => (
            <div
              key={item.id}
              className={`border rounded-lg p-4 ${getStatusColor(item.status)}`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1">
                  {getStatusIcon(item.status)}
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-gray-900">{item.error_type}</span>
                      <span className="text-xs px-2 py-1 bg-white/50 rounded text-gray-600">
                        Attempt {item.processing_attempt}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mb-2">{item.error_message}</p>
                    <p className="text-xs text-gray-500">
                      Created: {new Date(item.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>

                <div className="flex gap-2">
                  {item.status === 'pending_review' && (
                    <>
                      <button
                        onClick={() => {
                          setEditingId(editingId === item.id ? null : item.id)
                          setEditNotes(item.manual_notes || '')
                        }}
                        className="p-2 hover:bg-white/50 rounded transition-colors"
                        title="Edit notes"
                      >
                        <Edit2 className="w-4 h-4 text-gray-600" />
                      </button>
                      <button
                        onClick={() => handleRetry(item.id)}
                        className="p-2 hover:bg-white/50 rounded transition-colors text-blue-600"
                        title="Retry processing"
                      >
                        <RefreshCw className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </div>
              </div>

              {editingId === item.id && (
                <div className="mt-4 pt-4 border-t space-y-3">
                  <textarea
                    value={editNotes}
                    onChange={e => setEditNotes(e.target.value)}
                    placeholder="Add notes about this retry..."
                    className="w-full p-2 border border-gray-300 rounded text-sm"
                    rows={3}
                  />
                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => {
                        setEditingId(null)
                        setEditNotes('')
                      }}
                      className="px-3 py-1 text-sm bg-gray-200 text-gray-800 rounded hover:bg-gray-300 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleRetry(item.id)}
                      className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors flex items-center gap-2"
                    >
                      <RefreshCw className="w-4 h-4" />
                      Retry Now
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
