import React, { useState, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import { useToast } from '../components/Toast'
import axios from 'axios'

const API_URL = 'http://localhost:8000'

export const StorageConfig = () => {
  const { toasts, addToast } = useToast()
  const [formData, setFormData] = useState({
    provider: 'supabase',
    endpoint: '',
    bucket_name: '',
    region: 'us-east-1',
    access_key: '',
    secret_key: '',
    max_file_size_mb: 100,
  })
  const [currentConfig, setCurrentConfig] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isTesting, setIsTesting] = useState(false)

  // Load current config on mount
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/storage/config`)
        setCurrentConfig(response.data)
        setFormData(response.data)
      } catch {
        // No config yet
      }
    }
    fetchConfig()
  }, [])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: name === 'max_file_size_mb' ? parseInt(value) : value,
    }))
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      const endpoint = currentConfig
        ? `/api/storage/config/${currentConfig.id}`
        : '/api/storage/config'

      const method = currentConfig ? 'put' : 'post'

      const response = await axios({
        method,
        url: `${API_URL}${endpoint}`,
        data: formData,
      })

      setCurrentConfig(response.data)
      addToast('Storage configuration saved successfully', 'success')
    } catch (error: any) {
      addToast(error.response?.data?.detail || 'Failed to save configuration', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const handleTestConnection = async () => {
    setIsTesting(true)
    try {
      await axios.get(`${API_URL}/api/storage/config`)
      addToast('Storage connection successful', 'success')
    } catch (error: any) {
      addToast('Failed to connect to storage', 'error')
    } finally {
      setIsTesting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Storage Configuration</h1>
        <p className="text-gray-500 mt-2">Configure your object storage provider for file uploads</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Storage Settings</CardTitle>
          <CardDescription>
            Configure Supabase Storage or S3-compatible storage
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSave} className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Provider
                </label>
                <select
                  name="provider"
                  value={formData.provider}
                  onChange={handleInputChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="supabase">Supabase</option>
                  <option value="s3">AWS S3</option>
                </select>
              </div>

              <Input
                label="Region"
                name="region"
                value={formData.region}
                onChange={handleInputChange}
                required
              />
            </div>

            <Input
              label="Endpoint URL"
              name="endpoint"
              type="url"
              value={formData.endpoint}
              onChange={handleInputChange}
              placeholder="https://your-project.supabase.co/storage/v1/s3"
              required
            />

            <Input
              label="Bucket Name"
              name="bucket_name"
              value={formData.bucket_name}
              onChange={handleInputChange}
              placeholder="raw-files"
              required
            />

            <Input
              label="Access Key"
              name="access_key"
              type="password"
              value={formData.access_key}
              onChange={handleInputChange}
              required
            />

            <Input
              label="Secret Key"
              name="secret_key"
              type="password"
              value={formData.secret_key}
              onChange={handleInputChange}
              required
            />

            <Input
              label="Max File Size (MB)"
              name="max_file_size_mb"
              type="number"
              min="1"
              max="5000"
              value={formData.max_file_size_mb}
              onChange={handleInputChange}
              required
            />

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
