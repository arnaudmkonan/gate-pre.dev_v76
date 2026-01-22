import { useState, useCallback } from 'react'

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

interface Template {
  id: string
  name: string
  description?: string
  document_type: string
  customer_id?: string
  version: number
  is_active: boolean
  template_type: string
  source_document_id?: string
  field_definitions: FieldDefinition[]
  field_count: number
  visual_regions?: unknown[]
  extraction_prompt?: string
  few_shot_examples?: unknown[]
  matching_keywords?: string[]
  classification_categories?: string[]
  confidence_threshold: number
  usage_count: number
  last_used_at?: string
  avg_confidence?: number
  created_at?: string
  updated_at?: string
}

interface TemplateMatch {
  template_id: string
  template_name: string
  document_type: string
  confidence: number
  match_reasons: string[]
  field_count: number
}

interface UseTemplatesOptions {
  documentType?: string
  customerId?: string
  isActive?: boolean
  templateType?: string
}

export const useTemplates = (options: UseTemplatesOptions = {}) => {
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchTemplates = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (options.documentType) params.append('document_type', options.documentType)
      if (options.customerId) params.append('customer_id', options.customerId)
      if (options.isActive !== undefined) params.append('is_active', String(options.isActive))
      if (options.templateType) params.append('template_type', options.templateType)

      const response = await fetch(`/api/templates?${params.toString()}`)
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to fetch templates')
      }
      const data = await response.json()
      setTemplates(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch templates')
    } finally {
      setLoading(false)
    }
  }, [options.documentType, options.customerId, options.isActive, options.templateType])

  return { templates, loading, error, refetch: fetchTemplates }
}

export const useTemplate = (templateId: string | undefined) => {
  const [template, setTemplate] = useState<Template | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchTemplate = useCallback(async () => {
    if (!templateId) return
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/templates/${templateId}`)
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to fetch template')
      }
      const data = await response.json()
      setTemplate(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch template')
    } finally {
      setLoading(false)
    }
  }, [templateId])

  return { template, loading, error, refetch: fetchTemplate }
}

export const useTemplateActions = () => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const createTemplate = async (data: {
    name: string
    document_type: string
    field_definitions: FieldDefinition[]
    template_type?: string
    description?: string
    customer_id?: string
    extraction_prompt?: string
    few_shot_examples?: unknown[]
    matching_keywords?: string[]
    classification_categories?: string[]
    confidence_threshold?: number
  }) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to create template')
      }
      return await response.json()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create template'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const updateTemplate = async (templateId: string, updates: Partial<Template>) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/templates/${templateId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      })
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to update template')
      }
      return await response.json()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update template'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const deleteTemplate = async (templateId: string) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/templates/${templateId}`, {
        method: 'DELETE'
      })
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to delete template')
      }
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete template'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const cloneTemplate = async (templateId: string, newName: string, customerId?: string) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/templates/${templateId}/clone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_name: newName, customer_id: customerId })
      })
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to clone template')
      }
      return await response.json()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to clone template'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const matchTemplates = async (documentId: string, classification?: string, customerId?: string): Promise<TemplateMatch[]> => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (classification) params.append('classification', classification)
      if (customerId) params.append('customer_id', customerId)

      const response = await fetch(`/api/templates/match/${documentId}?${params.toString()}`)
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to match templates')
      }
      return await response.json()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to match templates'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  return { createTemplate, updateTemplate, deleteTemplate, cloneTemplate, matchTemplates, loading, error }
}
