import { Clock, AlertCircle, User } from 'lucide-react'
import { ConfidenceBadge } from './ConfidenceBadge'

interface ReviewItem {
  id: string
  document_id: string
  filename?: string
  file_type?: string
  priority: number
  status: string
  reason: string
  reason_code?: string
  confidence_score?: number
  assigned_to?: string
  created_at: string
  issues_detected?: unknown[]
}

interface ReviewItemCardProps {
  item: ReviewItem
  onClick: () => void
}

const getTimeAgo = (dateString: string): string => {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  return `${diffDays}d ago`
}

const getPriorityBadge = (priority: number) => {
  if (priority >= 8) return 'bg-red-100 text-red-800'
  if (priority >= 5) return 'bg-orange-100 text-orange-800'
  if (priority >= 3) return 'bg-yellow-100 text-yellow-800'
  return 'bg-gray-100 text-gray-800'
}

export const ReviewItemCard = ({ item, onClick }: ReviewItemCardProps) => {
  const issueCount = Array.isArray(item.issues_detected) ? item.issues_detected.length : 0

  return (
    <div
      onClick={onClick}
      className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-sm cursor-pointer transition-all"
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-gray-900 truncate">
              {item.filename || `Document ${item.document_id.slice(0, 8)}`}
            </h3>
            {item.file_type && (
              <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded uppercase">
                {item.file_type}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-600 mt-1">{item.reason}</p>
        </div>

        <div className="flex items-center gap-2 ml-4">
          {item.confidence_score !== undefined && (
            <ConfidenceBadge confidence={item.confidence_score} size="sm" />
          )}
          <span className={`text-xs px-2 py-1 rounded-full font-medium ${getPriorityBadge(item.priority)}`}>
            P{item.priority}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {getTimeAgo(item.created_at)}
        </div>
        {issueCount > 0 && (
          <div className="flex items-center gap-1 text-yellow-600">
            <AlertCircle className="w-3 h-3" />
            {issueCount} issue{issueCount !== 1 ? 's' : ''}
          </div>
        )}
        {item.assigned_to && (
          <div className="flex items-center gap-1">
            <User className="w-3 h-3" />
            {item.assigned_to}
          </div>
        )}
        <span className={`px-2 py-0.5 rounded text-xs ${
          item.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
          item.status === 'in_review' ? 'bg-blue-100 text-blue-800' :
          item.status === 'approved' ? 'bg-green-100 text-green-800' :
          'bg-gray-100 text-gray-800'
        }`}>
          {item.status}
        </span>
      </div>
    </div>
  )
}
