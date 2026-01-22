import { useState } from 'react'
import { Edit2, Check, AlertTriangle } from 'lucide-react'
import { ConfidenceBadge } from './ConfidenceBadge'
import { ExtractionEditor } from './ExtractionEditor'

interface Extraction {
  id: string
  field_name: string
  field_value: unknown
  raw_value?: string
  normalized_value?: string
  confidence: number
  status: string
  correction_value?: unknown
  agent_name?: string
  context_snippet?: string
}

interface ExtractionsListProps {
  extractions: Extraction[]
  onCorrect: (extractionId: string, correctedValue: unknown, notes?: string) => void
  isLoading?: boolean
}

export const ExtractionsList = ({
  extractions,
  onCorrect,
  isLoading = false
}: ExtractionsListProps) => {
  const [editingExtraction, setEditingExtraction] = useState<Extraction | null>(null)

  const getStatusIcon = (extraction: Extraction) => {
    if (extraction.correction_value !== undefined && extraction.correction_value !== null) {
      return <Check className="w-4 h-4 text-green-600" />
    }
    if (extraction.confidence < 0.7) {
      return <AlertTriangle className="w-4 h-4 text-yellow-600" />
    }
    return null
  }

  const getDisplayValue = (extraction: Extraction): string => {
    const value = extraction.correction_value ?? extraction.field_value
    if (value === null || value === undefined) return '-'
    if (typeof value === 'object') return JSON.stringify(value)
    return String(value)
  }

  const handleSave = (extractionId: string, correctedValue: unknown, notes?: string) => {
    onCorrect(extractionId, correctedValue, notes)
    setEditingExtraction(null)
  }

  return (
    <div className="space-y-2">
      {extractions.map((extraction) => (
        <div
          key={extraction.id}
          className={`border rounded-lg p-4 ${
            extraction.confidence < 0.7 ? 'border-yellow-300 bg-yellow-50' : 'border-gray-200'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                {getStatusIcon(extraction)}
                <span className="font-medium text-gray-900">{extraction.field_name}</span>
                <ConfidenceBadge confidence={extraction.confidence} size="sm" />
                {extraction.status === 'corrected' && (
                  <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-800 rounded">
                    corrected
                  </span>
                )}
              </div>
              <div className="mt-1 text-sm text-gray-700 truncate">
                {getDisplayValue(extraction)}
              </div>
              {extraction.raw_value && extraction.raw_value !== getDisplayValue(extraction) && (
                <div className="mt-1 text-xs text-gray-500">
                  Original: {extraction.raw_value}
                </div>
              )}
              {extraction.agent_name && (
                <div className="mt-1 text-xs text-gray-400">
                  Extracted by: {extraction.agent_name}
                </div>
              )}
            </div>
            <button
              onClick={() => setEditingExtraction(extraction)}
              className="ml-4 p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
              title="Edit extraction"
            >
              <Edit2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      ))}

      {editingExtraction && (
        <ExtractionEditor
          extraction={editingExtraction}
          onSave={handleSave}
          onClose={() => setEditingExtraction(null)}
          isLoading={isLoading}
        />
      )}
    </div>
  )
}
