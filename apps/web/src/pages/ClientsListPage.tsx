/**
 * Clients List Page
 * 
 * Main client management interface showing all importer clients
 * with search, filtering, and quick actions.
 * 
 * Task 4.2 from ROADMAP_FULL_WORKFLOW.md
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Plus,
    RefreshCw,
    Search,
    Filter,
    Building2,
    Shield,
    ChevronDown,
    Eye,
    Edit,
    Archive,
    CheckCircle,
    Clock,
    XCircle,
    MapPin,
} from 'lucide-react'
import { Card, CardContent } from '../components/Card'
import { Button } from '../components/Button'
import {
    useClients,
    useClientActions,
    ClientListItem,
    ClientFilters,
    CLIENT_STATUSES,
    getStatusInfo,
    getTypeName,
} from '../hooks/useClients'

// Status badge component
const StatusBadge = ({ status }: { status: string }) => {
    const info = getStatusInfo(status)
    return (
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${info.bgColor} ${info.textColor}`}>
            {info.label}
        </span>
    )
}

// Compliance badges
const ComplianceBadges = ({ client }: { client: ClientListItem }) => {
    return (
        <div className="flex items-center gap-1">
            {client.c_tpat_member && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-100 text-emerald-700" title="C-TPAT Member">
                    C-TPAT
                </span>
            )}
        </div>
    )
}

export const ClientsListPage = () => {
    const navigate = useNavigate()
    const [filters, setFilters] = useState<ClientFilters>({ limit: 50 })
    const [searchTerm, setSearchTerm] = useState('')
    const [showFilters, setShowFilters] = useState(false)
    const [selectedStatus, setSelectedStatus] = useState<string>('')

    const { clients, total, loading, error, refetch } = useClients(filters)
    const { deleteClient } = useClientActions()

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

    const handleCreateClient = () => {
        navigate('/clients/new')
    }

    const handleViewClient = (client: ClientListItem) => {
        navigate(`/clients/${client.id}`)
    }

    const handleArchiveClient = async (client: ClientListItem) => {
        if (!confirm(`Archive client "${client.name}"? This will mark them as terminated.`)) return

        const success = await deleteClient(client.id)
        if (success) {
            refetch()
        }
    }

    // Calculate stats from clients
    const stats = {
        active: clients.filter(c => c.status === 'active').length,
        onboarding: clients.filter(c => c.status === 'onboarding').length,
        ctpat: clients.filter(c => c.c_tpat_member).length,
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Clients</h1>
                    <p className="text-gray-500 mt-1">Manage your importer clients and their profiles</p>
                </div>
                <div className="flex items-center gap-3">
                    <Button onClick={() => refetch()} variant="secondary" disabled={loading}>
                        <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                    <Button onClick={handleCreateClient}>
                        <Plus className="w-4 h-4 mr-2" />
                        New Client
                    </Button>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-4 gap-4">
                <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setSelectedStatus('')}>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-blue-100 rounded-lg">
                                <Building2 className="w-5 h-5 text-blue-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{total}</p>
                                <p className="text-sm text-gray-500">Total Clients</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setSelectedStatus('active')}>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-green-100 rounded-lg">
                                <CheckCircle className="w-5 h-5 text-green-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{stats.active}</p>
                                <p className="text-sm text-gray-500">Active</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setSelectedStatus('onboarding')}>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-blue-100 rounded-lg">
                                <Clock className="w-5 h-5 text-blue-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{stats.onboarding}</p>
                                <p className="text-sm text-gray-500">Onboarding</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-emerald-100 rounded-lg">
                                <Shield className="w-5 h-5 text-emerald-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{stats.ctpat}</p>
                                <p className="text-sm text-gray-500">C-TPAT Members</p>
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
                                placeholder="Search by name, IOR, EIN, code..."
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
                            ...CLIENT_STATUSES.filter(s => s.value !== 'terminated'),
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
                            <div className="flex items-end">
                                <Button
                                    variant="secondary"
                                    onClick={() => {
                                        setFilters({ limit: 50 })
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

            {/* Clients Grid */}
            <div>
                <h2 className="text-lg font-semibold text-gray-900 mb-4">
                    {selectedStatus ? getStatusInfo(selectedStatus).label : 'All'} Clients ({clients.length} of {total})
                </h2>

                {loading ? (
                    <div className="flex items-center justify-center py-12">
                        <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
                    </div>
                ) : clients.length === 0 ? (
                    <Card>
                        <CardContent className="py-12 text-center">
                            <Building2 className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                            <p className="text-gray-500 mb-4">No clients found</p>
                            <Button onClick={handleCreateClient}>
                                <Plus className="w-4 h-4 mr-2" />
                                Add First Client
                            </Button>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {clients.map((client) => (
                            <Card
                                key={client.id}
                                className="cursor-pointer hover:shadow-lg transition-all hover:scale-[1.02]"
                                onClick={() => handleViewClient(client)}
                            >
                                <CardContent className="pt-4">
                                    <div className="space-y-3">
                                        {/* Header */}
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center text-white font-bold text-lg">
                                                    {client.name.charAt(0).toUpperCase()}
                                                </div>
                                                <div>
                                                    <h3 className="font-semibold text-gray-900 line-clamp-1">
                                                        {client.display_name}
                                                    </h3>
                                                    <p className="text-xs text-gray-500">
                                                        {getTypeName(client.client_type)}
                                                    </p>
                                                </div>
                                            </div>
                                            <StatusBadge status={client.status} />
                                        </div>

                                        {/* Identifiers */}
                                        <div className="grid grid-cols-2 gap-2 text-sm">
                                            <div>
                                                <span className="text-gray-500">IOR:</span>{' '}
                                                <span className="font-mono text-gray-900">
                                                    {client.ior_number || '-'}
                                                </span>
                                            </div>
                                            <div>
                                                <span className="text-gray-500">EIN:</span>{' '}
                                                <span className="font-mono text-gray-900">
                                                    {client.ein || '-'}
                                                </span>
                                            </div>
                                        </div>

                                        {/* Location */}
                                        {(client.city || client.state_province) && (
                                            <div className="flex items-center gap-1.5 text-sm text-gray-600">
                                                <MapPin className="w-3.5 h-3.5 text-gray-400" />
                                                <span>
                                                    {[client.city, client.state_province].filter(Boolean).join(', ')}
                                                </span>
                                            </div>
                                        )}

                                        {/* Port & Compliance */}
                                        <div className="flex items-center justify-between pt-2 border-t border-gray-100">
                                            <div className="flex items-center gap-2">
                                                {client.primary_port && (
                                                    <span className="text-xs text-gray-500">
                                                        Port: <span className="font-medium">{client.primary_port}</span>
                                                    </span>
                                                )}
                                            </div>
                                            <ComplianceBadges client={client} />
                                        </div>

                                        {/* Actions */}
                                        <div className="flex items-center gap-1 pt-2" onClick={(e) => e.stopPropagation()}>
                                            <button
                                                className="flex-1 py-1.5 px-3 text-sm text-gray-600 hover:bg-gray-100 rounded-lg flex items-center justify-center gap-1.5"
                                                onClick={() => handleViewClient(client)}
                                            >
                                                <Eye className="w-4 h-4" />
                                                View
                                            </button>
                                            <button
                                                className="flex-1 py-1.5 px-3 text-sm text-gray-600 hover:bg-gray-100 rounded-lg flex items-center justify-center gap-1.5"
                                                onClick={() => navigate(`/clients/${client.id}/edit`)}
                                            >
                                                <Edit className="w-4 h-4" />
                                                Edit
                                            </button>
                                            {client.status !== 'terminated' && (
                                                <button
                                                    className="py-1.5 px-3 text-sm text-red-600 hover:bg-red-50 rounded-lg flex items-center justify-center gap-1.5"
                                                    onClick={() => handleArchiveClient(client)}
                                                >
                                                    <Archive className="w-4 h-4" />
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}

export default ClientsListPage
