import { useState, useEffect } from 'react'
import { AlertCircle, CheckCircle, Clock, Zap, ChevronDown } from 'lucide-react'

interface IngestFile {
  id: string
  batch_id: string
  file_id: string
  file_type: string
  status: 'queued' | 'processing' | 'success' | 'failed' | 'retry'
  routing_decision?: string
  attempts: number
  max_attempts: number
  last_error?: string
  processing_started_at?: string
  processing_completed_at?: string
}

interface IngestBatch {
  id: string
  batch_name: string
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'partial'
  file_count: number
  success_count: number
  failure_count: number
  created_by?: string
  max_concurrent_jobs: number
  processing_started_at?: string
  processing_completed_at?: string
  created_at: string
}

export const IngestBatchMonitor = () => {
  const [batches, setBatches] = useState<IngestBatch[]>([])
  const [expandedBatch, setExpandedBatch] = useState<string | null>(null)
  const [batchFiles, setBatchFiles] = useState<Record<string, IngestFile[]>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchBatches()
    const interval = setInterval(fetchBatches, 5000)
    return () => clearInterval(interval)
  }, [])

  const fetchBatches = async () => {
    try {
      const response = await fetch('/api/ingest/batch')
      if (!response.ok) throw new Error('Failed to fetch batches')
      const data = await response.json()
      setBatches(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const fetchBatchFiles = async (batchId: string) => {
    if (batchFiles[batchId]) return

    try {
      const response = await fetch(`/api/ingest/batch/${batchId}`)
      if (!response.ok) throw new Error('Failed to fetch batch details')
      const data = await response.json()
      setBatchFiles(prev => ({
        ...prev,
        [batchId]: data.files
      }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'processing':
        return <Zap className="w-5 h-5 text-blue-500 animate-pulse" />
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />
      case 'pending':
      case 'queued':
        return <Clock className="w-5 h-5 text-gray-400" />
      default:
        return <Clock className="w-5 h-5 text-gray-400" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
      case 'success':
        return 'bg-green-50 border-green-200'
      case 'processing':
        return 'bg-blue-50 border-blue-200'
      case 'failed':
        return 'bg-red-50 border-red-200'
      case 'partial':
        return 'bg-yellow-50 border-yellow-200'
      case 'pending':
      case 'queued':
        return 'bg-gray-50 border-gray-200'
      default:
        return 'bg-gray-50 border-gray-200'
    }
  }

  const toggleBatchExpand = async (batchId: string) => {
    if (expandedBatch === batchId) {
      setExpandedBatch(null)
    } else {
      await fetchBatchFiles(batchId)
      setExpandedBatch(batchId)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-gray-500">Loading batches...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Batch Ingestion Monitor</h1>
        <p className="text-gray-600 mt-2">Monitor and manage document ingestion batches</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500" />
          <span className="text-red-700">{error}</span>
        </div>
      )}

      <div className="space-y-4">
        {batches.length === 0 ? (
          <div className="text-center py-8 text-gray-500">No batches found</div>
        ) : (
          batches.map(batch => (
            <div
              key={batch.id}
              className={`border rounded-lg overflow-hidden ${getStatusColor(batch.status)}`}
            >
              <button
                onClick={() => toggleBatchExpand(batch.id)}
                className="w-full p-4 hover:bg-white/50 transition-colors flex items-center justify-between"
              >
                <div className="flex items-center gap-4 flex-1 text-left">
                  {getStatusIcon(batch.status)}
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900">{batch.batch_name}</h3>
                    <p className="text-sm text-gray-600">
                      {batch.success_count} / {batch.file_count} files processed
                    </p>
                  </div>
                  <div className="text-sm font-medium text-gray-700">
                    {batch.status.charAt(0).toUpperCase() + batch.status.slice(1)}
                  </div>
                </div>
                <ChevronDown
                  className={`w-5 h-5 text-gray-400 transition-transform ${
                    expandedBatch === batch.id ? 'rotate-180' : ''
                  }`}
                />
              </button>

              {expandedBatch === batch.id && batchFiles[batch.id] && (
                <div className="border-t bg-white/50 p-4 space-y-2 max-h-96 overflow-y-auto">
                  {batchFiles[batch.id].map(file => (
                    <div
                      key={file.id}
                      className="flex items-center gap-3 p-3 bg-white rounded border border-gray-200"
                    >
                      {getStatusIcon(file.status)}
                      <div className="flex-1">
                        <p className="font-medium text-gray-900">{file.file_type}</p>
                        <p className="text-xs text-gray-600">
                          {file.routing_decision && `Agent: ${file.routing_decision}`}
                          {file.last_error && ` • Error: ${file.last_error.substring(0, 50)}...`}
                        </p>
                      </div>
                      <span className="text-xs font-medium text-gray-600">
                        {file.attempts}/{file.max_attempts}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
