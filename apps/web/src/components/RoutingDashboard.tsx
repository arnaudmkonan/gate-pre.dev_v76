import { useState, useEffect } from 'react'
import { RefreshCw, AlertCircle, CheckCircle, Clock, Loader } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from './Card'
import { Button } from './Button'
import { API_URL } from '../config/api'

interface RoutingStats {
  total_files: number
  pending: number
  completed: number
  failed: number
  average_processing_time: number
}

interface AdminAction {
  action: string
  status: 'idle' | 'loading' | 'success' | 'error'
  message?: string
  timestamp?: string
}

const STATUS_ICONS = {
  pending: Clock,
  completed: CheckCircle,
  failed: AlertCircle,
}

export const RoutingDashboard = () => {
  const [stats, setStats] = useState<RoutingStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [adminActions, setAdminActions] = useState<Record<string, AdminAction>>({
    refresh_routing: { action: 'refresh_routing', status: 'idle' },
    retry_extraction: { action: 'retry_extraction', status: 'idle' },
    trigger_normalization: { action: 'trigger_normalization', status: 'idle' },
  })

  const fetchStats = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_URL}/api/routing/stats`)
      if (!response.ok) {
        throw new Error('Failed to fetch routing stats')
      }
      const data = await response.json()
      setStats(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch stats')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
    const interval = setInterval(fetchStats, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [])

  const handleAdminAction = async (actionName: string, endpoint: string) => {
    const action = adminActions[actionName]
    if (!action) return

    setAdminActions((prev) => ({
      ...prev,
      [actionName]: { ...action, status: 'loading', message: undefined },
    }))

    try {
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        throw new Error(`API Error: ${response.statusText}`)
      }

      const result = await response.json()

      setAdminActions((prev) => ({
        ...prev,
        [actionName]: {
          ...action,
          status: 'success',
          message: result.message || 'Action completed successfully',
          timestamp: new Date().toLocaleTimeString(),
        },
      }))

      // Refresh stats after action
      setTimeout(fetchStats, 1000)

      // Clear success message after 5 seconds
      setTimeout(() => {
        setAdminActions((prev) => ({
          ...prev,
          [actionName]: { ...action, status: 'idle', message: undefined },
        }))
      }, 5000)
    } catch (err) {
      setAdminActions((prev) => ({
        ...prev,
        [actionName]: {
          ...action,
          status: 'error',
          message: err instanceof Error ? err.message : 'Action failed',
          timestamp: new Date().toLocaleTimeString(),
        },
      }))
    }
  }

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader className="w-8 h-8 animate-spin text-gray-400" />
        <span className="ml-2 text-gray-600">Loading routing dashboard...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Routing Dashboard</h1>
        <Button
          onClick={fetchStats}
          variant="secondary"
          size="sm"
          disabled={loading}
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {error && (
        <div className="flex gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-6">
              <p className="text-sm text-gray-600">Total Files</p>
              <p className="text-3xl font-bold mt-2">{stats.total_files}</p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <p className="text-sm text-gray-600">Pending</p>
              <p className="text-3xl font-bold text-yellow-600 mt-2">
                {stats.pending}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <p className="text-sm text-gray-600">Completed</p>
              <p className="text-3xl font-bold text-green-600 mt-2">
                {stats.completed}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <p className="text-sm text-gray-600">Failed</p>
              <p className="text-3xl font-bold text-red-600 mt-2">
                {stats.failed}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Processing Time */}
      {stats && (
        <Card>
          <CardHeader>
            <CardTitle>Processing Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <p className="text-sm text-gray-600">Average Processing Time</p>
                <p className="text-2xl font-bold mt-2">
                  {stats.average_processing_time.toFixed(2)}s
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Success Rate</p>
                <p className="text-2xl font-bold text-green-600 mt-2">
                  {stats.total_files > 0
                    ? ((stats.completed / stats.total_files) * 100).toFixed(1)
                    : 0}
                  %
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Admin Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Admin Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Refresh Routing */}
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <h3 className="font-medium">Refresh Routing</h3>
                <p className="text-sm text-gray-600">
                  Re-process routing decisions for all pending files
                </p>
                {adminActions.refresh_routing.status === 'success' && (
                  <p className="text-xs text-green-600 mt-1">
                    ✓ {adminActions.refresh_routing.message}
                  </p>
                )}
                {adminActions.refresh_routing.status === 'error' && (
                  <p className="text-xs text-red-600 mt-1">
                    ✗ {adminActions.refresh_routing.message}
                  </p>
                )}
              </div>
              <Button
                onClick={() =>
                  handleAdminAction('refresh_routing', '/api/routing/refresh')
                }
                isLoading={adminActions.refresh_routing.status === 'loading'}
                disabled={adminActions.refresh_routing.status === 'loading'}
              >
                Refresh Routing
              </Button>
            </div>

            {/* Retry Extraction */}
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <h3 className="font-medium">Retry Extraction</h3>
                <p className="text-sm text-gray-600">
                  Re-attempt extraction for failed items
                </p>
                {adminActions.retry_extraction.status === 'success' && (
                  <p className="text-xs text-green-600 mt-1">
                    ✓ {adminActions.retry_extraction.message}
                  </p>
                )}
                {adminActions.retry_extraction.status === 'error' && (
                  <p className="text-xs text-red-600 mt-1">
                    ✗ {adminActions.retry_extraction.message}
                  </p>
                )}
              </div>
              <Button
                onClick={() =>
                  handleAdminAction(
                    'retry_extraction',
                    '/api/extraction/retry'
                  )
                }
                isLoading={adminActions.retry_extraction.status === 'loading'}
                disabled={adminActions.retry_extraction.status === 'loading'}
              >
                Retry Extraction
              </Button>
            </div>

            {/* Trigger Normalization */}
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <h3 className="font-medium">Trigger Normalization</h3>
                <p className="text-sm text-gray-600">
                  Start normalization for completed extractions
                </p>
                {adminActions.trigger_normalization.status === 'success' && (
                  <p className="text-xs text-green-600 mt-1">
                    ✓ {adminActions.trigger_normalization.message}
                  </p>
                )}
                {adminActions.trigger_normalization.status === 'error' && (
                  <p className="text-xs text-red-600 mt-1">
                    ✗ {adminActions.trigger_normalization.message}
                  </p>
                )}
              </div>
              <Button
                onClick={() =>
                  handleAdminAction(
                    'trigger_normalization',
                    '/api/normalization/trigger'
                  )
                }
                isLoading={adminActions.trigger_normalization.status === 'loading'}
                disabled={adminActions.trigger_normalization.status === 'loading'}
              >
                Trigger Normalization
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Routing Status Distribution */}
      {stats && (
        <Card>
          <CardHeader>
            <CardTitle>Status Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {[
                { key: 'pending', label: 'Pending', value: stats.pending },
                { key: 'completed', label: 'Completed', value: stats.completed },
                { key: 'failed', label: 'Failed', value: stats.failed },
              ].map(({ key, label, value }) => {
                const percentage =
                  stats.total_files > 0
                    ? ((value / stats.total_files) * 100).toFixed(1)
                    : 0
                const Icon = STATUS_ICONS[key as keyof typeof STATUS_ICONS]

                return (
                  <div key={key}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <Icon className="w-4 h-4" />
                        <span className="text-sm font-medium">{label}</span>
                      </div>
                      <span className="text-sm text-gray-600">
                        {value} ({percentage}%)
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all ${key === 'pending'
                            ? 'bg-yellow-500'
                            : key === 'completed'
                              ? 'bg-green-500'
                              : 'bg-red-500'
                          }`}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
