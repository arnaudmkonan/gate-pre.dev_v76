import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { RefreshCw, Filter, PlayCircle, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'
import { ReviewQueueList } from '../components/review/ReviewQueueList'
import { useReviewQueue, useReviewStats, useReviewActions } from '../hooks/useReview'

export const ReviewQueuePage = () => {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState<string>('pending')
  const [currentReviewer] = useState('reviewer') // In production, get from auth

  const { items, loading, error, refetch } = useReviewQueue({ status: statusFilter })
  const { stats, refetch: refetchStats } = useReviewStats()
  const { assign, loading: actionLoading } = useReviewActions()

  useEffect(() => {
    refetch()
    refetchStats()
  }, [statusFilter])

  const handlePickNext = async () => {
    // Find the highest priority pending item
    const pendingItems = items.filter(item => item.status === 'pending')
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Review Queue</h1>
        <div className="flex items-center gap-3">
          <Button onClick={() => { refetch(); refetchStats() }} variant="secondary" disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={handlePickNext} disabled={loading || actionLoading || items.filter(i => i.status === 'pending').length === 0}>
            <PlayCircle className="w-4 h-4 mr-2" />
            Pick Next Item
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
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

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4" />
            <CardTitle>Filters</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            {['pending', 'in_review', 'approved', 'rejected', 'all'].map((status) => (
              <Button
                key={status}
                variant={statusFilter === status ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => setStatusFilter(status === 'all' ? '' : status)}
              >
                {status === 'all' ? 'All' : status.replace('_', ' ')}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Error State */}
      {error && (
        <div className="flex gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {/* Queue List */}
      <Card>
        <CardHeader>
          <CardTitle>
            Queue Items ({items.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : (
            <ReviewQueueList
              items={items}
              onItemClick={handleItemClick}
              emptyMessage={statusFilter ? `No ${statusFilter.replace('_', ' ')} items` : 'Review queue is empty'}
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
