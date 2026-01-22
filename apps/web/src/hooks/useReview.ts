import { useState, useCallback } from 'react'

interface ReviewItem {
  id: string
  document_id: string
  filename?: string
  file_type?: string
  priority: number
  status: string
  reason: string
  reason_code?: string
  confidence_score?: number
  assigned_to?: string
  assigned_at?: string
  reviewed_at?: string
  reviewed_by?: string
  review_notes?: string
  corrections_made?: unknown
  created_at: string
  updated_at?: string
  issues_detected?: unknown[]
  agent_results?: Record<string, unknown>
}

interface ReviewItemDetail extends ReviewItem {
  document?: {
    id: string
    filename: string
    file_type: string
    extracted_text_snippet?: string
    size?: number
  }
  extractions?: Extraction[]
  history?: ReviewAction[]
}

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

interface ReviewAction {
  id: string
  action: string
  actor: string
  notes?: string
  created_at: string
}

interface ReviewStats {
  total_pending: number
  total_in_review: number
  total_approved: number
  total_rejected: number
  avg_review_time_seconds?: number
  approval_rate?: number
}

interface UseReviewQueueOptions {
  status?: string
  assignedTo?: string
}

export const useReviewQueue = (options: UseReviewQueueOptions = {}) => {
  const [items, setItems] = useState<ReviewItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchQueue = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (options.status) params.append('status', options.status)
      if (options.assignedTo) params.append('assigned_to', options.assignedTo)

      const response = await fetch(`/api/review/queue?${params.toString()}`)
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to fetch review queue')
      }
      const data = await response.json()
      setItems(data.items || data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch review queue')
    } finally {
      setLoading(false)
    }
  }, [options.status, options.assignedTo])

  return { items, loading, error, refetch: fetchQueue }
}

export const useReviewItem = (itemId: string | undefined) => {
  const [item, setItem] = useState<ReviewItemDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchItem = useCallback(async () => {
    if (!itemId) return
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/review/item/${itemId}`)
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to fetch review item')
      }
      const data = await response.json()
      setItem(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch review item')
    } finally {
      setLoading(false)
    }
  }, [itemId])

  return { item, loading, error, refetch: fetchItem }
}

export const useReviewStats = () => {
  const [stats, setStats] = useState<ReviewStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchStats = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/review/stats')
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to fetch review stats')
      }
      const data = await response.json()
      setStats(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch review stats')
    } finally {
      setLoading(false)
    }
  }, [])

  return { stats, loading, error, refetch: fetchStats }
}

export const useReviewActions = () => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const assign = async (itemId: string, reviewer: string) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/review/item/${itemId}/assign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewer })
      })
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to assign item')
      }
      return await response.json()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to assign item'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const approve = async (itemId: string, reviewer: string, notes?: string) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/review/item/${itemId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewer, notes })
      })
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to approve item')
      }
      return await response.json()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to approve item'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const reject = async (itemId: string, reviewer: string, reason: string) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/review/item/${itemId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewer, reason })
      })
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to reject item')
      }
      return await response.json()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to reject item'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const skip = async (itemId: string) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/review/item/${itemId}/skip`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to skip item')
      }
      return await response.json()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to skip item'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const correct = async (
    itemId: string,
    extractionId: string,
    correctedValue: unknown,
    reviewer: string,
    notes?: string
  ) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/review/item/${itemId}/correct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          extraction_id: extractionId,
          corrected_value: correctedValue,
          reviewer,
          notes
        })
      })
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to correct extraction')
      }
      return await response.json()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to correct extraction'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  return { assign, approve, reject, skip, correct, loading, error }
}
