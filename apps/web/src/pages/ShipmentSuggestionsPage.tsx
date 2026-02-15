import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    RefreshCw, Package, FileText, Check, X,
    ChevronDown, ChevronUp, Ship,
    AlertCircle, Zap, Settings, Link2
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'

interface ShipmentSuggestion {
    id: string
    master_bl: string | null
    house_bl: string | null
    container_numbers: string[]
    booking_number: string | null
    confidence_score: number
    match_reasons: string[]
    status: 'PENDING' | 'ACCEPTED' | 'REJECTED'
    document_ids: string[]
    document_count: number
    suggested_details: {
        consignee?: string
        shipper?: string
        port_of_loading?: string
        port_of_discharge?: string
        [key: string]: string | undefined
    }
    created_shipment_id: string | null
    created_at: string
    reviewed_at: string | null
}

interface AssemblyMode {
    assembly_mode: 'auto' | 'manual' | 'assisted'
    auto_accept_threshold: number
    notify_on_suggestion: boolean
    notify_on_auto_accept: boolean
}

import { API_BASE } from '../config/api'

export const ShipmentSuggestionsPage = () => {
    const navigate = useNavigate()
    const [suggestions, setSuggestions] = useState<ShipmentSuggestion[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [expandedId, setExpandedId] = useState<string | null>(null)
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
    const [assemblyMode, setAssemblyMode] = useState<AssemblyMode | null>(null)
    const [autoAssembling, setAutoAssembling] = useState(false)

    // Fetch suggestions on mount
    useEffect(() => {
        fetchSuggestions()
        fetchAssemblyMode()
    }, [])

    const fetchSuggestions = async () => {
        setLoading(true)
        setError(null)
        try {
            const response = await fetch(`${API_BASE}/api/shipments/suggestions`)
            if (!response.ok) throw new Error('Failed to fetch suggestions')
            const data = await response.json()
            setSuggestions(data.suggestions || data)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred')
        } finally {
            setLoading(false)
        }
    }

    const fetchAssemblyMode = async () => {
        try {
            const response = await fetch(`${API_BASE}/api/shipments/assembly-mode`)
            if (response.ok) {
                const data = await response.json()
                setAssemblyMode(data)
            }
        } catch {
            // Default to manual if fetch fails
        }
    }

    const handleAccept = async (suggestionId: string) => {
        try {
            const response = await fetch(`${API_BASE}/api/shipments/suggestions/${suggestionId}/accept`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            if (!response.ok) throw new Error('Failed to accept suggestion')
            await fetchSuggestions()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to accept')
        }
    }

    const handleReject = async (suggestionId: string) => {
        try {
            const response = await fetch(`${API_BASE}/api/shipments/suggestions/${suggestionId}/reject`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            if (!response.ok) throw new Error('Failed to reject suggestion')
            await fetchSuggestions()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to reject')
        }
    }

    const handleBulkAccept = async () => {
        if (selectedIds.size === 0) return
        try {
            const response = await fetch(`${API_BASE}/api/shipments/suggestions/accept-bulk`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ suggestion_ids: Array.from(selectedIds) })
            })
            if (!response.ok) throw new Error('Failed to accept suggestions')
            setSelectedIds(new Set())
            await fetchSuggestions()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to bulk accept')
        }
    }

    const handleAutoAssemble = async () => {
        setAutoAssembling(true)
        setError(null)
        try {
            const response = await fetch(`${API_BASE}/api/shipments/auto-assemble`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            if (!response.ok) throw new Error('Auto-assembly failed')
            const result = await response.json()
            alert(`Auto-assembled ${result.shipments_created || 0} shipments from ${result.documents_analyzed || 0} documents`)
            await fetchSuggestions()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Auto-assembly failed')
        } finally {
            setAutoAssembling(false)
        }
    }

    const toggleSelection = (id: string) => {
        const newSelected = new Set(selectedIds)
        if (newSelected.has(id)) {
            newSelected.delete(id)
        } else {
            newSelected.add(id)
        }
        setSelectedIds(newSelected)
    }

    const selectAll = () => {
        const pending = suggestions.filter(s => s.status === 'PENDING').map(s => s.id)
        setSelectedIds(new Set(pending))
    }

    const pendingSuggestions = suggestions.filter(s => s.status === 'PENDING')
    const acceptedSuggestions = suggestions.filter(s => s.status === 'ACCEPTED')

    const getConfidenceColor = (score: number) => {
        if (score >= 0.9) return 'text-green-600 bg-green-100'
        if (score >= 0.7) return 'text-yellow-600 bg-yellow-100'
        return 'text-orange-600 bg-orange-100'
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold">Shipment Assembly</h1>
                    <p className="text-gray-500 mt-1">Review and accept suggested document groupings</p>
                </div>
                <div className="flex items-center gap-3">
                    <Button onClick={fetchSuggestions} variant="secondary" disabled={loading}>
                        <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                    <Button onClick={handleAutoAssemble} disabled={autoAssembling} variant="secondary">
                        <Zap className={`w-4 h-4 mr-2 ${autoAssembling ? 'animate-pulse' : ''}`} />
                        Auto-Assemble
                    </Button>
                    <Button onClick={() => navigate('/settings')} variant="secondary">
                        <Settings className="w-4 h-4 mr-2" />
                        Settings
                    </Button>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-4 gap-4">
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-blue-100 rounded-lg">
                                <Package className="w-5 h-5 text-blue-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{pendingSuggestions.length}</p>
                                <p className="text-sm text-gray-500">Pending Review</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-green-100 rounded-lg">
                                <Check className="w-5 h-5 text-green-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{acceptedSuggestions.length}</p>
                                <p className="text-sm text-gray-500">Accepted</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-purple-100 rounded-lg">
                                <Ship className="w-5 h-5 text-purple-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{acceptedSuggestions.filter(s => s.created_shipment_id).length}</p>
                                <p className="text-sm text-gray-500">Shipments Created</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-gray-100 rounded-lg">
                                <Link2 className="w-5 h-5 text-gray-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold capitalize">{assemblyMode?.assembly_mode || 'manual'}</p>
                                <p className="text-sm text-gray-500">Assembly Mode</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Error State */}
            {error && (
                <div className="flex gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
                    <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-red-600">{error}</p>
                </div>
            )}

            {/* Bulk Actions */}
            {pendingSuggestions.length > 0 && (
                <Card>
                    <CardContent className="py-3">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <input
                                    type="checkbox"
                                    checked={selectedIds.size === pendingSuggestions.length && pendingSuggestions.length > 0}
                                    onChange={() => selectedIds.size === pendingSuggestions.length ? setSelectedIds(new Set()) : selectAll()}
                                    className="w-4 h-4 rounded border-gray-300"
                                />
                                <span className="text-sm text-gray-600">
                                    {selectedIds.size} of {pendingSuggestions.length} selected
                                </span>
                            </div>
                            {selectedIds.size > 0 && (
                                <Button onClick={handleBulkAccept} size="sm">
                                    <Check className="w-4 h-4 mr-2" />
                                    Accept Selected ({selectedIds.size})
                                </Button>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Suggestions List */}
            <Card>
                <CardHeader>
                    <CardTitle>Suggested Shipments ({pendingSuggestions.length})</CardTitle>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <div className="flex items-center justify-center py-12">
                            <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
                        </div>
                    ) : pendingSuggestions.length === 0 ? (
                        <div className="text-center py-12 text-gray-500">
                            <Package className="w-12 h-12 mx-auto mb-4 opacity-30" />
                            <p>No pending suggestions</p>
                            <p className="text-sm mt-1">Documents will be analyzed automatically when uploaded</p>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {pendingSuggestions.map(suggestion => (
                                <div
                                    key={suggestion.id}
                                    className="border rounded-lg overflow-hidden hover:border-blue-300 transition-colors"
                                >
                                    <div className="p-4 bg-gray-50 flex items-center justify-between">
                                        <div className="flex items-center gap-4">
                                            <input
                                                type="checkbox"
                                                checked={selectedIds.has(suggestion.id)}
                                                onChange={() => toggleSelection(suggestion.id)}
                                                className="w-4 h-4 rounded border-gray-300"
                                            />
                                            <div className="flex items-center gap-3">
                                                <Ship className="w-6 h-6 text-blue-600" />
                                                <div>
                                                    <p className="font-semibold">
                                                        {suggestion.master_bl || suggestion.house_bl || 'Unknown BOL'}
                                                    </p>
                                                    <p className="text-sm text-gray-500">
                                                        {suggestion.document_count || suggestion.document_ids.length} documents
                                                    </p>
                                                </div>
                                            </div>
                                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getConfidenceColor(suggestion.confidence_score)}`}>
                                                {Math.round(suggestion.confidence_score * 100)}% confidence
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Button onClick={() => handleAccept(suggestion.id)} size="sm">
                                                <Check className="w-4 h-4 mr-1" /> Accept
                                            </Button>
                                            <Button onClick={() => handleReject(suggestion.id)} size="sm" variant="secondary">
                                                <X className="w-4 h-4 mr-1" /> Reject
                                            </Button>
                                            <button
                                                onClick={() => setExpandedId(expandedId === suggestion.id ? null : suggestion.id)}
                                                className="p-2 hover:bg-gray-200 rounded"
                                            >
                                                {expandedId === suggestion.id ? (
                                                    <ChevronUp className="w-4 h-4" />
                                                ) : (
                                                    <ChevronDown className="w-4 h-4" />
                                                )}
                                            </button>
                                        </div>
                                    </div>

                                    {expandedId === suggestion.id && (
                                        <div className="p-4 border-t bg-white">
                                            <div className="grid grid-cols-2 gap-6">
                                                <div>
                                                    <h4 className="text-sm font-medium text-gray-700 mb-2">Shipment Details</h4>
                                                    <dl className="space-y-1 text-sm">
                                                        {suggestion.master_bl && (
                                                            <div className="flex">
                                                                <dt className="w-32 text-gray-500">Master B/L:</dt>
                                                                <dd className="font-mono">{suggestion.master_bl}</dd>
                                                            </div>
                                                        )}
                                                        {suggestion.house_bl && (
                                                            <div className="flex">
                                                                <dt className="w-32 text-gray-500">House B/L:</dt>
                                                                <dd className="font-mono">{suggestion.house_bl}</dd>
                                                            </div>
                                                        )}
                                                        {suggestion.container_numbers?.length > 0 && (
                                                            <div className="flex">
                                                                <dt className="w-32 text-gray-500">Containers:</dt>
                                                                <dd className="font-mono">{suggestion.container_numbers.join(', ')}</dd>
                                                            </div>
                                                        )}
                                                        {suggestion.suggested_details?.consignee && (
                                                            <div className="flex">
                                                                <dt className="w-32 text-gray-500">Consignee:</dt>
                                                                <dd>{suggestion.suggested_details.consignee}</dd>
                                                            </div>
                                                        )}
                                                        {suggestion.suggested_details?.shipper && (
                                                            <div className="flex">
                                                                <dt className="w-32 text-gray-500">Shipper:</dt>
                                                                <dd>{suggestion.suggested_details.shipper}</dd>
                                                            </div>
                                                        )}
                                                    </dl>
                                                </div>
                                                <div>
                                                    <h4 className="text-sm font-medium text-gray-700 mb-2">
                                                        Documents ({suggestion.document_ids.length})
                                                    </h4>
                                                    <div className="space-y-1">
                                                        {suggestion.document_ids.slice(0, 5).map(docId => (
                                                            <div key={docId} className="flex items-center gap-2 text-sm">
                                                                <FileText className="w-4 h-4 text-gray-400" />
                                                                <span className="font-mono text-xs text-gray-600 truncate">
                                                                    {docId.substring(0, 8)}...
                                                                </span>
                                                            </div>
                                                        ))}
                                                        {suggestion.document_ids.length > 5 && (
                                                            <p className="text-sm text-gray-500 pl-6">
                                                                +{suggestion.document_ids.length - 5} more
                                                            </p>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                            {suggestion.match_reasons?.length > 0 && (
                                                <div className="mt-4 pt-4 border-t">
                                                    <h4 className="text-sm font-medium text-gray-700 mb-2">Match Reasons</h4>
                                                    <div className="flex flex-wrap gap-2">
                                                        {suggestion.match_reasons.map((reason, idx) => (
                                                            <span key={idx} className="px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded">
                                                                {reason}
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Accepted History */}
            {acceptedSuggestions.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Recently Accepted ({acceptedSuggestions.length})</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-2">
                            {acceptedSuggestions.slice(0, 5).map(suggestion => (
                                <div
                                    key={suggestion.id}
                                    className="flex items-center justify-between p-3 bg-green-50 rounded-lg"
                                >
                                    <div className="flex items-center gap-3">
                                        <Check className="w-5 h-5 text-green-600" />
                                        <div>
                                            <p className="font-medium">{suggestion.master_bl || suggestion.house_bl}</p>
                                            <p className="text-sm text-gray-500">
                                                {suggestion.document_ids.length} documents • Accepted {suggestion.reviewed_at ? new Date(suggestion.reviewed_at).toLocaleDateString() : 'recently'}
                                            </p>
                                        </div>
                                    </div>
                                    {suggestion.created_shipment_id && (
                                        <Button
                                            size="sm"
                                            variant="secondary"
                                            onClick={() => navigate(`/shipments/${suggestion.created_shipment_id}`)}
                                        >
                                            View Shipment
                                        </Button>
                                    )}
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    )
}
