/**
 * useACESettings Hook
 * 
 * React hooks for ACE Portal account configuration.
 * Task 3.3 from ROADMAP_FULL_WORKFLOW.md
 */
import { useState, useCallback, useEffect } from 'react'
import axios from 'axios'

const API_URL = 'http://localhost:8000'

// ==================== Types ====================

export interface FilerCode {
    id: string
    filer_code: string
    name: string | null
    client_id: string | null
    port_code: string | null
    bond_type: string | null
    bond_number: string | null
    surety_code: string | null
    is_active: boolean
    is_primary: boolean
    notes: string | null
    created_at: string
    updated_at: string
}

export interface ACESettings {
    id: string | null
    organization_id: string
    primary_filer_code: string | null
    primary_port_code: string | null
    default_bond_type: string | null
    default_bond_surety_code: string | null
    ace_portal_username: string | null
    ace_environment: string
    auto_file_when_ready: boolean
    require_dual_approval: boolean
    notify_on_filing: boolean
    notify_on_acceptance: boolean
    notify_on_rejection: boolean
    notify_on_liquidation: boolean
    notification_email: string | null
    filer_codes: FilerCode[]
    created_at: string | null
    updated_at: string | null
}

export interface ACESettingsCreate {
    organization_id: string
    primary_filer_code?: string
    primary_port_code?: string
    default_bond_type?: string
    default_bond_surety_code?: string
    ace_portal_username?: string
    ace_portal_client_id?: string
    ace_environment?: string
    auto_file_when_ready?: boolean
    require_dual_approval?: boolean
    notify_on_filing?: boolean
    notify_on_acceptance?: boolean
    notify_on_rejection?: boolean
    notify_on_liquidation?: boolean
    notification_email?: string
}

export interface FilerCodeCreate {
    filer_code: string
    name?: string
    client_id?: string
    port_code?: string
    bond_type?: string
    bond_number?: string
    surety_code?: string
    is_primary?: boolean
    notes?: string
}

export interface ValidationResult {
    code: string
    is_valid: boolean
    format: string
    example: string
}

// Bond types
export const BOND_TYPES = {
    continuous: 'Continuous Bond',
    single_transaction: 'Single Transaction Bond',
} as const

// ACE environments
export const ACE_ENVIRONMENTS = {
    test: 'Test/Certification',
    production: 'Production',
} as const

// ==================== Hooks ====================

export function useACESettings(organizationId: string) {
    const [settings, setSettings] = useState<ACESettings | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchSettings = useCallback(async () => {
        if (!organizationId) return

        setLoading(true)
        setError(null)

        try {
            const response = await axios.get<ACESettings>(
                `${API_URL}/api/settings/ace`,
                { params: { organization_id: organizationId } }
            )
            setSettings(response.data)
        } catch (err: any) {
            console.error('Error fetching ACE settings:', err)
            setError(err.response?.data?.detail || 'Failed to load ACE settings')
        } finally {
            setLoading(false)
        }
    }, [organizationId])

    useEffect(() => {
        fetchSettings()
    }, [fetchSettings])

    return {
        settings,
        loading,
        error,
        refetch: fetchSettings,
    }
}

export function useACESettingsActions() {
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const createSettings = useCallback(async (data: ACESettingsCreate): Promise<ACESettings | null> => {
        setLoading(true)
        setError(null)

        try {
            const response = await axios.post<ACESettings>(
                `${API_URL}/api/settings/ace`,
                data
            )
            return response.data
        } catch (err: any) {
            console.error('Error creating ACE settings:', err)
            setError(err.response?.data?.detail || 'Failed to create ACE settings')
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    const updateSettings = useCallback(async (
        organizationId: string,
        data: Partial<ACESettingsCreate>
    ): Promise<ACESettings | null> => {
        setLoading(true)
        setError(null)

        try {
            const response = await axios.put<ACESettings>(
                `${API_URL}/api/settings/ace`,
                data,
                { params: { organization_id: organizationId } }
            )
            return response.data
        } catch (err: any) {
            console.error('Error updating ACE settings:', err)
            setError(err.response?.data?.detail || 'Failed to update ACE settings')
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    const addFilerCode = useCallback(async (
        organizationId: string,
        data: FilerCodeCreate
    ): Promise<FilerCode | null> => {
        setLoading(true)
        setError(null)

        try {
            const response = await axios.post<FilerCode>(
                `${API_URL}/api/settings/ace/filer-codes`,
                data,
                { params: { organization_id: organizationId } }
            )
            return response.data
        } catch (err: any) {
            console.error('Error adding filer code:', err)
            setError(err.response?.data?.detail || 'Failed to add filer code')
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    const updateFilerCode = useCallback(async (
        filerCodeId: string,
        data: Partial<FilerCodeCreate>
    ): Promise<FilerCode | null> => {
        setLoading(true)
        setError(null)

        try {
            const response = await axios.put<FilerCode>(
                `${API_URL}/api/settings/ace/filer-codes/${filerCodeId}`,
                data
            )
            return response.data
        } catch (err: any) {
            console.error('Error updating filer code:', err)
            setError(err.response?.data?.detail || 'Failed to update filer code')
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    const deleteFilerCode = useCallback(async (filerCodeId: string): Promise<boolean> => {
        setLoading(true)
        setError(null)

        try {
            await axios.delete(`${API_URL}/api/settings/ace/filer-codes/${filerCodeId}`)
            return true
        } catch (err: any) {
            console.error('Error deleting filer code:', err)
            setError(err.response?.data?.detail || 'Failed to delete filer code')
            return false
        } finally {
            setLoading(false)
        }
    }, [])

    // Validation helpers
    const validateFilerCode = useCallback(async (code: string): Promise<ValidationResult | null> => {
        try {
            const response = await axios.post<ValidationResult>(
                `${API_URL}/api/settings/ace/validate/filer-code`,
                null,
                { params: { code } }
            )
            return response.data
        } catch {
            return null
        }
    }, [])

    const validatePortCode = useCallback(async (code: string): Promise<ValidationResult | null> => {
        try {
            const response = await axios.post<ValidationResult>(
                `${API_URL}/api/settings/ace/validate/port-code`,
                null,
                { params: { code } }
            )
            return response.data
        } catch {
            return null
        }
    }, [])

    return {
        loading,
        error,
        createSettings,
        updateSettings,
        addFilerCode,
        updateFilerCode,
        deleteFilerCode,
        validateFilerCode,
        validatePortCode,
    }
}

// Validation helper (client-side)
export function isValidFilerCode(code: string): boolean {
    if (!code || code.length !== 3) return false
    return /^[A-Z]{3}$/.test(code.toUpperCase())
}

export function isValidPortCode(code: string): boolean {
    if (!code || code.length !== 4) return false
    return /^\d{4}$/.test(code)
}

export function isValidSuretyCode(code: string): boolean {
    if (!code || code.length !== 3) return false
    return /^\d{3}$/.test(code)
}
