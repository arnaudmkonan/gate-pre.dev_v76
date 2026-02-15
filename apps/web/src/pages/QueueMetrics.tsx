import { useState, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/Card'
import { Button } from '../components/Button'
import axios from 'axios'
import { RefreshCw } from 'lucide-react'

import { API_URL } from '../config/api'

interface QueueStatus {
  pending: number
  running: number
  failed: number
}

export const QueueMetrics = () => {
  const [status, setStatus] = useState<QueueStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const fetchStatus = async () => {
    setIsLoading(true)
    try {
      const response = await axios.get(`${API_URL}/api/queue/status`)
      setStatus(response.data)
    } catch (error) {
      console.error('Failed to fetch queue status:', error)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 5000) // Auto-refresh every 5s
    return () => clearInterval(interval)
  }, [])

  const StatCard = ({
    label,
    value,
    color,
  }: {
    label: string
    value: number
    color: string
  }) => (
    <Card>
      <CardContent className="pt-6">
        <div className="text-center">
          <p className="text-sm font-medium text-gray-500 mb-2">{label}</p>
          <p className={`text-4xl font-bold ${color}`}>{value}</p>
          <div className={`mt-2 inline-block w-2 h-2 rounded-full ${color.replace('text', 'bg')}`} />
        </div>
      </CardContent>
    </Card>
  )

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Queue Metrics</h1>
          <p className="text-gray-500 mt-2">Real-time job queue status</p>
        </div>
        <Button onClick={fetchStatus} isLoading={isLoading} size="sm">
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {status ? (
        <div className="grid grid-cols-3 gap-6">
          <StatCard label="Pending Jobs" value={status.pending} color="text-yellow-600" />
          <StatCard label="Running Jobs" value={status.running} color="text-blue-600" />
          <StatCard label="Failed Jobs" value={status.failed} color="text-red-600" />
        </div>
      ) : (
        <Card>
          <CardContent className="pt-6">
            <p className="text-center text-gray-500">Loading queue status...</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">Auto-refresh</span>
              <span className="text-sm text-gray-500">Every 5 seconds</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">Last updated</span>
              <span className="text-sm text-gray-500">
                {status ? new Date().toLocaleTimeString() : 'Never'}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
