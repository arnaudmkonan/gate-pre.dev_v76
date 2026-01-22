import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, RefreshCw, Filter, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'
import { TemplateCard } from '../components/templates/TemplateCard'
import { useTemplates, useTemplateActions } from '../hooks/useTemplates'

const DOCUMENT_TYPES = [
  'all', 'invoice', 'contract', 'form', 'receipt', 'report', 'letter', 'other'
]

export const TemplatesPage = () => {
  const navigate = useNavigate()
  const [documentTypeFilter, setDocumentTypeFilter] = useState<string>('')
  const [showInactive, setShowInactive] = useState(false)

  const { templates, loading, error, refetch } = useTemplates({
    documentType: documentTypeFilter || undefined,
    isActive: showInactive ? undefined : true,
  })
  const { deleteTemplate, cloneTemplate, loading: actionLoading } = useTemplateActions()

  useEffect(() => {
    refetch()
  }, [documentTypeFilter, showInactive])

  const handleEdit = (templateId: string) => {
    navigate(`/templates/${templateId}`)
  }

  const handleClone = async (templateId: string, templateName: string) => {
    const newName = prompt('Enter name for cloned template:', `${templateName} (Copy)`)
    if (newName) {
      try {
        const cloned = await cloneTemplate(templateId, newName)
        navigate(`/templates/${cloned.id}`)
      } catch {
        // Error handled in hook
      }
    }
  }

  const handleDelete = async (templateId: string, templateName: string) => {
    if (confirm(`Are you sure you want to delete "${templateName}"?`)) {
      try {
        await deleteTemplate(templateId)
        refetch()
      } catch {
        // Error handled in hook
      }
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Extraction Templates</h1>
        <div className="flex items-center gap-3">
          <Button onClick={refetch} variant="secondary" disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={() => navigate('/templates/new')}>
            <Plus className="w-4 h-4 mr-2" />
            New Template
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4" />
            <CardTitle>Filters</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <div className="flex gap-2">
              {DOCUMENT_TYPES.map((type) => (
                <Button
                  key={type}
                  variant={documentTypeFilter === (type === 'all' ? '' : type) ? 'primary' : 'secondary'}
                  size="sm"
                  onClick={() => setDocumentTypeFilter(type === 'all' ? '' : type)}
                >
                  {type === 'all' ? 'All Types' : type}
                </Button>
              ))}
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(e) => setShowInactive(e.target.checked)}
                className="rounded"
              />
              Show inactive templates
            </label>
          </div>
        </CardContent>
      </Card>

      {/* Error State */}
      {error && (
        <div className="flex gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {/* Templates Grid */}
      <Card>
        <CardHeader>
          <CardTitle>
            Templates ({templates.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : templates.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-500">No templates found</p>
              <p className="text-sm text-gray-400 mt-1">
                Create a template to define extraction fields for your documents
              </p>
              <Button className="mt-4" onClick={() => navigate('/templates/new')}>
                <Plus className="w-4 h-4 mr-2" />
                Create First Template
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {templates.map((template) => (
                <TemplateCard
                  key={template.id}
                  template={template}
                  onEdit={() => handleEdit(template.id)}
                  onClone={() => handleClone(template.id, template.name)}
                  onDelete={() => handleDelete(template.id, template.name)}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
