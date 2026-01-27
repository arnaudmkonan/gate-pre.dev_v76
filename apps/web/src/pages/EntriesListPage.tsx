/**
 * Entries List Page
 * 
 * Main entry management interface showing all customs entries with
 * filtering, search, and quick actions.
 * 
 * Task 1.3 from ROADMAP_FULL_WORKFLOW.md
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Plus,
    RefreshCw,
    Search,
    Filter,
    FileText,
    DollarSign,
    Package,
    Clock,
    CheckCircle,
    XCircle,
    AlertTriangle,
    Ship,
    Truck,
    Plane,
    ChevronDown,
    MoreHorizontal,
    Eye,
    Edit,
    Trash2,
    Calculator,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import {
    useEntries,
    useEntryActions,
    EntryListItem,
    EntryFilters,
    ENTRY_STATUSES,
    getStatusInfo,
    getEntryTypeName,
    formatCurrency,
} from '../hooks/useEntries'

// Entry status with icon and color
const StatusBadge = ({ status }: { status: string }) => {
    const info = getStatusInfo(status)
    return (
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${info.bgColor} ${info.textColor}`}>
            {info.label}
        </span>
    )
}

// Transport mode icon
const TransportIcon = ({ mode }: { mode?: string | null }) => {
    switch (mode) {
        case '10':
            return <Ship className="w-4 h-4 text-blue-500" />
        case '30':
            return <Truck className="w-4 h-4 text-green-500" />
        case '40':
            return <Plane className="w-4 h-4 text-purple-500" />
        default:
            return <Package className="w-4 h-4 text-gray-400" />
    }
}

export const EntriesListPage = () => {
    const navigate = useNavigate()
    const [filters, setFilters] = useState<EntryFilters>({})
    const [searchTerm, setSearchTerm] = useState('')
    const [showFilters, setShowFilters] = useState(false)
    const [selectedStatus, setSelectedStatus] = useState<string>('')

    const { entries, total, loading, error, refetch } = useEntries(filters)
    const { deleteEntry, loading: actionLoading } = useEntryActions()

    // Debounced search
    useEffect(() => {
        const timer = setTimeout(() => {
            setFilters(prev => ({ ...prev, search: searchTerm || undefined }))
        }, 300)
        return () => clearTimeout(timer)
    }, [searchTerm])

    // Status filter
    useEffect(() => {
        setFilters(prev => ({ ...prev, status: selectedStatus || undefined }))
    }, [selectedStatus])

    const handleCreateEntry = () => {
        navigate('/entries/new')
    }

    const handleViewEntry = (entry: EntryListItem) => {
        navigate(`/entries/${entry.id}`)
    }

    const handleDeleteEntry = async (entry: EntryListItem) => {
        if (!confirm(`Cancel entry ${entry.entry_number || entry.id}?`)) return

        const success = await deleteEntry(entry.id)
        if (success) {
            refetch()
        }
    }

    // Calculate stats from entries
    const stats = {
        draft: entries.filter(e => e.status === 'draft').length,
        pending: entries.filter(e => ['pending_documents', 'pending_review', 'pending_client_approval'].includes(e.status)).length,
        ready: entries.filter(e => e.status === 'ready_to_file').length,
        filed: entries.filter(e => ['filed', 'accepted', 'released', 'liquidated'].includes(e.status)).length,
        totalValue: entries.reduce((sum, e) => sum + (e.total_entered_value || 0), 0),
        totalDuty: entries.reduce((sum, e) => sum + (e.total_amount_due || 0), 0),
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Customs Entries</h1>
                    <p className="text-gray-500 mt-1">Manage import entries and filings</p>
                </div>
                <div className="flex items-center gap-3">
                    <Button onClick={() => refetch()} variant="secondary" disabled={loading}>
                        <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                    <Button onClick={handleCreateEntry}>
                        <Plus className="w-4 h-4 mr-2" />
                        New Entry
                    </Button>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-6 gap-4">
                <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setSelectedStatus('')}>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-blue-100 rounded-lg">
                                <FileText className="w-5 h-5 text-blue-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{total}</p>
                                <p className="text-sm text-gray-500">All Entries</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setSelectedStatus('draft')}>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-gray-100 rounded-lg">
                                <Clock className="w-5 h-5 text-gray-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{stats.draft}</p>
                                <p className="text-sm text-gray-500">Drafts</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setSelectedStatus('pending_review')}>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-yellow-100 rounded-lg">
                                <AlertTriangle className="w-5 h-5 text-yellow-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{stats.pending}</p>
                                <p className="text-sm text-gray-500">Pending</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setSelectedStatus('ready_to_file')}>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-cyan-100 rounded-lg">
                                <CheckCircle className="w-5 h-5 text-cyan-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{stats.ready}</p>
                                <p className="text-sm text-gray-500">Ready</p>
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
                                <p className="text-2xl font-bold">{formatCurrency(stats.totalValue)}</p>
                                <p className="text-sm text-gray-500">Total Value</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-purple-100 rounded-lg">
                                <Calculator className="w-5 h-5 text-purple-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{formatCurrency(stats.totalDuty)}</p>
                                <p className="text-sm text-gray-500">Total Duty</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Search and Filters */}
            <Card>
                <CardContent className="py-4">
                    <div className="flex items-center gap-4">
                        <div className="flex-1 relative">
                            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                            <input
                                type="text"
                                placeholder="Search entries, BOL, importer..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            />
                        </div>
                        <Button
                            variant="secondary"
                            onClick={() => setShowFilters(!showFilters)}
                        >
                            <Filter className="w-4 h-4 mr-2" />
                            Filters
                            <ChevronDown className={`w-4 h-4 ml-2 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
                        </Button>
                    </div>

                    {/* Status Filter Pills */}
                    <div className="flex gap-2 mt-4">
                        {[
                            { value: '', label: 'All' },
                            { value: 'draft', label: 'Draft' },
                            { value: 'pending_review', label: 'Pending' },
                            { value: 'ready_to_file', label: 'Ready' },
                            { value: 'filed', label: 'Filed' },
                            { value: 'accepted', label: 'Accepted' },
                            { value: 'cancelled', label: 'Cancelled' },
                        ].map(status => (
                            <button
                                key={status.value}
                                onClick={() => setSelectedStatus(status.value)}
                                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${selectedStatus === status.value
                                        ? 'bg-blue-600 text-white'
                                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                    }`}
                            >
                                {status.label}
                            </button>
                        ))}
                    </div>

                    {/* Extended Filters */}
                    {showFilters && (
                        <div className="grid grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-200">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Port of Entry</label>
                                <input
                                    type="text"
                                    value={filters.port || ''}
                                    onChange={(e) => setFilters(prev => ({ ...prev, port: e.target.value || undefined }))}
                                    placeholder="Port code..."
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Date From</label>
                                <input
                                    type="date"
                                    value={filters.date_from || ''}
                                    onChange={(e) => setFilters(prev => ({ ...prev, date_from: e.target.value || undefined }))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Date To</label>
                                <input
                                    type="date"
                                    value={filters.date_to || ''}
                                    onChange={(e) => setFilters(prev => ({ ...prev, date_to: e.target.value || undefined }))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                                />
                            </div>
                            <div className="flex items-end">
                                <Button
                                    variant="secondary"
                                    onClick={() => {
                                        setFilters({})
                                        setSearchTerm('')
                                        setSelectedStatus('')
                                    }}
                                >
                                    Clear Filters
                                </Button>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Error State */}
            {error && (
                <div className="flex gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
                    <XCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-red-600">{error}</p>
                </div>
            )}

            {/* Entries Table */}
            <Card>
                <CardHeader>
                    <CardTitle>
                        {selectedStatus ? getStatusInfo(selectedStatus).label : 'All'} Entries ({entries.length} of {total})
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <div className="flex items-center justify-center py-12">
                            <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
                        </div>
                    ) : entries.length === 0 ? (
                        <div className="text-center py-12">
                            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                            <p className="text-gray-500 mb-4">No entries found</p>
                            <Button onClick={handleCreateEntry}>
                                <Plus className="w-4 h-4 mr-2" />
                                Create First Entry
                            </Button>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b border-gray-200">
                                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Entry</th>
                                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Status</th>
                                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Importer</th>
                                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Port</th>
                                        <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Value</th>
                                        <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Duty</th>
                                        <th className="text-center py-3 px-4 text-sm font-medium text-gray-500">Lines</th>
                                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Date</th>
                                        <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {entries.map((entry) => (
                                        <tr
                                            key={entry.id}
                                            className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                                            onClick={() => handleViewEntry(entry)}
                                        >
                                            <td className="py-3 px-4">
                                                <div>
                                                    <p className="font-medium text-gray-900">
                                                        {entry.entry_number || <span className="text-gray-400 italic">Pending</span>}
                                                    </p>
                                                    <p className="text-xs text-gray-500">
                                                        {getEntryTypeName(entry.entry_type)} • {entry.bill_of_lading || 'No BOL'}
                                                    </p>
                                                </div>
                                            </td>
                                            <td className="py-3 px-4">
                                                <StatusBadge status={entry.status} />
                                            </td>
                                            <td className="py-3 px-4">
                                                <p className="text-sm text-gray-900 truncate max-w-[200px]">
                                                    {entry.importer_name || '-'}
                                                </p>
                                            </td>
                                            <td className="py-3 px-4">
                                                <span className="text-sm text-gray-600">{entry.port_of_entry || '-'}</span>
                                            </td>
                                            <td className="py-3 px-4 text-right">
                                                <span className="font-medium text-gray-900">
                                                    {formatCurrency(entry.total_entered_value)}
                                                </span>
                                            </td>
                                            <td className="py-3 px-4 text-right">
                                                <span className={`font-medium ${entry.total_amount_due > 0 ? 'text-blue-600' : 'text-gray-400'}`}>
                                                    {formatCurrency(entry.total_amount_due)}
                                                </span>
                                            </td>
                                            <td className="py-3 px-4 text-center">
                                                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-gray-100 text-xs font-medium">
                                                    {entry.line_count}
                                                </span>
                                            </td>
                                            <td className="py-3 px-4">
                                                <span className="text-sm text-gray-500">
                                                    {entry.entry_date
                                                        ? new Date(entry.entry_date).toLocaleDateString()
                                                        : new Date(entry.created_at).toLocaleDateString()}
                                                </span>
                                            </td>
                                            <td className="py-3 px-4 text-right">
                                                <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                                                    <button
                                                        className="p-1.5 rounded hover:bg-gray-100"
                                                        title="View"
                                                        onClick={() => handleViewEntry(entry)}
                                                    >
                                                        <Eye className="w-4 h-4 text-gray-500" />
                                                    </button>
                                                    <button
                                                        className="p-1.5 rounded hover:bg-gray-100"
                                                        title="Edit"
                                                        onClick={() => navigate(`/entries/${entry.id}/edit`)}
                                                    >
                                                        <Edit className="w-4 h-4 text-gray-500" />
                                                    </button>
                                                    {entry.status === 'draft' && (
                                                        <button
                                                            className="p-1.5 rounded hover:bg-red-50"
                                                            title="Cancel"
                                                            onClick={() => handleDeleteEntry(entry)}
                                                        >
                                                            <Trash2 className="w-4 h-4 text-red-500" />
                                                        </button>
                                                    )}
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}

export default EntriesListPage
