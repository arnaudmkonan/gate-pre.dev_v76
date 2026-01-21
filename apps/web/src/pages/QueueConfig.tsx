import React, { useState, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import { useToast } from '../components/Toast'
import axios from 'axios'

const API_URL = 'http://localhost:8000'

export const QueueConfig = () => {
  const { toasts, addToast } = useToast()
  const [formData, setFormData] = useState({
    redis_host: 'localhost',
    redis_port: 6379,
    redis_password: '',
    worker_concurrency: 4,
    task_timeout: 3600,
    max_retries: 3,
    retry_backoff: true,
  })
  const [isLoading, setIsLoading] = useState(false)
  const [isTesting, setIsTesting] = useState(false)

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/queue/config`)
        setFormData(response.data)
      } catch {
        // No config yet
      }
    }
    fetchConfig()
  }, [])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]:
        type === 'checkbox'
          ? (e.target as HTMLInputElement).checked
          : isNaN(Number(value))
            ? value
            : Number(value),
    }))
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      await axios.post(`${API_URL}/api/queue/config`, formData)
      addToast('Queue configuration saved successfully', 'success')
    } catch (error: any) {
      addToast(error.response?.data?.detail || 'Failed to save configuration', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const handleTestConnection = async () => {
    setIsTesting(true)
    try {
      await axios.get(`${API_URL}/api/queue/config`)
      addToast('Queue connection successful', 'success')
    } catch (error: any) {
      addToast('Failed to connect to queue', 'error')
    } finally {
      setIsTesting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Queue Configuration</h1>
        <p className="text-gray-500 mt-2">Configure Redis and Celery for job processing</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Queue Settings</CardTitle>
          <CardDescription>Configure Redis broker and Celery workers</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSave} className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Redis Host"
                name="redis_host"
                value={formData.redis_host}
                onChange={handleInputChange}
                required
              />

              <Input
                label="Redis Port"
                name="redis_port"
                type="number"
                min="1"
                max="65535"
                value={formData.redis_port}
                onChange={handleInputChange}
                required
              />
            </div>

            <Input
              label="Redis Password (optional)"
              name="redis_password"
              type="password"
              value={formData.redis_password}
              onChange={handleInputChange}
            />

            <div className="grid grid-cols-3 gap-4">
              <Input
                label="Worker Concurrency"
                name="worker_concurrency"
                type="number"
                min="1"
                max="100"
                value={formData.worker_concurrency}
                onChange={handleInputChange}
                required
              />

              <Input
                label="Task Timeout (seconds)"
                name="task_timeout"
                type="number"
                min="60"
                max="86400"
                value={formData.task_timeout}
                onChange={handleInputChange}
                required
              />

              <Input
                label="Max Retries"
                name="max_retries"
                type="number"
                min="0"
                max="10"
                value={formData.max_retries}
                onChange={handleInputChange}
                required
              />
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="retry_backoff"
                name="retry_backoff"
                checked={formData.retry_backoff}
                onChange={handleInputChange}
                className="w-4 h-4"
              />
              <label htmlFor="retry_backoff" className="text-sm font-medium text-gray-700">
                Enable Retry Backoff (exponential backoff with jitter)
              </label>
            </div>

            <div className="flex gap-3 pt-4">
              <Button type="submit" isLoading={isLoading}>
                Save Configuration
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={handleTestConnection}
                isLoading={isTesting}
              >
                Test Connection
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <div className="fixed bottom-4 right-4 space-y-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`p-4 rounded-lg text-white ${
              toast.type === 'success' ? 'bg-green-500' : 'bg-red-500'
            }`}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  )
}
