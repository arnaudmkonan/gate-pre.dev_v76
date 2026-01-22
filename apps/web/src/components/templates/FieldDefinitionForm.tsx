import { useState } from 'react'
import { X, Plus } from 'lucide-react'
import { Button } from '../Button'
import { Input } from '../Input'

interface FieldDefinition {
  field_name: string
  display_name?: string
  field_type: string
  description?: string
  required: boolean
  validation_regex?: string
  extraction_hints?: string[]
  default_value?: string
  entity_type?: string
}

interface FieldDefinitionFormProps {
  field?: FieldDefinition
  onSave: (field: FieldDefinition) => void
  onCancel: () => void
}

const FIELD_TYPES = [
  { value: 'string', label: 'Text' },
  { value: 'number', label: 'Number' },
  { value: 'date', label: 'Date' },
  { value: 'money', label: 'Money/Currency' },
  { value: 'entity', label: 'Entity' },
  { value: 'boolean', label: 'Yes/No' },
]

const ENTITY_TYPES = [
  'person', 'organization', 'location', 'date', 'money',
  'email', 'phone', 'url', 'product', 'document_id'
]

export const FieldDefinitionForm = ({ field, onSave, onCancel }: FieldDefinitionFormProps) => {
  const [formData, setFormData] = useState<FieldDefinition>(field || {
    field_name: '',
    display_name: '',
    field_type: 'string',
    description: '',
    required: false,
    extraction_hints: [],
  })
  const [hintInput, setHintInput] = useState('')

  const handleChange = (key: keyof FieldDefinition, value: unknown) => {
    setFormData(prev => ({ ...prev, [key]: value }))
  }

  const addHint = () => {
    if (hintInput.trim()) {
      handleChange('extraction_hints', [...(formData.extraction_hints || []), hintInput.trim()])
      setHintInput('')
    }
  }

  const removeHint = (index: number) => {
    handleChange('extraction_hints', (formData.extraction_hints || []).filter((_, i) => i !== index))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.field_name) return
    onSave(formData)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Field Name *
          </label>
          <Input
            value={formData.field_name}
            onChange={(e) => handleChange('field_name', e.target.value.toLowerCase().replace(/\s+/g, '_'))}
            placeholder="e.g., invoice_number"
            required
          />
          <p className="text-xs text-gray-500 mt-1">Lowercase, no spaces</p>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Display Name
          </label>
          <Input
            value={formData.display_name || ''}
            onChange={(e) => handleChange('display_name', e.target.value)}
            placeholder="e.g., Invoice Number"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Field Type
          </label>
          <select
            value={formData.field_type}
            onChange={(e) => handleChange('field_type', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            {FIELD_TYPES.map(type => (
              <option key={type.value} value={type.value}>{type.label}</option>
            ))}
          </select>
        </div>
        {formData.field_type === 'entity' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Entity Type
            </label>
            <select
              value={formData.entity_type || ''}
              onChange={(e) => handleChange('entity_type', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="">Select type...</option>
              {ENTITY_TYPES.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Description
        </label>
        <textarea
          value={formData.description || ''}
          onChange={(e) => handleChange('description', e.target.value)}
          placeholder="Describe what this field contains and how to identify it"
          rows={2}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Extraction Hints
        </label>
        <div className="flex gap-2">
          <Input
            value={hintInput}
            onChange={(e) => setHintInput(e.target.value)}
            placeholder="Add a hint..."
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addHint())}
          />
          <Button type="button" variant="secondary" onClick={addHint}>
            <Plus className="w-4 h-4" />
          </Button>
        </div>
        {formData.extraction_hints && formData.extraction_hints.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {formData.extraction_hints.map((hint, index) => (
              <span key={index} className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-sm rounded">
                {hint}
                <button type="button" onClick={() => removeHint(index)} className="text-gray-400 hover:text-gray-600">
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={formData.required}
            onChange={(e) => handleChange('required', e.target.checked)}
            className="rounded"
          />
          <span className="text-sm text-gray-700">Required field</span>
        </label>
      </div>

      <div className="flex justify-end gap-3 pt-4 border-t">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={!formData.field_name}>
          {field ? 'Update Field' : 'Add Field'}
        </Button>
      </div>
    </form>
  )
}
