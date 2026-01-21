import { useState, useEffect } from 'react'
import { Card } from './Card'
import { Button } from './Button'
import { AlertCircle, CheckCircle, Clock, RefreshCw } from 'lucide-react'

interface IngestJob {
  id: string
  filename: string
  file_type: string
  size: number
  status: string
  created_at: string
  progress_percentage: number
  mode?: string
  error_message?: string
}

interface JobsDashboardProps {
  onJobSelect?: (job: IngestJob) => void
  onRetryClick?: (jobId: string) => void
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-800',
  queued: 'bg-blue-100 text-blue-800',
  processing: 'bg-yellow-100 text-yellow-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
}

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'completed':
      return <CheckCircle className="w-4 h-4 text-green-600" />
    case 'failed':
      return <AlertCircle className="w-4 h-4 text-red-600" />
    case 'processing':
      return <RefreshCw className="w-4 h-4 text-yellow-600 animate-spin" />
    case 'queued':
      return <Clock className="w-4 h-4 text-blue-600" />
    default:
      return <Clock className="w-4 h-4 text-gray-600" />
  }
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const formatDate = (dateString: string): string => {
  const date = new Date(dateString)
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
}

export const JobsDashboard: React.FC<JobsDashboardProps> = ({ onJobSelect, onRetryClick }) => {
  const [jobs, setJobs] = useState<IngestJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [selectedJob, setSelectedJob] = useState<IngestJob | null>(null)

  const fetchJobs = async (pageNum: number, status: string = '') => {
    try {
      setLoading(true)
      setError(null)

      const params = new URLSearchParams({
        page: pageNum.toString(),
        page_size: '50',
      })

      if (status) {
        params.append('status', status)
      }

      const response = await fetch(`/api/ingest/jobs?${params}`)
      if (!response.ok) {
        throw new Error('Failed to fetch jobs')
      }

      const data = await response.json()
      setJobs(data.items || data.jobs || [])
      const totalItems = data.total || 0
      const pageSize = data.page_size || 50
      const calculated_total_pages = Math.ceil(totalItems / pageSize) || 1
      setTotalPages(data.total_pages || calculated_total_pages)
      setPage(pageNum)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs')
      setJobs([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // Initial fetch
    fetchJobs(1, statusFilter)

    // Set up polling every 5 seconds to check for job status updates
    const pollInterval = setInterval(() => {
      fetchJobs(page, statusFilter)
    }, 5000)

    return () => clearInterval(pollInterval)
  }, [statusFilter, page])

  const handleJobClick = (job: IngestJob) => {
    setSelectedJob(job)
    if (onJobSelect) {
      onJobSelect(job)
    }
  }

  const handleRetry = (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (onRetryClick) {
      onRetryClick(jobId)
    }
  }

  return (
    <Card>
      <div className="p-6 space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Ingestion Jobs</h2>
          <Button
            onClick={() => fetchJobs(page, statusFilter)}
            size="sm"
            variant="ghost"
            className="flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </Button>
        </div>

        {/* Filters */}
        <div className="flex gap-2 items-center flex-wrap">
          <label className="text-sm font-medium">Status:</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="queued">Queued</option>
            <option value="processing">Processing</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="text-center py-8">
            <div className="inline-block">
              <RefreshCw className="w-6 h-6 text-blue-600 animate-spin" />
            </div>
            <p className="text-gray-600 mt-2">Loading jobs...</p>
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div className="flex gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && jobs.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            <p>No jobs found</p>
          </div>
        )}

        {/* Jobs List */}
        {!loading && jobs.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 px-2">Filename</th>
                  <th className="text-left py-2 px-2">Status</th>
                  <th className="text-left py-2 px-2">Progress</th>
                  <th className="text-left py-2 px-2">Size</th>
                  <th className="text-left py-2 px-2">Created</th>
                  <th className="text-left py-2 px-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    className="border-b hover:bg-gray-50 cursor-pointer transition"
                    onClick={() => handleJobClick(job)}
                  >
                    <td className="py-3 px-2 font-medium truncate">{job.filename}</td>
                    <td className="py-3 px-2">
                      <div className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[job.status] || STATUS_COLORS.pending}`}>
                        {getStatusIcon(job.status)}
                        {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
                      </div>
                    </td>
                    <td className="py-3 px-2">
                      <div className="flex items-center gap-2">
                        <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-600 transition-all"
                            style={{ width: `${job.progress_percentage}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-600">{job.progress_percentage}%</span>
                      </div>
                    </td>
                    <td className="py-3 px-2 text-gray-600">{formatFileSize(job.size)}</td>
                    <td className="py-3 px-2 text-gray-600 text-xs">{formatDate(job.created_at)}</td>
                    <td className="py-3 px-2">
                      {job.status === 'failed' && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={(e) => handleRetry(job.id, e)}
                          className="text-xs"
                        >
                          Retry
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {!loading && totalPages > 1 && (
          <div className="flex justify-between items-center pt-4">
            <div className="text-sm text-gray-600">
              Page {page} of {totalPages}
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => fetchJobs(Math.max(1, page - 1), statusFilter)}
                disabled={page === 1}
                size="sm"
                variant="ghost"
              >
                Previous
              </Button>
              <Button
                onClick={() => fetchJobs(Math.min(totalPages, page + 1), statusFilter)}
                disabled={page === totalPages}
                size="sm"
                variant="ghost"
              >
                Next
              </Button>
            </div>
          </div>
        )}

        {/* Selected Job Detail */}
        {selectedJob && (
          <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <h3 className="font-semibold mb-2">Selected Job Details</h3>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-gray-600">ID:</span>
                <span className="ml-2 font-mono text-xs">{selectedJob.id}</span>
              </div>
              <div>
                <span className="text-gray-600">Mode:</span>
                <span className="ml-2">{selectedJob.mode || 'quick_auto'}</span>
              </div>
              {selectedJob.error_message && (
                <div className="col-span-2">
                  <span className="text-gray-600">Error:</span>
                  <p className="ml-2 text-red-600 text-xs mt-1">{selectedJob.error_message}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}
