/**
 * Entry Detail Page
 * 
 * View and edit customs entry details including lines, parties, documents.
 * 
 * Task 1.4 from ROADMAP_FULL_WORKFLOW.md
 */
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
    ArrowLeft,
    RefreshCw,

    Send,
    Calculator,
    CheckCircle,
    XCircle,
    AlertTriangle,
    FileText,
    Package,
    Users,
    History,
    DollarSign,
    Plus,
    Edit,
    Trash2,
    Eye,
    Download,
    Ship,
    Anchor,
    Globe,
    Building,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'
import { ACEStatusPanel } from '../components/ACEStatusPanel'
import { DocumentViewer } from '../components/review/DocumentViewer'
import { HTSAutocompleteInput } from '../components/HTSAutocompleteInput'
import { authFetch } from '../lib/authFetch'
import {
    useEntry,
    useEntryActions,
    AddLineRequest,
    getStatusInfo,
    getEntryTypeName,
    formatCurrency,
} from '../hooks/useEntries'

// Status badge component
const StatusBadge = ({ status }: { status: string }) => {
    const info = getStatusInfo(status)
    return (
        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${info.bgColor} ${info.textColor}`}>
            {info.label}
        </span>
    )
}

// Section header component
const SectionHeader = ({ icon: Icon, title, children }: { icon: any; title: string; children?: React.ReactNode }) => (
    <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
            <Icon className="w-5 h-5 text-gray-500" />
            <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        </div>
        {children}
    </div>
)

// Add / Edit Line Modal
const AddLineModal = ({
    isOpen,
    onClose,
    onSave,
    nextLineNumber,
    initialLine,
}: {
    isOpen: boolean
    onClose: () => void
    onSave: (line: AddLineRequest) => void
    nextLineNumber: number
    initialLine?: any | null
}) => {
    const [formData, setFormData] = useState<AddLineRequest>({
        line_number: nextLineNumber,
        hts_code: '',
        product_description: '',
        country_of_origin: '',
        entered_value: 0,
        quantity_1: 1,
    })

    useEffect(() => {
        if (initialLine) {
            setFormData({
                line_number: initialLine.line_number || nextLineNumber,
                hts_code: initialLine.hts_code || '',
                product_description: initialLine.product_description || '',
                country_of_origin: initialLine.country_of_origin || '',
                entered_value: Number(initialLine.entered_value || 0),
                quantity_1: Number(initialLine.quantity_1 || 1),
            })
        } else {
            setFormData({
                line_number: nextLineNumber,
                hts_code: '',
                product_description: '',
                country_of_origin: '',
                entered_value: 0,
                quantity_1: 1,
            })
        }
    }, [nextLineNumber, initialLine, isOpen])

    if (!isOpen) return null

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        onSave(formData)
    }

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
                <h3 className="text-lg font-semibold mb-4">
                    {initialLine ? `Edit Line #${initialLine.line_number}` : 'Add Line Item'}
                </h3>
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Line #</label>
                            <input
                                type="number"
                                value={formData.line_number}
                                onChange={(e) => setFormData(prev => ({ ...prev, line_number: parseInt(e.target.value) }))}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                                min={1}
                                required
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">HTS Code</label>
                            <HTSAutocompleteInput
                                value={formData.hts_code || ''}
                                onChange={(code, suggestion) =>
                                    setFormData(prev => ({
                                        ...prev,
                                        hts_code: code,
                                        product_description:
                                            prev.product_description || suggestion?.description || '',
                                    }))
                                }
                                placeholder="Search HTS or keyword..."
                            />
                        </div>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                        <input
                            type="text"
                            value={formData.product_description}
                            onChange={(e) => setFormData(prev => ({ ...prev, product_description: e.target.value }))}
                            placeholder="Product description..."
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                        />
                    </div>
                    <div className="grid grid-cols-3 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Country</label>
                            <input
                                type="text"
                                value={formData.country_of_origin}
                                onChange={(e) => setFormData(prev => ({ ...prev, country_of_origin: e.target.value.toUpperCase() }))}
                                placeholder="CN"
                                maxLength={2}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg uppercase"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Quantity</label>
                            <input
                                type="number"
                                value={formData.quantity_1}
                                onChange={(e) => setFormData(prev => ({ ...prev, quantity_1: parseFloat(e.target.value) }))}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                                step="0.01"
                                min={0}
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Value (USD)</label>
                            <input
                                type="number"
                                value={formData.entered_value}
                                onChange={(e) => setFormData(prev => ({ ...prev, entered_value: parseFloat(e.target.value) }))}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                                step="0.01"
                                min={0}
                            />
                        </div>
                    </div>
                    <div className="flex justify-end gap-3 pt-4 border-t">
                        <Button variant="secondary" type="button" onClick={onClose}>Cancel</Button>
                        <Button type="submit">
                            {initialLine ? (
                                <>
                                    <Edit className="w-4 h-4 mr-2" />
                                    Save Line Changes
                                </>
                            ) : (
                                <>
                                    <Plus className="w-4 h-4 mr-2" />
                                    Add Line
                                </>
                            )}
                        </Button>
                    </div>
                </form>
            </div>
        </div>
    )
}

export const EntryDetailPage = () => {
    const { entryId } = useParams<{ entryId: string }>()
    const navigate = useNavigate()
    const { entry, loading, error, refetch } = useEntry(entryId)
    const { updateEntry, addLine, updateLine, deleteLine, calculateDuties, validateEntry, brokerOk, loading: actionLoading, error: actionError } = useEntryActions()

    const [showAddLineModal, setShowAddLineModal] = useState(false)
    const [editingLine, setEditingLine] = useState<any | null>(null)
    const [brokerHtsOk, setBrokerHtsOk] = useState(true)
    const [brokerValuesOk, setBrokerValuesOk] = useState(true)
    const [brokerAdcvd, setBrokerAdcvd] = useState('note-only')
    const [brokerNotes, setBrokerNotes] = useState('')
    const [selectedPreviewDocId, setSelectedPreviewDocId] = useState<string | null>(null)
    const [showEditEntryModal, setShowEditEntryModal] = useState(
        typeof window !== 'undefined' && window.location.pathname.endsWith('/edit')
    )
    const [editForm, setEditForm] = useState<Record<string, any>>({})
    const [pgaData, setPgaData] = useState<Record<string, any> | null>(null)
    const [validationResult, setValidationResult] = useState<any>(null)
    const [activeTab, setActiveTab] = useState<'lines' | 'parties' | 'documents' | 'history'>('lines')

    useEffect(() => {
        if (entry) {
            setEditForm({
                entry_number: entry.entry_number || '',
                entry_type: entry.entry_type || '01',
                port_of_entry: entry.port_of_entry || '',
                importer_of_record_name: entry.importer_of_record_name || '',
                importer_of_record_number: entry.importer_of_record_number || '',
                ultimate_consignee_name: entry.ultimate_consignee_name || '',
                bill_of_lading: entry.bill_of_lading || '',
                vessel_name: entry.vessel_name || '',
                carrier_code: entry.carrier_code || '',
                notes: entry.notes || '',
            })
        }
    }, [entry])

    useEffect(() => {
        if (!entryId) return
        authFetch(`/api/pga/entry/${entryId}`)
            .then(r => (r.ok ? r.json() : null))
            .then(data => {
                if (data) setPgaData(data)
            })
            .catch(() => {})
    }, [entryId, entry?.lines?.length])

    const handleSaveEntryHeader = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!entryId) return
        const success = await updateEntry(entryId, editForm as any)
        if (success) {
            setShowEditEntryModal(false)
            refetch()
        }
    }

    const handleDownloadDoc = async (docId: string) => {
        try {
            const resp = await authFetch(`/api/files/document/${docId}/content?download=true`)
            if (!resp.ok) return
            const blob = await resp.blob()
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `document_${docId.slice(0, 8)}`
            a.click()
            URL.revokeObjectURL(url)
        } catch (err) {
            console.error('Document download failed:', err)
        }
    }

    const handleCalculate = async () => {
        if (!entryId) return
        const result = await calculateDuties(entryId)
        if (result) {
            refetch()
        }
    }

    const handleValidate = async () => {
        if (!entryId) return
        const result = await validateEntry(entryId)
        setValidationResult(result)
    }

    const handleSaveLine = async (lineData: AddLineRequest) => {
        if (!entryId) return
        if (editingLine?.id) {
            const updated = await updateLine(entryId, editingLine.id, lineData)
            if (updated) {
                setEditingLine(null)
                setShowAddLineModal(false)
                refetch()
            }
            return
        }
        const result = await addLine(entryId, lineData)
        if (result) {
            setShowAddLineModal(false)
            refetch()
        }
    }

    const handleDeleteLine = async (lineId: string) => {
        if (!entryId) return
        const ok = await deleteLine(entryId, lineId)
        if (ok) {
            refetch()
        }
    }

    const handleStatusChange = async (newStatus: string) => {
        if (!entryId) return
        const success = await updateEntry(entryId, { status: newStatus } as any)
        if (success) {
            refetch()
        }
    }

    const handleBrokerOk = async () => {
        if (!entryId) return
        const result = await brokerOk(entryId, {
            hts_confirmed: brokerHtsOk,
            values_confirmed: brokerValuesOk,
            adcvd_notes: brokerAdcvd || undefined,
            notes: brokerNotes || undefined,
            mark_ready_to_file: true,
        })
        if (result) {
            refetch()
        }
    }

    const handleExport = async (format: 'pdf' | 'excel' | 'cargowise') => {
        if (!entryId) return
        try {
            const urlPath =
                format === 'cargowise'
                    ? `/api/export/cargowise/${entryId}/download`
                    : `/api/export/${format}/${entryId}`
            const resp = await authFetch(urlPath)
            if (!resp.ok) return
            const blob = await resp.blob()
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            const ext = format === 'pdf' ? 'pdf' : format === 'excel' ? 'xlsx' : 'xml'
            a.download = `CBP_7501_${entry?.entry_number || entryId.slice(0, 8)}.${ext}`
            a.click()
            URL.revokeObjectURL(url)
        } catch (err) {
            console.error('Export failed:', err)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
            </div>
        )
    }

    if (error || !entry) {
        return (
            <div className="text-center py-12">
                <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
                <p className="text-gray-600 mb-4">{error || 'Entry not found'}</p>
                <Button variant="secondary" onClick={() => navigate('/entries')}>
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Back to Entries
                </Button>
            </div>
        )
    }

    const nextLineNumber = Math.max(...entry.lines.map(l => l.line_number), 0) + 1

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div>
                    <button
                        onClick={() => navigate('/entries')}
                        className="flex items-center gap-1 text-gray-500 hover:text-gray-700 mb-2"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        <span className="text-sm">Back to Entries</span>
                    </button>
                    <div className="flex items-center gap-4">
                        <h1 className="text-3xl font-bold text-gray-900">
                            {entry.entry_number || <span className="text-gray-400">Draft Entry</span>}
                        </h1>
                        <StatusBadge status={entry.status} />
                    </div>
                    <p className="text-gray-500 mt-1">
                        {getEntryTypeName(entry.entry_type)} • Created {new Date(entry.created_at).toLocaleString()}
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <Button onClick={() => refetch()} variant="secondary" disabled={loading || actionLoading}>
                        <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                    <Button onClick={handleCalculate} variant="secondary" disabled={actionLoading}>
                        <Calculator className="w-4 h-4 mr-2" />
                        Calculate
                    </Button>
                    <Button onClick={handleValidate} variant="secondary" disabled={actionLoading}>
                        <CheckCircle className="w-4 h-4 mr-2" />
                        Validate
                    </Button>
                    {entry.status === 'ready_to_file' && (
                        <p className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-md px-3 py-2 max-w-xs">
                            Broker OK complete — use <strong>File to ACE</strong> in the ACE panel (single filing path).
                        </p>
                    )}
                </div>
            </div>

            {/* Validation Result */}
            {validationResult && (
                <Card className={validationResult.valid ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}>
                    <CardContent className="py-4">
                        <div className="flex items-start gap-3">
                            {validationResult.valid ? (
                                <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                            ) : (
                                <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                            )}
                            <div>
                                <p className={`font-medium ${validationResult.valid ? 'text-green-700' : 'text-red-700'}`}>
                                    {validationResult.valid ? 'Entry is valid and ready to file' : 'Entry has validation errors'}
                                </p>
                                {validationResult.errors?.length > 0 && (
                                    <ul className="mt-2 space-y-1">
                                        {validationResult.errors.map((err: any, i: number) => (
                                            <li key={i} className="text-sm text-red-600">• {err.message}</li>
                                        ))}
                                    </ul>
                                )}
                                {validationResult.warnings?.length > 0 && (
                                    <ul className="mt-2 space-y-1">
                                        {validationResult.warnings.map((warn: any, i: number) => (
                                            <li key={i} className="text-sm text-yellow-600">⚠ {warn.message}</li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Summary Cards */}
            <div className="grid grid-cols-5 gap-4">
                <Card>
                    <CardContent className="pt-4">
                        <p className="text-sm text-gray-500">Entered Value</p>
                        <p className="text-2xl font-bold text-gray-900">{formatCurrency(entry.total_entered_value)}</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <p className="text-sm text-gray-500">Base Duty</p>
                        <p className="text-2xl font-bold text-gray-900">{formatCurrency(entry.total_duty)}</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <p className="text-sm text-gray-500">Section 301</p>
                        <p className={`text-2xl font-bold ${entry.section_301_amount > 0 ? 'text-orange-600' : 'text-gray-400'}`}>
                            {formatCurrency(entry.section_301_amount)}
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <p className="text-sm text-gray-500">MPF + HMF</p>
                        <p className="text-2xl font-bold text-gray-900">
                            {formatCurrency(entry.mpf_amount + entry.hmf_amount)}
                        </p>
                    </CardContent>
                </Card>
                <Card className="bg-blue-50 border-blue-200">
                    <CardContent className="pt-4">
                        <p className="text-sm text-blue-600">Total Due</p>
                        <p className="text-2xl font-bold text-blue-700">{formatCurrency(entry.total_amount_due)}</p>
                    </CardContent>
                </Card>
            </div>

            {/* Main Content Grid */}
            <div className="grid grid-cols-3 gap-6">
                {/* Left Column - Entry Details */}
                <div className="col-span-2 space-y-6">
                    {/* Entry Info */}
                    <Card>
                        <CardHeader>
                            <SectionHeader icon={FileText} title="Entry Information" />
                        </CardHeader>
                        <CardContent>
                            <div className="grid grid-cols-3 gap-4">
                                <div>
                                    <p className="text-sm text-gray-500">Entry Number</p>
                                    <p className="font-medium">{entry.entry_number || '-'}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Entry Type</p>
                                    <p className="font-medium">{getEntryTypeName(entry.entry_type)}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Port of Entry</p>
                                    <p className="font-medium">{entry.port_of_entry || '-'}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Entry Date</p>
                                    <p className="font-medium">
                                        {entry.entry_date ? new Date(entry.entry_date).toLocaleDateString() : '-'}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Import Date</p>
                                    <p className="font-medium">
                                        {entry.import_date ? new Date(entry.import_date).toLocaleDateString() : '-'}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Mode of Transport</p>
                                    <p className="font-medium">{entry.mode_of_transport || '-'}</p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Transport & Importer */}
                    <Card>
                        <CardHeader>
                            <SectionHeader icon={Ship} title="Transport & Parties" />
                        </CardHeader>
                        <CardContent>
                            <div className="grid grid-cols-2 gap-6">
                                <div className="space-y-3">
                                    <h4 className="font-medium text-gray-700 flex items-center gap-2">
                                        <Anchor className="w-4 h-4" /> Transport
                                    </h4>
                                    <div>
                                        <p className="text-sm text-gray-500">Bill of Lading</p>
                                        <p className="font-medium">{entry.bill_of_lading || '-'}</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-gray-500">Vessel</p>
                                        <p className="font-medium">{entry.vessel_name || '-'}</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-gray-500">Carrier</p>
                                        <p className="font-medium">{entry.carrier_code || '-'}</p>
                                    </div>
                                </div>
                                <div className="space-y-3">
                                    <h4 className="font-medium text-gray-700 flex items-center gap-2">
                                        <Building className="w-4 h-4" /> Importer
                                    </h4>
                                    <div>
                                        <p className="text-sm text-gray-500">Importer of Record</p>
                                        <p className="font-medium">{entry.importer_of_record_name || '-'}</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-gray-500">IOR Number</p>
                                        <p className="font-medium">{entry.importer_of_record_number || '-'}</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-gray-500">Consignee</p>
                                        <p className="font-medium">{entry.ultimate_consignee_name || '-'}</p>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Tabs */}
                    <div className="border-b border-gray-200">
                        <nav className="flex gap-6">
                            {[
                                { id: 'lines', label: 'Line Items', icon: Package, count: entry.lines.length },
                                { id: 'parties', label: 'Parties', icon: Users, count: entry.parties.length },
                                { id: 'documents', label: 'Documents', icon: FileText, count: entry.documents.length },
                                { id: 'history', label: 'History', icon: History, count: entry.status_history.length },
                            ].map(tab => (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id as any)}
                                    className={`flex items-center gap-2 py-3 border-b-2 transition-colors ${activeTab === tab.id
                                        ? 'border-blue-600 text-blue-600'
                                        : 'border-transparent text-gray-500 hover:text-gray-700'
                                        }`}
                                >
                                    <tab.icon className="w-4 h-4" />
                                    {tab.label}
                                    <span className="px-1.5 py-0.5 bg-gray-100 rounded-full text-xs">{tab.count}</span>
                                </button>
                            ))}
                        </nav>
                    </div>

                    {/* Tab Content */}
                    {activeTab === 'lines' && (
                        <Card>
                            <CardHeader>
                                <div className="flex items-center justify-between">
                                    <CardTitle>Line Items</CardTitle>
                                    <Button
                                        size="sm"
                                        onClick={() => {
                                            setEditingLine(null)
                                            setShowAddLineModal(true)
                                        }}
                                    >
                                        <Plus className="w-4 h-4 mr-2" />
                                        Add Line
                                    </Button>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {entry.lines.length === 0 ? (
                                    <div className="text-center py-8">
                                        <Package className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                                        <p className="text-gray-500 mb-3">No line items yet</p>
                                        <Button
                                            size="sm"
                                            onClick={() => {
                                                setEditingLine(null)
                                                setShowAddLineModal(true)
                                            }}
                                        >
                                            <Plus className="w-4 h-4 mr-2" />
                                            Add First Line
                                        </Button>
                                    </div>
                                ) : (
                                    <table className="w-full">
                                        <thead>
                                            <tr className="border-b text-left">
                                                <th className="py-2 text-sm font-medium text-gray-500">#</th>
                                                <th className="py-2 text-sm font-medium text-gray-500">HTS Code</th>
                                                <th className="py-2 text-sm font-medium text-gray-500">Description</th>
                                                <th className="py-2 text-sm font-medium text-gray-500">Origin</th>
                                                <th className="py-2 text-sm font-medium text-gray-500 text-right">Value</th>
                                                <th className="py-2 text-sm font-medium text-gray-500 text-right">Duty</th>
                                                <th className="py-2 text-sm font-medium text-gray-500 text-right">Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {entry.lines.map(line => (
                                                <tr key={line.id} className="border-b border-gray-100">
                                                    <td className="py-3">{line.line_number}</td>
                                                    <td className="py-3 font-mono text-sm">
                                                        {line.hts_code || (
                                                            <span className="text-amber-600 text-xs font-sans font-medium">Unclassified</span>
                                                        )}
                                                    </td>
                                                    <td className="py-3">
                                                        <p className="text-sm truncate max-w-[200px]">{line.product_description || '-'}</p>
                                                        {line.hts_description && (
                                                            <p className="text-xs text-gray-400 truncate max-w-[200px]">{line.hts_description}</p>
                                                        )}
                                                    </td>
                                                    <td className="py-3">
                                                        <span className="inline-flex items-center gap-1">
                                                            <Globe className="w-3 h-3 text-gray-400" />
                                                            {line.country_of_origin || '-'}
                                                        </span>
                                                    </td>
                                                    <td className="py-3 text-right font-medium">{formatCurrency(line.entered_value)}</td>
                                                    <td className="py-3 text-right">
                                                        <span className={line.total_line_duty > 0 ? 'text-blue-600 font-medium' : 'text-gray-400'}>
                                                            {formatCurrency(line.total_line_duty)}
                                                        </span>
                                                        {line.fta_eligible && (
                                                            <span className="ml-2 text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">FTA</span>
                                                        )}
                                                    </td>
                                                    <td className="py-3 text-right">
                                                        <div className="inline-flex items-center gap-1">
                                                            <button
                                                                type="button"
                                                                title="Edit line item"
                                                                onClick={() => {
                                                                    setEditingLine(line)
                                                                    setShowAddLineModal(true)
                                                                }}
                                                                className="p-1.5 text-gray-500 hover:text-blue-600 rounded hover:bg-blue-50"
                                                            >
                                                                <Edit className="w-3.5 h-3.5" />
                                                            </button>
                                                            <button
                                                                type="button"
                                                                title="Delete line item"
                                                                onClick={() => handleDeleteLine(line.id)}
                                                                className="p-1.5 text-gray-400 hover:text-red-600 rounded hover:bg-red-50"
                                                            >
                                                                <Trash2 className="w-3.5 h-3.5" />
                                                            </button>
                                                        </div>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                        <tfoot>
                                            <tr className="bg-gray-50 font-medium">
                                                <td colSpan={4} className="py-3 text-right">Total</td>
                                                <td className="py-3 text-right">{formatCurrency(entry.total_entered_value)}</td>
                                                <td className="py-3 text-right text-blue-600">{formatCurrency(entry.total_amount_due)}</td>
                                                <td />
                                            </tr>
                                        </tfoot>
                                    </table>
                                )}
                            </CardContent>
                        </Card>
                    )}

                    {activeTab === 'parties' && (
                        <Card>
                            <CardContent className="py-6">
                                {entry.parties.length === 0 ? (
                                    <div className="text-center py-8">
                                        <Users className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                                        <p className="text-gray-500">No additional parties</p>
                                    </div>
                                ) : (
                                    <div className="space-y-4">
                                        {entry.parties.map(party => (
                                            <div key={party.id} className="p-4 bg-gray-50 rounded-lg">
                                                <p className="text-sm text-gray-500 uppercase">{party.role.replace('_', ' ')}</p>
                                                <p className="font-medium">{party.name}</p>
                                                {party.address_line_1 && (
                                                    <p className="text-sm text-gray-600">
                                                        {party.address_line_1}, {party.city}, {party.state_province} {party.postal_code}
                                                    </p>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}

                    {activeTab === 'documents' && (
                        <Card>
                            <CardContent className="py-6">
                                {entry.documents.length === 0 ? (
                                    <div className="text-center py-8">
                                        <FileText className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                                        <p className="text-gray-500">No documents linked</p>
                                    </div>
                                ) : (
                                    <div className="space-y-4">
                                        <div className="space-y-2">
                                            {entry.documents.map(doc => {
                                                const activeDocId = selectedPreviewDocId || entry.documents[0]?.document_id
                                                const isSelected = activeDocId === doc.document_id
                                                return (
                                                    <div
                                                        key={doc.id}
                                                        className={`flex items-center justify-between p-3 rounded-lg border ${
                                                            isSelected ? 'bg-blue-50 border-blue-200' : 'bg-gray-50 border-transparent'
                                                        }`}
                                                    >
                                                        <div className="flex items-center gap-3">
                                                            <FileText className="w-5 h-5 text-blue-500" />
                                                            <div>
                                                                <p className="font-medium">{doc.document_type || 'Source Document'}</p>
                                                                <p className="text-xs text-gray-500 font-mono">{doc.document_id}</p>
                                                            </div>
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            {doc.is_primary && (
                                                                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">Primary</span>
                                                            )}
                                                            <button
                                                                type="button"
                                                                onClick={() => setSelectedPreviewDocId(doc.document_id)}
                                                                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-gray-700 bg-white border border-gray-200 rounded hover:bg-gray-100"
                                                            >
                                                                <Eye className="w-3.5 h-3.5" />
                                                                Preview
                                                            </button>
                                                            <button
                                                                type="button"
                                                                onClick={() => handleDownloadDoc(doc.document_id)}
                                                                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-blue-600 bg-white border border-gray-200 rounded hover:bg-blue-50"
                                                            >
                                                                <Download className="w-3.5 h-3.5" />
                                                                Download
                                                            </button>
                                                        </div>
                                                    </div>
                                                )
                                            })}
                                        </div>

                                        <DocumentViewer
                                            documentId={selectedPreviewDocId || entry.documents[0]?.document_id}
                                            filename={`entry_doc_${(selectedPreviewDocId || entry.documents[0]?.document_id || '').slice(0, 8)}.pdf`}
                                            fileType="pdf"
                                        />
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}

                    {activeTab === 'history' && (
                        <Card>
                            <CardContent className="py-6">
                                <div className="space-y-4">
                                    {entry.status_history.map((hist, i) => (
                                        <div key={i} className="flex items-start gap-4">
                                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
                                                <History className="w-4 h-4 text-gray-500" />
                                            </div>
                                            <div>
                                                <p className="font-medium">
                                                    {hist.from_status ? (
                                                        <>
                                                            <span className="text-gray-500">{getStatusInfo(hist.from_status).label}</span>
                                                            {' → '}
                                                        </>
                                                    ) : null}
                                                    <StatusBadge status={hist.to_status} />
                                                </p>
                                                <p className="text-sm text-gray-500">
                                                    {new Date(hist.changed_at).toLocaleString()} by {hist.changed_by || 'System'}
                                                </p>
                                                {hist.reason && <p className="text-sm text-gray-600 mt-1">{hist.reason}</p>}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </div>

                {/* Right Column - Quick Actions & Status */}
                <div className="space-y-6">
                    {/* Broker OK gate */}
                    <Card className={entry.broker_ok?.ok || entry.status === 'ready_to_file' ? 'border-emerald-200 bg-emerald-50/40' : 'border-amber-200'}>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base flex items-center gap-2">
                                <CheckCircle className="w-4 h-4" />
                                Broker OK
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3 text-sm">
                            {entry.broker_ok?.ok || entry.status === 'ready_to_file' ? (
                                <div className="space-y-1 text-emerald-900">
                                    <p className="font-medium">Signed off</p>
                                    {entry.broker_ok?.by && (
                                        <p className="text-xs">By {entry.broker_ok.by}{entry.broker_ok.at ? ` · ${new Date(entry.broker_ok.at).toLocaleString()}` : ''}</p>
                                    )}
                                    {entry.broker_ok?.notes && (
                                        <p className="text-xs text-emerald-800/80">{entry.broker_ok.notes}</p>
                                    )}
                                    <p className="text-xs pt-1">Entry is Ready to File — use ACE panel to submit.</p>
                                </div>
                            ) : (
                                <>
                                    <p className="text-amber-900 text-xs">
                                        Licensed broker confirms HTS / values before ACE. Required to unlock filing.
                                    </p>
                                    <label className="flex items-center gap-2">
                                        <input type="checkbox" checked={brokerHtsOk} onChange={(e) => setBrokerHtsOk(e.target.checked)} />
                                        HTS classifications confirmed
                                    </label>
                                    <label className="flex items-center gap-2">
                                        <input type="checkbox" checked={brokerValuesOk} onChange={(e) => setBrokerValuesOk(e.target.checked)} />
                                        Entered values confirmed
                                    </label>
                                    <div>
                                        <label className="block text-xs text-slate-600 mb-1">AD/CVD notes</label>
                                        <input
                                            value={brokerAdcvd}
                                            onChange={(e) => setBrokerAdcvd(e.target.value)}
                                            className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
                                            placeholder="note-only / HOLD / N/A"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs text-slate-600 mb-1">Notes (optional)</label>
                                        <textarea
                                            value={brokerNotes}
                                            onChange={(e) => setBrokerNotes(e.target.value)}
                                            rows={2}
                                            className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
                                            placeholder="Scope memo, FCC, etc."
                                        />
                                    </div>
                                    {actionError && (
                                        <p className="text-xs text-red-600">{actionError}</p>
                                    )}
                                    <Button
                                        className="w-full"
                                        onClick={handleBrokerOk}
                                        disabled={actionLoading || !brokerHtsOk || !brokerValuesOk}
                                    >
                                        <CheckCircle className="w-4 h-4 mr-2" />
                                        Record Broker OK → Ready to File
                                    </Button>
                                </>
                            )}
                        </CardContent>
                    </Card>

                    {/* Quick Actions */}
                    <Card>
                        <CardHeader>
                            <CardTitle>Actions</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            {entry.status === 'draft' && (
                                <Button
                                    variant="secondary"
                                    className="w-full justify-start"
                                    onClick={() => handleStatusChange('pending_review')}
                                >
                                    <Send className="w-4 h-4 mr-2" />
                                    Send to entry review queue
                                </Button>
                            )}
                            {(entry.status === 'pending_review' || entry.status === 'ready_to_file') && (
                                <Button
                                    variant="secondary"
                                    className="w-full justify-start text-red-600"
                                    onClick={() => handleStatusChange('draft')}
                                >
                                    <XCircle className="w-4 h-4 mr-2" />
                                    Return to Draft
                                </Button>
                            )}
                            <Button
                                variant="secondary"
                                className="w-full justify-start"
                                onClick={() => setShowEditEntryModal(true)}
                            >
                                <Edit className="w-4 h-4 mr-2" />
                                Edit Entry
                            </Button>
                            <div className="pt-2 border-t border-gray-100 space-y-2">
                                <Button
                                    variant="secondary"
                                    className="w-full justify-start"
                                    onClick={() => handleExport('pdf')}
                                >
                                    <Download className="w-4 h-4 mr-2" />
                                    Export Form 7501 (PDF)
                                </Button>
                                <Button
                                    variant="secondary"
                                    className="w-full justify-start"
                                    onClick={() => handleExport('excel')}
                                >
                                    <Download className="w-4 h-4 mr-2" />
                                    Export Summary (Excel)
                                </Button>
                                <Button
                                    variant="secondary"
                                    className="w-full justify-start"
                                    onClick={() => handleExport('cargowise')}
                                >
                                    <Download className="w-4 h-4 mr-2" />
                                    Export CargoWise (XML)
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    {/* ACE Status Panel */}
                    <ACEStatusPanel
                        entryId={entryId || ''}
                        onStatusChange={refetch}
                    />

                    {/* Duty Breakdown */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <DollarSign className="w-5 h-5" />
                                Duty Breakdown
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <div className="flex justify-between">
                                <span className="text-gray-500">Base Duty</span>
                                <span className="font-medium">{formatCurrency(entry.total_duty)}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-gray-500">Section 301</span>
                                <span className={entry.section_301_amount > 0 ? 'font-medium text-orange-600' : 'text-gray-400'}>
                                    {formatCurrency(entry.section_301_amount)}
                                </span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-gray-500">Section 232</span>
                                <span className={entry.section_232_amount > 0 ? 'font-medium' : 'text-gray-400'}>
                                    {formatCurrency(entry.section_232_amount)}
                                </span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-gray-500">ADD</span>
                                <span className={entry.add_amount > 0 ? 'font-medium text-red-600' : 'text-gray-400'}>
                                    {formatCurrency(entry.add_amount)}
                                </span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-gray-500">CVD</span>
                                <span className={entry.cvd_amount > 0 ? 'font-medium text-red-600' : 'text-gray-400'}>
                                    {formatCurrency(entry.cvd_amount)}
                                </span>
                            </div>
                            <hr />
                            <div className="flex justify-between">
                                <span className="text-gray-500">MPF</span>
                                <span className="font-medium">{formatCurrency(entry.mpf_amount)}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-gray-500">HMF</span>
                                <span className="font-medium">{formatCurrency(entry.hmf_amount)}</span>
                            </div>
                            <hr />
                            <div className="flex justify-between text-lg">
                                <span className="font-semibold">Total</span>
                                <span className="font-bold text-blue-600">{formatCurrency(entry.total_amount_due)}</span>
                            </div>
                        </CardContent>
                    </Card>

                    {/* PGA Compliance & POA Check */}
                    {pgaData && (
                        <Card className={pgaData.pga_required ? 'border-amber-200 bg-amber-50' : 'border-green-200 bg-green-50'}>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-base flex items-center justify-between">
                                    <span>PGA & Compliance Check</span>
                                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                                        pgaData.pga_required
                                            ? 'bg-amber-200 text-amber-900'
                                            : 'bg-green-200 text-green-900'
                                    }`}>
                                        {pgaData.pga_required ? 'PGA Required' : 'Cleared'}
                                    </span>
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="text-sm space-y-2">
                                {pgaData.pga_required ? (
                                    <div>
                                        <p className="text-amber-800 font-medium">
                                            Agencies flagged: {(pgaData.agencies || []).join(', ')}
                                        </p>
                                        <p className="text-xs text-amber-700 mt-1">
                                            Ensure PGA Message Set (FDA Prior Notice / EPA TSCA / USDA Lacey) is attached before ACE transmission.
                                        </p>
                                    </div>
                                ) : (
                                    <p className="text-green-800 text-xs">
                                        ✓ No additional FDA / EPA / USDA PGA message sets required for the current HTS lines.
                                    </p>
                                )}
                            </CardContent>
                        </Card>
                    )}

                    {/* Notes */}
                    {entry.notes && (
                        <Card>
                            <CardHeader>
                                <CardTitle>Notes</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <p className="text-sm text-gray-600">{entry.notes}</p>
                            </CardContent>
                        </Card>
                    )}
                </div>
            </div>

            {/* Add / Edit Line Modal */}
            <AddLineModal
                isOpen={showAddLineModal}
                onClose={() => {
                    setEditingLine(null)
                    setShowAddLineModal(false)
                }}
                onSave={handleSaveLine}
                nextLineNumber={nextLineNumber}
                initialLine={editingLine}
            />

            {/* Edit Entry Modal */}
            {showEditEntryModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl p-6 max-h-[90vh] overflow-y-auto">
                        <h3 className="text-lg font-semibold mb-4">Edit CBP Form 7501 Entry Header</h3>
                        <form onSubmit={handleSaveEntryHeader} className="space-y-4">
                            <div className="grid grid-cols-3 gap-4">
                                <div>
                                    <label className="block text-xs font-medium text-gray-700 mb-1">Entry Number</label>
                                    <input
                                        type="text"
                                        value={editForm.entry_number || ''}
                                        onChange={(e) => setEditForm(prev => ({ ...prev, entry_number: e.target.value }))}
                                        placeholder="e.g. 999-1234567-8"
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium text-gray-700 mb-1">Entry Type</label>
                                    <select
                                        value={editForm.entry_type || '01'}
                                        onChange={(e) => setEditForm(prev => ({ ...prev, entry_type: e.target.value }))}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                                    >
                                        <option value="01">01 - Consumption</option>
                                        <option value="02">02 - Consumption Quota</option>
                                        <option value="03">03 - AD/CVD</option>
                                        <option value="06">06 - FTZ Consumption</option>
                                        <option value="11">11 - Informal</option>
                                        <option value="21">21 - Warehouse</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-xs font-medium text-gray-700 mb-1">Port of Entry (4-digit)</label>
                                    <input
                                        type="text"
                                        value={editForm.port_of_entry || ''}
                                        onChange={(e) => setEditForm(prev => ({ ...prev, port_of_entry: e.target.value }))}
                                        placeholder="2704"
                                        maxLength={4}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono"
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-medium text-gray-700 mb-1">Importer of Record Name</label>
                                    <input
                                        type="text"
                                        value={editForm.importer_of_record_name || ''}
                                        onChange={(e) => setEditForm(prev => ({ ...prev, importer_of_record_name: e.target.value }))}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium text-gray-700 mb-1">Importer IOR Number (EIN)</label>
                                    <input
                                        type="text"
                                        value={editForm.importer_of_record_number || ''}
                                        onChange={(e) => setEditForm(prev => ({ ...prev, importer_of_record_number: e.target.value }))}
                                        placeholder="12-345678900"
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono"
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-3 gap-4">
                                <div>
                                    <label className="block text-xs font-medium text-gray-700 mb-1">Bill of Lading</label>
                                    <input
                                        type="text"
                                        value={editForm.bill_of_lading || ''}
                                        onChange={(e) => setEditForm(prev => ({ ...prev, bill_of_lading: e.target.value }))}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium text-gray-700 mb-1">Vessel Name</label>
                                    <input
                                        type="text"
                                        value={editForm.vessel_name || ''}
                                        onChange={(e) => setEditForm(prev => ({ ...prev, vessel_name: e.target.value }))}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium text-gray-700 mb-1">Carrier SCAC</label>
                                    <input
                                        type="text"
                                        value={editForm.carrier_code || ''}
                                        onChange={(e) => setEditForm(prev => ({ ...prev, carrier_code: e.target.value.toUpperCase() }))}
                                        maxLength={4}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono uppercase"
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-xs font-medium text-gray-700 mb-1">Ultimate Consignee Name</label>
                                <input
                                    type="text"
                                    value={editForm.ultimate_consignee_name || ''}
                                    onChange={(e) => setEditForm(prev => ({ ...prev, ultimate_consignee_name: e.target.value }))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-medium text-gray-700 mb-1">Broker Notes</label>
                                <textarea
                                    value={editForm.notes || ''}
                                    onChange={(e) => setEditForm(prev => ({ ...prev, notes: e.target.value }))}
                                    rows={3}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                                />
                            </div>

                            <div className="flex justify-end gap-3 pt-4 border-t">
                                <Button
                                    variant="secondary"
                                    type="button"
                                    onClick={() => setShowEditEntryModal(false)}
                                >
                                    Cancel
                                </Button>
                                <Button type="submit" disabled={actionLoading}>
                                    {actionLoading ? 'Saving...' : 'Save Changes'}
                                </Button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    )
}

export default EntryDetailPage
