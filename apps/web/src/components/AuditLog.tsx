import { useState, useEffect } from 'react'
import { Download, AlertCircle, Loader } from 'lucide-react'
import { Card } from './Card'
import { Button } from './Button'

interface AuditEntry {
  audit_id: string
  resource_type: string
  resource_id: string
  action: string
  actor_id: string | null
  timestamp: string
  changes: Record<string, any> | null
}

interface AuditLogProps {
  resourceId?: string
  resourceType?: string
}

export const AuditLog: React.FC<AuditLogProps> = ({ resourceId, resourceType }) => {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedAction, setSelectedAction] = useState<string | null>(null)

  const fetchEntries = async (action?: string | null) => {
    setLoading(true)
    setError(null)

    try {
      const url = new URL('/api/audit', window.location.origin)
      if (resourceId) {
        url.searchParams.append('resource_id', resourceId)
      }
      if (resourceType) {
        url.searchParams.append('resource_type', resourceType)
      }
      if (action) {
        url.searchParams.append('action', action)
      }

      const response = await fetch(url.toString())

      if (!response.ok) {
        throw new Error('Failed to fetch audit logs')
      }

      const data = await response.json()
      setEntries(data.logs || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load audit logs')
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async () => {
    try {
      const response = await fetch('/api/audit/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resource_id: resourceId,
          resource_type: resourceType,
          action: selectedAction,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to export logs')
      }

      const data = await response.json()
      const dataStr = JSON.stringify(data, null, 2)
      const dataBlob = new Blob([dataStr], { type: 'application/json' })
      const url = URL.createObjectURL(dataBlob)
      const link = document.createElement('a')
      link.href = url
      link.download = `audit-export-${new Date().toISOString()}.json`
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Export failed')
    }
  }

  useEffect(() => {
    fetchEntries(selectedAction)
  }, [resourceId, resourceType, selectedAction])

  const getActionColor = (action: string) => {
    switch (action) {
      case 'create':
        return 'bg-green-100 text-green-800'
      case 'update':
        return 'bg-blue-100 text-blue-800'
      case 'delete':
        return 'bg-red-100 text-red-800'
      case 'download':
        return 'bg-purple-100 text-purple-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <Card>
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Audit Log</h2>
          <div className="flex items-center gap-2">
            <select
              value={selectedAction || ''}
              onChange={(e) => setSelectedAction(e.target.value || null)}
              className="px-3 py-1 text-sm border rounded"
            >
              <option value="">All Actions</option>
              <option value="create">Create</option>
              <option value="update">Update</option>
              <option value="delete">Delete</option>
              <option value="download">Download</option>
            </select>
            <Button onClick={handleExport} size="sm">
              <Download className="w-4 h-4" />
              Export
            </Button>
          </div>
        </div>

        {loading && (
          <div className="flex items-center justify-center gap-2 py-4">
            <Loader className="w-5 h-5 animate-spin" />
            <span>Loading audit logs...</span>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-3 p-3 bg-red-50 border border-red-200 rounded">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {!loading && !error && entries.length === 0 && (
          <p className="text-center text-gray-500 py-4">No audit entries found</p>
        )}

        {!loading && !error && entries.length > 0 && (
          <div className="space-y-3">
            {entries.map((entry) => (
              <div key={entry.audit_id} className="p-4 border rounded-lg hover:bg-gray-50 transition">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`text-xs px-2 py-1 rounded ${getActionColor(entry.action)}`}>
                        {entry.action}
                      </span>
                      <span className="text-xs text-gray-600">
                        {entry.resource_type}
                      </span>
                      <code className="text-xs bg-gray-100 px-2 py-1 rounded">
                        {entry.resource_id.substring(0, 8)}...
                      </code>
                    </div>
                    <div className="text-sm text-gray-600">
                      {entry.actor_id && <span>Actor: {entry.actor_id} • </span>}
                      <span>{new Date(entry.timestamp).toLocaleString()}</span>
                    </div>
                    {entry.changes && (
                      <details className="mt-2 text-xs">
                        <summary className="cursor-pointer text-gray-500 hover:text-gray-700">
                          Changes
                        </summary>
                        <pre className="mt-2 p-2 bg-gray-100 rounded text-xs overflow-auto max-h-40">
                          {JSON.stringify(entry.changes, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}
