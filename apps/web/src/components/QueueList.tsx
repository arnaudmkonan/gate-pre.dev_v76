import { useState, useEffect } from 'react'
import { RotateCw, AlertCircle, Loader } from 'lucide-react'
import { Card } from './Card'

interface QueueJob {
  job_id: string
  file_id: string
  status: string
  priority: string
  attempts: number
  max_attempts: number
  last_error: string | null
  last_attempted_at: string | null
  created_at: string
}

interface QueueListProps {
  autoRefresh?: boolean
  refreshInterval?: number
}

export const QueueList: React.FC<QueueListProps> = ({
  autoRefresh = true,
  refreshInterval = 2000,
}) => {
  const [jobs, setJobs] = useState<QueueJob[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState({ queued: 0, processing: 0, completed: 0, failed: 0 })
  const [selectedStatus, setSelectedStatus] = useState<string | null>(null)

  const fetchJobs = async (status?: string | null) => {
    setLoading(true)
    setError(null)

    try {
      const url = new URL('/api/queue', window.location.origin)
      if (status) {
        url.searchParams.append('status', status)
      }

      const response = await fetch(url.toString())

      if (!response.ok) {
        throw new Error('Failed to fetch queue jobs')
      }

      const data = await response.json()
      setJobs(data.jobs || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load queue')
    } finally {
      setLoading(false)
    }
  }

  const fetchStats = async () => {
    try {
      const response = await fetch('/api/queue/stats/overview')
      if (response.ok) {
        const data = await response.json()
        setStats(data)
      }
    } catch (err) {
      console.error('Failed to fetch stats:', err)
    }
  }

  const handleRetry = async (jobId: string) => {
    try {
      const response = await fetch(`/api/queue/${jobId}/retry`, {
        method: 'POST',
      })

      if (response.ok) {
        await fetchJobs(selectedStatus)
        await fetchStats()
      } else {
        alert('Failed to retry job')
      }
    } catch (err) {
      console.error('Retry error:', err)
    }
  }

  useEffect(() => {
    fetchJobs(selectedStatus)
    fetchStats()

    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchJobs(selectedStatus)
        fetchStats()
      }, refreshInterval)

      return () => clearInterval(interval)
    }
  }, [selectedStatus, autoRefresh, refreshInterval])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'queued':
        return 'bg-yellow-100 text-yellow-800'
      case 'processing':
        return 'bg-blue-100 text-blue-800'
      case 'completed':
        return 'bg-green-100 text-green-800'
      case 'failed':
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high':
        return 'bg-red-100 text-red-800'
      case 'normal':
        return 'bg-gray-100 text-gray-800'
      case 'low':
        return 'bg-blue-100 text-blue-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="space-y-4">
      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <div className="p-4 text-center">
            <div className="text-2xl font-bold text-yellow-600">{stats.queued}</div>
            <div className="text-xs text-gray-600 mt-1">Queued</div>
          </div>
        </Card>
        <Card>
          <div className="p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">{stats.processing}</div>
            <div className="text-xs text-gray-600 mt-1">Processing</div>
          </div>
        </Card>
        <Card>
          <div className="p-4 text-center">
            <div className="text-2xl font-bold text-green-600">{stats.completed}</div>
            <div className="text-xs text-gray-600 mt-1">Completed</div>
          </div>
        </Card>
        <Card>
          <div className="p-4 text-center">
            <div className="text-2xl font-bold text-red-600">{stats.failed}</div>
            <div className="text-xs text-gray-600 mt-1">Failed</div>
          </div>
        </Card>
      </div>

      {/* Jobs */}
      <Card>
        <div className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Queue Jobs</h2>
            <select
              value={selectedStatus || ''}
              onChange={(e) => setSelectedStatus(e.target.value || null)}
              className="px-3 py-1 text-sm border rounded"
            >
              <option value="">All Statuses</option>
              <option value="queued">Queued</option>
              <option value="processing">Processing</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          {loading && (
            <div className="flex items-center justify-center gap-2 py-4">
              <Loader className="w-5 h-5 animate-spin" />
              <span>Loading jobs...</span>
            </div>
          )}

          {error && (
            <div className="flex items-start gap-3 p-3 bg-red-50 border border-red-200 rounded">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          {!loading && !error && jobs.length === 0 && (
            <p className="text-center text-gray-500 py-4">No jobs found</p>
          )}

          {!loading && !error && jobs.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-3 px-4 font-semibold">File ID</th>
                    <th className="text-left py-3 px-4 font-semibold">Status</th>
                    <th className="text-left py-3 px-4 font-semibold">Priority</th>
                    <th className="text-left py-3 px-4 font-semibold">Attempts</th>
                    <th className="text-left py-3 px-4 font-semibold">Last Error</th>
                    <th className="text-left py-3 px-4 font-semibold">Created</th>
                    <th className="text-left py-3 px-4 font-semibold">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr key={job.job_id} className="border-b hover:bg-gray-50">
                      <td className="py-3 px-4">
                        <code className="text-xs bg-gray-100 px-2 py-1 rounded">
                          {job.file_id.substring(0, 8)}...
                        </code>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`text-xs px-2 py-1 rounded ${getStatusColor(job.status)}`}>
                          {job.status}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`text-xs px-2 py-1 rounded ${getPriorityColor(job.priority)}`}>
                          {job.priority}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        {job.attempts}/{job.max_attempts}
                      </td>
                      <td className="py-3 px-4">
                        {job.last_error ? (
                          <div className="text-xs text-red-600 max-w-xs truncate" title={job.last_error}>
                            {job.last_error}
                          </div>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-xs">
                        {new Date(job.created_at).toLocaleString()}
                      </td>
                      <td className="py-3 px-4">
                        {job.status === 'failed' && job.attempts < job.max_attempts && (
                          <button
                            onClick={() => handleRetry(job.job_id)}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded hover:bg-blue-100 transition text-sm text-blue-600"
                          >
                            <RotateCw className="w-4 h-4" />
                            Retry
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
