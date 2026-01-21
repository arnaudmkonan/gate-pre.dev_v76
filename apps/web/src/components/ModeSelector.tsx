import { useState } from 'react'
import { Card } from './Card'
import { Button } from './Button'
import { AlertCircle, CheckCircle } from 'lucide-react'

interface ModeSelectorProps {
  jobId: string
  onModeSelect?: (mode: string) => void
  onSuccess?: () => void
}

const MODES = [
  {
    id: 'quick_auto',
    name: 'Quick Auto',
    description: 'Automatic extraction with default settings',
    recommended: true,
    useCases: 'Best for simple documents with standard structure',
  },
  {
    id: 'guided_mapping',
    name: 'Guided Mapping',
    description: 'Define custom field mappings interactively',
    recommended: false,
    useCases: 'Best for documents with custom or complex structure',
  },
  {
    id: 'advanced_batch',
    name: 'Advanced Batch',
    description: 'Schedule batch processing with custom settings',
    recommended: false,
    useCases: 'Best for processing large volumes with fine-grained control',
  },
]

export const ModeSelector: React.FC<ModeSelectorProps> = ({ jobId, onModeSelect, onSuccess }) => {
  const [selectedMode, setSelectedMode] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleSelect = async (modeId: string) => {
    setSelectedMode(modeId)
    setError(null)
    setSuccess(false)
  }

  const handleConfirm = async () => {
    if (!selectedMode) {
      setError('Please select a mode')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/ingest/jobs/${jobId}/mode`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          mode: selectedMode,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to select mode')
      }

      setSuccess(true)
      if (onModeSelect) {
        onModeSelect(selectedMode)
      }

      // Auto-close after 2 seconds
      setTimeout(() => {
        if (onSuccess) {
          onSuccess()
        }
      }, 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to select mode')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <div className="p-6 space-y-4">
        <h2 className="text-lg font-semibold">Select Ingestion Mode</h2>
        <p className="text-sm text-gray-600">
          Choose how you want to process this document
        </p>

        {error && (
          <div className="flex gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {success && (
          <div className="flex gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-green-600">Mode selected successfully!</p>
          </div>
        )}

        {!success ? (
          <div className="space-y-3">
            {MODES.map((mode) => (
              <label
                key={mode.id}
                className={`p-4 border-2 rounded-lg cursor-pointer transition ${
                  selectedMode === mode.id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300 bg-white'
                }`}
              >
                <div className="flex items-start gap-3">
                  <input
                    type="radio"
                    name="mode"
                    value={mode.id}
                    checked={selectedMode === mode.id}
                    onChange={() => handleSelect(mode.id)}
                    className="mt-1"
                    disabled={loading}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold text-sm">{mode.name}</h3>
                      {mode.recommended && (
                        <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded">
                          Recommended
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600 mb-1">{mode.description}</p>
                    <p className="text-xs text-gray-500">{mode.useCases}</p>
                  </div>
                </div>
              </label>
            ))}

            <Button
              onClick={handleConfirm}
              disabled={!selectedMode || loading}
              isLoading={loading}
              className="w-full mt-4"
            >
              {loading ? 'Saving Mode...' : 'Confirm Mode Selection'}
            </Button>
          </div>
        ) : null}
      </div>
    </Card>
  )
}
