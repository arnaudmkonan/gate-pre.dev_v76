import { useState, useEffect } from 'react'
import {
  Search,
  Loader,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  FileText,
} from 'lucide-react'
import { Card } from './Card'
import { Input } from './Input'
import { Button } from './Button'
import { API_URL } from '../config/api'

interface ExtractionResult {
  id: string
  file_id: string
  filename: string
  status: 'pending' | 'in_progress' | 'success' | 'partial' | 'failed'
  extracted_text?: string
  extracted_tables?: any[]
  extracted_metadata?: Record<string, any>
  error_message?: string
  error_details?: Record<string, any>
  extraction_timestamp?: string
  extractor_version?: string
  created_at: string
  updated_at: string
}

interface ExtractionResponse {
  total: number
  page: number
  page_size: number
  items: ExtractionResult[]
}

const STATUS_COLORS = {
  pending: 'bg-yellow-100 text-yellow-800',
  in_progress: 'bg-blue-100 text-blue-800',
  success: 'bg-green-100 text-green-800',
  partial: 'bg-orange-100 text-orange-800',
  failed: 'bg-red-100 text-red-800',
}

export const ExtractionStatusViewer = () => {
  const [fileId, setFileId] = useState<string>('')
  const [status, setStatus] = useState<string>('')
  const [page, setPage] = useState(1)
  const pageSize = 20

  const [data, setData] = useState<ExtractionResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const fetchExtractions = async () => {
    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams()
      if (fileId) params.append('file_id', fileId)
      if (status) params.append('status', status)
      params.append('page', page.toString())
      params.append('page_size', pageSize.toString())

      const response = await fetch(
        `${API_URL}/api/extractions?${params.toString()}`
      )

      if (response.status === 204) {
        setData(null)
        return
      }

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to fetch extractions')
      }

      const result: ExtractionResponse = await response.json()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch extractions')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchExtractions()
  }, [page])

  const handleSearch = () => {
    setPage(1)
    fetchExtractions()
  }

  const handleReset = () => {
    setFileId('')
    setStatus('')
    setPage(1)
    setExpandedId(null)
  }

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Extraction Status Viewer</h1>
      </div>

      {/* Search Filters */}
      <Card>
        <div className="p-6 space-y-4">
          <h2 className="text-lg font-semibold">Search Filters</h2>

          <div className="grid grid-cols-2 gap-4">
            <Input
              type="text"
              placeholder="File ID (UUID)"
              value={fileId}
              onChange={(e) => setFileId(e.target.value)}
              disabled={loading}
            />
            <Input
              type="text"
              placeholder="Status (pending, success, failed, etc.)"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="flex gap-2">
            <Button onClick={handleSearch} disabled={loading}>
              {loading ? (
                <>
                  <Loader className="w-4 h-4 mr-2 animate-spin" />
                  Searching...
                </>
              ) : (
                <>
                  <Search className="w-4 h-4 mr-2" />
                  Search
                </>
              )}
            </Button>
            <Button onClick={handleReset} variant="secondary" disabled={loading}>
              Reset
            </Button>
          </div>
        </div>
      </Card>

      {/* Status Messages */}
      {error && (
        <div className="flex gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {/* Results */}
      {data && data.items.length > 0 && (
        <>
          <Card>
            <div className="p-6">
              <h2 className="text-lg font-semibold mb-4">
                Results ({data.total} total)
              </h2>

              <div className="space-y-3">
                {data.items.map((item) => (
                  <div key={item.id} className="border rounded-lg overflow-hidden">
                    {/* Main Row */}
                    <div
                      className="p-4 flex items-center justify-between cursor-pointer hover:bg-gray-50"
                      onClick={() => toggleExpand(item.id)}
                    >
                      <div className="flex items-center gap-3 flex-1">
                        <button className="text-gray-400 hover:text-gray-600">
                          {expandedId === item.id ? (
                            <ChevronUp className="w-5 h-5" />
                          ) : (
                            <ChevronDown className="w-5 h-5" />
                          )}
                        </button>
                        <FileText className="w-5 h-5 text-gray-400 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <h3 className="font-semibold text-gray-900 truncate">
                            {item.filename}
                          </h3>
                          <p className="text-xs text-gray-500 mt-1">
                            ID: {item.file_id}
                          </p>
                        </div>
                      </div>

                      <span
                        className={`px-3 py-1 rounded-full text-xs font-medium flex-shrink-0 ${STATUS_COLORS[item.status] || 'bg-gray-100 text-gray-800'
                          }`}
                      >
                        {item.status}
                      </span>
                    </div>

                    {/* Expanded Details */}
                    {expandedId === item.id && (
                      <div className="border-t bg-gray-50 p-4 space-y-4">
                        {/* Timestamps */}
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <span className="font-medium text-gray-700">
                              Created:
                            </span>
                            <p className="text-gray-600 mt-1">
                              {new Date(item.created_at).toLocaleString()}
                            </p>
                          </div>
                          <div>
                            <span className="font-medium text-gray-700">
                              Updated:
                            </span>
                            <p className="text-gray-600 mt-1">
                              {new Date(item.updated_at).toLocaleString()}
                            </p>
                          </div>
                          {item.extraction_timestamp && (
                            <div>
                              <span className="font-medium text-gray-700">
                                Extracted:
                              </span>
                              <p className="text-gray-600 mt-1">
                                {new Date(
                                  item.extraction_timestamp
                                ).toLocaleString()}
                              </p>
                            </div>
                          )}
                          {item.extractor_version && (
                            <div>
                              <span className="font-medium text-gray-700">
                                Extractor Version:
                              </span>
                              <p className="text-gray-600 mt-1">
                                {item.extractor_version}
                              </p>
                            </div>
                          )}
                        </div>

                        {/* Extracted Text Preview */}
                        {item.extracted_text && (
                          <div>
                            <span className="font-medium text-gray-700 text-sm">
                              Extracted Text Preview:
                            </span>
                            <div className="bg-white rounded border border-gray-200 p-3 mt-2 max-h-48 overflow-y-auto">
                              <p className="text-sm text-gray-700 whitespace-pre-wrap">
                                {item.extracted_text.substring(0, 500)}
                                {item.extracted_text.length > 500 ? '...' : ''}
                              </p>
                            </div>
                          </div>
                        )}

                        {/* Extracted Tables */}
                        {item.extracted_tables &&
                          item.extracted_tables.length > 0 && (
                            <div>
                              <span className="font-medium text-gray-700 text-sm">
                                Tables Found: {item.extracted_tables.length}
                              </span>
                              <div className="bg-white rounded border border-gray-200 p-3 mt-2 max-h-48 overflow-y-auto">
                                <pre className="text-xs text-gray-700 font-mono">
                                  {JSON.stringify(
                                    item.extracted_tables.slice(0, 2),
                                    null,
                                    2
                                  )}
                                </pre>
                                {item.extracted_tables.length > 2 && (
                                  <p className="text-xs text-gray-500 mt-2">
                                    ... and {item.extracted_tables.length - 2}{' '}
                                    more tables
                                  </p>
                                )}
                              </div>
                            </div>
                          )}

                        {/* Extracted Metadata */}
                        {item.extracted_metadata &&
                          Object.keys(item.extracted_metadata).length > 0 && (
                            <div>
                              <span className="font-medium text-gray-700 text-sm">
                                Metadata:
                              </span>
                              <div className="bg-white rounded border border-gray-200 p-3 mt-2 max-h-48 overflow-y-auto">
                                <pre className="text-xs text-gray-700 font-mono">
                                  {JSON.stringify(
                                    item.extracted_metadata,
                                    null,
                                    2
                                  )}
                                </pre>
                              </div>
                            </div>
                          )}

                        {/* Error Details */}
                        {item.error_message && (
                          <div className="bg-red-50 border border-red-200 rounded p-3">
                            <p className="text-sm font-medium text-red-800">
                              Error Message:
                            </p>
                            <p className="text-sm text-red-700 mt-1">
                              {item.error_message}
                            </p>

                            {item.error_details &&
                              Object.keys(item.error_details).length > 0 && (
                                <div className="mt-3">
                                  <p className="text-xs font-medium text-red-800">
                                    Error Details:
                                  </p>
                                  <pre className="text-xs text-red-700 font-mono mt-2 bg-red-100 p-2 rounded overflow-x-auto">
                                    {JSON.stringify(
                                      item.error_details,
                                      null,
                                      2
                                    )}
                                  </pre>
                                </div>
                              )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </Card>

          {/* Pagination */}
          {data.total > pageSize && (
            <Card>
              <div className="p-6 flex items-center justify-between">
                <p className="text-sm text-gray-600">
                  Page {data.page} of {Math.ceil(data.total / pageSize)}
                </p>
                <div className="flex gap-2">
                  <Button
                    onClick={() => setPage(Math.max(1, page - 1))}
                    disabled={page === 1 || loading}
                    variant="secondary"
                  >
                    Previous
                  </Button>
                  <Button
                    onClick={() =>
                      setPage(
                        Math.min(Math.ceil(data.total / pageSize), page + 1)
                      )
                    }
                    disabled={page >= Math.ceil(data.total / pageSize) || loading}
                    variant="secondary"
                  >
                    Next
                  </Button>
                </div>
              </div>
            </Card>
          )}
        </>
      )}

      {data && data.items.length === 0 && (
        <Card>
          <div className="p-12 text-center">
            <p className="text-gray-500">
              No extraction results found matching your filters
            </p>
          </div>
        </Card>
      )}

      {!data && !loading && !error && (
        <Card>
          <div className="p-12 text-center">
            <p className="text-gray-500">
              Use the search filters above to find extraction results
            </p>
          </div>
        </Card>
      )}
    </div>
  )
}
