import { useState, useRef } from 'react'
import { Upload, AlertCircle, CheckCircle } from 'lucide-react'
import { Card } from './Card'
import { Button } from './Button'
import { Input } from './Input'

const ALLOWED_TYPES = ['.txt', '.docx', '.xlsx', '.pptx', '.html', '.md', '.json', '.csv', '.yml', '.xml']
const MAX_FILE_SIZE_MB = 50

interface UploadFormProps {
  onUploadSuccess?: (fileId: string, jobId: string) => void
}

interface UploadResponse {
  job_id: string
  file_id: string
  filename: string
  file_type: string
  size: number
  storage_path: string
  status: string
  message: string
}

export const UploadForm: React.FC<UploadFormProps> = ({ onUploadSuccess }) => {
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

      const response = await fetch('/api/upload', {
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
      setSuccess(data)
      setSelectedFile(null)
      setSource('')
      setCustomerId('')
      setTags('')

      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }

      if (onUploadSuccess) {
        onUploadSuccess(data.file_id, data.job_id)
      }

      // Reset success message after 5 seconds
      setTimeout(() => setSuccess(null), 5000)
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

        <div className="space-y-3">
          <Input
            type="text"
            placeholder="Source (e.g., crm, email) - optional"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            disabled={loading}
          />
          <Input
            type="text"
            placeholder="Customer ID - optional"
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            disabled={loading}
          />
          <Input
            type="text"
            placeholder="Tags (comma-separated) - optional"
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

        {success && (
          <div className="flex gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-green-600">
              <p className="font-medium">File uploaded successfully</p>
              <p className="text-xs mt-1">Job ID: <code className="bg-green-100 px-2 py-1 rounded">{success.job_id}</code></p>
              <p className="text-xs mt-1">File ID: <code className="bg-green-100 px-2 py-1 rounded">{success.file_id}</code></p>
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
