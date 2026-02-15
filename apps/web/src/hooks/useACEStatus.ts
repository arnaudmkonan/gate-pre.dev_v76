/**
 * useACEStatus Hook
 * 
 * React hooks for ACE status tracking.
 * Task 3.4 from ROADMAP_FULL_WORKFLOW.md
 */
import { useState, useCallback } from 'react'
import axios from 'axios'

import { API_URL } from '../config/api'

// ==================== Types ====================

export interface StatusHistoryItem {
    from_status: string | null
    to_status: string
    changed_by: string | null
    changed_at: string
    reason: string | null
    ace_message: any | null
}

export interface RejectionDetail {
    error_codes: string[]
    error_messages: { code: string; description: string }[]
    rejected_at: string | null
    cbp_message: string
    can_resubmit: boolean
    correction_hints: string[]
}

export interface ACEStatusResponse {
    entry_id: string
    entry_number: string | null
    entry_status: string
    ace_status: string | null
    ace_entry_id: string | null
    filed_at: string | null
    release_date: string | null
    liquidation_date: string | null
    ace_response: any | null
    status_history: StatusHistoryItem[]
    can_resubmit: boolean
    rejection_details: RejectionDetail | null
}

export interface FileEntryResponse {
    entry_id: string
    entry_number: string | null
    ace_entry_id: string
    status: string
    ace_status: string
    filed_at: string
    message: string
    next_steps: string[]
}

export interface SimulateACERequest {
    ace_status: string
    message?: string
    error_codes?: string[]
}

// ACE Status display configs
export const ACE_STATUS_CONFIG: Record<string, { label: string; color: string; bgColor: string; icon: string }> = {
    pending: { label: 'Pending', color: 'text-gray-600', bgColor: 'bg-gray-100', icon: '⏳' },
    submitted: { label: 'Submitted', color: 'text-blue-600', bgColor: 'bg-blue-100', icon: '📤' },
    received: { label: 'Received', color: 'text-blue-700', bgColor: 'bg-blue-100', icon: '📥' },
    accepted: { label: 'Accepted', color: 'text-green-600', bgColor: 'bg-green-100', icon: '✅' },
    rejected: { label: 'Rejected', color: 'text-red-600', bgColor: 'bg-red-100', icon: '❌' },
    under_review: { label: 'Under Review', color: 'text-yellow-600', bgColor: 'bg-yellow-100', icon: '🔍' },
    hold: { label: 'CBP Hold', color: 'text-orange-600', bgColor: 'bg-orange-100', icon: '🔒' },
    intensive_exam: { label: 'Intensive Exam', color: 'text-orange-700', bgColor: 'bg-orange-100', icon: '🔬' },
    released: { label: 'Released', color: 'text-emerald-600', bgColor: 'bg-emerald-100', icon: '🚢' },
    pending_liquidation: { label: 'Pending Liquidation', color: 'text-purple-600', bgColor: 'bg-purple-100', icon: '📊' },
    liquidated: { label: 'Liquidated', color: 'text-purple-700', bgColor: 'bg-purple-100', icon: '✓' },
    suspended: { label: 'Suspended', color: 'text-gray-500', bgColor: 'bg-gray-100', icon: '⏸️' },
}

// Entry status display configs
export const ENTRY_STATUS_CONFIG: Record<string, { label: string; color: string; bgColor: string }> = {
    draft: { label: 'Draft', color: 'text-gray-600', bgColor: 'bg-gray-100' },
    pending_documents: { label: 'Pending Documents', color: 'text-yellow-600', bgColor: 'bg-yellow-100' },
    pending_review: { label: 'Pending Review', color: 'text-yellow-700', bgColor: 'bg-yellow-100' },
    pending_client_approval: { label: 'Pending Client Approval', color: 'text-orange-600', bgColor: 'bg-orange-100' },
    ready_to_file: { label: 'Ready to File', color: 'text-blue-600', bgColor: 'bg-blue-100' },
    filing: { label: 'Filing', color: 'text-blue-700', bgColor: 'bg-blue-100' },
    filed: { label: 'Filed', color: 'text-indigo-600', bgColor: 'bg-indigo-100' },
    accepted: { label: 'Accepted', color: 'text-green-600', bgColor: 'bg-green-100' },
    rejected: { label: 'Rejected', color: 'text-red-600', bgColor: 'bg-red-100' },
    hold: { label: 'CBP Hold', color: 'text-orange-600', bgColor: 'bg-orange-100' },
    released: { label: 'Released', color: 'text-emerald-600', bgColor: 'bg-emerald-100' },
    liquidated: { label: 'Liquidated', color: 'text-purple-600', bgColor: 'bg-purple-100' },
    cancelled: { label: 'Cancelled', color: 'text-gray-500', bgColor: 'bg-gray-100' },
}

// ==================== Hooks ====================

export function useACEStatus(entryId: string) {
    const [status, setStatus] = useState<ACEStatusResponse | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchStatus = useCallback(async () => {
        if (!entryId) return

        setLoading(true)
        setError(null)

        try {
            const response = await axios.get<ACEStatusResponse>(
                `${API_URL}/api/entries/${entryId}/ace-status`
            )
            setStatus(response.data)
        } catch (err: any) {
            console.error('Error fetching ACE status:', err)
            setError(err.response?.data?.detail || 'Failed to fetch ACE status')
        } finally {
            setLoading(false)
        }
    }, [entryId])

    return {
        status,
        loading,
        error,
        refetch: fetchStatus,
    }
}

export function useACEStatusActions() {
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fileEntry = useCallback(async (entryId: string): Promise<FileEntryResponse | null> => {
        setLoading(true)
        setError(null)

        try {
            const response = await axios.post<FileEntryResponse>(
                `${API_URL}/api/entries/${entryId}/file`
            )
            return response.data
        } catch (err: any) {
            console.error('Error filing entry:', err)
            setError(err.response?.data?.detail || 'Failed to file entry')
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    const pollStatus = useCallback(async (entryId: string): Promise<any> => {
        setLoading(true)
        setError(null)

        try {
            const response = await axios.post(`${API_URL}/api/entries/${entryId}/poll-ace`)
            return response.data
        } catch (err: any) {
            console.error('Error polling ACE:', err)
            setError(err.response?.data?.detail || 'Failed to poll ACE')
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    const resubmitEntry = useCallback(async (
        entryId: string,
        corrections?: Record<string, any>
    ): Promise<any> => {
        setLoading(true)
        setError(null)

        try {
            const response = await axios.post(
                `${API_URL}/api/entries/${entryId}/resubmit`,
                corrections ? { corrections } : {}
            )
            return response.data
        } catch (err: any) {
            console.error('Error resubmitting entry:', err)
            setError(err.response?.data?.detail || 'Failed to resubmit entry')
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    const simulateACEResponse = useCallback(async (
        entryId: string,
        request: SimulateACERequest
    ): Promise<any> => {
        setLoading(true)
        setError(null)

        try {
            const response = await axios.post(
                `${API_URL}/api/entries/${entryId}/simulate-ace-response`,
                request
            )
            return response.data
        } catch (err: any) {
            console.error('Error simulating ACE response:', err)
            setError(err.response?.data?.detail || 'Failed to simulate ACE response')
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    return {
        loading,
        error,
        fileEntry,
        pollStatus,
        resubmitEntry,
        simulateACEResponse,
    }
}

// ==================== Utility Functions ====================

export function getACEStatusConfig(status: string | null) {
    if (!status) return { label: 'Unknown', color: 'text-gray-500', bgColor: 'bg-gray-100', icon: '?' }
    return ACE_STATUS_CONFIG[status] || { label: status, color: 'text-gray-600', bgColor: 'bg-gray-100', icon: '?' }
}

export function getEntryStatusConfig(status: string) {
    return ENTRY_STATUS_CONFIG[status] || { label: status, color: 'text-gray-600', bgColor: 'bg-gray-100' }
}

export function formatRelativeTime(dateString: string): string {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / (1000 * 60))
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
}
