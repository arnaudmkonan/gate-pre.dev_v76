import { useState, useEffect } from 'react'
import { UploadForm } from '../components/UploadForm'
import { IngestJobList } from '../components/IngestJobList'
import { Card } from '../components/Card'

export const IngestQueuePage: React.FC = () => {
  const [queueStatus, setQueueStatus] = useState({
    pending: 0,
    processing: 0,
    completed: 0,
    failed: 0,
  })

  const loadQueueStatus = async () => {
    try {
      const response = await fetch('/api/ingest/status')
      if (response.ok) {
        const data = await response.json()
        setQueueStatus(data)
      }
    } catch (err) {
      console.error('Failed to load queue status:', err)
    }
  }

  useEffect(() => {
    loadQueueStatus()
    const interval = setInterval(loadQueueStatus, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleUploadSuccess = () => {
    // Refresh queue status after successful upload
    loadQueueStatus()
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Document Ingestion Queue</h1>
        <p className="text-gray-600">Upload documents for ingestion and processing</p>
      </div>

      {/* Upload Form */}
      <UploadForm onUploadSuccess={handleUploadSuccess} />

      {/* Queue Status Summary */}
      <Card>
        <div className="p-6">
          <h2 className="text-lg font-semibold mb-4">Queue Status</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-yellow-50 p-4 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Pending</p>
              <p className="text-2xl font-bold text-yellow-600">{queueStatus.pending}</p>
            </div>
            <div className="bg-blue-50 p-4 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Processing</p>
              <p className="text-2xl font-bold text-blue-600">{queueStatus.processing}</p>
            </div>
            <div className="bg-green-50 p-4 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Completed</p>
              <p className="text-2xl font-bold text-green-600">{queueStatus.completed}</p>
            </div>
            <div className="bg-red-50 p-4 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Failed</p>
              <p className="text-2xl font-bold text-red-600">{queueStatus.failed}</p>
            </div>
          </div>
        </div>
      </Card>

      {/* Job List */}
      <IngestJobList onJobSelect={undefined} autoRefresh={true} refreshInterval={5000} />
    </div>
  )
}
