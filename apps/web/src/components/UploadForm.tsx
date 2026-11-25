import { useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Upload, AlertCircle, CheckCircle, ArrowRight } from 'lucide-react'
import { Card } from './Card'
import { Button } from './Button'
import { Input } from './Input'
import { authFetch } from '../lib/authFetch'

const ALLOWED_TYPES = ['.txt', '.docx', '.xlsx', '.pptx', '.html', '.md', '.json', '.csv', '.yml', '.xml', '.pdf']
const MAX_FILE_SIZE_MB = 50

export interface UploadResponse {
  job_id: string
  file_id: string
  filename: string
  file_type: string
  size: number
  storage_path: string
  status: string
  message: string
}

interface UploadFormProps {
  onUploadSuccess?: (fileId: string, jobId: string, meta?: UploadResponse) => void
  /** When true, skip the inline success banner (parent shows next-steps). */
  hideInlineSuccess?: boolean
}

export const UploadForm: React.FC<UploadFormProps> = ({
  onUploadSuccess,
  hideInlineSuccess = false,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<UploadResponse | null>(null)
  const [source, setSource] = useState<string>('')
  const [customerId, setCustomerId] = useState<string>('')
  const [tags, setTags] = useState<string>('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const validateFile = (file: File): { valid: boolean; error?: string } => {
    // Check file type
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!ALLOWED_TYPES.includes(ext)) {
      return {
        valid: false,
        error: `File type ${ext} not supported. Allowed: ${ALLOWED_TYPES.join(', ')}`,
      }
    }

    // Check file size
    const fileSizeMB = file.size / (1024 * 1024)
    if (fileSizeMB > MAX_FILE_SIZE_MB) {
      return {
        valid: false,
        error: `File size ${fileSizeMB.toFixed(2)}MB exceeds limit of ${MAX_FILE_SIZE_MB}MB`,
      }
    }

    return { valid: true }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const validation = validateFile(file)
    if (!validation.valid) {
      setError(validation.error || 'Invalid file')
      setSelectedFile(null)
      return
    }

    setError(null)
    setSelectedFile(file)
  }

  const handleUpload = async () => {
    if (!selectedFile) return

    setLoading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      if (source) formData.append('source', source)
      if (customerId) formData.append('customer_id', customerId)
      if (tags) formData.append('tags', tags)

      // Generate idempotency key for this upload
      const idempotencyKey = `${customerId || 'default'}-${selectedFile.name}-${selectedFile.size}-${Date.now()}`

      const response = await authFetch('/api/upload', {
        method: 'POST',
        body: formData,
        headers: {
          'Idempotency-Key': idempotencyKey,
        },
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Upload failed')
      }

      const data: UploadResponse = await response.json()
      if (!hideInlineSuccess) {
        setSuccess(data)
      }
      setSelectedFile(null)
      setSource('')
      setCustomerId('')
      setTags('')

      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }

      if (onUploadSuccess) {
        onUploadSuccess(data.file_id, data.job_id, data)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <div className="p-6 space-y-4">
        <h2 className="text-lg font-semibold">Upload Document</h2>

        <div className="border-2 border-dashed rounded-lg p-6 text-center hover:bg-gray-50 cursor-pointer transition">
          <input
            ref={fileInputRef}
            type="file"
            onChange={handleFileSelect}
            accept={ALLOWED_TYPES.join(',')}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="flex flex-col items-center gap-2 w-full"
          >
            <Upload className="w-8 h-8 text-gray-400" />
            <span className="text-sm text-gray-600">
              {selectedFile ? selectedFile.name : 'Click to select file or drag and drop'}
            </span>
            <span className="text-xs text-gray-500">
              Max {MAX_FILE_SIZE_MB}MB • Allowed: {ALLOWED_TYPES.join(', ')}
            </span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Input
            type="text"
            placeholder="Channel / Source (e.g., Importer Email, Forwarder EDI) - optional"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            disabled={loading}
          />
          <Input
            type="text"
            placeholder="Shipment / B/L Tags (e.g., MAEU123456789, Priority) - optional"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            disabled={loading}
          />
        </div>

        {error && (
          <div className="flex gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {success && !hideInlineSuccess && (
          <div className="flex gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <div className="min-w-0 flex-1 space-y-2 text-sm text-green-900">
              <p className="font-medium">
                {success.filename || 'Document'} is in the ingest queue
              </p>
              <p className="text-xs text-green-800">
                Extraction starts automatically. Next: watch the pipeline, clear any doc exceptions,
                then open shipment assembly from the Workbench.
              </p>
              <div className="flex flex-wrap gap-2 pt-1">
                <Link
                  to="/dashboard"
                  className="inline-flex items-center gap-1 rounded-md bg-green-700 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-green-800"
                >
                  Open Workbench <ArrowRight className="h-3 w-3" />
                </Link>
                <button
                  type="button"
                  onClick={() => setSuccess(null)}
                  className="text-xs text-green-800 underline-offset-2 hover:underline"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        )}

        <Button
          onClick={handleUpload}
          disabled={!selectedFile || loading}
          className="w-full"
        >
          {loading ? 'Uploading...' : 'Upload'}
        </Button>
      </div>
    </Card>
  )
}
