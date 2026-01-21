import { useState } from 'react'
import { Card } from './Card'
import { Button } from './Button'
import { AlertCircle, CheckCircle } from 'lucide-react'

interface AdvancedBatchProps {
  jobId: string
  onBatchApply?: (settings: Record<string, any>) => void
  onClose?: () => void
}

export const AdvancedBatch: React.FC<AdvancedBatchProps> = ({ jobId, onBatchApply, onClose }) => {
  const [batchSize, setBatchSize] = useState<number>(10)
  const [scheduleType, setScheduleType] = useState<string>('immediate')
  const [scheduleTime, setScheduleTime] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleApply = async () => {
    if (scheduleType === 'scheduled' && !scheduleTime) {
      setError('Please select a scheduled time')
      return
    }

    if (batchSize < 1 || batchSize > 100) {
      setError('Batch size must be between 1 and 100')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const requestBody: any = {
        mode: 'advanced_batch',
        batch_size: batchSize,
      }

      if (scheduleType === 'scheduled' && scheduleTime) {
        requestBody.schedule_time = scheduleTime
      }

      const response = await fetch(`/api/ingest/jobs/${jobId}/mode`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to apply batch settings')
      }

      setSuccess(true)
      if (onBatchApply) {
        onBatchApply({
          batch_size: batchSize,
          schedule_type: scheduleType,
          schedule_time: scheduleTime,
        })
      }

      // Auto-close after 2 seconds
      setTimeout(() => {
        if (onClose) onClose()
      }, 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to apply batch settings')
    } finally {
      setLoading(false)
    }
  }

  // Get minimum time for scheduled processing (at least 1 minute from now)
  const getMinDateTime = () => {
    const now = new Date()
    now.setMinutes(now.getMinutes() + 1)
    return now.toISOString().slice(0, 16)
  }

  return (
    <Card>
      <div className="p-6 space-y-4">
        <h2 className="text-lg font-semibold">Advanced Batch Settings</h2>
        <p className="text-sm text-gray-600">
          Configure batch processing parameters for this ingestion job
        </p>

        {error && (
          <div className="flex gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {success && (
          <div className="flex gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-green-600">Batch settings applied successfully!</p>
          </div>
        )}

        {!success ? (
          <div className="space-y-4">
            {/* Batch Size */}
            <div>
              <label className="text-sm font-medium block mb-2">
                Batch Size
                <span className="text-xs text-gray-500 font-normal ml-2">
                  (1-100, default 10)
                </span>
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="1"
                  max="100"
                  value={batchSize}
                  onChange={(e) => setBatchSize(parseInt(e.target.value))}
                  disabled={loading}
                  className="flex-1"
                />
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={batchSize}
                  onChange={(e) => {
                    const val = parseInt(e.target.value)
                    if (!isNaN(val) && val >= 1 && val <= 100) {
                      setBatchSize(val)
                    }
                  }}
                  disabled={loading}
                  className="w-16 px-2 py-1 border border-gray-300 rounded text-sm text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Process {batchSize} items at a time
              </p>
            </div>

            {/* Schedule Type */}
            <div>
              <label className="text-sm font-medium block mb-2">Schedule Type</label>
              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="scheduleType"
                    value="immediate"
                    checked={scheduleType === 'immediate'}
                    onChange={(e) => setScheduleType(e.target.value)}
                    disabled={loading}
                  />
                  <span className="text-sm">Immediate (start processing now)</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="scheduleType"
                    value="scheduled"
                    checked={scheduleType === 'scheduled'}
                    onChange={(e) => setScheduleType(e.target.value)}
                    disabled={loading}
                  />
                  <span className="text-sm">Scheduled (start at specified time)</span>
                </label>
              </div>
            </div>

            {/* Scheduled Time */}
            {scheduleType === 'scheduled' && (
              <div>
                <label className="text-sm font-medium block mb-2">Scheduled Start Time</label>
                <input
                  type="datetime-local"
                  value={scheduleTime}
                  onChange={(e) => setScheduleTime(e.target.value)}
                  min={getMinDateTime()}
                  disabled={loading}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Must be at least 1 minute from now
                </p>
              </div>
            )}

            {/* Summary */}
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm text-blue-800">
                <span className="font-medium">Summary:</span> Process {batchSize} items at a time{' '}
                {scheduleType === 'scheduled' && scheduleTime
                  ? `starting at ${new Date(scheduleTime).toLocaleString()}`
                  : 'starting immediately'}
              </p>
            </div>

            {/* Actions */}
            <Button
              onClick={handleApply}
              disabled={loading || (scheduleType === 'scheduled' && !scheduleTime)}
              isLoading={loading}
              className="w-full"
            >
              Apply Batch Settings
            </Button>
          </div>
        ) : null}
      </div>
    </Card>
  )
}
