import { useEffect, useState } from "react";
import axios from "axios";
import {
    Users,
    Mail,
    Building2,
    Phone,
    Calendar,
    Eye,
    Edit,
    Trash2,
    RefreshCw,
    Search,
    Filter,
    TrendingUp,
    ChevronDown,
    X,
} from "lucide-react";

interface Lead {
    id: string;
    first_name: string;
    last_name: string;
    email: string;
    company: string;
    phone: string | null;
    company_size: string | null;
    role: string | null;
    source: string | null;
    status: string;
    registered_at: string;
    created_at: string;
}

interface LeadStats {
    total: number;
    by_status: Record<string, number>;
    by_source: Record<string, number>;
    by_role: Record<string, number>;
}

const STATUS_COLORS: Record<string, string> = {
    new: "bg-blue-100 text-blue-700",
    contacted: "bg-yellow-100 text-yellow-700",
    qualified: "bg-purple-100 text-purple-700",
    converted: "bg-green-100 text-green-700",
    lost: "bg-gray-100 text-gray-700",
};

const ROLE_LABELS: Record<string, string> = {
    customs_broker: "Customs Broker",
    freight_forwarder: "Freight Forwarder",
    importer: "Importer / Shipper",
    compliance: "Trade Compliance",
    operations: "Operations Manager",
    it: "IT / Technology",
    executive: "Executive / Owner",
    other: "Other",
};

export function LeadManagementPage() {
    const [leads, setLeads] = useState<Lead[]>([]);
    const [stats, setStats] = useState<LeadStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [_error, setError] = useState<string | null>(null);
    const [searchTerm, setSearchTerm] = useState("");
    const [statusFilter, setStatusFilter] = useState<string>("");
    const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
    const [editingLead, setEditingLead] = useState<Lead | null>(null);
    const [editStatus, setEditStatus] = useState("");
    const [editNotes, setEditNotes] = useState("");

    const fetchLeads = async () => {
        try {
            setLoading(true);
            const [leadsRes, statsRes] = await Promise.all([
                axios.get("/api/leads"),
                axios.get("/api/leads/stats/summary"),
            ]);
            setLeads(leadsRes.data.leads);
            setStats(statsRes.data);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to fetch leads");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchLeads();
    }, []);

    const handleUpdateLead = async () => {
        if (!editingLead) return;

        try {
            await axios.patch(`/api/leads/${editingLead.id}`, {
                status: editStatus,
                notes: editNotes || undefined,
            });
            setEditingLead(null);
            fetchLeads();
        } catch (err) {
            console.error("Failed to update lead:", err);
        }
    };

    const handleDeleteLead = async (id: string) => {
        if (!confirm("Are you sure you want to delete this lead?")) return;

        try {
            await axios.delete(`/api/leads/${id}`);
            fetchLeads();
        } catch (err) {
            console.error("Failed to delete lead:", err);
        }
    };

    const filteredLeads = leads.filter((lead) => {
        const matchesSearch =
            lead.first_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            lead.last_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            lead.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
            lead.company.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesStatus = !statusFilter || lead.status === statusFilter;
        return matchesSearch && matchesStatus;
    });

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    };

    if (loading && leads.length === 0) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
            </div>
        );
    }

    return (
        <div className="space-y-6 p-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Lead Management</h1>
                    <p className="text-gray-500 mt-1">
                        Manage trial registrations and demo requests
                    </p>
                </div>
                <button
                    onClick={fetchLeads}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
                >
                    <RefreshCw className="h-4 w-4" />
                    Refresh
                </button>
            </div>

            {/* Stats Cards */}
            {stats && (
                <div className="grid grid-cols-4 gap-4">
                    <div className="bg-white rounded-xl border p-6 shadow-sm">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-indigo-100 rounded-lg">
                                <Users className="h-6 w-6 text-indigo-600" />
                            </div>
                            <div>
                                <p className="text-sm text-gray-500">Total Leads</p>
                                <p className="text-2xl font-bold">{stats.total}</p>
                            </div>
                        </div>
                    </div>

                    <div className="bg-white rounded-xl border p-6 shadow-sm">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-blue-100 rounded-lg">
                                <TrendingUp className="h-6 w-6 text-blue-600" />
                            </div>
                            <div>
                                <p className="text-sm text-gray-500">New</p>
                                <p className="text-2xl font-bold">{stats.by_status.new || 0}</p>
                            </div>
                        </div>
                    </div>

                    <div className="bg-white rounded-xl border p-6 shadow-sm">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-yellow-100 rounded-lg">
                                <Mail className="h-6 w-6 text-yellow-600" />
                            </div>
                            <div>
                                <p className="text-sm text-gray-500">Contacted</p>
                                <p className="text-2xl font-bold">
                                    {stats.by_status.contacted || 0}
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="bg-white rounded-xl border p-6 shadow-sm">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-green-100 rounded-lg">
                                <Building2 className="h-6 w-6 text-green-600" />
                            </div>
                            <div>
                                <p className="text-sm text-gray-500">Converted</p>
                                <p className="text-2xl font-bold">
                                    {stats.by_status.converted || 0}
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Filters */}
            <div className="flex items-center gap-4 bg-white rounded-xl border p-4 shadow-sm">
                <div className="flex-1 relative">
                    <Search className="h-5 w-5 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
                    <input
                        type="text"
                        placeholder="Search by name, email, or company..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    />
                </div>

                <div className="relative">
                    <Filter className="h-5 w-5 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
                    <select
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                        className="pl-10 pr-8 py-2 border rounded-lg appearance-none bg-white focus:ring-2 focus:ring-indigo-500 cursor-pointer"
                    >
                        <option value="">All Statuses</option>
                        <option value="new">New</option>
                        <option value="contacted">Contacted</option>
                        <option value="qualified">Qualified</option>
                        <option value="converted">Converted</option>
                        <option value="lost">Lost</option>
                    </select>
                    <ChevronDown className="h-4 w-4 text-gray-400 absolute right-3 top-1/2 transform -translate-y-1/2 pointer-events-none" />
                </div>
            </div>

            {/* Leads Table */}
            <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
                <table className="w-full">
                    <thead className="bg-gray-50 border-b">
                        <tr>
                            <th className="text-left px-6 py-4 text-sm font-semibold text-gray-600">
                                Contact
                            </th>
                            <th className="text-left px-6 py-4 text-sm font-semibold text-gray-600">
                                Company
                            </th>
                            <th className="text-left px-6 py-4 text-sm font-semibold text-gray-600">
                                Role
                            </th>
                            <th className="text-left px-6 py-4 text-sm font-semibold text-gray-600">
                                Source
                            </th>
                            <th className="text-left px-6 py-4 text-sm font-semibold text-gray-600">
                                Status
                            </th>
                            <th className="text-left px-6 py-4 text-sm font-semibold text-gray-600">
                                Registered
                            </th>
                            <th className="text-right px-6 py-4 text-sm font-semibold text-gray-600">
                                Actions
                            </th>
                        </tr>
                    </thead>
                    <tbody className="divide-y">
                        {filteredLeads.length === 0 ? (
                            <tr>
                                <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                                    {leads.length === 0
                                        ? "No leads yet. They'll appear here when users register."
                                        : "No leads match your search criteria."}
                                </td>
                            </tr>
                        ) : (
                            filteredLeads.map((lead) => (
                                <tr key={lead.id} className="hover:bg-gray-50 transition-colors">
                                    <td className="px-6 py-4">
                                        <div>
                                            <p className="font-medium text-gray-900">
                                                {lead.first_name} {lead.last_name}
                                            </p>
                                            <p className="text-sm text-gray-500">{lead.email}</p>
                                            {lead.phone && (
                                                <p className="text-xs text-gray-400 flex items-center gap-1 mt-1">
                                                    <Phone className="h-3 w-3" />
                                                    {lead.phone}
                                                </p>
                                            )}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-2">
                                            <Building2 className="h-4 w-4 text-gray-400" />
                                            <div>
                                                <p className="font-medium text-gray-900">{lead.company}</p>
                                                {lead.company_size && (
                                                    <p className="text-xs text-gray-500">
                                                        {lead.company_size} employees
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className="text-sm text-gray-600">
                                            {lead.role
                                                ? ROLE_LABELS[lead.role] || lead.role
                                                : "—"}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className="text-sm text-gray-600">
                                            {lead.source?.replace(/_/g, " ") || "—"}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4">
                                        <span
                                            className={`px-3 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[lead.status] || "bg-gray-100 text-gray-700"
                                                }`}
                                        >
                                            {lead.status.toUpperCase()}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-2 text-sm text-gray-500">
                                            <Calendar className="h-4 w-4" />
                                            {formatDate(lead.registered_at)}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center justify-end gap-2">
                                            <button
                                                onClick={() => setSelectedLead(lead)}
                                                className="p-2 text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                                                title="View details"
                                            >
                                                <Eye className="h-4 w-4" />
                                            </button>
                                            <button
                                                onClick={() => {
                                                    setEditingLead(lead);
                                                    setEditStatus(lead.status);
                                                    setEditNotes("");
                                                }}
                                                className="p-2 text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                                                title="Edit"
                                            >
                                                <Edit className="h-4 w-4" />
                                            </button>
                                            <button
                                                onClick={() => handleDeleteLead(lead.id)}
                                                className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                                title="Delete"
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            {/* View Lead Modal */}
            {selectedLead && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold">Lead Details</h2>
                            <button
                                onClick={() => setSelectedLead(null)}
                                className="p-2 hover:bg-gray-100 rounded-lg"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <p className="text-sm text-gray-500">Name</p>
                                    <p className="font-medium">
                                        {selectedLead.first_name} {selectedLead.last_name}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Email</p>
                                    <a
                                        href={`mailto:${selectedLead.email}`}
                                        className="font-medium text-indigo-600 hover:underline"
                                    >
                                        {selectedLead.email}
                                    </a>
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <p className="text-sm text-gray-500">Company</p>
                                    <p className="font-medium">{selectedLead.company}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Company Size</p>
                                    <p className="font-medium">
                                        {selectedLead.company_size || "Not specified"}
                                    </p>
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <p className="text-sm text-gray-500">Phone</p>
                                    <p className="font-medium">
                                        {selectedLead.phone || "Not provided"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Role</p>
                                    <p className="font-medium">
                                        {selectedLead.role
                                            ? ROLE_LABELS[selectedLead.role] || selectedLead.role
                                            : "Not specified"}
                                    </p>
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <p className="text-sm text-gray-500">Source</p>
                                    <p className="font-medium">
                                        {selectedLead.source?.replace(/_/g, " ") || "Unknown"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Status</p>
                                    <span
                                        className={`px-3 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[selectedLead.status] ||
                                            "bg-gray-100 text-gray-700"
                                            }`}
                                    >
                                        {selectedLead.status.toUpperCase()}
                                    </span>
                                </div>
                            </div>

                            <div>
                                <p className="text-sm text-gray-500">Registered</p>
                                <p className="font-medium">
                                    {formatDate(selectedLead.registered_at)}
                                </p>
                            </div>
                        </div>

                        <div className="flex justify-end gap-3 mt-6 pt-4 border-t">
                            <button
                                onClick={() => setSelectedLead(null)}
                                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                            >
                                Close
                            </button>
                            <a
                                href={`mailto:${selectedLead.email}?subject=DocuMind%20-%20Follow%20up%20on%20your%20trial&body=Hi%20${selectedLead.first_name},%0A%0AThank%20you%20for%20signing%20up%20for%20DocuMind!`}
                                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
                            >
                                Send Email
                            </a>
                        </div>
                    </div>
                </div>
            )}

            {/* Edit Lead Modal */}
            {editingLead && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold">Update Lead Status</h2>
                            <button
                                onClick={() => setEditingLead(null)}
                                className="p-2 hover:bg-gray-100 rounded-lg"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Status
                                </label>
                                <select
                                    value={editStatus}
                                    onChange={(e) => setEditStatus(e.target.value)}
                                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500"
                                >
                                    <option value="new">New</option>
                                    <option value="contacted">Contacted</option>
                                    <option value="qualified">Qualified</option>
                                    <option value="converted">Converted</option>
                                    <option value="lost">Lost</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Notes
                                </label>
                                <textarea
                                    value={editNotes}
                                    onChange={(e) => setEditNotes(e.target.value)}
                                    placeholder="Add notes about this lead..."
                                    rows={3}
                                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500"
                                />
                            </div>
                        </div>

                        <div className="flex justify-end gap-3 mt-6 pt-4 border-t">
                            <button
                                onClick={() => setEditingLead(null)}
                                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleUpdateLead}
                                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
                            >
                                Save Changes
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default LeadManagementPage;
