import { useState, useRef } from 'react'
import { BatchScheduleList } from '../components/BatchScheduleList'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'

export const BatchSchedulePage: React.FC = () => {
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    schedule_name: '',
    cron_expression: '',
    max_concurrency: 5,
    batch_size: 10,
    description: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const listRefreshRef = useRef<() => void>(() => {})

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/batch/schedules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Failed to create schedule')
      }

      setSuccess(true)
      setFormData({
        schedule_name: '',
        cron_expression: '',
        max_concurrency: 5,
        batch_size: 10,
        description: '',
      })
      setShowForm(false)

      // Trigger list refresh
      listRefreshRef.current()

      setTimeout(() => setSuccess(false), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create schedule')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold mb-2">Batch Schedules</h1>
          <p className="text-gray-600">Configure and manage batch processing schedules</p>
        </div>
        <Button onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : 'Create Schedule'}
        </Button>
      </div>

      {/* Create Form */}
      {showForm && (
        <Card>
          <form onSubmit={handleSubmit} className="p-6 space-y-4">
            <h2 className="text-lg font-semibold">Create Batch Schedule</h2>

            <div>
              <label className="block text-sm font-medium mb-1">Schedule Name</label>
              <Input
                type="text"
                value={formData.schedule_name}
                onChange={(e) =>
                  setFormData({ ...formData, schedule_name: e.target.value })
                }
                placeholder="e.g., Daily Evening Batch"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Cron Expression</label>
              <Input
                type="text"
                value={formData.cron_expression}
                onChange={(e) =>
                  setFormData({ ...formData, cron_expression: e.target.value })
                }
                placeholder="e.g., 0 18 * * * (6 PM every day)"
                required
              />
              <p className="text-xs text-gray-500 mt-1">
                Use standard cron format: minute hour day month day_of_week
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Max Concurrency</label>
                <Input
                  type="number"
                  value={formData.max_concurrency}
                  onChange={(e) =>
                    setFormData({ ...formData, max_concurrency: parseInt(e.target.value) })
                  }
                  min="1"
                  max="100"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Batch Size</label>
                <Input
                  type="number"
                  value={formData.batch_size}
                  onChange={(e) =>
                    setFormData({ ...formData, batch_size: parseInt(e.target.value) })
                  }
                  min="1"
                  max="500"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Description (Optional)</label>
              <Input
                type="text"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder="Optional description for this schedule"
              />
            </div>

            {error && <p className="text-sm text-red-600">{error}</p>}
            {success && <p className="text-sm text-green-600">Schedule created successfully!</p>}

            <Button type="submit" disabled={loading} className="w-full">
              {loading ? 'Creating...' : 'Create Schedule'}
            </Button>
          </form>
        </Card>
      )}

      {/* Schedule List */}
      <BatchScheduleList refreshCallback={listRefreshRef} />
    </div>
  )
}
