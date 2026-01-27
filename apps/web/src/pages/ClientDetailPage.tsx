/**
 * Client Detail Page
 * 
 * Detailed view and edit page for a single client with tabs for:
 * - Profile information
 * - Contacts
 * - Bonds
 * - Entries
 * - Settings
 * 
 * Task 4.2 from ROADMAP_FULL_WORKFLOW.md
 */
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
    ArrowLeft,
    Building2,
    Users,
    FileText,
    Shield,
    Settings,
    RefreshCw,
    Edit,
    Save,
    X,
    Plus,
    Phone,
    Mail,
    MapPin,
    Globe,
    Calendar,
    AlertTriangle,
    CheckCircle,
    User,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import {
    useClient,
    useClientActions,
    Client,
    ClientBond,
    getStatusInfo,
    getTypeName,
    formatCurrency,
} from '../hooks/useClients'

// Tab types
type TabType = 'profile' | 'contacts' | 'bonds' | 'entries' | 'settings'

// Status badge
const StatusBadge = ({ status }: { status: string }) => {
    const info = getStatusInfo(status)
    return (
        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${info.bgColor} ${info.textColor}`}>
            {info.label}
        </span>
    )
}

// Bond status badge
const BondStatusBadge = ({ bond }: { bond: ClientBond }) => {
    if (bond.is_expired) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                <X className="w-3 h-3" /> Expired
            </span>
        )
    }
    if (bond.days_until_expiration !== null && bond.days_until_expiration !== undefined && bond.days_until_expiration <= 30) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">
                <AlertTriangle className="w-3 h-3" /> {bond.days_until_expiration}d left
            </span>
        )
    }
    if (bond.is_active) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                <CheckCircle className="w-3 h-3" /> Active
            </span>
        )
    }
    return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
            Inactive
        </span>
    )
}

export const ClientDetailPage = () => {
    const { clientId } = useParams<{ clientId: string }>()
    const navigate = useNavigate()
    const [activeTab, setActiveTab] = useState<TabType>('profile')
    const [isEditing, setIsEditing] = useState(false)
    const [showAddContact, setShowAddContact] = useState(false)
    const [showAddBond, setShowAddBond] = useState(false)

    const { client, loading, error, refetch } = useClient(clientId)
    const { updateClient, addContact, addBond, loading: actionLoading } = useClientActions()

    // Edit form state
    const [editForm, setEditForm] = useState<Partial<Client>>({})

    // New contact form
    const [newContact, setNewContact] = useState({
        first_name: '',
        last_name: '',
        email: '',
        phone: '',
        title: '',
        contact_type: 'primary',
        is_primary: false,
    })

    // New bond form
    const [newBond, setNewBond] = useState({
        bond_type: 'continuous',
        bond_number: '',
        surety_code: '',
        surety_name: '',
        bond_amount: '',
        coverage_start: '',
        coverage_end: '',
    })

    useEffect(() => {
        if (client) {
            setEditForm({
                name: client.name,
                legal_name: client.legal_name,
                dba_name: client.dba_name,
                notes: client.notes,
            })
        }
    }, [client])

    const handleSave = async () => {
        if (!clientId) return
        const success = await updateClient(clientId, editForm as any)
        if (success) {
            setIsEditing(false)
            refetch()
        }
    }

    const handleAddContact = async () => {
        if (!clientId || !newContact.first_name || !newContact.last_name) return
        const result = await addContact(clientId, newContact)
        if (result) {
            setShowAddContact(false)
            setNewContact({
                first_name: '',
                last_name: '',
                email: '',
                phone: '',
                title: '',
                contact_type: 'primary',
                is_primary: false,
            })
            refetch()
        }
    }

    const handleAddBond = async () => {
        if (!clientId || !newBond.bond_number || !newBond.surety_code) return
        const result = await addBond(clientId, {
            ...newBond,
            bond_amount: newBond.bond_amount ? parseFloat(newBond.bond_amount) : undefined,
        })
        if (result) {
            setShowAddBond(false)
            setNewBond({
                bond_type: 'continuous',
                bond_number: '',
                surety_code: '',
                surety_name: '',
                bond_amount: '',
                coverage_start: '',
                coverage_end: '',
            })
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

    if (error || !client) {
        return (
            <div className="space-y-4">
                <Button variant="secondary" onClick={() => navigate('/clients')}>
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Back to Clients
                </Button>
                <Card>
                    <CardContent className="py-12 text-center">
                        <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
                        <p className="text-gray-600">{error || 'Client not found'}</p>
                    </CardContent>
                </Card>
            </div>
        )
    }

    const tabs = [
        { id: 'profile' as const, label: 'Profile', icon: Building2 },
        { id: 'contacts' as const, label: 'Contacts', icon: Users, count: client.contacts?.length },
        { id: 'bonds' as const, label: 'Bonds', icon: Shield, count: client.bonds?.length },
        { id: 'entries' as const, label: 'Entries', icon: FileText },
        { id: 'settings' as const, label: 'Settings', icon: Settings },
    ]

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                    <Button variant="secondary" onClick={() => navigate('/clients')}>
                        <ArrowLeft className="w-4 h-4 mr-2" />
                        Back
                    </Button>
                    <div className="flex items-center gap-4">
                        <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center text-white font-bold text-2xl shadow-lg">
                            {client.name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                            <div className="flex items-center gap-3">
                                <h1 className="text-2xl font-bold text-gray-900">{client.display_name}</h1>
                                <StatusBadge status={client.status} />
                            </div>
                            <p className="text-gray-500 mt-0.5">
                                {getTypeName(client.client_type)} • IOR: {client.identifiers.ior_number || 'Not set'}
                            </p>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="secondary" onClick={() => refetch()}>
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Refresh
                    </Button>
                    {!isEditing ? (
                        <Button onClick={() => setIsEditing(true)}>
                            <Edit className="w-4 h-4 mr-2" />
                            Edit Client
                        </Button>
                    ) : (
                        <>
                            <Button variant="secondary" onClick={() => setIsEditing(false)}>
                                <X className="w-4 h-4 mr-2" />
                                Cancel
                            </Button>
                            <Button onClick={handleSave} disabled={actionLoading}>
                                <Save className="w-4 h-4 mr-2" />
                                Save Changes
                            </Button>
                        </>
                    )}
                </div>
            </div>

            {/* Tabs */}
            <div className="border-b border-gray-200">
                <nav className="flex gap-6">
                    {tabs.map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`flex items-center gap-2 py-3 px-1 border-b-2 text-sm font-medium transition-colors ${activeTab === tab.id
                                ? 'border-blue-600 text-blue-600'
                                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                }`}
                        >
                            <tab.icon className="w-4 h-4" />
                            {tab.label}
                            {tab.count !== undefined && (
                                <span className="ml-1 px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs">
                                    {tab.count}
                                </span>
                            )}
                        </button>
                    ))}
                </nav>
            </div>

            {/* Tab Content */}
            {activeTab === 'profile' && (
                <div className="grid grid-cols-3 gap-6">
                    {/* Main Info */}
                    <Card className="col-span-2">
                        <CardHeader>
                            <CardTitle>Company Information</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-500 mb-1">Company Name</label>
                                    {isEditing ? (
                                        <Input
                                            value={editForm.name || ''}
                                            onChange={(e) => setEditForm(prev => ({ ...prev, name: e.target.value }))}
                                        />
                                    ) : (
                                        <p className="text-lg font-medium text-gray-900">{client.name}</p>
                                    )}
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-500 mb-1">DBA Name</label>
                                    {isEditing ? (
                                        <Input
                                            value={editForm.dba_name || ''}
                                            onChange={(e) => setEditForm(prev => ({ ...prev, dba_name: e.target.value }))}
                                        />
                                    ) : (
                                        <p className="text-gray-900">{client.dba_name || '-'}</p>
                                    )}
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-500 mb-1">Legal Name</label>
                                    {isEditing ? (
                                        <Input
                                            value={editForm.legal_name || ''}
                                            onChange={(e) => setEditForm(prev => ({ ...prev, legal_name: e.target.value }))}
                                        />
                                    ) : (
                                        <p className="text-gray-900">{client.legal_name || '-'}</p>
                                    )}
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-500 mb-1">Entity Type</label>
                                    <p className="text-gray-900">{getTypeName(client.client_type)}</p>
                                </div>
                            </div>

                            <div className="pt-4 border-t border-gray-100">
                                <h4 className="font-medium text-gray-900 mb-3">Identifiers</h4>
                                <div className="grid grid-cols-4 gap-4">
                                    <div>
                                        <label className="block text-xs font-medium text-gray-500 mb-1">IOR Number</label>
                                        <p className="font-mono text-gray-900">{client.identifiers.ior_number || '-'}</p>
                                    </div>
                                    <div>
                                        <label className="block text-xs font-medium text-gray-500 mb-1">EIN</label>
                                        <p className="font-mono text-gray-900">{client.identifiers.ein || '-'}</p>
                                    </div>
                                    <div>
                                        <label className="block text-xs font-medium text-gray-500 mb-1">DUNS</label>
                                        <p className="font-mono text-gray-900">{client.identifiers.duns || '-'}</p>
                                    </div>
                                    <div>
                                        <label className="block text-xs font-medium text-gray-500 mb-1">CBP Assigned</label>
                                        <p className="font-mono text-gray-900">{client.identifiers.cbp_assigned_number || '-'}</p>
                                    </div>
                                </div>
                            </div>

                            <div className="pt-4 border-t border-gray-100">
                                <h4 className="font-medium text-gray-900 mb-3">Notes</h4>
                                {isEditing ? (
                                    <textarea
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                        rows={4}
                                        value={editForm.notes || ''}
                                        onChange={(e) => setEditForm(prev => ({ ...prev, notes: e.target.value }))}
                                    />
                                ) : (
                                    <p className="text-gray-700 whitespace-pre-wrap">{client.notes || 'No notes'}</p>
                                )}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Sidebar Info */}
                    <div className="space-y-6">
                        {/* Contact Info */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base">Contact Information</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {client.contact_info.phone && (
                                    <div className="flex items-center gap-2 text-sm">
                                        <Phone className="w-4 h-4 text-gray-400" />
                                        <span>{client.contact_info.phone}</span>
                                    </div>
                                )}
                                {client.contact_info.email && (
                                    <div className="flex items-center gap-2 text-sm">
                                        <Mail className="w-4 h-4 text-gray-400" />
                                        <a href={`mailto:${client.contact_info.email}`} className="text-blue-600 hover:underline">
                                            {client.contact_info.email}
                                        </a>
                                    </div>
                                )}
                                {client.contact_info.website && (
                                    <div className="flex items-center gap-2 text-sm">
                                        <Globe className="w-4 h-4 text-gray-400" />
                                        <a href={client.contact_info.website} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                                            {client.contact_info.website}
                                        </a>
                                    </div>
                                )}
                                {client.address.full && (
                                    <div className="flex items-start gap-2 text-sm pt-2 border-t border-gray-100">
                                        <MapPin className="w-4 h-4 text-gray-400 mt-0.5" />
                                        <span className="whitespace-pre-line">{client.address.full}</span>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Compliance */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base">Compliance Status</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="flex items-center justify-between text-sm">
                                    <span className="text-gray-600">C-TPAT Member</span>
                                    {client.compliance.c_tpat_member ? (
                                        <span className="flex items-center gap-1 text-emerald-600">
                                            <CheckCircle className="w-4 h-4" /> Yes
                                        </span>
                                    ) : (
                                        <span className="text-gray-400">No</span>
                                    )}
                                </div>
                                <div className="flex items-center justify-between text-sm">
                                    <span className="text-gray-600">Known Importer</span>
                                    {client.compliance.known_importer ? (
                                        <span className="flex items-center gap-1 text-emerald-600">
                                            <CheckCircle className="w-4 h-4" /> Yes
                                        </span>
                                    ) : (
                                        <span className="text-gray-400">No</span>
                                    )}
                                </div>
                                <div className="flex items-center justify-between text-sm">
                                    <span className="text-gray-600">Trusted Trader</span>
                                    {client.compliance.trusted_trader ? (
                                        <span className="flex items-center gap-1 text-emerald-600">
                                            <CheckCircle className="w-4 h-4" /> Yes
                                        </span>
                                    ) : (
                                        <span className="text-gray-400">No</span>
                                    )}
                                </div>
                            </CardContent>
                        </Card>

                        {/* Broker Relationship */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base">Broker Relationship</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="flex items-center gap-2 text-sm">
                                    <User className="w-4 h-4 text-gray-400" />
                                    <span className="text-gray-600">Assigned:</span>
                                    <span className="font-medium">{client.broker_relationship.assigned_broker || 'Unassigned'}</span>
                                </div>
                                <div className="flex items-center gap-2 text-sm">
                                    <Calendar className="w-4 h-4 text-gray-400" />
                                    <span className="text-gray-600">Onboarded:</span>
                                    <span>{client.broker_relationship.onboarding_date || '-'}</span>
                                </div>
                                <div className="flex items-center gap-2 text-sm">
                                    <FileText className="w-4 h-4 text-gray-400" />
                                    <span className="text-gray-600">First Entry:</span>
                                    <span>{client.broker_relationship.first_entry_date || 'None yet'}</span>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            )}

            {activeTab === 'contacts' && (
                <div className="space-y-4">
                    <div className="flex justify-between items-center">
                        <h3 className="text-lg font-medium text-gray-900">Contacts ({client.contacts?.length || 0})</h3>
                        <Button onClick={() => setShowAddContact(true)}>
                            <Plus className="w-4 h-4 mr-2" />
                            Add Contact
                        </Button>
                    </div>

                    {/* Add Contact Form */}
                    {showAddContact && (
                        <Card className="border-blue-200 bg-blue-50">
                            <CardContent className="pt-4">
                                <h4 className="font-medium text-gray-900 mb-4">New Contact</h4>
                                <div className="grid grid-cols-4 gap-4">
                                    <Input
                                        placeholder="First Name *"
                                        value={newContact.first_name}
                                        onChange={(e) => setNewContact(prev => ({ ...prev, first_name: e.target.value }))}
                                    />
                                    <Input
                                        placeholder="Last Name *"
                                        value={newContact.last_name}
                                        onChange={(e) => setNewContact(prev => ({ ...prev, last_name: e.target.value }))}
                                    />
                                    <Input
                                        placeholder="Title"
                                        value={newContact.title}
                                        onChange={(e) => setNewContact(prev => ({ ...prev, title: e.target.value }))}
                                    />
                                    <Input
                                        placeholder="Email"
                                        type="email"
                                        value={newContact.email}
                                        onChange={(e) => setNewContact(prev => ({ ...prev, email: e.target.value }))}
                                    />
                                    <Input
                                        placeholder="Phone"
                                        value={newContact.phone}
                                        onChange={(e) => setNewContact(prev => ({ ...prev, phone: e.target.value }))}
                                    />
                                    <select
                                        className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                                        value={newContact.contact_type}
                                        onChange={(e) => setNewContact(prev => ({ ...prev, contact_type: e.target.value }))}
                                    >
                                        <option value="primary">Primary</option>
                                        <option value="billing">Billing</option>
                                        <option value="operations">Operations</option>
                                        <option value="compliance">Compliance</option>
                                        <option value="executive">Executive</option>
                                    </select>
                                    <div className="flex items-center gap-4">
                                        <label className="flex items-center gap-2">
                                            <input
                                                type="checkbox"
                                                checked={newContact.is_primary}
                                                onChange={(e) => setNewContact(prev => ({ ...prev, is_primary: e.target.checked }))}
                                            />
                                            <span className="text-sm">Primary Contact</span>
                                        </label>
                                    </div>
                                    <div className="flex gap-2">
                                        <Button onClick={handleAddContact} disabled={!newContact.first_name || !newContact.last_name}>
                                            Add
                                        </Button>
                                        <Button variant="secondary" onClick={() => setShowAddContact(false)}>
                                            Cancel
                                        </Button>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {/* Contacts List */}
                    {client.contacts && client.contacts.length > 0 ? (
                        <div className="grid grid-cols-2 gap-4">
                            {client.contacts.map((contact) => (
                                <Card key={contact.id}>
                                    <CardContent className="pt-4">
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center">
                                                    <User className="w-5 h-5 text-gray-500" />
                                                </div>
                                                <div>
                                                    <div className="flex items-center gap-2">
                                                        <h4 className="font-medium text-gray-900">{contact.full_name}</h4>
                                                        {contact.is_primary && (
                                                            <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full">Primary</span>
                                                        )}
                                                    </div>
                                                    <p className="text-sm text-gray-500">{contact.title || contact.contact_type}</p>
                                                </div>
                                            </div>
                                        </div>
                                        <div className="mt-3 pt-3 border-t border-gray-100 space-y-1.5">
                                            {contact.email && (
                                                <div className="flex items-center gap-2 text-sm">
                                                    <Mail className="w-3.5 h-3.5 text-gray-400" />
                                                    <a href={`mailto:${contact.email}`} className="text-blue-600">{contact.email}</a>
                                                </div>
                                            )}
                                            {contact.phone && (
                                                <div className="flex items-center gap-2 text-sm">
                                                    <Phone className="w-3.5 h-3.5 text-gray-400" />
                                                    <span>{contact.phone}</span>
                                                </div>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    ) : (
                        <Card>
                            <CardContent className="py-8 text-center">
                                <Users className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                                <p className="text-gray-500">No contacts added yet</p>
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}

            {activeTab === 'bonds' && (
                <div className="space-y-4">
                    <div className="flex justify-between items-center">
                        <h3 className="text-lg font-medium text-gray-900">Customs Bonds ({client.bonds?.length || 0})</h3>
                        <Button onClick={() => setShowAddBond(true)}>
                            <Plus className="w-4 h-4 mr-2" />
                            Add Bond
                        </Button>
                    </div>

                    {/* Add Bond Form */}
                    {showAddBond && (
                        <Card className="border-blue-200 bg-blue-50">
                            <CardContent className="pt-4">
                                <h4 className="font-medium text-gray-900 mb-4">New Bond</h4>
                                <div className="grid grid-cols-4 gap-4">
                                    <select
                                        className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                                        value={newBond.bond_type}
                                        onChange={(e) => setNewBond(prev => ({ ...prev, bond_type: e.target.value }))}
                                    >
                                        <option value="continuous">Continuous</option>
                                        <option value="single_transaction">Single Transaction</option>
                                        <option value="isf">ISF</option>
                                    </select>
                                    <Input
                                        placeholder="Bond Number *"
                                        value={newBond.bond_number}
                                        onChange={(e) => setNewBond(prev => ({ ...prev, bond_number: e.target.value }))}
                                    />
                                    <Input
                                        placeholder="Surety Code (3 digits) *"
                                        maxLength={3}
                                        value={newBond.surety_code}
                                        onChange={(e) => setNewBond(prev => ({ ...prev, surety_code: e.target.value }))}
                                    />
                                    <Input
                                        placeholder="Surety Name"
                                        value={newBond.surety_name}
                                        onChange={(e) => setNewBond(prev => ({ ...prev, surety_name: e.target.value }))}
                                    />
                                    <Input
                                        placeholder="Bond Amount"
                                        type="number"
                                        value={newBond.bond_amount}
                                        onChange={(e) => setNewBond(prev => ({ ...prev, bond_amount: e.target.value }))}
                                    />
                                    <Input
                                        type="date"
                                        placeholder="Coverage Start"
                                        value={newBond.coverage_start}
                                        onChange={(e) => setNewBond(prev => ({ ...prev, coverage_start: e.target.value }))}
                                    />
                                    <Input
                                        type="date"
                                        placeholder="Coverage End"
                                        value={newBond.coverage_end}
                                        onChange={(e) => setNewBond(prev => ({ ...prev, coverage_end: e.target.value }))}
                                    />
                                    <div className="flex gap-2">
                                        <Button onClick={handleAddBond} disabled={!newBond.bond_number || !newBond.surety_code}>
                                            Add
                                        </Button>
                                        <Button variant="secondary" onClick={() => setShowAddBond(false)}>
                                            Cancel
                                        </Button>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {/* Bonds List */}
                    {client.bonds && client.bonds.length > 0 ? (
                        <div className="space-y-3">
                            {client.bonds.map((bond) => (
                                <Card key={bond.id}>
                                    <CardContent className="py-4">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-4">
                                                <div className="p-2 bg-indigo-100 rounded-lg">
                                                    <Shield className="w-5 h-5 text-indigo-600" />
                                                </div>
                                                <div>
                                                    <div className="flex items-center gap-2">
                                                        <h4 className="font-medium text-gray-900">{bond.bond_number}</h4>
                                                        <BondStatusBadge bond={bond} />
                                                    </div>
                                                    <p className="text-sm text-gray-500">
                                                        {bond.bond_type.replace('_', ' ').charAt(0).toUpperCase() + bond.bond_type.slice(1).replace('_', ' ')}
                                                        • Surety: {bond.surety_code} {bond.surety_name && `(${bond.surety_name})`}
                                                    </p>
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                {bond.bond_amount && (
                                                    <p className="font-medium text-gray-900">{formatCurrency(bond.bond_amount)}</p>
                                                )}
                                                <p className="text-sm text-gray-500">
                                                    {bond.coverage_start && bond.coverage_end && (
                                                        <>
                                                            {new Date(bond.coverage_start).toLocaleDateString()} - {new Date(bond.coverage_end).toLocaleDateString()}
                                                        </>
                                                    )}
                                                </p>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    ) : (
                        <Card>
                            <CardContent className="py-8 text-center">
                                <Shield className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                                <p className="text-gray-500">No bonds on file</p>
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}

            {activeTab === 'entries' && (
                <Card>
                    <CardContent className="py-8 text-center">
                        <FileText className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                        <p className="text-gray-500 mb-4">View entries filed for this client</p>
                        <Button onClick={() => navigate(`/entries?client=${clientId}`)}>
                            View Entries
                        </Button>
                    </CardContent>
                </Card>
            )}

            {activeTab === 'settings' && (
                <div className="grid grid-cols-2 gap-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Entry Preferences</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex items-center justify-between py-2 border-b border-gray-100">
                                <span className="text-gray-600">Default Entry Type</span>
                                <span className="font-medium">{client.settings?.default_entry_type || '01'}</span>
                            </div>
                            <div className="flex items-center justify-between py-2 border-b border-gray-100">
                                <span className="text-gray-600">Default Port</span>
                                <span className="font-medium">{client.settings?.default_port || client.customs?.primary_port || '-'}</span>
                            </div>
                            <div className="flex items-center justify-between py-2 border-b border-gray-100">
                                <span className="text-gray-600">Require Approval Before Filing</span>
                                <span className={`font-medium ${client.settings?.require_approval_before_file ? 'text-green-600' : 'text-gray-400'}`}>
                                    {client.settings?.require_approval_before_file ? 'Yes' : 'No'}
                                </span>
                            </div>
                            <div className="flex items-center justify-between py-2">
                                <span className="text-gray-600">Auto-Calculate Duties</span>
                                <span className={`font-medium ${client.settings?.auto_calculate_duties ? 'text-green-600' : 'text-gray-400'}`}>
                                    {client.settings?.auto_calculate_duties ? 'Yes' : 'No'}
                                </span>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Notification Settings</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex items-center justify-between py-2 border-b border-gray-100">
                                <span className="text-gray-600">On Entry Filing</span>
                                {client.settings?.notifications?.on_entry_file ? (
                                    <CheckCircle className="w-4 h-4 text-green-600" />
                                ) : (
                                    <X className="w-4 h-4 text-gray-400" />
                                )}
                            </div>
                            <div className="flex items-center justify-between py-2 border-b border-gray-100">
                                <span className="text-gray-600">On CBP Response</span>
                                {client.settings?.notifications?.on_cbp_response ? (
                                    <CheckCircle className="w-4 h-4 text-green-600" />
                                ) : (
                                    <X className="w-4 h-4 text-gray-400" />
                                )}
                            </div>
                            <div className="flex items-center justify-between py-2 border-b border-gray-100">
                                <span className="text-gray-600">On Document Ready</span>
                                {client.settings?.notifications?.on_document_ready ? (
                                    <CheckCircle className="w-4 h-4 text-green-600" />
                                ) : (
                                    <X className="w-4 h-4 text-gray-400" />
                                )}
                            </div>
                            <div className="flex items-center justify-between py-2">
                                <span className="text-gray-600">On Duty Payment</span>
                                {client.settings?.notifications?.on_duty_payment ? (
                                    <CheckCircle className="w-4 h-4 text-green-600" />
                                ) : (
                                    <X className="w-4 h-4 text-gray-400" />
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    )
}

export default ClientDetailPage
