import { useState, useEffect } from 'react'
import { Search, Loader, AlertCircle } from 'lucide-react'
import { AdminLayout } from '../components/AdminLayout'
import { Card } from '../components/Card'
import { Input } from '../components/Input'
import { Button } from '../components/Button'

interface Metadata {
  id: string
  job_id: string
  filename: string
  file_type: string
  size: number
  uploader?: string
  ingestion_status: string
  extracted_text_snippet?: string
  detected_language?: string
  vector_store_id?: string
  raw_storage_path?: string
  extraction_timestamp?: string
  extractor_agent_version?: string
  page_count?: number
  mime_type?: string
  title?: string
  author?: string
  subject?: string
  keywords?: string[]
  customer_id?: string
  source?: string
  tags?: string[]
  created_at: string
  updated_at: string
}

interface MetadataResponse {
  total: number
  page: number
  page_size: number
  items: Metadata[]
}

const STATUS_COLORS: { [key: string]: string } = {
  pending: 'bg-yellow-100 text-yellow-800',
  extracting: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
}

export const MetadataPage = () => {
  const [jobId, setJobId] = useState<string>('')
  const [customerId, setCustomerId] = useState<string>('')
  const [fileType, setFileType] = useState<string>('')
  const [status, setStatus] = useState<string>('')
  const [page, setPage] = useState(1)
  const pageSize = 20

  const [data, setData] = useState<MetadataResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [noDataYet, setNoDataYet] = useState(false)

  const fetchMetadata = async () => {
    setLoading(true)
    setError(null)
    setNoDataYet(false)

    try {
      const params = new URLSearchParams()
      if (jobId) params.append('job_id', jobId)
      if (customerId) params.append('customer_id', customerId)
      if (fileType) params.append('file_type', fileType)
      if (status) params.append('ingestion_status', status)
      params.append('page', page.toString())
      params.append('page_size', pageSize.toString())

      const response = await fetch(`/api/metadata?${params.toString()}`)

      if (response.status === 204) {
        setNoDataYet(true)
        setData(null)
        return
      }

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to fetch metadata')
      }

      const result: MetadataResponse = await response.json()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch metadata')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchMetadata()
  }, [page, pageSize])

  const handleSearch = () => {
    setPage(1)
    fetchMetadata()
  }

  const handleReset = () => {
    setJobId('')
    setCustomerId('')
    setFileType('')
    setStatus('')
    setPage(1)
    fetchMetadata()
  }

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">Metadata Search</h1>
        </div>

        {/* Search Filters */}
        <Card>
          <div className="p-6 space-y-4">
            <h2 className="text-lg font-semibold">Search Filters</h2>

            <div className="grid grid-cols-2 gap-4">
              <Input
                type="text"
                placeholder="Job ID"
                value={jobId}
                onChange={(e) => setJobId(e.target.value)}
                disabled={loading}
              />
              <Input
                type="text"
                placeholder="Customer ID"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                disabled={loading}
              />
              <Input
                type="text"
                placeholder="File Type (txt, pdf, docx, etc.)"
                value={fileType}
                onChange={(e) => setFileType(e.target.value)}
                disabled={loading}
              />
              <Input
                type="text"
                placeholder="Status (pending, extracting, completed, failed)"
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

        {noDataYet && (
          <div className="flex gap-2 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-yellow-600">
              <p className="font-medium">Metadata Not Available Yet</p>
              <p className="text-xs mt-1">The extraction is still in progress. Please check back in a few moments.</p>
            </div>
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

                <div className="space-y-4">
                  {data.items.map((item) => (
                    <div key={item.id} className="border rounded-lg p-4 space-y-3">
                      <div className="flex items-start justify-between">
                        <div>
                          <h3 className="font-semibold">{item.filename}</h3>
                          <p className="text-sm text-gray-600">
                            {item.file_type.toUpperCase()} • {(item.size / 1024).toFixed(2)} KB
                          </p>
                        </div>
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-medium ${
                            STATUS_COLORS[item.ingestion_status] || 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {item.ingestion_status}
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="font-medium text-gray-700">Job ID:</span>
                          <code className="block bg-gray-100 p-2 rounded mt-1 text-xs">{item.job_id}</code>
                        </div>
                        {item.customer_id && (
                          <div>
                            <span className="font-medium text-gray-700">Customer ID:</span>
                            <p className="text-gray-600">{item.customer_id}</p>
                          </div>
                        )}
                      </div>

                      {item.extracted_text_snippet && (
                        <div>
                          <span className="font-medium text-gray-700 text-sm">Preview:</span>
                          <p className="text-gray-600 text-sm mt-1">
                            {item.extracted_text_snippet.substring(0, 200)}
                            {item.extracted_text_snippet.length > 200 ? '...' : ''}
                          </p>
                        </div>
                      )}

                      <div className="grid grid-cols-3 gap-4 text-xs">
                        {item.detected_language && (
                          <div>
                            <span className="font-medium text-gray-700">Language:</span>
                            <p className="text-gray-600">{item.detected_language}</p>
                          </div>
                        )}
                        {item.page_count && (
                          <div>
                            <span className="font-medium text-gray-700">Pages:</span>
                            <p className="text-gray-600">{item.page_count}</p>
                          </div>
                        )}
                        {item.extraction_timestamp && (
                          <div>
                            <span className="font-medium text-gray-700">Extracted:</span>
                            <p className="text-gray-600">
                              {new Date(item.extraction_timestamp).toLocaleDateString()}
                            </p>
                          </div>
                        )}
                      </div>
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

        {data && data.items.length === 0 && !noDataYet && (
          <Card>
            <div className="p-12 text-center">
              <p className="text-gray-500">No metadata found matching your filters</p>
            </div>
          </Card>
        )}
      </div>
    </AdminLayout>
  )
}
