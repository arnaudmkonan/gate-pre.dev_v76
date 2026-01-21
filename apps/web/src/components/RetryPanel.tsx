import { useState } from 'react'
import { Card } from './Card'
import { Button } from './Button'
import { AlertCircle, CheckCircle, X } from 'lucide-react'

interface RetryPanelProps {
  jobId?: string
  onRetrySuccess?: (newJobId: string) => void
  onClose?: () => void
}

interface RetryResult {
  job_id: string
  new_job_id: string
  status: string
  message: string
}

export const RetryPanel: React.FC<RetryPanelProps> = ({ jobId, onRetrySuccess, onClose }) => {
  const [selectedJobIds, setSelectedJobIds] = useState<Set<string>>(jobId ? new Set([jobId]) : new Set())
  const [modeOverride, setModeOverride] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<RetryResult[] | null>(null)
  const [showConfirmation, setShowConfirmation] = useState(false)


  const handleRetry = async () => {
    if (selectedJobIds.size === 0) {
      setError('Please select at least one job to retry')
      return
    }

    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await fetch('/api/jobs/retry', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          job_ids: Array.from(selectedJobIds),
          mode_override: modeOverride || undefined,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to retry jobs')
      }

      const data = await response.json()
      setSuccess(data.results || [])
      setSelectedJobIds(new Set())
      setModeOverride('')

      // Notify parent if single job was retried successfully
      if (data.results?.[0]) {
        if (onRetrySuccess) {
          onRetrySuccess(data.results[0].new_job_id)
        }
      }

      // Auto-close after 3 seconds
      setTimeout(() => {
        if (onClose) onClose()
      }, 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to retry jobs')
    } finally {
      setLoading(false)
      setShowConfirmation(false)
    }
  }

  return (
    <Card>
      <div className="p-6 space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Retry Failed Jobs</h2>
          {onClose && (
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {error && (
          <div className="flex gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {success && success.length > 0 && (
          <div className="flex gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-green-600">
              <p className="font-medium">{success.length} job(s) retried successfully</p>
              {success.map((result) => (
                <p key={result.job_id} className="text-xs mt-1">
                  Job {result.job_id.slice(0, 8)}... → New ID: {result.new_job_id.slice(0, 8)}...
                </p>
              ))}
            </div>
          </div>
        )}

        {!success ? (
          <div className="space-y-4">
            {/* Job Selection */}
            {!jobId && (
              <div>
                <label className="text-sm font-medium block mb-2">Select Jobs to Retry</label>
                <div className="space-y-2 p-3 bg-gray-50 rounded-lg max-h-48 overflow-y-auto">
                  <p className="text-xs text-gray-500">
                    Paste job IDs (one per line) or select from dashboard
                  </p>
                  <textarea
                    className="w-full p-2 border border-gray-300 rounded text-sm font-mono"
                    placeholder="Enter job IDs..."
                    rows={3}
                    onChange={(e) => {
                      const ids = e.target.value
                        .split('\n')
                        .map((id) => id.trim())
                        .filter((id) => id.length > 0)
                      setSelectedJobIds(new Set(ids))
                    }}
                  />
                </div>
                {selectedJobIds.size > 0 && (
                  <p className="text-xs text-gray-600 mt-2">
                    {selectedJobIds.size} job(s) selected (max 100)
                  </p>
                )}
              </div>
            )}

            {jobId && selectedJobIds.has(jobId) && (
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-800">
                  <span className="font-medium">Job Selected:</span> {jobId.slice(0, 8)}...
                </p>
              </div>
            )}

            {/* Mode Override */}
            <div>
              <label className="text-sm font-medium block mb-2">Mode Override (Optional)</label>
              <select
                value={modeOverride}
                onChange={(e) => setModeOverride(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={loading}
              >
                <option value="">No Override (use original mode)</option>
                <option value="quick_auto">Quick Auto</option>
                <option value="guided_mapping">Guided Mapping</option>
                <option value="advanced_batch">Advanced Batch</option>
              </select>
            </div>

            {/* Confirmation Dialog */}
            {showConfirmation ? (
              <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg space-y-3">
                <p className="text-sm text-yellow-800 font-medium">
                  Confirm retry of {selectedJobIds.size} job(s)?
                </p>
                <div className="flex gap-2 justify-end">
                  <Button
                    onClick={() => setShowConfirmation(false)}
                    variant="ghost"
                    size="sm"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleRetry}
                    isLoading={loading}
                    size="sm"
                  >
                    Confirm Retry
                  </Button>
                </div>
              </div>
            ) : (
              <Button
                onClick={() => setShowConfirmation(true)}
                disabled={selectedJobIds.size === 0 || loading}
                className="w-full"
              >
                Retry Jobs ({selectedJobIds.size})
              </Button>
            )}
          </div>
        ) : null}
      </div>
    </Card>
  )
}
