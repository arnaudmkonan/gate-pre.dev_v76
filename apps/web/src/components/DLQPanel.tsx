import { useState, useEffect } from 'react'
import { Card } from './Card'
import { Button } from './Button'
import { AlertCircle, Trash2, RotateCcw, ChevronDown, ChevronUp } from 'lucide-react'

interface DLQItem {
  id: string
  job_id: string
  original_filename?: string
  error_message: string
  retry_history?: any[]
  failure_count: number
  manual_notes?: string
  status: 'pending_review' | 'archived'
  created_at: string
}

export const DLQPanel: React.FC = () => {
  const [items, setItems] = useState<DLQItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<'pending_review' | 'archived' | null>('pending_review')

  const loadDLQ = async () => {
    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams({
        limit: '50',
      })

      if (statusFilter) {
        params.append('status', statusFilter)
      }

      const response = await fetch(`/api/ingest/dlq?${params}`)

      if (!response.ok) {
        throw new Error('Failed to load DLQ items')
      }

      const data = await response.json()
      setItems(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load DLQ')
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDLQ()
  }, [statusFilter])

  const handleReprocess = async (dlqId: string) => {
    try {
      const response = await fetch(`/api/ingest/dlq/${dlqId}/reprocess`, {
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error('Failed to reprocess item')
      }

      setItems(items.filter((item) => item.id !== dlqId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reprocess')
    }
  }

  const handleDelete = async (dlqId: string) => {
    if (!window.confirm('Are you sure you want to delete this DLQ item?')) return

    try {
      const response = await fetch(`/api/ingest/dlq/${dlqId}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error('Failed to delete item')
      }

      setItems(items.filter((item) => item.id !== dlqId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete')
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  return (
    <Card>
      <div className="p-6 space-y-4">
        <h2 className="text-lg font-semibold">Dead Letter Queue</h2>

        {/* Status Tabs */}
        <div className="flex gap-2">
          <button
            onClick={() => setStatusFilter(null)}
            className={`px-3 py-1 rounded-full text-sm ${
              statusFilter === null ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'
            }`}
          >
            All ({items.length})
          </button>
          <button
            onClick={() => setStatusFilter('pending_review')}
            className={`px-3 py-1 rounded-full text-sm ${
              statusFilter === 'pending_review' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'
            }`}
          >
            Pending Review
          </button>
          <button
            onClick={() => setStatusFilter('archived')}
            className={`px-3 py-1 rounded-full text-sm ${
              statusFilter === 'archived' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'
            }`}
          >
            Archived
          </button>
        </div>

        {error && (
          <div className="flex gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {loading ? (
          <p className="text-center py-4 text-gray-500">Loading...</p>
        ) : items.length === 0 ? (
          <p className="text-center py-4 text-gray-500">No DLQ items</p>
        ) : (
          <div className="space-y-2">
            {items.map((item) => (
              <div key={item.id} className="border border-red-200 rounded-lg overflow-hidden">
                <div
                  className="p-4 bg-red-50 cursor-pointer hover:bg-red-100 flex items-center justify-between"
                  onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-sm">{item.original_filename || 'Unknown file'}</p>
                      <p className="text-xs text-red-700 truncate">{item.error_message}</p>
                    </div>
                  </div>
                  {expandedId === item.id ? (
                    <ChevronUp className="w-5 h-5 text-gray-400" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-gray-400" />
                  )}
                </div>

                {expandedId === item.id && (
                  <div className="p-4 bg-white border-t border-red-200 space-y-3">
                    <div>
                      <p className="text-xs font-semibold text-gray-600">Error Details</p>
                      <p className="text-sm text-gray-700 mt-1">{item.error_message}</p>
                    </div>

                    <div>
                      <p className="text-xs font-semibold text-gray-600">Failure Count</p>
                      <p className="text-sm text-gray-700 mt-1">{item.failure_count} attempt(s)</p>
                    </div>

                    <div>
                      <p className="text-xs font-semibold text-gray-600">Created At</p>
                      <p className="text-sm text-gray-700 mt-1">{formatDate(item.created_at)}</p>
                    </div>

                    {item.manual_notes && (
                      <div>
                        <p className="text-xs font-semibold text-gray-600">Notes</p>
                        <p className="text-sm text-gray-700 mt-1">{item.manual_notes}</p>
                      </div>
                    )}

                    <div className="flex gap-2 pt-2">
                      {item.status === 'pending_review' && (
                        <>
                          <Button
                            onClick={() => handleReprocess(item.id)}
                            variant="secondary"
                            size="sm"
                            className="flex items-center gap-2"
                          >
                            <RotateCcw className="w-4 h-4" />
                            Reprocess
                          </Button>
                          <Button
                            onClick={() => handleDelete(item.id)}
                            variant="secondary"
                            size="sm"
                            className="flex items-center gap-2 text-red-600"
                          >
                            <Trash2 className="w-4 h-4" />
                            Delete
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}
