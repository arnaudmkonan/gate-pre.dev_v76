import { useState, useEffect, MutableRefObject } from 'react'
import { Card } from './Card'
import { Button } from './Button'
import { AlertCircle, Trash2, RefreshCw } from 'lucide-react'

interface BatchSchedule {
  id: string
  schedule_name: string
  cron_expression: string
  max_concurrency: number
  batch_size: number
  is_active: boolean
  last_run_at?: string
  next_run_at?: string
  created_at: string
}

interface BatchScheduleListProps {
  refreshCallback?: MutableRefObject<() => void>
}

export const BatchScheduleList: React.FC<BatchScheduleListProps> = ({ refreshCallback }) => {
  const [schedules, setSchedules] = useState<BatchSchedule[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSchedules = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/batch/schedules?is_active=true')

      if (!response.ok) {
        throw new Error('Failed to load schedules')
      }

      const data = await response.json()
      setSchedules(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load schedules')
      setSchedules([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSchedules()
    // Expose refresh function to parent
    if (refreshCallback) {
      refreshCallback.current = loadSchedules
    }
  }, [refreshCallback])

  const handleDelete = async (scheduleId: string) => {
    if (!window.confirm('Are you sure you want to delete this schedule?')) return

    try {
      const response = await fetch(`/api/batch/schedules/${scheduleId}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error('Failed to delete schedule')
      }

      setSchedules(schedules.filter((s) => s.id !== scheduleId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete schedule')
    }
  }

  const toggleActive = async (schedule: BatchSchedule) => {
    try {
      const response = await fetch(`/api/batch/schedules/${schedule.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !schedule.is_active }),
      })

      if (!response.ok) {
        throw new Error('Failed to update schedule')
      }

      const updated = await response.json()
      setSchedules(schedules.map((s) => (s.id === schedule.id ? updated : s)))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update schedule')
    }
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Never'
    return new Date(dateString).toLocaleString()
  }

  return (
    <Card>
      <div className="p-6 space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Batch Schedules</h2>
          <Button onClick={loadSchedules} disabled={loading} variant="secondary" size="sm">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>

        {error && (
          <div className="flex gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {loading ? (
          <p className="text-center py-4 text-gray-500">Loading schedules...</p>
        ) : schedules.length === 0 ? (
          <p className="text-center py-4 text-gray-500">No active schedules</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 px-3 font-semibold">Name</th>
                  <th className="text-left py-2 px-3 font-semibold">Cron Expression</th>
                  <th className="text-left py-2 px-3 font-semibold">Concurrency</th>
                  <th className="text-left py-2 px-3 font-semibold">Batch Size</th>
                  <th className="text-left py-2 px-3 font-semibold">Next Run</th>
                  <th className="text-left py-2 px-3 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {schedules.map((schedule) => (
                  <tr key={schedule.id} className="border-b hover:bg-gray-50">
                    <td className="py-3 px-3">{schedule.schedule_name}</td>
                    <td className="py-3 px-3 font-mono text-xs">{schedule.cron_expression}</td>
                    <td className="py-3 px-3">{schedule.max_concurrency}</td>
                    <td className="py-3 px-3">{schedule.batch_size}</td>
                    <td className="py-3 px-3 text-xs text-gray-600">{formatDate(schedule.next_run_at)}</td>
                    <td className="py-3 px-3">
                      <div className="flex gap-2">
                        <button
                          onClick={() => toggleActive(schedule)}
                          className={`px-2 py-1 rounded text-xs font-medium ${
                            schedule.is_active
                              ? 'bg-green-100 text-green-700'
                              : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {schedule.is_active ? 'Active' : 'Inactive'}
                        </button>
                        <Button
                          onClick={() => handleDelete(schedule.id)}
                          variant="secondary"
                          size="sm"
                          className="text-red-600"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Card>
  )
}
