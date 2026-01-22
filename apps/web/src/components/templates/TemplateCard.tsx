import { FileText, Copy, Trash2, Edit2 } from 'lucide-react'
import { Button } from '../Button'

interface Template {
  id: string
  name: string
  description?: string
  document_type: string
  field_count: number
  usage_count: number
  is_active: boolean
  template_type: string
  avg_confidence?: number
  last_used_at?: string
}

interface TemplateCardProps {
  template: Template
  onEdit: () => void
  onClone: () => void
  onDelete: () => void
}

export const TemplateCard = ({ template, onEdit, onClone, onDelete }: TemplateCardProps) => {
  return (
    <div className={`border rounded-lg p-4 ${template.is_active ? 'border-gray-200' : 'border-gray-200 opacity-60'}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <FileText className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h3 className="font-medium text-gray-900">{template.name}</h3>
            {template.description && (
              <p className="text-sm text-gray-500 mt-1">{template.description}</p>
            )}
          </div>
        </div>
        {!template.is_active && (
          <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
            Inactive
          </span>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <span className="text-xs px-2 py-1 bg-purple-100 text-purple-700 rounded">
          {template.document_type}
        </span>
        <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded">
          {template.field_count} fields
        </span>
        <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded">
          {template.template_type}
        </span>
      </div>

      <div className="mt-4 flex items-center gap-4 text-xs text-gray-500">
        <span>Used {template.usage_count} times</span>
        {template.avg_confidence && (
          <span>Avg confidence: {Math.round(template.avg_confidence * 100)}%</span>
        )}
        {template.last_used_at && (
          <span>Last used: {new Date(template.last_used_at).toLocaleDateString()}</span>
        )}
      </div>

      <div className="mt-4 flex gap-2">
        <Button size="sm" variant="secondary" onClick={onEdit}>
          <Edit2 className="w-3 h-3 mr-1" />
          Edit
        </Button>
        <Button size="sm" variant="secondary" onClick={onClone}>
          <Copy className="w-3 h-3 mr-1" />
          Clone
        </Button>
        <Button size="sm" variant="ghost" onClick={onDelete}>
          <Trash2 className="w-3 h-3 mr-1" />
          Delete
        </Button>
      </div>
    </div>
  )
}
