/**
 * Alerts Management Page
 */

import { useState, useEffect } from "react";
import { alertsApi, AlertRule } from "../lib/api/alerts";

export default function AlertsPage() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<{
    name: string;
    metric_type: string;
    threshold: number;
    severity: "critical" | "warning" | "info";
    notification_channels: string[];
  }>({
    name: "",
    metric_type: "error_rate",
    threshold: 10,
    severity: "warning",
    notification_channels: ["email"],
  });

  useEffect(() => {
    loadRules();
  }, []);

  const loadRules = async () => {
    try {
      setLoading(true);
      const data = await alertsApi.listRules();
      setRules(data.rules || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load alert rules");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRule = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    try {
      await alertsApi.createRule(formData);
      setShowForm(false);
      setFormData({
        name: "",
        metric_type: "error_rate",
        threshold: 10,
        severity: "warning",
        notification_channels: ["email"],
      });
      loadRules();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create alert rule");
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "critical":
        return "bg-red-100 text-red-800";
      case "warning":
        return "bg-yellow-100 text-yellow-800";
      case "info":
        return "bg-blue-100 text-blue-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Alert Rules</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
        >
          {showForm ? "Cancel" : "Create Alert Rule"}
        </button>
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {showForm && (
        <form onSubmit={handleCreateRule} className="bg-white p-4 rounded mb-6 border">
          <div className="grid grid-cols-2 gap-4">
            <input
              type="text"
              placeholder="Rule Name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="border rounded px-3 py-2"
              required
            />
            <select
              value={formData.metric_type}
              onChange={(e) => setFormData({ ...formData, metric_type: e.target.value })}
              className="border rounded px-3 py-2"
            >
              <option value="error_rate">Error Rate</option>
              <option value="dlq_size">DLQ Size</option>
              <option value="pipeline_latency">Pipeline Latency</option>
              <option value="sla_breach">SLA Breach</option>
            </select>
            <input
              type="number"
              placeholder="Threshold"
              value={formData.threshold}
              onChange={(e) => setFormData({ ...formData, threshold: Number(e.target.value) })}
              className="border rounded px-3 py-2"
            />
            <select
              value={formData.severity}
              onChange={(e) => setFormData({ ...formData, severity: e.target.value as "critical" | "warning" | "info" })}
              className="border rounded px-3 py-2"
            >
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
          </div>
          <button
            type="submit"
            className="mt-4 bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
          >
            Create Rule
          </button>
        </form>
      )}

      {loading ? (
        <p className="text-gray-600">Loading alert rules...</p>
      ) : rules.length === 0 ? (
        <p className="text-gray-600">No alert rules configured</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {rules.map((rule) => (
            <div key={rule.id} className="border rounded-lg p-4 bg-white">
              <div className="flex justify-between items-start mb-3">
                <h3 className="font-semibold">{rule.name}</h3>
                <span className={`px-3 py-1 rounded text-xs font-medium ${getSeverityColor(rule.severity)}`}>
                  {rule.severity.toUpperCase()}
                </span>
              </div>
              <div className="text-sm text-gray-600 space-y-2">
                <p>Metric Type: {rule.metric_type}</p>
                <p>Threshold: {rule.threshold}</p>
                <p>Evaluation Window: {rule.evaluation_window_minutes} minutes</p>
                <p>Status: {rule.enabled ? "Enabled" : "Disabled"}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
