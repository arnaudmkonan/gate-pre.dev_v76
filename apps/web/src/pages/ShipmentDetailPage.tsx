import { authFetch } from '../lib/authFetch';
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
    ArrowLeft, RefreshCw, FileText, Ship, Package,
    User, MapPin, Calendar, DollarSign, AlertCircle,
    Trash2, CheckCircle, Download, ShieldCheck, Send
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'

interface ShipmentDocument {
    id: string
    filename: string
    document_type?: string
    uploaded_at?: string
}

interface Shipment {
    id: string
    name?: string
    reference_num?: string
    primary_key_type?: string
    primary_key_value?: string
    status: string
    document_count: number
    document_types?: string[]
    entry_number?: string
    bol_number?: string
    awb_number?: string
    container_numbers?: string[]
    po_numbers?: string[]
    importer_name?: string
    exporter_name?: string
    manufacturer_name?: string
    origin?: string
    destination?: string
    port_of_entry?: string
    ship_date?: string
    arrival_date?: string
    entry_date?: string
    total_declared_value?: number
    total_duty?: number
    currency?: string
    documents?: string[]
    created_at: string
    updated_at?: string
}

import { API_BASE } from '../config/api'

export const ShipmentDetailPage = () => {
    const { shipmentId } = useParams<{ shipmentId: string }>()
    const navigate = useNavigate()
    const [shipment, setShipment] = useState<Shipment | null>(null)
    const [documents, setDocuments] = useState<ShipmentDocument[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [creatingEntry, setCreatingEntry] = useState(false)
    const [generatingISF, setGeneratingISF] = useState(false)
    const [isfData, setIsfData] = useState<Record<string, any> | null>(null)
    const [showDocRequestModal, setShowDocRequestModal] = useState(false)
    const [docRequestType, setDocRequestType] = useState('commercial_invoice')
    const [docRequestNote, setDocRequestNote] = useState('')
    const [docRequestSent, setDocRequestSent] = useState<string | null>(null)

    useEffect(() => {
        if (shipmentId) {
            fetchShipment()
        }
    }, [shipmentId])

    const fetchShipment = async () => {
        setLoading(true)
        setError(null)
        try {
            const response = await authFetch(`${API_BASE}/api/shipments/${shipmentId}`)
            if (!response.ok) throw new Error('Failed to fetch shipment')
            const data = await response.json()
            setShipment(data)

            await fetchDocuments()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred')
        } finally {
            setLoading(false)
        }
    }

    const fetchDocuments = async () => {
        if (!shipmentId) return
        try {
            const response = await authFetch(`${API_BASE}/api/shipments/${shipmentId}/documents`)
            if (response.ok) {
                const links = await response.json()
                const docData: ShipmentDocument[] = (links || []).map((link: any) => ({
                    id: link.document_id,
                    filename: link.filename || `Document ${String(link.document_id).slice(0, 8)}`,
                    document_type: link.file_type || link.linked_by_key_type,
                    uploaded_at: link.linked_at,
                }))
                setDocuments(docData)
            }
        } catch (err) {
            console.error('Error fetching documents:', err)
        }
    }

    const handleDownloadDocument = async (docId: string, filename: string) => {
        try {
            const resp = await authFetch(`${API_BASE}/api/files/document/${docId}/content?download=true`)
            if (!resp.ok) return
            const blob = await resp.blob()
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = filename
            a.click()
            URL.revokeObjectURL(url)
        } catch (err) {
            console.error('Error downloading document:', err)
        }
    }

    const handleCreateOfficialEntry = async () => {
        if (!shipmentId) return
        setCreatingEntry(true)
        try {
            const resp = await authFetch(`${API_BASE}/api/shipments/${shipmentId}/create-entry`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ entry_type: '01', auto_calculate: true }),
            })
            if (!resp.ok) {
                const err = await resp.json()
                throw new Error(err.detail || 'Failed to create entry')
            }
            const data = await resp.json()
            if (data.entry_id) {
                navigate(`/entries/${data.entry_id}`)
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to create entry')
        } finally {
            setCreatingEntry(false)
        }
    }

    const handleGenerateISF = async () => {
        if (!shipmentId) return
        setGeneratingISF(true)
        try {
            const resp = await authFetch(`${API_BASE}/api/isf/from-shipment/${shipmentId}`, {
                method: 'POST',
            })
            if (!resp.ok) throw new Error('Failed to generate ISF (10+2)')
            const data = await resp.json()
            setIsfData(data.isf || data)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to generate ISF')
        } finally {
            setGeneratingISF(false)
        }
    }

    const handleDownloadIsfAbi = async () => {
        const isfId = isfData?.id || isfData?.isf_id
        if (!isfId) return
        try {
            const resp = await authFetch(`${API_BASE}/api/isf/${isfId}/abi-message`)
            if (!resp.ok) throw new Error('Failed to generate ISF-10 ABI file')
            const data = await resp.json()
            const abiText = typeof data.abi_message === 'string' ? data.abi_message : JSON.stringify(data, null, 2)
            const blob = new Blob([abiText], { type: 'text/plain;charset=utf-8' })
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `ISF10_${shipment?.bol_number || String(isfId).slice(0, 8)}.abi`
            a.click()
            URL.revokeObjectURL(url)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to export ISF ABI draft')
        }
    }

    const handleDeleteShipment = async () => {
        if (!shipmentId) return
        if (!window.confirm('Delete this shipment record? Linked source documents will remain in storage.')) {
            return
        }
        try {
            const resp = await authFetch(`${API_BASE}/api/shipments/${shipmentId}`, {
                method: 'DELETE',
            })
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}))
                throw new Error(err.detail || 'Failed to delete shipment')
            }
            navigate('/shipments/assembly')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to delete shipment')
        }
    }

    const handleRequestMissingDocument = async () => {
        if (!shipmentId) return
        try {
            const resp = await authFetch(`${API_BASE}/api/shipments/${shipmentId}/request-document`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    doc_type: docRequestType,
                    note: docRequestNote || undefined,
                }),
            })
            if (resp.ok) {
                const data = await resp.json()
                setDocRequestSent(
                    data.message ||
                    (data.email_dispatched
                        ? `Requested ${docRequestType.replace(/_/g, ' ')} from importer (${shipment?.importer_name || 'Client'})`
                        : `Request recorded but email was not sent — check SMTP / client contact.`)
                )
            } else {
                const err = await resp.json().catch(() => ({}))
                setDocRequestSent(
                    err.detail ||
                    `Failed to request ${docRequestType.replace(/_/g, ' ')} — try again or email the importer manually.`
                )
            }
        } catch {
            setDocRequestSent(
                `Failed to request ${docRequestType.replace(/_/g, ' ')} — network error. Email the importer manually.`
            )
        } finally {
            setShowDocRequestModal(false)
            setDocRequestNote('')
        }
    }

    const getStatusBadge = (status: string) => {
        const statusConfig: Record<string, { color: string; icon: React.ReactNode }> = {
            partial: { color: 'bg-yellow-100 text-yellow-700', icon: <Package className="w-4 h-4" /> },
            complete: { color: 'bg-green-100 text-green-700', icon: <CheckCircle className="w-4 h-4" /> },
            filed: { color: 'bg-blue-100 text-blue-700', icon: <FileText className="w-4 h-4" /> },
            released: { color: 'bg-purple-100 text-purple-700', icon: <Ship className="w-4 h-4" /> },
        }
        const config = statusConfig[status?.toLowerCase()] || { color: 'bg-gray-100 text-gray-700', icon: null }
        return (
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${config.color}`}>
                {config.icon}
                {status?.toUpperCase() || 'UNKNOWN'}
            </span>
        )
    }

    const formatCurrency = (amount?: number, currency = 'USD') => {
        if (!amount) return '-'
        return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount)
    }

    const formatDate = (dateStr?: string) => {
        if (!dateStr) return '-'
        return new Date(dateStr).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        })
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-96">
                <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
            </div>
        )
    }

    if (error || !shipment) {
        return (
            <div className="space-y-4">
                <Button onClick={() => navigate(-1)} variant="secondary">
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Back
                </Button>
                <div className="flex gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
                    <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                    <p className="text-red-600">{error || 'Shipment not found'}</p>
                </div>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Button onClick={() => navigate(-1)} variant="secondary" size="sm">
                        <ArrowLeft className="w-4 h-4" />
                    </Button>
                    <div>
                        <div className="flex items-center gap-3">
                            <h1 className="text-2xl font-bold">
                                {shipment.name || shipment.bol_number || `Shipment ${shipment.id.substring(0, 8)}`}
                            </h1>
                            {getStatusBadge(shipment.status)}
                        </div>
                        <p className="text-gray-500 mt-1">
                            {shipment.primary_key_value && (
                                <span className="font-mono">{shipment.primary_key_type}: {shipment.primary_key_value}</span>
                            )}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button onClick={fetchShipment} variant="secondary">
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Refresh
                    </Button>
                    <Button variant="secondary" onClick={handleGenerateISF} disabled={generatingISF}>
                        <ShieldCheck className="w-4 h-4 mr-2" />
                        {generatingISF ? 'Generating ISF...' : 'Generate ISF (10+2)'}
                    </Button>
                    <Button variant="secondary" onClick={() => navigate(`/entries/prep/${shipment.id}`)}>
                        <FileText className="w-4 h-4 mr-2" />
                        Prepare 7501
                    </Button>
                    <Button onClick={handleCreateOfficialEntry} disabled={creatingEntry}>
                        <CheckCircle className="w-4 h-4 mr-2" />
                        {creatingEntry ? 'Creating...' : 'Create Official Entry'}
                    </Button>
                </div>
            </div>

            {docRequestSent && (
                <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800 flex items-center justify-between">
                    <span>✓ {docRequestSent}</span>
                    <button onClick={() => setDocRequestSent(null)} className="text-green-600 hover:underline text-xs">Dismiss</button>
                </div>
            )}

            {isfData && (
                <Card className="border-blue-200 bg-blue-50">
                    <CardHeader className="pb-2">
                        <CardTitle className="flex items-center justify-between text-base text-blue-900">
                            <span className="flex items-center gap-2">
                                <ShieldCheck className="w-5 h-5 text-blue-600" />
                                ISF (10+2 Importer Security Filing) Prepared
                            </span>
                            <div className="flex items-center gap-2">
                                {(isfData.id || isfData.isf_id) && (
                                    <button
                                        type="button"
                                        onClick={handleDownloadIsfAbi}
                                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-blue-700 bg-white border border-blue-200 rounded hover:bg-blue-100"
                                    >
                                        <Download className="w-3.5 h-3.5" />
                                        Download ISF-10 ABI Draft
                                    </button>
                                )}
                                <span className="text-xs px-2.5 py-0.5 bg-blue-100 text-blue-800 rounded-full uppercase">
                                    {isfData.status || 'Draft'}
                                </span>
                            </div>
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-blue-900 grid grid-cols-4 gap-4">
                        <div>
                            <span className="text-xs text-blue-600 block">ISF Importer</span>
                            <span className="font-medium">{isfData.importer_name || shipment.importer_name || '-'}</span>
                        </div>
                        <div>
                            <span className="text-xs text-blue-600 block">Seller / Manufacturer</span>
                            <span className="font-medium">{isfData.seller_name || isfData.manufacturer_name || shipment.exporter_name || '-'}</span>
                        </div>
                        <div>
                            <span className="text-xs text-blue-600 block">Master Bill of Lading</span>
                            <span className="font-mono font-medium">{isfData.bill_of_lading_number || shipment.bol_number || '-'}</span>
                        </div>
                        <div>
                            <span className="text-xs text-blue-600 block">Completeness</span>
                            <span className="font-medium">{isfData.completeness_percentage ?? 80}% (10+2 Elements)</span>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Quick Stats */}
            <div className="grid grid-cols-4 gap-4">
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-blue-100 rounded-lg">
                                <FileText className="w-5 h-5 text-blue-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{shipment.document_count || shipment.documents?.length || 0}</p>
                                <p className="text-sm text-gray-500">Documents</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-purple-100 rounded-lg">
                                <Package className="w-5 h-5 text-purple-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{shipment.container_numbers?.length || 0}</p>
                                <p className="text-sm text-gray-500">Containers</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-green-100 rounded-lg">
                                <DollarSign className="w-5 h-5 text-green-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{formatCurrency(shipment.total_declared_value)}</p>
                                <p className="text-sm text-gray-500">Declared Value</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-orange-100 rounded-lg">
                                <DollarSign className="w-5 h-5 text-orange-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{formatCurrency(shipment.total_duty)}</p>
                                <p className="text-sm text-gray-500">Estimated Duty</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            <div className="grid grid-cols-3 gap-6">
                {/* Shipment Details */}
                <Card className="col-span-2">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Ship className="w-5 h-5" />
                            Shipment Details
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-2 gap-6">
                            {/* Left Column */}
                            <div className="space-y-4">
                                <div>
                                    <h4 className="text-sm font-medium text-gray-500 mb-2">Identifiers</h4>
                                    <dl className="space-y-2 text-sm">
                                        {shipment.bol_number && (
                                            <div className="flex justify-between">
                                                <dt className="text-gray-600">Bill of Lading:</dt>
                                                <dd className="font-mono font-medium">{shipment.bol_number}</dd>
                                            </div>
                                        )}
                                        {shipment.entry_number && (
                                            <div className="flex justify-between">
                                                <dt className="text-gray-600">Entry Number:</dt>
                                                <dd className="font-mono font-medium">{shipment.entry_number}</dd>
                                            </div>
                                        )}
                                        {shipment.awb_number && (
                                            <div className="flex justify-between">
                                                <dt className="text-gray-600">AWB Number:</dt>
                                                <dd className="font-mono font-medium">{shipment.awb_number}</dd>
                                            </div>
                                        )}
                                        {shipment.reference_num && (
                                            <div className="flex justify-between">
                                                <dt className="text-gray-600">Reference:</dt>
                                                <dd className="font-mono font-medium">{shipment.reference_num}</dd>
                                            </div>
                                        )}
                                    </dl>
                                </div>

                                <div>
                                    <h4 className="text-sm font-medium text-gray-500 mb-2">Route</h4>
                                    <dl className="space-y-2 text-sm">
                                        {shipment.origin && (
                                            <div className="flex justify-between">
                                                <dt className="text-gray-600 flex items-center gap-1">
                                                    <MapPin className="w-3 h-3" /> Origin:
                                                </dt>
                                                <dd className="font-medium">{shipment.origin}</dd>
                                            </div>
                                        )}
                                        {shipment.destination && (
                                            <div className="flex justify-between">
                                                <dt className="text-gray-600 flex items-center gap-1">
                                                    <MapPin className="w-3 h-3" /> Destination:
                                                </dt>
                                                <dd className="font-medium">{shipment.destination}</dd>
                                            </div>
                                        )}
                                        {shipment.port_of_entry && (
                                            <div className="flex justify-between">
                                                <dt className="text-gray-600">Port of Entry:</dt>
                                                <dd className="font-medium">{shipment.port_of_entry}</dd>
                                            </div>
                                        )}
                                    </dl>
                                </div>
                            </div>

                            {/* Right Column */}
                            <div className="space-y-4">
                                <div>
                                    <h4 className="text-sm font-medium text-gray-500 mb-2">Parties</h4>
                                    <dl className="space-y-2 text-sm">
                                        {shipment.importer_name && (
                                            <div className="flex justify-between">
                                                <dt className="text-gray-600 flex items-center gap-1">
                                                    <User className="w-3 h-3" /> Importer:
                                                </dt>
                                                <dd className="font-medium">{shipment.importer_name}</dd>
                                            </div>
                                        )}
                                        {shipment.exporter_name && (
                                            <div className="flex justify-between">
                                                <dt className="text-gray-600 flex items-center gap-1">
                                                    <User className="w-3 h-3" /> Exporter:
                                                </dt>
                                                <dd className="font-medium">{shipment.exporter_name}</dd>
                                            </div>
                                        )}
                                        {shipment.manufacturer_name && (
                                            <div className="flex justify-between">
                                                <dt className="text-gray-600">Manufacturer:</dt>
                                                <dd className="font-medium">{shipment.manufacturer_name}</dd>
                                            </div>
                                        )}
                                    </dl>
                                </div>

                                <div>
                                    <h4 className="text-sm font-medium text-gray-500 mb-2">Dates</h4>
                                    <dl className="space-y-2 text-sm">
                                        {shipment.ship_date && (
                                            <div className="flex justify-between">
                                                <dt className="text-gray-600 flex items-center gap-1">
                                                    <Calendar className="w-3 h-3" /> Ship Date:
                                                </dt>
                                                <dd className="font-medium">{formatDate(shipment.ship_date)}</dd>
                                            </div>
                                        )}
                                        {shipment.arrival_date && (
                                            <div className="flex justify-between">
                                                <dt className="text-gray-600 flex items-center gap-1">
                                                    <Calendar className="w-3 h-3" /> Arrival:
                                                </dt>
                                                <dd className="font-medium">{formatDate(shipment.arrival_date)}</dd>
                                            </div>
                                        )}
                                        {shipment.entry_date && (
                                            <div className="flex justify-between">
                                                <dt className="text-gray-600">Entry Date:</dt>
                                                <dd className="font-medium">{formatDate(shipment.entry_date)}</dd>
                                            </div>
                                        )}
                                    </dl>
                                </div>
                            </div>
                        </div>

                        {/* Containers */}
                        {shipment.container_numbers && shipment.container_numbers.length > 0 && (
                            <div className="mt-6 pt-6 border-t">
                                <h4 className="text-sm font-medium text-gray-500 mb-3">Container Numbers</h4>
                                <div className="flex flex-wrap gap-2">
                                    {shipment.container_numbers.map((container, idx) => (
                                        <span key={idx} className="px-3 py-1 bg-gray-100 rounded font-mono text-sm">
                                            {container}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* PO Numbers */}
                        {shipment.po_numbers && shipment.po_numbers.length > 0 && (
                            <div className="mt-4">
                                <h4 className="text-sm font-medium text-gray-500 mb-3">PO Numbers</h4>
                                <div className="flex flex-wrap gap-2">
                                    {shipment.po_numbers.map((po, idx) => (
                                        <span key={idx} className="px-3 py-1 bg-blue-50 text-blue-700 rounded font-mono text-sm">
                                            {po}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Documents Panel */}
                <Card>
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <CardTitle className="flex items-center gap-2">
                                <FileText className="w-5 h-5" />
                                Linked Documents ({documents.length})
                            </CardTitle>
                            <Button size="sm" variant="secondary" onClick={() => setShowDocRequestModal(true)}>
                                <Send className="w-3.5 h-3.5 mr-1" />
                                Request Doc
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent>
                        {documents.length === 0 ? (
                            <div className="text-center py-8 text-gray-500">
                                <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
                                <p>No documents linked</p>
                            </div>
                        ) : (
                            <div className="space-y-2 max-h-96 overflow-y-auto">
                                {documents.map(doc => (
                                    <div
                                        key={doc.id}
                                        className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                                    >
                                        <div className="flex items-center gap-3 min-w-0">
                                            <FileText className="w-4 h-4 text-blue-500 flex-shrink-0" />
                                            <div className="min-w-0">
                                                <p className="text-sm font-medium truncate">{doc.filename}</p>
                                                {doc.document_type && (
                                                    <p className="text-xs text-gray-500 uppercase">{doc.document_type.replace(/_/g, ' ')}</p>
                                                )}
                                            </div>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => handleDownloadDocument(doc.id, doc.filename)}
                                            title="Download original document"
                                            className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 bg-white border border-gray-200 rounded hover:bg-blue-50 flex-shrink-0"
                                        >
                                            <Download className="w-3.5 h-3.5" />
                                            Download
                                        </button>
                                    </div>
                                ))}
                                {shipment.documents && shipment.documents.length > 20 && (
                                    <p className="text-center text-sm text-gray-500 py-2">
                                        +{shipment.documents.length - 20} more documents
                                    </p>
                                )}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Actions Bar */}
            <Card>
                <CardContent className="py-4">
                    <div className="flex items-center justify-between">
                        <div className="text-sm text-gray-500">
                            Created {formatDate(shipment.created_at)}
                            {shipment.updated_at && ` • Updated ${formatDate(shipment.updated_at)}`}
                        </div>
                        <div className="flex items-center gap-2">
                            <Button variant="secondary" onClick={() => setShowDocRequestModal(true)}>
                                <Send className="w-4 h-4 mr-2" />
                                Request Missing Doc
                            </Button>
                            <Button variant="secondary" onClick={() => navigate(`/entries/prep/${shipment.id}`)}>
                                <FileText className="w-4 h-4 mr-2" />
                                Prepare Form 7501
                            </Button>
                            <Button onClick={handleCreateOfficialEntry} disabled={creatingEntry}>
                                <CheckCircle className="w-4 h-4 mr-2" />
                                {creatingEntry ? 'Creating...' : 'Create Official Entry'}
                            </Button>
                            <Button variant="secondary" onClick={handleDeleteShipment}>
                                <Trash2 className="w-4 h-4 mr-2" />
                                Delete Shipment
                            </Button>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Request Missing Document Modal */}
            {showDocRequestModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6 space-y-4">
                        <h3 className="text-lg font-semibold">Request Missing Document from Importer</h3>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Document Type</label>
                            <select
                                value={docRequestType}
                                onChange={(e) => setDocRequestType(e.target.value)}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                            >
                                <option value="commercial_invoice">Commercial Invoice</option>
                                <option value="packing_list">Packing List</option>
                                <option value="bill_of_lading">Bill of Lading (MBL / HBL)</option>
                                <option value="arrival_notice">Arrival Notice</option>
                                <option value="power_of_attorney">Power of Attorney (POA)</option>
                                <option value="pga_certificate">PGA / FDA / Lacey Act Certificate</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Instructions for Importer</label>
                            <textarea
                                value={docRequestNote}
                                onChange={(e) => setDocRequestNote(e.target.value)}
                                rows={3}
                                placeholder="e.g. Please provide a signed Commercial Invoice showing HTS codes and Country of Origin..."
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                            />
                        </div>
                        <div className="flex justify-end gap-2 pt-2 border-t">
                            <Button variant="secondary" onClick={() => setShowDocRequestModal(false)}>
                                Cancel
                            </Button>
                            <Button onClick={handleRequestMissingDocument}>
                                <Send className="w-4 h-4 mr-2" />
                                Send Request
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
