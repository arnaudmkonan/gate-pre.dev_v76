import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Save, RefreshCw, AlertCircle, Plus, X } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import { FieldsList } from '../components/templates/FieldsList'
import { useTemplate, useTemplateActions } from '../hooks/useTemplates'

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

const DOCUMENT_TYPES = [
  'invoice', 'contract', 'form', 'receipt', 'report', 'letter', 'resume', 'other'
]

export const TemplateEditorPage = () => {
  const { templateId } = useParams<{ templateId: string }>()
  const navigate = useNavigate()
  const isNew = templateId === 'new' || !templateId

  const { template, loading, error, refetch } = useTemplate(isNew ? undefined : templateId)
  const { createTemplate, updateTemplate, loading: actionLoading, error: actionError } = useTemplateActions()

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    document_type: 'invoice',
    template_type: 'field_list',
    field_definitions: [] as FieldDefinition[],
    matching_keywords: [] as string[],
    classification_categories: [] as string[],
    confidence_threshold: 0.7,
    extraction_prompt: '',
  })
  const [keywordInput, setKeywordInput] = useState('')
  const [categoryInput, setCategoryInput] = useState('')

  useEffect(() => {
    if (!isNew && templateId) {
      refetch()
    }
  }, [templateId, isNew])

  useEffect(() => {
    if (template) {
      setFormData({
        name: template.name,
        description: template.description || '',
        document_type: template.document_type,
        template_type: template.template_type,
        field_definitions: template.field_definitions || [],
        matching_keywords: template.matching_keywords || [],
        classification_categories: template.classification_categories || [],
        confidence_threshold: template.confidence_threshold,
        extraction_prompt: template.extraction_prompt || '',
      })
    }
  }, [template])

  const handleChange = (key: string, value: unknown) => {
    setFormData(prev => ({ ...prev, [key]: value }))
  }

  const addKeyword = () => {
    if (keywordInput.trim() && !formData.matching_keywords.includes(keywordInput.trim())) {
      handleChange('matching_keywords', [...formData.matching_keywords, keywordInput.trim()])
      setKeywordInput('')
    }
  }

  const removeKeyword = (keyword: string) => {
    handleChange('matching_keywords', formData.matching_keywords.filter(k => k !== keyword))
  }

  const addCategory = () => {
    if (categoryInput.trim() && !formData.classification_categories.includes(categoryInput.trim())) {
      handleChange('classification_categories', [...formData.classification_categories, categoryInput.trim()])
      setCategoryInput('')
    }
  }

  const removeCategory = (category: string) => {
    handleChange('classification_categories', formData.classification_categories.filter(c => c !== category))
  }

  const handleSave = async () => {
    if (!formData.name || formData.field_definitions.length === 0) {
      alert('Please provide a name and at least one field definition')
      return
    }

    try {
      if (isNew) {
        const created = await createTemplate({
          name: formData.name,
          description: formData.description || undefined,
          document_type: formData.document_type,
          template_type: formData.template_type,
          field_definitions: formData.field_definitions,
          matching_keywords: formData.matching_keywords.length > 0 ? formData.matching_keywords : undefined,
          classification_categories: formData.classification_categories.length > 0 ? formData.classification_categories : undefined,
          confidence_threshold: formData.confidence_threshold,
          extraction_prompt: formData.extraction_prompt || undefined,
        })
        navigate(`/templates/${created.id}`)
      } else {
        await updateTemplate(templateId!, {
          name: formData.name,
          description: formData.description || undefined,
          field_definitions: formData.field_definitions,
          matching_keywords: formData.matching_keywords.length > 0 ? formData.matching_keywords : undefined,
          classification_categories: formData.classification_categories.length > 0 ? formData.classification_categories : undefined,
          confidence_threshold: formData.confidence_threshold,
          extraction_prompt: formData.extraction_prompt || undefined,
        })
        refetch()
      }
    } catch {
      // Error handled in hook
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (!isNew && error) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => navigate('/templates')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Templates
        </Button>
        <div className="flex gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-600">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => navigate('/templates')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <h1 className="text-2xl font-bold">
            {isNew ? 'Create Template' : `Edit: ${template?.name || 'Template'}`}
          </h1>
        </div>
        <Button onClick={handleSave} disabled={actionLoading}>
          <Save className="w-4 h-4 mr-2" />
          {actionLoading ? 'Saving...' : 'Save Template'}
        </Button>
      </div>

      {/* Action Error */}
      {actionError && (
        <div className="flex gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-600">{actionError}</p>
        </div>
      )}

      {/* Basic Info */}
      <Card>
        <CardHeader>
          <CardTitle>Basic Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Template Name *
              </label>
              <Input
                value={formData.name}
                onChange={(e) => handleChange('name', e.target.value)}
                placeholder="e.g., Standard Invoice"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Document Type *
              </label>
              <select
                value={formData.document_type}
                onChange={(e) => handleChange('document_type', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
                disabled={!isNew}
              >
                {DOCUMENT_TYPES.map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => handleChange('description', e.target.value)}
              placeholder="Describe when this template should be used..."
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
          </div>
        </CardContent>
      </Card>

      {/* Field Definitions */}
      <Card>
        <CardHeader>
          <CardTitle>Field Definitions</CardTitle>
        </CardHeader>
        <CardContent>
          <FieldsList
            fields={formData.field_definitions}
            onChange={(fields) => handleChange('field_definitions', fields)}
          />
        </CardContent>
      </Card>

      {/* Matching Criteria */}
      <Card>
        <CardHeader>
          <CardTitle>Template Matching</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Matching Keywords
            </label>
            <p className="text-xs text-gray-500 mb-2">
              Keywords that help identify documents this template should extract
            </p>
            <div className="flex gap-2">
              <Input
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                placeholder="Add keyword..."
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addKeyword())}
              />
              <Button type="button" variant="secondary" onClick={addKeyword}>
                <Plus className="w-4 h-4" />
              </Button>
            </div>
            {formData.matching_keywords.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {formData.matching_keywords.map((keyword) => (
                  <span key={keyword} className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-sm rounded">
                    {keyword}
                    <button type="button" onClick={() => removeKeyword(keyword)} className="text-gray-400 hover:text-gray-600">
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Classification Categories
            </label>
            <p className="text-xs text-gray-500 mb-2">
              Document categories that match this template (from document classifier)
            </p>
            <div className="flex gap-2">
              <Input
                value={categoryInput}
                onChange={(e) => setCategoryInput(e.target.value)}
                placeholder="Add category..."
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addCategory())}
              />
              <Button type="button" variant="secondary" onClick={addCategory}>
                <Plus className="w-4 h-4" />
              </Button>
            </div>
            {formData.classification_categories.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {formData.classification_categories.map((category) => (
                  <span key={category} className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-700 text-sm rounded">
                    {category}
                    <button type="button" onClick={() => removeCategory(category)} className="text-blue-400 hover:text-blue-600">
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Confidence Threshold
            </label>
            <p className="text-xs text-gray-500 mb-2">
              Minimum confidence score to auto-apply this template
            </p>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={formData.confidence_threshold}
              onChange={(e) => handleChange('confidence_threshold', parseFloat(e.target.value))}
              className="w-full"
            />
            <div className="text-sm text-gray-600 mt-1">
              {Math.round(formData.confidence_threshold * 100)}%
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Advanced Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Advanced Settings</CardTitle>
        </CardHeader>
        <CardContent>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Custom Extraction Prompt
            </label>
            <p className="text-xs text-gray-500 mb-2">
              Override the default extraction prompt (leave empty to auto-generate from field definitions)
            </p>
            <textarea
              value={formData.extraction_prompt}
              onChange={(e) => handleChange('extraction_prompt', e.target.value)}
              placeholder="Custom system prompt for extraction..."
              rows={6}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-mono"
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
