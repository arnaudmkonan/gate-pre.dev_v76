import { useState, useEffect } from 'react'
import { AlertCircle, FileText, Clock, User, Globe } from 'lucide-react'

interface SilverRecord {
  id: string
  file_id: string
  raw_content?: Record<string, unknown>
  title?: string
  author?: string
  extraction_date?: string
  document_date?: string
  file_type: string
  size_bytes: number
  language?: string
  content?: string
  record_metadata?: {
    processing_steps?: string[]
    checksum?: string
    [key: string]: unknown
  }
  processing_status: 'pending' | 'completed' | 'failed'
  processing_error?: string
  created_at: string
  updated_at: string
}

interface SilverRecordViewerProps {
  fileId: string
}

export const SilverRecordViewer = ({ fileId }: SilverRecordViewerProps) => {
  const [record, setRecord] = useState<SilverRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    content: true,
    metadata: false,
    raw: false
  })

  useEffect(() => {
    fetchSilverRecord()
    const interval = setInterval(fetchSilverRecord, 5000)
    return () => clearInterval(interval)
  }, [fileId])

  const fetchSilverRecord = async () => {
    try {
      const response = await fetch(`/api/metadata/silver/${fileId}`)
      if (response.status === 204) {
        setError('Record is still processing...')
        return
      }
      if (!response.ok) throw new Error('Failed to fetch silver record')
      const data = await response.json()
      setRecord(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }))
  }

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-gray-500">Loading silver record...</div>
      </div>
    )
  }

  if (error && !record) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-center gap-3">
        <AlertCircle className="w-5 h-5 text-yellow-500" />
        <span className="text-yellow-700">{error}</span>
      </div>
    )
  }

  if (!record) {
    return (
      <div className="text-center py-8 text-gray-500">No silver record found</div>
    )
  }

  const processingSteps = record.record_metadata?.processing_steps || []

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-600 font-medium">File Type</p>
          <p className="text-lg font-semibold text-blue-900 mt-1">{record.file_type}</p>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-sm text-green-600 font-medium">Size</p>
          <p className="text-lg font-semibold text-green-900 mt-1">{formatBytes(record.size_bytes)}</p>
        </div>
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
          <p className="text-sm text-purple-600 font-medium">Status</p>
          <p className="text-lg font-semibold text-purple-900 mt-1 capitalize">
            {record.processing_status}
          </p>
        </div>
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
          <p className="text-sm text-orange-600 font-medium">Language</p>
          <p className="text-lg font-semibold text-orange-900 mt-1">{record.language || 'N/A'}</p>
        </div>
      </div>

      {record.title && (
        <div className="border rounded-lg p-4 bg-gray-50">
          <h2 className="text-xl font-bold text-gray-900">{record.title}</h2>
          {record.author && (
            <p className="text-sm text-gray-600 mt-1 flex items-center gap-2">
              <User className="w-4 h-4" />
              {record.author}
            </p>
          )}
        </div>
      )}

      {/* Content Section */}
      <div className="border rounded-lg overflow-hidden">
        <button
          onClick={() => toggleSection('content')}
          className="w-full px-4 py-3 bg-gray-100 hover:bg-gray-200 font-medium text-gray-900 flex items-center justify-between transition-colors"
        >
          <span className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Extracted Content
          </span>
          <span className={`transform transition-transform ${expandedSections.content ? 'rotate-180' : ''}`}>
            ▼
          </span>
        </button>
        {expandedSections.content && (
          <div className="p-4 bg-white border-t">
            {record.content ? (
              <div className="bg-gray-50 p-4 rounded font-mono text-sm text-gray-700 max-h-96 overflow-y-auto whitespace-pre-wrap break-words">
                {record.content.substring(0, 500)}
                {record.content.length > 500 && '...'}
              </div>
            ) : (
              <p className="text-gray-500">No content available</p>
            )}
          </div>
        )}
      </div>

      {/* Metadata Section */}
      <div className="border rounded-lg overflow-hidden">
        <button
          onClick={() => toggleSection('metadata')}
          className="w-full px-4 py-3 bg-gray-100 hover:bg-gray-200 font-medium text-gray-900 flex items-center justify-between transition-colors"
        >
          <span className="flex items-center gap-2">
            <Clock className="w-5 h-5" />
            Processing Metadata
          </span>
          <span className={`transform transition-transform ${expandedSections.metadata ? 'rotate-180' : ''}`}>
            ▼
          </span>
        </button>
        {expandedSections.metadata && (
          <div className="p-4 bg-white border-t space-y-4">
            {record.extraction_date && (
              <div>
                <p className="text-sm font-medium text-gray-600">Extraction Date</p>
                <p className="text-gray-900">
                  {new Date(record.extraction_date).toLocaleString()}
                </p>
              </div>
            )}
            {record.document_date && (
              <div>
                <p className="text-sm font-medium text-gray-600">Document Date</p>
                <p className="text-gray-900">
                  {new Date(record.document_date).toLocaleString()}
                </p>
              </div>
            )}

            {processingSteps.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-600 mb-2">Processing Steps</p>
                <div className="space-y-1">
                  {processingSteps.map((step: string, index: number) => (
                    <div key={index} className="flex items-center gap-2 text-sm">
                      <span className="w-6 h-6 rounded-full bg-green-100 text-green-700 flex items-center justify-center text-xs font-bold">
                        ✓
                      </span>
                      <span className="text-gray-700 capitalize">{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {record.record_metadata?.checksum && (
              <div>
                <p className="text-sm font-medium text-gray-600">Checksum</p>
                <p className="font-mono text-xs text-gray-500 break-all">
                  {record.record_metadata.checksum}
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Raw Content Section */}
      {record.raw_content && (
        <div className="border rounded-lg overflow-hidden">
          <button
            onClick={() => toggleSection('raw')}
            className="w-full px-4 py-3 bg-gray-100 hover:bg-gray-200 font-medium text-gray-900 flex items-center justify-between transition-colors"
          >
            <span className="flex items-center gap-2">
              <Globe className="w-5 h-5" />
              Raw Content (JSON)
            </span>
            <span className={`transform transition-transform ${expandedSections.raw ? 'rotate-180' : ''}`}>
              ▼
            </span>
          </button>
          {expandedSections.raw && (
            <div className="p-4 bg-white border-t">
              <pre className="bg-gray-50 p-4 rounded font-mono text-xs text-gray-700 max-h-96 overflow-y-auto">
                {JSON.stringify(record.raw_content, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

      {record.processing_error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm font-medium text-red-600 mb-1">Processing Error</p>
          <p className="text-red-700">{record.processing_error}</p>
        </div>
      )}
    </div>
  )
}
