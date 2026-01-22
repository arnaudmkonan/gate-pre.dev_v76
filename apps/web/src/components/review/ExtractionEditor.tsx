import { useState } from 'react'
import { X, Save } from 'lucide-react'
import { Button } from '../Button'
import { Input } from '../Input'
import { ConfidenceBadge } from './ConfidenceBadge'

interface Extraction {
  id: string
  field_name: string
  field_value: unknown
  raw_value?: string
  normalized_value?: string
  confidence: number
  status: string
  correction_value?: unknown
}

interface ExtractionEditorProps {
  extraction: Extraction
  onSave: (extractionId: string, correctedValue: unknown, notes?: string) => void
  onClose: () => void
  isLoading?: boolean
}

export const ExtractionEditor = ({
  extraction,
  onSave,
  onClose,
  isLoading = false
}: ExtractionEditorProps) => {
  const currentValue = extraction.correction_value ?? extraction.field_value
  const [value, setValue] = useState(
    typeof currentValue === 'object' ? JSON.stringify(currentValue, null, 2) : String(currentValue ?? '')
  )
  const [notes, setNotes] = useState('')
  const [isJson, setIsJson] = useState(typeof currentValue === 'object')

  const handleSave = () => {
    let finalValue: unknown = value
    if (isJson) {
      try {
        finalValue = JSON.parse(value)
      } catch {
        // Keep as string if invalid JSON
      }
    }
    onSave(extraction.id, finalValue, notes || undefined)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="text-lg font-semibold">Edit Extraction</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-6 py-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Field Name
            </label>
            <p className="text-sm text-gray-900 font-mono bg-gray-50 px-3 py-2 rounded">
              {extraction.field_name}
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Original Value
            </label>
            <p className="text-sm text-gray-600 bg-gray-50 px-3 py-2 rounded">
              {extraction.raw_value || String(extraction.field_value)}
            </p>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-gray-700">
                Confidence
              </label>
              <ConfidenceBadge confidence={extraction.confidence} size="sm" />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-gray-700">
                Corrected Value
              </label>
              <label className="flex items-center text-xs text-gray-500">
                <input
                  type="checkbox"
                  checked={isJson}
                  onChange={(e) => setIsJson(e.target.checked)}
                  className="mr-1"
                />
                JSON
              </label>
            </div>
            {isJson ? (
              <textarea
                value={value}
                onChange={(e) => setValue(e.target.value)}
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            ) : (
              <Input
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Notes (optional)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Reason for correction..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t bg-gray-50">
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isLoading}>
            <Save className="w-4 h-4 mr-2" />
            {isLoading ? 'Saving...' : 'Save Correction'}
          </Button>
        </div>
      </div>
    </div>
  )
}
