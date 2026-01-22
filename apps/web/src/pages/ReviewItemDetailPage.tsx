import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, RefreshCw, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'
import { DocumentViewer } from '../components/review/DocumentViewer'
import { ExtractionsList } from '../components/review/ExtractionsList'
import { ReviewActions } from '../components/review/ReviewActions'
import { ConfidenceBadge } from '../components/review/ConfidenceBadge'
import { useReviewItem, useReviewActions } from '../hooks/useReview'

export const ReviewItemDetailPage = () => {
  const { itemId } = useParams<{ itemId: string }>()
  const navigate = useNavigate()
  const [currentReviewer] = useState('reviewer') // In production, get from auth
  const [notes, setNotes] = useState('')
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectModal, setShowRejectModal] = useState(false)

  const { item, loading, error, refetch } = useReviewItem(itemId)
  const { approve, reject, skip, correct, loading: actionLoading, error: actionError } = useReviewActions()

  useEffect(() => {
    if (itemId) {
      refetch()
    }
  }, [itemId])

  const handleApprove = async () => {
    if (!itemId) return
    try {
      await approve(itemId, currentReviewer, notes || undefined)
      navigate('/review')
    } catch {
      // Error handled in hook
    }
  }

  const handleReject = async () => {
    if (!itemId || !rejectReason) return
    try {
      await reject(itemId, currentReviewer, rejectReason)
      setShowRejectModal(false)
      navigate('/review')
    } catch {
      // Error handled in hook
    }
  }

  const handleSkip = async () => {
    if (!itemId) return
    try {
      await skip(itemId)
      navigate('/review')
    } catch {
      // Error handled in hook
    }
  }

  const handleCorrect = async (extractionId: string, correctedValue: unknown, correctionNotes?: string) => {
    if (!itemId) return
    try {
      await correct(itemId, extractionId, correctedValue, currentReviewer, correctionNotes)
      refetch()
    } catch {
      // Error handled in hook
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (error || !item) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => navigate('/review')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Queue
        </Button>
        <div className="flex gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-600">{error || 'Item not found'}</p>
        </div>
      </div>
    )
  }

  const issues = Array.isArray(item.issues_detected) ? item.issues_detected : []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => navigate('/review')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold">
              {item.document?.filename || `Document ${item.document_id.slice(0, 8)}`}
            </h1>
            <div className="flex items-center gap-2 mt-1 text-sm text-gray-500">
              <span className={`px-2 py-0.5 rounded text-xs ${
                item.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                item.status === 'in_review' ? 'bg-blue-100 text-blue-800' :
                'bg-gray-100 text-gray-800'
              }`}>
                {item.status}
              </span>
              {item.confidence_score !== undefined && (
                <ConfidenceBadge confidence={item.confidence_score} />
              )}
              <span>Priority: {item.priority}</span>
            </div>
          </div>
        </div>
        <Button variant="secondary" onClick={refetch} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Action Error */}
      {actionError && (
        <div className="flex gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-600">{actionError}</p>
        </div>
      )}

      {/* Main Content - Split View */}
      <div className="grid grid-cols-2 gap-6">
        {/* Left: Document Viewer */}
        <Card>
          <CardHeader>
            <CardTitle>Document Preview</CardTitle>
          </CardHeader>
          <CardContent>
            <DocumentViewer
              content={item.document?.extracted_text_snippet}
              filename={item.document?.filename}
              fileType={item.document?.file_type}
            />
          </CardContent>
        </Card>

        {/* Right: Extractions and Review */}
        <div className="space-y-6">
          {/* Issues */}
          {issues.length > 0 && (
            <Card className="border-yellow-300 bg-yellow-50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-yellow-800">
                  <AlertCircle className="w-5 h-5" />
                  Issues Detected ({issues.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {issues.map((issue, index) => (
                    <li key={index} className="text-sm text-yellow-800">
                      {typeof issue === 'object' && issue !== null
                        ? JSON.stringify(issue)
                        : String(issue)
                      }
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Review Reason */}
          <Card>
            <CardHeader>
              <CardTitle>Review Reason</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-700">{item.reason}</p>
              {item.reason_code && (
                <span className="inline-block mt-2 text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded">
                  {item.reason_code}
                </span>
              )}
            </CardContent>
          </Card>

          {/* Extractions */}
          <Card>
            <CardHeader>
              <CardTitle>Extracted Fields ({item.extractions?.length || 0})</CardTitle>
            </CardHeader>
            <CardContent>
              {item.extractions && item.extractions.length > 0 ? (
                <ExtractionsList
                  extractions={item.extractions}
                  onCorrect={handleCorrect}
                  isLoading={actionLoading}
                />
              ) : (
                <p className="text-sm text-gray-500 text-center py-4">
                  No extractions available
                </p>
              )}
            </CardContent>
          </Card>

          {/* Notes */}
          <Card>
            <CardHeader>
              <CardTitle>Review Notes</CardTitle>
            </CardHeader>
            <CardContent>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add notes about this review (optional)..."
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </CardContent>
          </Card>

          {/* Actions */}
          <Card>
            <CardContent className="pt-4">
              <ReviewActions
                onApprove={handleApprove}
                onReject={() => setShowRejectModal(true)}
                onSkip={handleSkip}
                isLoading={actionLoading}
                disabled={item.status === 'approved' || item.status === 'rejected'}
              />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <h3 className="text-lg font-semibold mb-4">Reject Document</h3>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Reason for rejection (required)..."
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <div className="flex justify-end gap-3 mt-4">
              <Button variant="secondary" onClick={() => setShowRejectModal(false)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={handleReject}
                disabled={!rejectReason || actionLoading}
              >
                {actionLoading ? 'Rejecting...' : 'Reject'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
