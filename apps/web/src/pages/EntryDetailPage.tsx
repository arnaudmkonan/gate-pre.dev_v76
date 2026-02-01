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

    Ship,
    Anchor,
    Globe,
    Building,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'
import { ACEStatusPanel } from '../components/ACEStatusPanel'
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

// Add Line Modal
const AddLineModal = ({
    isOpen,
    onClose,
    onAdd,
    nextLineNumber
}: {
    isOpen: boolean
    onClose: () => void
    onAdd: (line: AddLineRequest) => void
    nextLineNumber: number
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
        setFormData(prev => ({ ...prev, line_number: nextLineNumber }))
    }, [nextLineNumber])

    if (!isOpen) return null

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        onAdd(formData)
        setFormData({
            line_number: nextLineNumber + 1,
            hts_code: '',
            product_description: '',
            country_of_origin: '',
            entered_value: 0,
            quantity_1: 1,
        })
    }

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
                <h3 className="text-lg font-semibold mb-4">Add Line Item</h3>
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
                            <input
                                type="text"
                                value={formData.hts_code}
                                onChange={(e) => setFormData(prev => ({ ...prev, hts_code: e.target.value }))}
                                placeholder="8471.30.0100"
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
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
                            <Plus className="w-4 h-4 mr-2" />
                            Add Line
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
    const { updateEntry, addLine, calculateDuties, validateEntry, loading: actionLoading } = useEntryActions()

    const [showAddLineModal, setShowAddLineModal] = useState(false)
    const [validationResult, setValidationResult] = useState<any>(null)
    const [activeTab, setActiveTab] = useState<'lines' | 'parties' | 'documents' | 'history'>('lines')

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

    const handleAddLine = async (lineData: AddLineRequest) => {
        if (!entryId) return
        const result = await addLine(entryId, lineData)
        if (result) {
            setShowAddLineModal(false)
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
                        <Button onClick={() => handleStatusChange('filing')} disabled={actionLoading}>
                            <Send className="w-4 h-4 mr-2" />
                            Submit to ACE
                        </Button>
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
                                    <Button size="sm" onClick={() => setShowAddLineModal(true)}>
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
                                        <Button size="sm" onClick={() => setShowAddLineModal(true)}>
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
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {entry.lines.map(line => (
                                                <tr key={line.id} className="border-b border-gray-100">
                                                    <td className="py-3">{line.line_number}</td>
                                                    <td className="py-3 font-mono text-sm">{line.hts_code || '-'}</td>
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
                                                </tr>
                                            ))}
                                        </tbody>
                                        <tfoot>
                                            <tr className="bg-gray-50 font-medium">
                                                <td colSpan={4} className="py-3 text-right">Total</td>
                                                <td className="py-3 text-right">{formatCurrency(entry.total_entered_value)}</td>
                                                <td className="py-3 text-right text-blue-600">{formatCurrency(entry.total_amount_due)}</td>
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
                                    <div className="space-y-3">
                                        {entry.documents.map(doc => (
                                            <div key={doc.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                                                <div className="flex items-center gap-3">
                                                    <FileText className="w-5 h-5 text-blue-500" />
                                                    <div>
                                                        <p className="font-medium">{doc.document_type || 'Unknown'}</p>
                                                        <p className="text-xs text-gray-500">{doc.document_id}</p>
                                                    </div>
                                                </div>
                                                {doc.is_primary && (
                                                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">Primary</span>
                                                )}
                                            </div>
                                        ))}
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
                    {/* Quick Actions */}
                    <Card>
                        <CardHeader>
                            <CardTitle>Actions</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            {entry.status === 'draft' && (
                                <>
                                    <Button
                                        variant="secondary"
                                        className="w-full justify-start"
                                        onClick={() => handleStatusChange('pending_review')}
                                    >
                                        <Send className="w-4 h-4 mr-2" />
                                        Submit for Review
                                    </Button>
                                </>
                            )}
                            {entry.status === 'pending_review' && (
                                <>
                                    <Button
                                        variant="secondary"
                                        className="w-full justify-start"
                                        onClick={() => handleStatusChange('ready_to_file')}
                                    >
                                        <CheckCircle className="w-4 h-4 mr-2" />
                                        Mark Ready to File
                                    </Button>
                                    <Button
                                        variant="secondary"
                                        className="w-full justify-start text-red-600"
                                        onClick={() => handleStatusChange('draft')}
                                    >
                                        <XCircle className="w-4 h-4 mr-2" />
                                        Return to Draft
                                    </Button>
                                </>
                            )}
                            <Button
                                variant="secondary"
                                className="w-full justify-start"
                                onClick={() => navigate(`/entries/${entryId}/edit`)}
                            >
                                <Edit className="w-4 h-4 mr-2" />
                                Edit Entry
                            </Button>
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

            {/* Add Line Modal */}
            <AddLineModal
                isOpen={showAddLineModal}
                onClose={() => setShowAddLineModal(false)}
                onAdd={handleAddLine}
                nextLineNumber={nextLineNumber}
            />
        </div>
    )
}

export default EntryDetailPage
