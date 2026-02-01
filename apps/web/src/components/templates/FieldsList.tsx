import { useState } from 'react'
import { Plus, GripVertical, Edit2, Trash2 } from 'lucide-react'
import { Button } from '../Button'
import { FieldDefinitionForm } from './FieldDefinitionForm'

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

interface FieldsListProps {
  fields: FieldDefinition[]
  onChange: (fields: FieldDefinition[]) => void
}

export const FieldsList = ({ fields, onChange }: FieldsListProps) => {
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)

  const handleAddField = (field: FieldDefinition) => {
    onChange([...fields, field])
    setShowAddForm(false)
  }

  const handleUpdateField = (index: number, field: FieldDefinition) => {
    const newFields = [...fields]
    newFields[index] = field
    onChange(newFields)
    setEditingIndex(null)
  }

  const handleDeleteField = (index: number) => {
    onChange(fields.filter((_, i) => i !== index))
  }

  const moveField = (from: number, to: number) => {
    if (to < 0 || to >= fields.length) return
    const newFields = [...fields]
    const [removed] = newFields.splice(from, 1)
    newFields.splice(to, 0, removed)
    onChange(newFields)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-gray-900">
          Field Definitions ({fields.length})
        </h3>
        <Button size="sm" onClick={() => setShowAddForm(true)}>
          <Plus className="w-4 h-4 mr-1" />
          Add Field
        </Button>
      </div>

      {fields.length === 0 ? (
        <div className="text-center py-8 text-gray-500 border-2 border-dashed rounded-lg">
          <p>No fields defined yet</p>
          <p className="text-sm mt-1">Click "Add Field" to define extraction fields</p>
        </div>
      ) : (
        <div className="space-y-2">
          {fields.map((field, index) => (
            <div key={index}>
              {editingIndex === index ? (
                <div className="border rounded-lg p-4 bg-gray-50">
                  <FieldDefinitionForm
                    field={field}
                    onSave={(updated) => handleUpdateField(index, updated)}
                    onCancel={() => setEditingIndex(null)}
                  />
                </div>
              ) : (
                <div className="flex items-center gap-3 p-3 border rounded-lg bg-white hover:bg-gray-50">
                  <button
                    type="button"
                    className="text-gray-400 cursor-grab"
                    onMouseDown={() => {}}
                  >
                    <GripVertical className="w-4 h-4" />
                  </button>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900">
                        {field.display_name || field.field_name}
                      </span>
                      <code className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">
                        {field.field_name}
                      </code>
                      <span className="text-xs px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded">
                        {field.field_type}
                      </span>
                      {field.required && (
                        <span className="text-xs px-1.5 py-0.5 bg-red-100 text-red-700 rounded">
                          required
                        </span>
                      )}
                    </div>
                    {field.description && (
                      <p className="text-sm text-gray-500 mt-1 truncate">
                        {field.description}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => moveField(index, index - 1)}
                      disabled={index === 0}
                    >
                      ↑
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => moveField(index, index + 1)}
                      disabled={index === fields.length - 1}
                    >
                      ↓
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setEditingIndex(index)}
                    >
                      <Edit2 className="w-3 h-3" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleDeleteField(index)}
                    >
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showAddForm && (
        <div className="border rounded-lg p-4 bg-gray-50">
          <h4 className="font-medium mb-4">Add New Field</h4>
          <FieldDefinitionForm
            onSave={handleAddField}
            onCancel={() => setShowAddForm(false)}
          />
        </div>
      )}
    </div>
  )
}
