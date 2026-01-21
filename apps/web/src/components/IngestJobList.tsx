import { useState, useEffect } from 'react'
import { Card } from './Card'
import { Button } from './Button'
import { RefreshCw, AlertCircle, CheckCircle, Clock, Loader } from 'lucide-react'

interface IngestJob {
  id: string
  filename: string
  file_type: string
  size: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  created_at: string
  error_message?: string
}

interface IngestJobListProps {
  onJobSelect?: (job: IngestJob) => void
  autoRefresh?: boolean
  refreshInterval?: number
}

export const IngestJobList: React.FC<IngestJobListProps> = ({
  onJobSelect,
  autoRefresh = true,
  refreshInterval = 5000,
}) => {
  const [jobs, setJobs] = useState<IngestJob[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState<string | null>(null)

  const loadJobs = async () => {
    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
      })

      if (statusFilter) {
        params.append('status', statusFilter)
      }

      const response = await fetch(`/api/ingest/jobs?${params}`)

      if (!response.ok) {
        throw new Error('Failed to load jobs')
      }

      const data = await response.json()
      setJobs(data.items || [])
      setTotal(data.total || 0)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs')
      setJobs([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadJobs()
  }, [page, statusFilter])

  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(() => {
      loadJobs()
    }, refreshInterval)

    return () => clearInterval(interval)
  }, [autoRefresh, refreshInterval])

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-4 h-4 text-yellow-500" />
      case 'processing':
        return <Loader className="w-4 h-4 text-blue-500 animate-spin" />
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" />
      default:
        return null
    }
  }

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  return (
    <Card>
      <div className="p-6 space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Ingest Jobs</h2>
          <Button onClick={loadJobs} disabled={loading} variant="secondary" size="sm">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => {
              setStatusFilter(null)
              setPage(1)
            }}
            className={`px-3 py-1 rounded-full text-sm ${
              statusFilter === null ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'
            }`}
          >
            All
          </button>
          {['pending', 'processing', 'completed', 'failed'].map((status) => (
            <button
              key={status}
              onClick={() => {
                setStatusFilter(status)
                setPage(1)
              }}
              className={`px-3 py-1 rounded-full text-sm capitalize ${
                statusFilter === status ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'
              }`}
            >
              {status}
            </button>
          ))}
        </div>

        {error && (
          <div className="flex gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {loading && jobs.length === 0 ? (
          <div className="text-center py-8">
            <Loader className="w-6 h-6 animate-spin mx-auto text-gray-400 mb-2" />
            <p className="text-gray-500">Loading jobs...</p>
          </div>
        ) : (
          <div className="space-y-2">
            {jobs.length === 0 ? (
              <p className="text-center py-8 text-gray-500">No jobs found</p>
            ) : (
              jobs.map((job) => (
                <div
                  key={job.id}
                  className="p-3 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer"
                  onClick={() => onJobSelect?.(job)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      {getStatusIcon(job.status)}
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-sm truncate">{job.filename}</p>
                        <p className="text-xs text-gray-500">
                          {job.file_type} • {formatBytes(job.size)} • {formatDate(job.created_at)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-2 py-1 bg-gray-100 rounded capitalize">
                        {job.status}
                      </span>
                    </div>
                  </div>
                  {job.error_message && (
                    <p className="text-xs text-red-600 mt-1">{job.error_message}</p>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {total > pageSize && (
          <div className="flex justify-between items-center pt-4 border-t">
            <p className="text-sm text-gray-600">
              Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, total)} of {total}
            </p>
            <div className="flex gap-2">
              <Button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                variant="secondary"
                size="sm"
              >
                Previous
              </Button>
              <Button
                onClick={() => setPage(page + 1)}
                disabled={page * pageSize >= total}
                variant="secondary"
                size="sm"
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}
