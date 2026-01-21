/**
 * Retry Policy Management Page
 */

import { useState } from "react";
import { retryPolicyApi, RetryPolicy } from "../lib/api/retry_policy";

export default function RetryPolicyPage() {
  const [pipelineId, setPipelineId] = useState("");
  const [policy, setPolicy] = useState<RetryPolicy | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<{
    policy_type: "exponential" | "fixed" | "linear" | "none";
    max_attempts: number;
    base_delay_ms: number;
    max_delay_ms: number;
    jitter: boolean;
  }>({
    policy_type: "exponential",
    max_attempts: 3,
    base_delay_ms: 1000,
    max_delay_ms: 60000,
    jitter: true,
  });

  const loadPolicy = async (id: string) => {
    if (!id) return;
    try {
      setLoading(true);
      setError(null);
      const data = await retryPolicyApi.getPolicy(id);
      setPolicy(data);
      setFormData({
        policy_type: data.policy_type as "exponential" | "fixed" | "linear" | "none",
        max_attempts: data.max_attempts,
        base_delay_ms: data.base_delay_ms,
        max_delay_ms: data.max_delay_ms,
        jitter: data.jitter,
      });
    } catch (err) {
      if ((err as any).message?.includes("404")) {
        setPolicy(null);
      } else {
        setError(err instanceof Error ? err.message : "Failed to load policy");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!pipelineId) {
      setError("Pipeline ID is required");
      return;
    }

    try {
      if (policy) {
        await retryPolicyApi.updatePolicy(pipelineId, formData);
      } else {
        await retryPolicyApi.createPolicy({
          pipeline_id: pipelineId,
          ...formData,
        });
      }
      setShowForm(false);
      loadPolicy(pipelineId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save policy");
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">Retry Policy Management</h1>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      <div className="mb-6 flex gap-4">
        <input
          type="text"
          placeholder="Enter Pipeline ID"
          value={pipelineId}
          onChange={(e) => {
            setPipelineId(e.target.value);
            setPolicy(null);
          }}
          className="border rounded px-3 py-2 flex-1"
        />
        <button
          onClick={() => loadPolicy(pipelineId)}
          disabled={loading || !pipelineId}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:bg-gray-400"
        >
          Load Policy
        </button>
      </div>

      {loading ? (
        <p className="text-gray-600">Loading policy...</p>
      ) : policy ? (
        <div className="bg-white border rounded-lg p-6">
          <div className="mb-6">
            <h2 className="text-xl font-semibold mb-4">Current Policy</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-600">Policy Type</p>
                <p className="font-medium">{policy.policy_type}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Max Attempts</p>
                <p className="font-medium">{policy.max_attempts}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Base Delay (ms)</p>
                <p className="font-medium">{policy.base_delay_ms}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Max Delay (ms)</p>
                <p className="font-medium">{policy.max_delay_ms}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Jitter Enabled</p>
                <p className="font-medium">{policy.jitter ? "Yes" : "No"}</p>
              </div>
            </div>
          </div>

          <button
            onClick={() => setShowForm(!showForm)}
            className="bg-yellow-600 text-white px-4 py-2 rounded hover:bg-yellow-700"
          >
            {showForm ? "Cancel" : "Edit Policy"}
          </button>
        </div>
      ) : pipelineId ? (
        <div className="bg-white border rounded-lg p-6 text-center">
          <p className="text-gray-600 mb-4">No policy found for this pipeline</p>
          <button
            onClick={() => setShowForm(true)}
            className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
          >
            Create New Policy
          </button>
        </div>
      ) : null}

      {showForm && pipelineId && (
        <form onSubmit={(e) => { e.preventDefault(); handleSave(); }} className="bg-white border rounded-lg p-6 mt-6">
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium mb-2">Policy Type</label>
              <select
                value={formData.policy_type}
                onChange={(e) => {
                  const val = e.target.value as "exponential" | "fixed" | "linear" | "none";
                  setFormData({ ...formData, policy_type: val });
                }}
                className="border rounded px-3 py-2 w-full"
              >
                <option value="exponential">Exponential Backoff</option>
                <option value="linear">Linear Backoff</option>
                <option value="fixed">Fixed Delay</option>
                <option value="none">No Retry</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Max Attempts</label>
              <input
                type="number"
                min="1"
                value={formData.max_attempts}
                onChange={(e) => setFormData({ ...formData, max_attempts: Number(e.target.value) })}
                className="border rounded px-3 py-2 w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Base Delay (ms)</label>
              <input
                type="number"
                min="100"
                value={formData.base_delay_ms}
                onChange={(e) => setFormData({ ...formData, base_delay_ms: Number(e.target.value) })}
                className="border rounded px-3 py-2 w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Max Delay (ms)</label>
              <input
                type="number"
                min="1000"
                value={formData.max_delay_ms}
                onChange={(e) => setFormData({ ...formData, max_delay_ms: Number(e.target.value) })}
                className="border rounded px-3 py-2 w-full"
              />
            </div>
          </div>
          <div className="mb-4">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={formData.jitter}
                onChange={(e) => setFormData({ ...formData, jitter: e.target.checked })}
                className="rounded"
              />
              <span className="text-sm font-medium">Enable Jitter</span>
            </label>
          </div>
          <button
            type="submit"
            className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
          >
            Save Policy
          </button>
        </form>
      )}
    </div>
  );
}
