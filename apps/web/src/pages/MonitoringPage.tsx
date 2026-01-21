/**
 * Monitoring Dashboard Page
 */

import { useState, useEffect } from "react";
import { monitoringApi, MonitoringStatus } from "../lib/api/monitoring";

export default function MonitoringPage() {
  const [statuses, setStatuses] = useState<MonitoringStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadStatuses = async () => {
      try {
        setLoading(true);
        const data = await monitoringApi.listStatuses();
        setStatuses(data.statuses || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load monitoring statuses");
      } finally {
        setLoading(false);
      }
    };

    loadStatuses();
    // Refresh every 30 seconds
    const interval = setInterval(loadStatuses, 30000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "healthy":
        return "bg-green-100 text-green-800";
      case "degraded":
        return "bg-yellow-100 text-yellow-800";
      case "failed":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">Monitoring Dashboard</h1>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-gray-600">Loading monitoring statuses...</p>
      ) : statuses.length === 0 ? (
        <p className="text-gray-600">No monitoring data available</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {statuses.map((status) => (
            <div key={status.id} className="border rounded-lg p-4 bg-white">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h3 className="font-semibold">
                    {status.pipeline_id ? `Pipeline: ${status.pipeline_id}` : `Worker: ${status.worker_id}`}
                  </h3>
                </div>
                <span className={`px-3 py-1 rounded text-sm font-medium ${getStatusColor(status.status)}`}>
                  {status.status.toUpperCase()}
                </span>
              </div>

              <div className="text-sm text-gray-600 space-y-2">
                <p>Last Checked: {new Date(status.last_checked_at).toLocaleString()}</p>

                {status.connectivity_status && (
                  <div className="mt-3 pt-3 border-t">
                    <p className="font-medium mb-2">Connectivity:</p>
                    <ul className="space-y-1 text-xs">
                      <li>Storage: {status.connectivity_status.storage}</li>
                      <li>Queue: {status.connectivity_status.queue}</li>
                      <li>Database: {status.connectivity_status.database}</li>
                    </ul>
                  </div>
                )}

                {status.error_message && (
                  <div className="mt-3 pt-3 border-t">
                    <p className="font-medium text-red-700 text-xs">Error: {status.error_message}</p>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
