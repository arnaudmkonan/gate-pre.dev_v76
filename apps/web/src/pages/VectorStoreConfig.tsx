import React, { useState, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import { useToast } from '../components/Toast'
import axios from 'axios'

import { API_URL } from '../config/api'

export const VectorStoreConfig = () => {
  const { toasts, addToast } = useToast()
  const [formData, setFormData] = useState({
    backend: 'supabase',
    url: '',
    api_key: '',
    embedding_model: 'text-embedding-3-small',
    embedding_dimension: 1536,
    namespace_collection_name: '',
  })
  const [currentConfig, setCurrentConfig] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isTesting, setIsTesting] = useState(false)

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/vector-store/config`)
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
      [name]:
        name === 'embedding_dimension' ? parseInt(value) : value,
    }))
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      const endpoint = currentConfig
        ? `/api/vector-store/config/${currentConfig.id}`
        : '/api/vector-store/config'

      const method = currentConfig ? 'put' : 'post'

      const response = await axios({
        method,
        url: `${API_URL}${endpoint}`,
        data: formData,
      })

      setCurrentConfig(response.data)
      addToast('Vector store configuration saved successfully', 'success')
    } catch (error: any) {
      addToast(error.response?.data?.detail || 'Failed to save configuration', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const handleTestConnection = async () => {
    setIsTesting(true)
    try {
      await axios.get(`${API_URL}/api/vector-store/config`)
      addToast('Vector store connection successful', 'success')
    } catch (error: any) {
      addToast('Failed to connect to vector store', 'error')
    } finally {
      setIsTesting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Vector Store Configuration</h1>
        <p className="text-gray-500 mt-2">Configure vector database for semantic search</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Vector Store Settings</CardTitle>
          <CardDescription>
            Configure vector database backend and embedding parameters
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSave} className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Backend
                </label>
                <select
                  name="backend"
                  value={formData.backend}
                  onChange={handleInputChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="supabase">Supabase (pgvector)</option>
                  <option value="pinecone">Pinecone</option>
                </select>
              </div>

              <Input
                label="Embedding Model"
                name="embedding_model"
                value={formData.embedding_model}
                onChange={handleInputChange}
                required
              />
            </div>

            <Input
              label="Vector Store URL"
              name="url"
              type="url"
              value={formData.url}
              onChange={handleInputChange}
              placeholder="https://your-project.supabase.co"
              required
            />

            <Input
              label="API Key"
              name="api_key"
              type="password"
              value={formData.api_key}
              onChange={handleInputChange}
              required
            />

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Embedding Dimension
                </label>
                <div className="px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-500">
                  {formData.embedding_dimension}
                </div>
                <p className="text-sm text-gray-500 mt-1">Read-only, auto-set by model</p>
              </div>

              <Input
                label="Namespace/Collection (optional)"
                name="namespace_collection_name"
                value={formData.namespace_collection_name}
                onChange={handleInputChange}
                placeholder="my-documents"
              />
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
