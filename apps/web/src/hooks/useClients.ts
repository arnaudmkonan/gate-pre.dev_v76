/**
 * Client Management Hook
 * 
 * React hooks for managing importer clients, contacts, and bonds.
 * 
 * Task 4.2 from ROADMAP_FULL_WORKFLOW.md
 */
import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from '../config/api'

// ==================== Types ====================

export interface Client {
    id: string
    name: string
    legal_name?: string
    dba_name?: string
    display_name: string
    client_type: string
    status: string
    identifiers: {
        ior_number?: string
        ein?: string
        duns?: string
        cbp_assigned_number?: string
    }
    address: {
        line_1?: string
        line_2?: string
        city?: string
        state_province?: string
        postal_code?: string
        country?: string
        full?: string
    }
    contact_info: {
        phone?: string
        fax?: string
        email?: string
        website?: string
    }
    customs: {
        primary_port?: string
        common_hts_chapters?: string[]
        common_origin_countries?: string[]
        ace_portal_account?: string
    }
    compliance: {
        c_tpat_member: boolean
        c_tpat_svi_number?: string
        trusted_trader: boolean
        known_importer: boolean
    }
    financial: {
        credit_limit?: number
        payment_terms?: string
        billing_method?: string
    }
    broker_relationship: {
        assigned_broker?: string
        onboarding_date?: string
        first_entry_date?: string
    }
    notes?: string
    internal_code?: string
    preferences?: Record<string, any>
    created_at: string
    updated_at?: string
    contacts?: ClientContact[]
    bonds?: ClientBond[]
    settings?: ClientSettings
}

export interface ClientListItem {
    id: string
    name: string
    display_name: string
    status: string
    client_type: string
    ior_number?: string
    ein?: string
    city?: string
    state_province?: string
    country?: string
    primary_port?: string
    c_tpat_member: boolean
    internal_code?: string
    created_at: string
}

export interface ClientContact {
    id: string
    first_name: string
    last_name: string
    full_name: string
    title?: string
    contact_type: string
    is_primary: boolean
    email?: string
    phone?: string
    mobile?: string
    receives_notifications: boolean
}

export interface ClientBond {
    id: string
    bond_type: string
    bond_number: string
    surety_code: string
    surety_name?: string
    bond_amount?: number
    coverage_start?: string
    coverage_end?: string
    is_active: boolean
    is_expired: boolean
    days_until_expiration?: number
}

export interface ClientSettings {
    default_entry_type?: string
    default_port?: string
    require_approval_before_file: boolean
    auto_calculate_duties: boolean
    notifications: {
        on_entry_file: boolean
        on_cbp_response: boolean
        on_document_ready: boolean
        on_duty_payment: boolean
        emails?: string[]
    }
    preferred_fta?: string
    invoice_delivery_method?: string
}

export interface ClientCreate {
    name: string
    legal_name?: string
    dba_name?: string
    client_type?: string
    ior_number?: string
    ein?: string
    duns?: string
    address_line_1?: string
    address_line_2?: string
    city?: string
    state_province?: string
    postal_code?: string
    country?: string
    phone?: string
    email?: string
    website?: string
    primary_port?: string
    c_tpat_member?: boolean
    notes?: string
    internal_code?: string
}

export interface ClientFilters {
    status?: string
    search?: string
    limit?: number
    offset?: number
}

// ==================== Status Helpers ====================

export const CLIENT_STATUSES = [
    { value: 'active', label: 'Active', bgColor: 'bg-green-100', textColor: 'text-green-700' },
    { value: 'inactive', label: 'Inactive', bgColor: 'bg-gray-100', textColor: 'text-gray-700' },
    { value: 'onboarding', label: 'Onboarding', bgColor: 'bg-blue-100', textColor: 'text-blue-700' },
    { value: 'suspended', label: 'Suspended', bgColor: 'bg-yellow-100', textColor: 'text-yellow-700' },
    { value: 'terminated', label: 'Terminated', bgColor: 'bg-red-100', textColor: 'text-red-700' },
]

export const CLIENT_TYPES = [
    { value: 'corporation', label: 'Corporation' },
    { value: 'llc', label: 'LLC' },
    { value: 'partnership', label: 'Partnership' },
    { value: 'sole_proprietor', label: 'Sole Proprietor' },
    { value: 'government', label: 'Government' },
    { value: 'non_profit', label: 'Non-Profit' },
    { value: 'other', label: 'Other' },
]

export const getStatusInfo = (status: string) => {
    return CLIENT_STATUSES.find(s => s.value === status) || {
        value: status,
        label: status,
        bgColor: 'bg-gray-100',
        textColor: 'text-gray-700',
    }
}

export const getTypeName = (type: string) => {
    return CLIENT_TYPES.find(t => t.value === type)?.label || type
}

export const formatCurrency = (value?: number | null): string => {
    if (value === null || value === undefined) return '-'
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
    }).format(value)
}

// ==================== Main Hook: useClients ====================

export function useClients(filters: ClientFilters = {}) {
    const [clients, setClients] = useState<ClientListItem[]>([])
    const [total, setTotal] = useState(0)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const fetchClients = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const params = new URLSearchParams()
            if (filters.status) params.append('status', filters.status)
            if (filters.search) params.append('search', filters.search)
            if (filters.limit) params.append('limit', filters.limit.toString())
            if (filters.offset) params.append('offset', filters.offset.toString())

            const url = `${API_BASE}/api/clients?${params.toString()}`
            const response = await fetch(url)

            if (!response.ok) {
                throw new Error(`Failed to fetch clients: ${response.statusText}`)
            }

            const data = await response.json()
            setClients(data.clients || [])
            setTotal(data.total || 0)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to fetch clients')
            setClients([])
        } finally {
            setLoading(false)
        }
    }, [filters.status, filters.search, filters.limit, filters.offset])

    useEffect(() => {
        fetchClients()
    }, [fetchClients])

    return { clients, total, loading, error, refetch: fetchClients }
}

// ==================== Hook: useClient (Single) ====================

export function useClient(clientId: string | undefined) {
    const [client, setClient] = useState<Client | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const fetchClient = useCallback(async () => {
        if (!clientId) {
            setClient(null)
            setLoading(false)
            return
        }

        setLoading(true)
        setError(null)
        try {
            const response = await fetch(`${API_BASE}/api/clients/${clientId}`)

            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('Client not found')
                }
                throw new Error(`Failed to fetch client: ${response.statusText}`)
            }

            const data = await response.json()
            setClient(data)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to fetch client')
            setClient(null)
        } finally {
            setLoading(false)
        }
    }, [clientId])

    useEffect(() => {
        fetchClient()
    }, [fetchClient])

    return { client, loading, error, refetch: fetchClient }
}

// ==================== Hook: useClientActions ====================

export function useClientActions() {
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const createClient = async (data: ClientCreate): Promise<{ id: string } | null> => {
        setLoading(true)
        setError(null)
        try {
            const response = await fetch(`${API_BASE}/api/clients`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            })

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}))
                throw new Error(errorData.detail || 'Failed to create client')
            }

            return await response.json()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to create client')
            return null
        } finally {
            setLoading(false)
        }
    }

    const updateClient = async (clientId: string, data: Partial<ClientCreate>): Promise<boolean> => {
        setLoading(true)
        setError(null)
        try {
            const response = await fetch(`${API_BASE}/api/clients/${clientId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            })

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}))
                throw new Error(errorData.detail || 'Failed to update client')
            }

            return true
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to update client')
            return false
        } finally {
            setLoading(false)
        }
    }

    const deleteClient = async (clientId: string): Promise<boolean> => {
        setLoading(true)
        setError(null)
        try {
            const response = await fetch(`${API_BASE}/api/clients/${clientId}`, {
                method: 'DELETE',
            })

            if (!response.ok) {
                throw new Error('Failed to delete client')
            }

            return true
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to delete client')
            return false
        } finally {
            setLoading(false)
        }
    }

    const addContact = async (clientId: string, contact: {
        first_name: string
        last_name: string
        email?: string
        phone?: string
        contact_type?: string
        is_primary?: boolean
    }) => {
        setLoading(true)
        setError(null)
        try {
            const response = await fetch(`${API_BASE}/api/clients/${clientId}/contacts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(contact),
            })

            if (!response.ok) {
                throw new Error('Failed to add contact')
            }

            return await response.json()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to add contact')
            return null
        } finally {
            setLoading(false)
        }
    }

    const addBond = async (clientId: string, bond: {
        bond_type: string
        bond_number: string
        surety_code: string
        surety_name?: string
        bond_amount?: number
        coverage_start?: string
        coverage_end?: string
    }) => {
        setLoading(true)
        setError(null)
        try {
            const response = await fetch(`${API_BASE}/api/clients/${clientId}/bonds`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(bond),
            })

            if (!response.ok) {
                throw new Error('Failed to add bond')
            }

            return await response.json()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to add bond')
            return null
        } finally {
            setLoading(false)
        }
    }

    return {
        loading,
        error,
        createClient,
        updateClient,
        deleteClient,
        addContact,
        addBond,
    }
}
