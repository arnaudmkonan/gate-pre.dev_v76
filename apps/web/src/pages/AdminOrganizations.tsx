import { useEffect, useState } from "react";
import axios from "axios";
import { Plus, Edit2, Trash2, Users } from "lucide-react";

interface Organization {
  id: string;
  name: string;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface CreateOrgData {
  name: string;
  description?: string;
}

export default function AdminOrganizations() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState<CreateOrgData>({ name: "", description: "" });
  const [submitting, setSubmitting] = useState(false);

  const fetchOrganizations = async () => {
    try {
      setLoading(true);
      const response = await axios.get("/api/admin/organizations/");
      setOrganizations(response.data.organizations || []);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch organizations"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrganizations();
  }, []);

  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      setError("Organization name is required");
      return;
    }

    try {
      setSubmitting(true);
      await axios.post("/api/admin/organizations/", formData);
      setFormData({ name: "", description: "" });
      setShowCreateForm(false);
      fetchOrganizations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create organization");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteOrg = async (orgId: string) => {
    if (!window.confirm("Are you sure you want to delete this organization?")) return;

    try {
      await axios.delete(`/api/admin/organizations/${orgId}`);
      fetchOrganizations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete organization");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Organizations</h1>
        <button
          onClick={() => setShowCreateForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 font-medium"
        >
          <Plus className="h-4 w-4" />
          New Organization
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Create Form */}
      {showCreateForm && (
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold mb-4">Create Organization</h2>
          <form onSubmit={handleCreateOrg} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Organization name"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Description</label>
              <textarea
                value={formData.description || ""}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Organization description"
                rows={3}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {submitting ? "Creating..." : "Create"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Organizations List */}
      <div className="rounded-lg border bg-white shadow-sm overflow-hidden">
        {organizations.length > 0 ? (
          <div className="divide-y">
            {organizations.map((org) => (
              <div key={org.id} className="p-4 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-medium text-lg">{org.name}</h3>
                    {org.description && (
                      <p className="text-sm text-gray-600 mt-1">{org.description}</p>
                    )}
                    <div className="flex gap-4 mt-2 text-xs text-gray-500">
                      <span>Created: {new Date(org.created_at).toLocaleDateString()}</span>
                      <span>Status: {org.is_active ? "Active" : "Inactive"}</span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                      title="Manage users"
                    >
                      <Users className="h-4 w-4" />
                    </button>
                    <button
                      className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                      title="Edit organization"
                    >
                      <Edit2 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => handleDeleteOrg(org.id)}
                      className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                      title="Delete organization"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-8 text-center text-gray-500">
            No organizations created yet
          </div>
        )}
      </div>
    </div>
  );
}
