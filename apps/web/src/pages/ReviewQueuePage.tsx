import { useState, useEffect, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { RefreshCw, Filter, PlayCircle, Clock, CheckCircle, XCircle, AlertCircle, Upload, Package } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'
import { ReviewQueueList } from '../components/review/ReviewQueueList'
import { useReviewQueue, useReviewStats, useReviewActions } from '../hooks/useReview'
import { useAuth } from '../contexts/AuthContext'

export const ReviewQueuePage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const currentReviewer = user?.email || 'reviewer'
  const [statusFilter, setStatusFilter] = useState<string>('pending')
  const [reasonFilter, setReasonFilter] = useState<string>('')
  const [fileTypeFilter, setFileTypeFilter] = useState<string>('')
  const [mineOnly, setMineOnly] = useState(false)

  const { items, loading, error, refetch } = useReviewQueue({
    status: statusFilter,
    assignedTo: mineOnly ? currentReviewer : undefined,
    reasonCode: reasonFilter || undefined,
    fileType: fileTypeFilter || undefined,
  })
  const { stats, refetch: refetchStats } = useReviewStats()
  const { assign, loading: actionLoading } = useReviewActions()

  useEffect(() => {
    refetch()
    refetchStats()
  }, [statusFilter, reasonFilter, fileTypeFilter, mineOnly])

  const reasonOptions = useMemo(() => {
    const codes = new Set<string>()
    items.forEach((i) => {
      if (i.reason_code) codes.add(i.reason_code)
    })
    return Array.from(codes).sort()
  }, [items])

  const fileTypeOptions = useMemo(() => {
    const types = new Set<string>()
    items.forEach((i) => {
      if (i.file_type) types.add(i.file_type)
    })
    return Array.from(types).sort()
  }, [items])

  const handlePickNext = async () => {
    const pendingItems = items.filter((item) => item.status === 'pending' || item.status === 'in_review')
    if (pendingItems.length === 0) return

    const highestPriority = pendingItems.reduce((prev, current) =>
      current.priority > prev.priority ? current : prev
    )

    try {
      await assign(highestPriority.id, currentReviewer)
      navigate(`/review/${highestPriority.id}`)
    } catch {
      // Error handled in hook
    }
  }

  const handleItemClick = (item: { id: string }) => {
    navigate(`/review/${item.id}`)
  }

  const emptyMessage =
    statusFilter === 'pending'
      ? 'No documents waiting for HITL — high-confidence files may have auto-cleared.'
      : statusFilter
        ? `No ${statusFilter.replace('_', ' ')} items`
        : 'Review queue is empty'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Doc exceptions</h1>
          <p className="mt-1 text-sm text-slate-500">
            Document HITL only (not shipment assembly or entry Broker OK). Fix extractions, then continue the job.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button onClick={() => { refetch(); refetchStats() }} variant="secondary" disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={handlePickNext} disabled={loading || actionLoading || items.length === 0}>
            <PlayCircle className="w-4 h-4 mr-2" />
            Pick Next Item
          </Button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-yellow-100 rounded-lg">
                  <Clock className="w-5 h-5 text-yellow-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats.total_pending}</p>
                  <p className="text-sm text-gray-500">Pending</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <AlertCircle className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats.total_in_review}</p>
                  <p className="text-sm text-gray-500">In Review</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-100 rounded-lg">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats.total_approved}</p>
                  <p className="text-sm text-gray-500">Approved</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-red-100 rounded-lg">
                  <XCircle className="w-5 h-5 text-red-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats.total_rejected}</p>
                  <p className="text-sm text-gray-500">Rejected</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4" />
            <CardTitle>Filters</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {['pending', 'in_review', 'approved', 'rejected', 'all'].map((status) => (
              <Button
                key={status}
                variant={statusFilter === (status === 'all' ? '' : status) ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => setStatusFilter(status === 'all' ? '' : status)}
              >
                {status === 'all' ? 'All' : status.replace('_', ' ')}
              </Button>
            ))}
            <Button
              variant={mineOnly ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => setMineOnly((v) => !v)}
            >
              Assigned to me
            </Button>
          </div>
          <div className="flex flex-wrap gap-3">
            <label className="text-sm text-slate-600">
              Reason{' '}
              <select
                className="ml-1 rounded border border-slate-300 px-2 py-1 text-sm"
                value={reasonFilter}
                onChange={(e) => setReasonFilter(e.target.value)}
              >
                <option value="">Any</option>
                {reasonOptions.map((code) => (
                  <option key={code} value={code}>{code}</option>
                ))}
              </select>
            </label>
            <label className="text-sm text-slate-600">
              Doc type{' '}
              <select
                className="ml-1 rounded border border-slate-300 px-2 py-1 text-sm"
                value={fileTypeFilter}
                onChange={(e) => setFileTypeFilter(e.target.value)}
              >
                <option value="">Any</option>
                {fileTypeOptions.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </label>
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="flex gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Queue Items ({items.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : items.length === 0 ? (
            <div className="space-y-4 py-10 text-center">
              <p className="text-sm text-slate-600">{emptyMessage}</p>
              <div className="flex flex-wrap items-center justify-center gap-2">
                <Link to="/ingest-ui">
                  <Button size="sm">
                    <Upload className="mr-1.5 h-3.5 w-3.5" />
                    Ingest documents
                  </Button>
                </Link>
                <Link to="/shipments/assembly">
                  <Button size="sm" variant="secondary">
                    <Package className="mr-1.5 h-3.5 w-3.5" />
                    Shipment assembly
                  </Button>
                </Link>
                <Link to="/dashboard">
                  <Button size="sm" variant="secondary">
                    Workbench
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <ReviewQueueList
              items={items}
              onItemClick={handleItemClick}
              emptyMessage={emptyMessage}
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
