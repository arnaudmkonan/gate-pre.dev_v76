/**
 * useEntries Hook
 * 
 * React hooks for managing customs entries data.
 * Task 1.3 from ROADMAP_FULL_WORKFLOW.md
 */
import { useState, useCallback, useEffect } from 'react'
import axios from 'axios'

const API_URL = 'http://localhost:8000'

// ==================== Types ====================

export interface EntryLine {
    id: string
    line_number: number
    hts_code: string | null
    hts_description: string | null
    product_description: string | null
    country_of_origin: string | null
    manufacturer_name: string | null
    quantity_1: number | null
    uom_1: string | null
    entered_value: number
    duty_rate: number | null
    duty_amount: number
    total_line_duty: number
    fta_code: string | null
    fta_eligible: boolean
}

export interface EntryParty {
    id: string
    role: string
    name: string
    address_line_1: string | null
    city: string | null
    state_province: string | null
    postal_code: string | null
    country: string | null
    cbp_number: string | null
}

export interface EntryDocument {
    id: string
    document_id: string
    document_type: string | null
    is_primary: boolean
    added_by: string | null
}

export interface EntryStatusHistory {
    from_status: string | null
    to_status: string
    changed_by: string | null
    changed_at: string
    reason: string | null
}

export interface Entry {
    id: string
    entry_number: string | null
    entry_type: string
    filer_code: string | null
    status: string
    entry_date: string | null
    import_date: string | null
    release_date: string | null
    port_of_entry: string | null
    port_of_unlading: string | null
    mode_of_transport: string | null
    carrier_code: string | null
    vessel_name: string | null
    voyage_flight_number: string | null
    bill_of_lading: string | null
    master_bill: string | null
    house_bill: string | null
    container_numbers: string[]
    importer_of_record_number: string | null
    importer_of_record_name: string | null
    ultimate_consignee_name: string | null
    bond_type: string | null
    bond_number: string | null
    surety_code: string | null
    total_entered_value: number
    total_dutiable_value: number
    total_duty: number
    mpf_amount: number
    hmf_amount: number
    section_301_amount: number
    section_232_amount: number
    add_amount: number
    cvd_amount: number
    total_amount_due: number
    currency: string
    line_count: number
    lines: EntryLine[]
    parties: EntryParty[]
    documents: EntryDocument[]
    status_history: EntryStatusHistory[]
    assigned_to: string | null
    internal_reference: string | null
    notes: string | null
    is_ftz: boolean
    has_add_cvd: boolean
    is_reconciliation_flagged: boolean
    requires_license: boolean
    created_at: string
    updated_at: string
}

export interface EntryListItem {
    id: string
    entry_number: string | null
    entry_type: string
    status: string
    port_of_entry: string | null
    importer_name: string | null
    entry_date: string | null
    total_entered_value: number
    total_duty: number
    total_amount_due: number
    line_count: number
    bill_of_lading: string | null
    assigned_to: string | null
    created_at: string
    updated_at: string
}

export interface EntryListResponse {
    count: number
    total: number
    offset: number
    limit: number
    entries: EntryListItem[]
}

export interface EntryFilters {
    status?: string
    client_id?: string
    port?: string
    search?: string
    date_from?: string
    date_to?: string
}

export interface CreateEntryRequest {
    entry_type?: string
    port_of_entry?: string
    entry_date?: string
    importer_of_record_number?: string
    importer_of_record_name?: string
    bill_of_lading?: string
    mode_of_transport?: string
    client_id?: string
    internal_reference?: string
    notes?: string
    // For wizard - include line items with entry creation
    line_items?: {
        line_number: number
        hts_code?: string
        hts_description?: string
        quantity?: number
        unit_of_measure?: string
        unit_value?: number
        entered_value?: number
        country_of_origin?: string
        gross_weight?: number
        net_weight?: number
    }[]
}

export interface AddLineRequest {
    line_number: number
    hts_code?: string
    product_description?: string
    country_of_origin?: string
    manufacturer_name?: string
    quantity_1?: number
    uom_1?: string
    entered_value?: number
    fta_code?: string
}

// ==================== Hooks ====================

export function useEntries(filters?: EntryFilters) {
    const [entries, setEntries] = useState<EntryListItem[]>([])
    const [total, setTotal] = useState(0)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchEntries = useCallback(async (offset = 0, limit = 50) => {
        setLoading(true)
        setError(null)

        try {
            const params = new URLSearchParams()
            if (filters?.status) params.set('status', filters.status)
            if (filters?.client_id) params.set('client_id', filters.client_id)
            if (filters?.port) params.set('port', filters.port)
            if (filters?.search) params.set('search', filters.search)
            if (filters?.date_from) params.set('date_from', filters.date_from)
            if (filters?.date_to) params.set('date_to', filters.date_to)
            params.set('offset', String(offset))
            params.set('limit', String(limit))

            const response = await axios.get<EntryListResponse>(
                `${API_URL}/api/entries?${params.toString()}`
            )
            setEntries(response.data.entries)
            setTotal(response.data.total)
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message)
        } finally {
            setLoading(false)
        }
    }, [filters])

    useEffect(() => {
        fetchEntries()
    }, [fetchEntries])

    return { entries, total, loading, error, refetch: fetchEntries }
}

export function useEntry(entryId?: string) {
    const [entry, setEntry] = useState<Entry | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchEntry = useCallback(async () => {
        if (!entryId) return

        setLoading(true)
        setError(null)

        try {
            const response = await axios.get<Entry>(`${API_URL}/api/entries/${entryId}`)
            setEntry(response.data)
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message)
        } finally {
            setLoading(false)
        }
    }, [entryId])

    useEffect(() => {
        fetchEntry()
    }, [fetchEntry])

    return { entry, loading, error, refetch: fetchEntry }
}

export function useEntryActions() {
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const createEntry = useCallback(async (data: CreateEntryRequest): Promise<Entry | null> => {
        setLoading(true)
        setError(null)

        try {
            const response = await axios.post(`${API_URL}/api/entries`, data)
            return response.data
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message)
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    const updateEntry = useCallback(async (entryId: string, data: Partial<Entry>): Promise<boolean> => {
        setLoading(true)
        setError(null)

        try {
            await axios.put(`${API_URL}/api/entries/${entryId}`, data)
            return true
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message)
            return false
        } finally {
            setLoading(false)
        }
    }, [])

    const deleteEntry = useCallback(async (entryId: string): Promise<boolean> => {
        setLoading(true)
        setError(null)

        try {
            await axios.delete(`${API_URL}/api/entries/${entryId}`)
            return true
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message)
            return false
        } finally {
            setLoading(false)
        }
    }, [])

    const addLine = useCallback(async (entryId: string, data: AddLineRequest): Promise<any> => {
        setLoading(true)
        setError(null)

        try {
            const response = await axios.post(`${API_URL}/api/entries/${entryId}/lines`, data)
            return response.data
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message)
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    const calculateDuties = useCallback(async (entryId: string): Promise<any> => {
        setLoading(true)
        setError(null)

        try {
            const response = await axios.post(`${API_URL}/api/entries/${entryId}/calculate`)
            return response.data
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message)
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    const validateEntry = useCallback(async (entryId: string): Promise<any> => {
        setLoading(true)
        setError(null)

        try {
            const response = await axios.post(`${API_URL}/api/entries/${entryId}/validate`)
            return response.data
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message)
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    return {
        loading,
        error,
        createEntry,
        updateEntry,
        deleteEntry,
        addLine,
        calculateDuties,
        validateEntry,
    }
}

export function useDutyCalculator() {
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const calculateDuty = useCallback(async (
        hts_code: string,
        value: number,
        quantity: number = 1,
        country_of_origin: string = '',
        fta_code?: string
    ) => {
        setLoading(true)
        setError(null)

        try {
            const response = await axios.post(`${API_URL}/api/tools/duty-calculator/calculate`, {
                hts_code,
                value,
                quantity,
                country_of_origin,
                fta_code,
            })
            return response.data
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message)
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    const calculateFees = useCallback(async (
        total_value: number,
        line_count: number = 1,
        entry_type: string = 'formal'
    ) => {
        setLoading(true)
        setError(null)

        try {
            const response = await axios.post(`${API_URL}/api/tools/duty-calculator/calculate-fees`, {
                total_value,
                line_count,
                entry_type,
            })
            return response.data
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message)
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    return { loading, error, calculateDuty, calculateFees }
}

// ==================== Document Linking ====================

export interface LinkedDocument {
    id: string
    document_type: string | null
    is_primary: boolean
    added_by: string | null
    added_at: string | null
    filename: string | null
    storage_path: string | null
}

export interface ExtractionSuggestion {
    field_name: string
    current_value: string | null
    suggested_value: string
    confidence: number
    source_document_id: string
    source_document_type: string | null
}

export interface ExtractionConflict {
    field_name: string
    current_value: string | null
    conflicting_values: Array<{
        value: string
        confidence: number
        source_document_id: string
        source_document_type: string | null
    }>
}

export function useDocumentLinking(entryId?: string) {
    const [documents, setDocuments] = useState<LinkedDocument[]>([])
    const [suggestions, setSuggestions] = useState<ExtractionSuggestion[]>([])
    const [conflicts, setConflicts] = useState<ExtractionConflict[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchDocuments = useCallback(async () => {
        if (!entryId) return

        setLoading(true)
        setError(null)

        try {
            const response = await axios.get(`${API_URL}/api/entries/${entryId}/documents`)
            setDocuments(response.data.documents || [])
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message)
        } finally {
            setLoading(false)
        }
    }, [entryId])

    const fetchSuggestions = useCallback(async () => {
        if (!entryId) return

        try {
            const response = await axios.get(`${API_URL}/api/entries/${entryId}/extraction-suggestions`)
            setSuggestions(response.data.suggestions || [])
            setConflicts(response.data.conflicts || [])
        } catch (err: any) {
            // Non-critical, don't set error
            console.error('Failed to fetch suggestions:', err)
        }
    }, [entryId])

    useEffect(() => {
        fetchDocuments()
    }, [fetchDocuments])

    const linkDocuments = useCallback(async (
        documentIds: string[],
        autoPopulate: boolean = true
    ): Promise<{
        linked_count: number
        fields_updated: string[]
        suggestions: ExtractionSuggestion[]
    } | null> => {
        if (!entryId) return null

        setLoading(true)
        setError(null)

        try {
            const response = await axios.post(`${API_URL}/api/entries/${entryId}/documents`, {
                document_ids: documentIds,
                auto_populate: autoPopulate,
            })

            // Refresh documents list and suggestions
            await fetchDocuments()
            await fetchSuggestions()

            return {
                linked_count: response.data.linked_count,
                fields_updated: response.data.fields_updated || [],
                suggestions: response.data.suggestions || [],
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message)
            return null
        } finally {
            setLoading(false)
        }
    }, [entryId, fetchDocuments, fetchSuggestions])

    const unlinkDocument = useCallback(async (documentId: string): Promise<boolean> => {
        if (!entryId) return false

        setLoading(true)
        setError(null)

        try {
            await axios.delete(`${API_URL}/api/entries/${entryId}/documents/${documentId}`)
            await fetchDocuments()
            return true
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message)
            return false
        } finally {
            setLoading(false)
        }
    }, [entryId, fetchDocuments])

    const applySuggestion = useCallback(async (
        fieldName: string,
        value: string
    ): Promise<boolean> => {
        if (!entryId) return false

        setLoading(true)
        setError(null)

        try {
            await axios.post(`${API_URL}/api/entries/${entryId}/apply-suggestion`, null, {
                params: { field_name: fieldName, value },
            })

            // Remove applied suggestion from list
            setSuggestions(prev => prev.filter(s => s.field_name !== fieldName))

            return true
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message)
            return false
        } finally {
            setLoading(false)
        }
    }, [entryId])

    return {
        documents,
        suggestions,
        conflicts,
        loading,
        error,
        linkDocuments,
        unlinkDocument,
        applySuggestion,
        refetch: fetchDocuments,
        refetchSuggestions: fetchSuggestions,
    }
}


// ==================== Status Helpers ====================

export const ENTRY_STATUSES = {
    draft: { label: 'Draft', color: 'gray', bgColor: 'bg-gray-100', textColor: 'text-gray-700' },
    pending_documents: { label: 'Pending Docs', color: 'yellow', bgColor: 'bg-yellow-100', textColor: 'text-yellow-700' },
    pending_review: { label: 'Pending Review', color: 'blue', bgColor: 'bg-blue-100', textColor: 'text-blue-700' },
    pending_client_approval: { label: 'Client Approval', color: 'purple', bgColor: 'bg-purple-100', textColor: 'text-purple-700' },
    ready_to_file: { label: 'Ready to File', color: 'cyan', bgColor: 'bg-cyan-100', textColor: 'text-cyan-700' },
    filing: { label: 'Filing...', color: 'indigo', bgColor: 'bg-indigo-100', textColor: 'text-indigo-700' },
    filed: { label: 'Filed', color: 'blue', bgColor: 'bg-blue-100', textColor: 'text-blue-700' },
    accepted: { label: 'Accepted', color: 'green', bgColor: 'bg-green-100', textColor: 'text-green-700' },
    rejected: { label: 'Rejected', color: 'red', bgColor: 'bg-red-100', textColor: 'text-red-700' },
    hold: { label: 'On Hold', color: 'orange', bgColor: 'bg-orange-100', textColor: 'text-orange-700' },
    released: { label: 'Released', color: 'emerald', bgColor: 'bg-emerald-100', textColor: 'text-emerald-700' },
    liquidated: { label: 'Liquidated', color: 'teal', bgColor: 'bg-teal-100', textColor: 'text-teal-700' },
    cancelled: { label: 'Cancelled', color: 'gray', bgColor: 'bg-gray-200', textColor: 'text-gray-500' },
} as const

export const ENTRY_TYPES = {
    '01': 'Consumption',
    '02': 'Consumption FTZ',
    '03': 'ADD/CVD',
    '05': 'Informal',
    '06': 'Warehouse',
    '07': 'FTZ Admission',
    '09': 'Reconciliation',
    '22': 'Drawback',
    '23': 'TIB',
    '24': 'In Transit',
} as const

export function getStatusInfo(status: string) {
    return ENTRY_STATUSES[status as keyof typeof ENTRY_STATUSES] || ENTRY_STATUSES.draft
}

export function getEntryTypeName(type: string) {
    return ENTRY_TYPES[type as keyof typeof ENTRY_TYPES] || type
}

export function formatCurrency(value: number, currency = 'USD'): string {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency,
    }).format(value)
}
