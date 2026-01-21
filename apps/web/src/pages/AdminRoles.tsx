import { useEffect, useState } from "react";
import axios from "axios";
import { Plus, Edit2, Trash2, Lock } from "lucide-react";

interface Role {
  id: string;
  name: string;
  description?: string;
  organization_id: string;
  permissions: string[];
  is_system: string;
  created_at: string;
  updated_at: string;
}

interface CreateRoleData {
  name: string;
  description?: string;
  organization_id: string;
  permissions: string[];
}

const AVAILABLE_PERMISSIONS = [
  "manage_organization",
  "manage_roles",
  "manage_users",
  "manage_mappings",
  "manage_retry",
  "view_dashboard",
  "view_audit",
  "manage_agents",
  "view_files",
  "manage_files",
];

export default function AdminRoles() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [orgId, setOrgId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState<CreateRoleData>({
    name: "",
    description: "",
    organization_id: "",
    permissions: [],
  });
  const [submitting, setSubmitting] = useState(false);

  const fetchRoles = async (selectedOrgId: string) => {
    if (!selectedOrgId) return;

    try {
      setLoading(true);
      const response = await axios.get("/api/admin/roles/", {
        params: { org_id: selectedOrgId },
      });
      setRoles(response.data.roles || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch roles");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (orgId) {
      fetchRoles(orgId);
    }
  }, [orgId]);

  const handleCreateRole = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.organization_id) {
      setError("Role name and organization are required");
      return;
    }

    try {
      setSubmitting(true);
      await axios.post("/api/admin/roles/", {
        ...formData,
        organization_id: formData.organization_id || orgId,
      });
      setFormData({
        name: "",
        description: "",
        organization_id: "",
        permissions: [],
      });
      setShowCreateForm(false);
      fetchRoles(orgId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create role");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteRole = async (roleId: string) => {
    if (!window.confirm("Are you sure you want to delete this role?")) return;

    try {
      await axios.delete(`/api/admin/roles/${roleId}`);
      fetchRoles(orgId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete role");
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Roles & Permissions</h1>
        {orgId && (
          <button
            onClick={() => setShowCreateForm(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 font-medium"
          >
            <Plus className="h-4 w-4" />
            New Role
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Organization Selector */}
      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <label className="block text-sm font-medium mb-2">Select Organization</label>
        <input
          type="text"
          placeholder="Enter organization ID or select from list"
          value={orgId}
          onChange={(e) => setOrgId(e.target.value)}
          className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <p className="text-xs text-gray-500 mt-1">
          Roles are organization-specific. Select an organization to view and manage its roles.
        </p>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold mb-4">Create Role</h2>
          <form onSubmit={handleCreateRole} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Role name (e.g., Manager, Editor)"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Description</label>
              <textarea
                value={formData.description || ""}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Role description"
                rows={2}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Permissions</label>
              <div className="grid grid-cols-2 gap-3">
                {AVAILABLE_PERMISSIONS.map((perm) => (
                  <label key={perm} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formData.permissions.includes(perm)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setFormData({
                            ...formData,
                            permissions: [...formData.permissions, perm],
                          });
                        } else {
                          setFormData({
                            ...formData,
                            permissions: formData.permissions.filter((p) => p !== perm),
                          });
                        }
                      }}
                      className="rounded"
                    />
                    <span className="text-sm">{perm.replace(/_/g, " ")}</span>
                  </label>
                ))}
              </div>
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
                disabled={submitting || !orgId}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {submitting ? "Creating..." : "Create"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Roles List */}
      {orgId ? (
        loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <div className="rounded-lg border bg-white shadow-sm overflow-hidden">
            {roles.length > 0 ? (
              <div className="divide-y">
                {roles.map((role) => (
                  <div key={role.id} className="p-4 hover:bg-gray-50">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium text-lg">{role.name}</h3>
                          {role.is_system === "true" && (
                            <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded-full">
                              System
                            </span>
                          )}
                        </div>
                        {role.description && (
                          <p className="text-sm text-gray-600 mt-1">{role.description}</p>
                        )}
                        <div className="mt-3 flex flex-wrap gap-1">
                          {role.permissions.map((perm) => (
                            <span
                              key={perm}
                              className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full"
                            >
                              <Lock className="h-3 w-3" />
                              {perm.replace(/_/g, " ")}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                          title="Edit role"
                        >
                          <Edit2 className="h-4 w-4" />
                        </button>
                        {role.is_system !== "true" && (
                          <button
                            onClick={() => handleDeleteRole(role.id)}
                            className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                            title="Delete role"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-gray-500">
                No roles found for this organization
              </div>
            )}
          </div>
        )
      ) : (
        <div className="p-8 text-center text-gray-500 rounded-lg border bg-white">
          Select an organization to view its roles
        </div>
      )}
    </div>
  );
}
