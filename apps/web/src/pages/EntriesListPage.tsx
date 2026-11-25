/**
 * Entries List Page — broker ops worklist as a real table.
 */
import { useState, useEffect, Fragment } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
    Plus,
    RefreshCw,
    Search,
    Filter,
    FileText,
    DollarSign,
    Clock,
    CheckCircle,
    XCircle,
    AlertTriangle,
    ChevronDown,
    ChevronRight,
    Eye,
    Edit,
    Trash2,
    Calculator,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'
import { useAuth } from '../contexts/AuthContext'
import {
    useEntries,
    useEntryActions,
    EntryListItem,
    EntryFilters,
    EntryLine,
    getStatusInfo,
    getEntryTypeName,
    formatCurrency,
} from '../hooks/useEntries'
import { apiClient } from '../lib/apiClient'
import { API_URL } from '../config/api'

const StatusBadge = ({ status }: { status: string }) => {
    const info = getStatusInfo(status)
    return (
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${info.bgColor} ${info.textColor}`}>
            {info.label}
        </span>
    )
}

export const EntriesListPage = () => {
    const navigate = useNavigate()
    const { user } = useAuth()
    const [filters, setFilters] = useState<EntryFilters>({})
    const [searchTerm, setSearchTerm] = useState('')
    const [showFilters, setShowFilters] = useState(false)
    const [selectedStatus, setSelectedStatus] = useState<string>('')
    const [expandedId, setExpandedId] = useState<string | null>(null)
    const [linesByEntry, setLinesByEntry] = useState<Record<string, EntryLine[]>>({})
    const [linesLoading, setLinesLoading] = useState<string | null>(null)

    const { entries, total, loading, error, refetch } = useEntries(filters)
    const { deleteEntry, updateLine, loading: lineSaving } = useEntryActions()
    const [editingLineId, setEditingLineId] = useState<string | null>(null)
    const [editDraft, setEditDraft] = useState<{ hts_code: string; country_of_origin: string; entered_value: string }>({
        hts_code: '',
        country_of_origin: '',
        entered_value: '',
    })
    const [lineSaveError, setLineSaveError] = useState<string | null>(null)

    const isImporterPortal = Boolean(user?.role === 'user' || user?.role === 'readonly') && Boolean(user?.client_id)
    const isBrokerStaff = user?.role === 'admin' || user?.role === 'broker_staff'

    useEffect(() => {
        const timer = setTimeout(() => {
            setFilters((prev) => ({ ...prev, search: searchTerm || undefined }))
        }, 300)
        return () => clearTimeout(timer)
    }, [searchTerm])

    useEffect(() => {
        setFilters((prev) => ({ ...prev, status: selectedStatus || undefined }))
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
        if (success) refetch()
    }

    const startEditLine = (line: EntryLine) => {
        setEditingLineId(line.id)
        setLineSaveError(null)
        setEditDraft({
            hts_code: line.hts_code || '',
            country_of_origin: line.country_of_origin || '',
            entered_value: String(line.entered_value ?? ''),
        })
    }

    const saveEditLine = async (entryId: string, lineId: string) => {
        setLineSaveError(null)
        const value = Number(editDraft.entered_value)
        if (Number.isNaN(value) || value < 0) {
            setLineSaveError('Entered value must be a number')
            return
        }
        const updated = await updateLine(entryId, lineId, {
            hts_code: editDraft.hts_code || undefined,
            country_of_origin: editDraft.country_of_origin || undefined,
            entered_value: value,
        })
        if (!updated) {
            setLineSaveError('Failed to save line — open entry for details')
            return
        }
        setEditingLineId(null)
        // Refresh cached lines + header totals
        try {
            const resp = await apiClient.get<{ lines: EntryLine[] }>(`${API_URL}/api/entries/${entryId}/lines`)
            setLinesByEntry((prev) => ({ ...prev, [entryId]: resp.data.lines || [] }))
        } catch {
            /* ignore */
        }
        refetch()
    }

    const toggleExpand = async (entry: EntryListItem, e: React.MouseEvent) => {
        e.stopPropagation()
        if (expandedId === entry.id) {
            setExpandedId(null)
            return
        }
        setExpandedId(entry.id)
        if (linesByEntry[entry.id]) return
        setLinesLoading(entry.id)
        try {
            const resp = await apiClient.get<{ lines: EntryLine[] }>(
                `${API_URL}/api/entries/${entry.id}/lines`
            )
            setLinesByEntry((prev) => ({
                ...prev,
                [entry.id]: resp.data.lines || (resp.data as unknown as EntryLine[]) || [],
            }))
        } catch {
            // Fallback: open detail if lines endpoint shape differs
            try {
                const detail = await apiClient.get<{ lines: EntryLine[] }>(
                    `${API_URL}/api/entries/${entry.id}`
                )
                setLinesByEntry((prev) => ({
                    ...prev,
                    [entry.id]: detail.data.lines || [],
                }))
            } catch {
                setLinesByEntry((prev) => ({ ...prev, [entry.id]: [] }))
            }
        } finally {
            setLinesLoading(null)
        }
    }

    const stats = {
        draft: entries.filter((e) => e.status === 'draft').length,
        pending: entries.filter((e) =>
            ['pending_documents', 'pending_review', 'pending_client_approval'].includes(e.status)
        ).length,
        ready: entries.filter((e) => e.status === 'ready_to_file').length,
        filed: entries.filter((e) =>
            ['filed', 'accepted', 'released', 'liquidated'].includes(e.status)
        ).length,
        totalValue: entries.reduce((sum, e) => sum + (e.total_entered_value || 0), 0),
        totalDuty: entries.reduce((sum, e) => sum + (e.total_amount_due || 0), 0),
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Customs Entries</h1>
                    <p className="mt-1 text-gray-500">
                        Manage import entries and filings
                        {user?.email ? (
                            <span className="text-slate-400">
                                {' '}
                                · signed in as {user.email}
                                {isImporterPortal ? ' (importer portal)' : isBrokerStaff ? ' (broker staff)' : ''}
                            </span>
                        ) : null}
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <Button onClick={() => refetch()} variant="secondary" disabled={loading}>
                        <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                    <Button onClick={handleCreateEntry}>
                        <Plus className="w-4 h-4 mr-2" />
                        {isImporterPortal ? 'Manual entry' : 'New Entry'}
                    </Button>
                </div>
            </div>

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
                        <div className="flex items-center gap-3 min-w-0">
                            <div className="p-2 bg-green-100 rounded-lg flex-shrink-0">
                                <DollarSign className="w-5 h-5 text-green-600" />
                            </div>
                            <div className="min-w-0">
                                <p className="text-xl font-bold truncate" title={formatCurrency(stats.totalValue)}>
                                    {formatCurrency(stats.totalValue)}
                                </p>
                                <p className="text-sm text-gray-500">Total Value</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3 min-w-0">
                            <div className="p-2 bg-purple-100 rounded-lg flex-shrink-0">
                                <Calculator className="w-5 h-5 text-purple-600" />
                            </div>
                            <div className="min-w-0">
                                <p className="text-xl font-bold truncate" title={formatCurrency(stats.totalDuty)}>
                                    {formatCurrency(stats.totalDuty)}
                                </p>
                                <p className="text-sm text-gray-500">Total Duty</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            <Card>
                <CardContent className="py-4">
                    <div className="flex items-center gap-4">
                        <div className="relative flex-1">
                            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                            <input
                                type="text"
                                placeholder="Search entries, BOL, importer..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="w-full rounded-lg border border-gray-300 py-2 pl-10 pr-4 focus:border-transparent focus:ring-2 focus:ring-blue-500"
                            />
                        </div>
                        <Button variant="secondary" onClick={() => setShowFilters(!showFilters)}>
                            <Filter className="w-4 h-4 mr-2" />
                            Filters
                            <ChevronDown className={`ml-2 h-4 w-4 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
                        </Button>
                    </div>

                    <div className="mt-4 flex gap-2">
                        {[
                            { value: '', label: 'All' },
                            { value: 'draft', label: 'Draft' },
                            { value: 'pending_review', label: 'Pending' },
                            { value: 'ready_to_file', label: 'Ready' },
                            { value: 'filed', label: 'Filed' },
                            { value: 'accepted', label: 'Accepted' },
                            { value: 'released', label: 'Released' },
                            { value: 'cancelled', label: 'Cancelled' },
                        ].map((status) => (
                            <button
                                key={status.value}
                                onClick={() => setSelectedStatus(status.value)}
                                className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                                    selectedStatus === status.value
                                        ? 'bg-blue-600 text-white'
                                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                }`}
                            >
                                {status.label}
                            </button>
                        ))}
                    </div>

                    {showFilters && (
                        <div className="mt-4 grid grid-cols-4 gap-4 border-t border-gray-200 pt-4">
                            <div>
                                <label className="mb-1 block text-sm font-medium text-gray-700">Port of Entry</label>
                                <input
                                    type="text"
                                    value={filters.port || ''}
                                    onChange={(e) =>
                                        setFilters((prev) => ({ ...prev, port: e.target.value || undefined }))
                                    }
                                    placeholder="Port code..."
                                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                                />
                            </div>
                            <div>
                                <label className="mb-1 block text-sm font-medium text-gray-700">Date From</label>
                                <input
                                    type="date"
                                    value={filters.date_from || ''}
                                    onChange={(e) =>
                                        setFilters((prev) => ({ ...prev, date_from: e.target.value || undefined }))
                                    }
                                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                                />
                            </div>
                            <div>
                                <label className="mb-1 block text-sm font-medium text-gray-700">Date To</label>
                                <input
                                    type="date"
                                    value={filters.date_to || ''}
                                    onChange={(e) =>
                                        setFilters((prev) => ({ ...prev, date_to: e.target.value || undefined }))
                                    }
                                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
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

            {error && (
                <div className="flex gap-2 rounded-lg border border-red-200 bg-red-50 p-4">
                    <XCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600" />
                    <p className="text-sm text-red-600">{error}</p>
                </div>
            )}

            <Card>
                <CardHeader>
                    <CardTitle>
                        {selectedStatus ? getStatusInfo(selectedStatus).label : 'All'} Entries ({entries.length} of{' '}
                        {total})
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <div className="flex items-center justify-center py-12">
                            <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
                        </div>
                    ) : entries.length === 0 ? (
                        <div className="space-y-4 py-10 text-center">
                            <FileText className="mx-auto mb-2 h-12 w-12 text-gray-300" />
                            <p className="text-gray-600">No entries found</p>
                            {isImporterPortal ? (
                                <div className="mx-auto max-w-lg rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-left text-sm text-amber-900">
                                    <p className="font-medium">Importer portal view</p>
                                    <p className="mt-1">
                                        You&apos;re signed in as <strong>{user?.email}</strong>, which only shows entries
                                        linked to your client. Broker-created workbench entries (Meridian, Helios, etc.)
                                        appear when you sign in as broker staff (e.g. <code>admin@example.com</code>).
                                    </p>
                                    <div className="mt-3 flex flex-wrap gap-2">
                                        <Link to="/dashboard">
                                            <Button size="sm" variant="secondary">
                                                Workbench
                                            </Button>
                                        </Link>
                                        <Link to="/shipments/assembly">
                                            <Button size="sm" variant="secondary">
                                                Shipments
                                            </Button>
                                        </Link>
                                    </div>
                                </div>
                            ) : (
                                <Button onClick={handleCreateEntry}>
                                    <Plus className="mr-2 h-4 w-4" />
                                    Create First Entry
                                </Button>
                            )}
                        </div>
                    ) : (
                        <div className="overflow-x-auto rounded-lg border border-slate-200">
                            <table className="w-full text-sm">
                                <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500">
                                    <tr className="border-b border-slate-200">
                                        <th className="w-8 px-2 py-3" />
                                        <th className="px-3 py-3 font-medium">Entry</th>
                                        <th className="px-3 py-3 font-medium">Status</th>
                                        <th className="px-3 py-3 font-medium">Importer</th>
                                        <th className="px-3 py-3 font-medium">Port</th>
                                        <th className="px-3 py-3 text-right font-medium">Value</th>
                                        <th className="px-3 py-3 text-right font-medium">Duty</th>
                                        <th className="px-3 py-3 text-center font-medium">Lines</th>
                                        <th className="px-3 py-3 font-medium">Date</th>
                                        <th className="px-3 py-3 text-right font-medium">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {entries.map((entry) => {
                                        const open = expandedId === entry.id
                                        const lines = linesByEntry[entry.id]
                                        return (
                                            <Fragment key={entry.id}>
                                                <tr
                                                    className="cursor-pointer hover:bg-slate-50"
                                                    onClick={() => handleViewEntry(entry)}
                                                >
                                                    <td className="px-2 py-3" onClick={(e) => toggleExpand(entry, e)}>
                                                        <button
                                                            type="button"
                                                            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                                                            title="Show line items"
                                                        >
                                                            {open ? (
                                                                <ChevronDown className="h-4 w-4" />
                                                            ) : (
                                                                <ChevronRight className="h-4 w-4" />
                                                            )}
                                                        </button>
                                                    </td>
                                                    <td className="px-3 py-3">
                                                        <p className="font-medium text-gray-900">
                                                            {entry.entry_number || (
                                                                <span className="italic text-gray-400">Pending</span>
                                                            )}
                                                        </p>
                                                        <p className="text-xs text-gray-500">
                                                            {getEntryTypeName(entry.entry_type)} ·{' '}
                                                            {entry.bill_of_lading || 'No BOL'}
                                                        </p>
                                                    </td>
                                                    <td className="px-3 py-3">
                                                        <StatusBadge status={entry.status} />
                                                    </td>
                                                    <td className="px-3 py-3">
                                                        <p className="max-w-[200px] truncate text-gray-900">
                                                            {entry.importer_name || '—'}
                                                        </p>
                                                    </td>
                                                    <td className="px-3 py-3 text-gray-600">{entry.port_of_entry || '—'}</td>
                                                    <td className="px-3 py-3 text-right font-medium text-gray-900">
                                                        {formatCurrency(entry.total_entered_value)}
                                                    </td>
                                                    <td className="px-3 py-3 text-right">
                                                        <span
                                                            className={
                                                                entry.total_amount_due > 0
                                                                    ? 'font-medium text-blue-600'
                                                                    : 'text-gray-400'
                                                            }
                                                        >
                                                            {formatCurrency(entry.total_amount_due)}
                                                        </span>
                                                    </td>
                                                    <td className="px-3 py-3 text-center">
                                                        <span className="inline-flex h-6 min-w-[1.5rem] items-center justify-center rounded-full bg-gray-100 px-1.5 text-xs font-medium">
                                                            {entry.line_count}
                                                        </span>
                                                    </td>
                                                    <td className="px-3 py-3 text-gray-500">
                                                        {entry.entry_date
                                                            ? new Date(entry.entry_date).toLocaleDateString()
                                                            : new Date(entry.created_at).toLocaleDateString()}
                                                    </td>
                                                    <td
                                                        className="px-3 py-3 text-right"
                                                        onClick={(e) => e.stopPropagation()}
                                                    >
                                                        <div className="flex items-center justify-end gap-1">
                                                            <button
                                                                className="rounded p-1.5 hover:bg-gray-100"
                                                                title="View"
                                                                onClick={() => handleViewEntry(entry)}
                                                            >
                                                                <Eye className="h-4 w-4 text-gray-500" />
                                                            </button>
                                                            <button
                                                                className="rounded p-1.5 hover:bg-gray-100"
                                                                title="Edit"
                                                                onClick={() => navigate(`/entries/${entry.id}/edit`)}
                                                            >
                                                                <Edit className="h-4 w-4 text-gray-500" />
                                                            </button>
                                                            {entry.status === 'draft' && (
                                                                <button
                                                                    className="rounded p-1.5 hover:bg-red-50"
                                                                    title="Cancel"
                                                                    onClick={() => handleDeleteEntry(entry)}
                                                                >
                                                                    <Trash2 className="h-4 w-4 text-red-500" />
                                                                </button>
                                                            )}
                                                        </div>
                                                    </td>
                                                </tr>
                                                {open && (
                                                    <tr className="bg-slate-50/80">
                                                        <td colSpan={10} className="px-4 py-3">
                                                            {linesLoading === entry.id ? (
                                                                <div className="flex items-center gap-2 text-xs text-slate-500">
                                                                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                                                                    Loading line items…
                                                                </div>
                                                            ) : !lines || lines.length === 0 ? (
                                                                <p className="text-xs text-slate-500">
                                                                    No line items on this entry yet.{' '}
                                                                    <button
                                                                        type="button"
                                                                        className="font-medium text-blue-700 underline-offset-2 hover:underline"
                                                                        onClick={() => handleViewEntry(entry)}
                                                                    >
                                                                        Open entry
                                                                    </button>
                                                                </p>
                                                            ) : (
                                                                <div className="overflow-hidden rounded-md border border-slate-200 bg-white">
                                                                    {lineSaveError && (
                                                                        <p className="border-b border-red-100 bg-red-50 px-3 py-1.5 text-[11px] text-red-700">
                                                                            {lineSaveError}
                                                                        </p>
                                                                    )}
                                                                    <table className="w-full text-left text-xs">
                                                                        <thead className="bg-slate-100 text-[10px] uppercase text-slate-500">
                                                                            <tr>
                                                                                <th className="px-3 py-1.5">#</th>
                                                                                <th className="px-3 py-1.5">HTS</th>
                                                                                <th className="px-3 py-1.5">Description</th>
                                                                                <th className="px-3 py-1.5">COO</th>
                                                                                <th className="px-3 py-1.5 text-right">Qty</th>
                                                                                <th className="px-3 py-1.5 text-right">Value</th>
                                                                                <th className="px-3 py-1.5 text-right">Duty</th>
                                                                                <th className="px-3 py-1.5 text-right">Edit</th>
                                                                            </tr>
                                                                        </thead>
                                                                        <tbody className="divide-y divide-slate-100">
                                                                            {lines.map((line) => {
                                                                                const isEditing = editingLineId === line.id
                                                                                return (
                                                                                    <tr key={line.id}>
                                                                                        <td className="px-3 py-1.5">{line.line_number}</td>
                                                                                        <td className="px-3 py-1.5 font-mono">
                                                                                            {isEditing ? (
                                                                                                <input
                                                                                                    value={editDraft.hts_code}
                                                                                                    onChange={(e) =>
                                                                                                        setEditDraft((d) => ({
                                                                                                            ...d,
                                                                                                            hts_code: e.target.value,
                                                                                                        }))
                                                                                                    }
                                                                                                    className="w-28 rounded border border-slate-300 px-1.5 py-0.5 font-mono text-xs"
                                                                                                />
                                                                                            ) : (
                                                                                                line.hts_code || '—'
                                                                                            )}
                                                                                        </td>
                                                                                        <td className="max-w-[240px] truncate px-3 py-1.5">
                                                                                            {line.product_description || '—'}
                                                                                        </td>
                                                                                        <td className="px-3 py-1.5">
                                                                                            {isEditing ? (
                                                                                                <input
                                                                                                    value={editDraft.country_of_origin}
                                                                                                    onChange={(e) =>
                                                                                                        setEditDraft((d) => ({
                                                                                                            ...d,
                                                                                                            country_of_origin: e.target.value.toUpperCase().slice(0, 2),
                                                                                                        }))
                                                                                                    }
                                                                                                    className="w-12 rounded border border-slate-300 px-1.5 py-0.5 text-xs uppercase"
                                                                                                    maxLength={2}
                                                                                                />
                                                                                            ) : (
                                                                                                line.country_of_origin || '—'
                                                                                            )}
                                                                                        </td>
                                                                                        <td className="px-3 py-1.5 text-right">
                                                                                            {line.quantity_1 ?? '—'}
                                                                                            {line.uom_1 ? ` ${line.uom_1}` : ''}
                                                                                        </td>
                                                                                        <td className="px-3 py-1.5 text-right">
                                                                                            {isEditing ? (
                                                                                                <input
                                                                                                    value={editDraft.entered_value}
                                                                                                    onChange={(e) =>
                                                                                                        setEditDraft((d) => ({
                                                                                                            ...d,
                                                                                                            entered_value: e.target.value,
                                                                                                        }))
                                                                                                    }
                                                                                                    className="w-24 rounded border border-slate-300 px-1.5 py-0.5 text-right text-xs"
                                                                                                />
                                                                                            ) : (
                                                                                                formatCurrency(line.entered_value)
                                                                                            )}
                                                                                        </td>
                                                                                        <td className="px-3 py-1.5 text-right">
                                                                                            {formatCurrency(line.total_line_duty)}
                                                                                        </td>
                                                                                        <td className="px-3 py-1.5 text-right">
                                                                                            {isEditing ? (
                                                                                                <div className="inline-flex gap-1">
                                                                                                    <button
                                                                                                        type="button"
                                                                                                        disabled={lineSaving}
                                                                                                        className="rounded bg-slate-900 px-2 py-0.5 text-[10px] font-medium text-white"
                                                                                                        onClick={() => saveEditLine(entry.id, line.id)}
                                                                                                    >
                                                                                                        Save
                                                                                                    </button>
                                                                                                    <button
                                                                                                        type="button"
                                                                                                        className="rounded px-2 py-0.5 text-[10px] text-slate-600 hover:bg-slate-100"
                                                                                                        onClick={() => setEditingLineId(null)}
                                                                                                    >
                                                                                                        Cancel
                                                                                                    </button>
                                                                                                </div>
                                                                                            ) : (
                                                                                                <button
                                                                                                    type="button"
                                                                                                    className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                                                                                                    title="Edit HTS / COO / value"
                                                                                                    onClick={() => startEditLine(line)}
                                                                                                >
                                                                                                    <Edit className="h-3.5 w-3.5" />
                                                                                                </button>
                                                                                            )}
                                                                                        </td>
                                                                                    </tr>
                                                                                )
                                                                            })}
                                                                        </tbody>
                                                                    </table>
                                                                    <div className="flex items-center justify-between border-t border-slate-100 px-3 py-1.5">
                                                                        <p className="text-[10px] text-slate-500">
                                                                            Inline edit HTS / COO / value · ACE filing only on entry detail after Broker OK
                                                                        </p>
                                                                        <button
                                                                            type="button"
                                                                            className="text-[11px] font-medium text-blue-700 hover:underline"
                                                                            onClick={() => handleViewEntry(entry)}
                                                                        >
                                                                            Open full entry →
                                                                        </button>
                                                                    </div>
                                                                </div>
                                                            )}
                                                        </td>
                                                    </tr>
                                                )}
                                            </Fragment>
                                        )
                                    })}
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
