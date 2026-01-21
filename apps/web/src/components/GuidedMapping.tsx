import { useState } from 'react'
import { Card } from './Card'
import { Button } from './Button'
import { AlertCircle, CheckCircle } from 'lucide-react'

interface GuidedMappingProps {
  jobId: string
  onMappingApply?: (mapping: Record<string, string>) => void
  onClose?: () => void
}

export const GuidedMapping: React.FC<GuidedMappingProps> = ({ jobId, onMappingApply, onClose }) => {
  const [documentType, setDocumentType] = useState<string>('')
  const [date, setDate] = useState<string>('')
  const [reference, setReference] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [validationWarnings, setValidationWarnings] = useState<string[]>([])

  const documentTypes = [
    'Invoice',
    'Receipt',
    'Contract',
    'Report',
    'Letter',
    'Certificate',
    'Other',
  ]

  const handlePreview = async () => {
    setLoading(true)
    setError(null)
    setValidationWarnings([])

    try {
      const response = await fetch(`/api/ingest/jobs/${jobId}/mapping-preview`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          mapping_config: {
            document_type: documentType,
            date,
            reference,
          },
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to preview mapping')
      }

      const data = await response.json()
      if (data.warnings) {
        setValidationWarnings(data.warnings)
      }
      if (!data.is_valid) {
        setError(data.errors?.join(', ') || 'Mapping validation failed')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to preview mapping')
    } finally {
      setLoading(false)
    }
  }

  const handleApply = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/ingest/jobs/${jobId}/mode`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          mode: 'guided_mapping',
          mapping_config: {
            document_type: documentType,
            date,
            reference,
          },
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to apply mapping')
      }

      setSuccess(true)
      if (onMappingApply) {
        onMappingApply({
          document_type: documentType,
          date,
          reference,
        })
      }

      // Auto-close after 2 seconds
      setTimeout(() => {
        if (onClose) onClose()
      }, 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to apply mapping')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <div className="p-6 space-y-4">
        <h2 className="text-lg font-semibold">Guided Field Mapping</h2>
        <p className="text-sm text-gray-600">
          Define custom mappings for document metadata extraction
        </p>

        {error && (
          <div className="flex gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {validationWarnings.length > 0 && (
          <div className="flex gap-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-yellow-800">
              <p className="font-medium mb-1">Validation Warnings:</p>
              <ul className="text-xs space-y-1">
                {validationWarnings.map((warning, i) => (
                  <li key={i}>• {warning}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {success && (
          <div className="flex gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-green-600">Mapping applied successfully!</p>
          </div>
        )}

        {!success ? (
          <div className="space-y-4">
            {/* Document Type */}
            <div>
              <label className="text-sm font-medium block mb-2">Document Type</label>
              <select
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value)}
                disabled={loading}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select a type...</option>
                {documentTypes.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>

            {/* Date Field */}
            <div>
              <label className="text-sm font-medium block mb-2">Date (YYYY-MM-DD)</label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                disabled={loading}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Reference Field */}
            <div>
              <label className="text-sm font-medium block mb-2">Reference ID</label>
              <input
                type="text"
                value={reference}
                onChange={(e) => setReference(e.target.value)}
                placeholder="e.g., Invoice-001"
                disabled={loading}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Actions */}
            <div className="flex gap-2 pt-2">
              <Button
                onClick={handlePreview}
                variant="ghost"
                disabled={loading}
                isLoading={loading}
                className="flex-1"
              >
                Preview
              </Button>
              <Button
                onClick={handleApply}
                disabled={loading || !documentType}
                isLoading={loading}
                className="flex-1"
              >
                Apply Mapping
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </Card>
  )
}
