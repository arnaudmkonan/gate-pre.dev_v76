import { useEffect, useState } from "react";
import axios from "axios";
import { Activity, AlertCircle, BarChart3, Clock } from "lucide-react";

interface DashboardData {
  pipeline_status: {
    status: string;
    active_jobs: number;
    completed_jobs: number;
    failed_jobs: number;
  };
  queue_length: {
    pending: number;
    running: number;
    failed: number;
    total: number;
  };
  recent_errors: {
    errors: Array<{
      id: string;
      error_type: string;
      message: string;
      timestamp: string;
      file_id?: string;
    }>;
    total_errors_24h: number;
  };
  throughput: {
    metrics: Array<{
      timestamp: string;
      files_processed: number;
    }>;
    average_files_per_hour: number;
  };
  timestamp: string;
}

export default function AdminDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const fetchData = async () => {
    try {
      setLoading(true);
      const response = await axios.get("/api/admin/dashboard/");
      setData(response.data);
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch dashboard data"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000); // Auto-refresh every 15 seconds
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      </div>
    );
  }

  if (!data) {
    return <div className="text-center py-10">No data available</div>;
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Admin Dashboard</h1>
        <button
          onClick={fetchData}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
        >
          Refresh
        </button>
      </div>

      <div className="text-sm text-gray-500">
        Last updated: {lastUpdate.toLocaleTimeString()}
      </div>

      {/* Pipeline Status Widget */}
      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Pipeline Status
          </h2>
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${
              data.pipeline_status.status === "idle"
                ? "bg-gray-100 text-gray-700"
                : data.pipeline_status.status === "running"
                  ? "bg-green-100 text-green-700"
                  : data.pipeline_status.status === "paused"
                    ? "bg-yellow-100 text-yellow-700"
                    : "bg-red-100 text-red-700"
            }`}
          >
            {data.pipeline_status.status.toUpperCase()}
          </span>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-sm text-gray-500">Active Jobs</p>
            <p className="text-2xl font-bold">{data.pipeline_status.active_jobs}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Completed</p>
            <p className="text-2xl font-bold">{data.pipeline_status.completed_jobs}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Failed</p>
            <p className="text-2xl font-bold text-red-600">{data.pipeline_status.failed_jobs}</p>
          </div>
        </div>
      </div>

      {/* Queue Length Widget */}
      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
          <Clock className="h-5 w-5" />
          Queue Metrics
        </h2>
        <div className="grid grid-cols-4 gap-4">
          <div>
            <p className="text-sm text-gray-500">Pending</p>
            <p className="text-2xl font-bold">{data.queue_length.pending}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Running</p>
            <p className="text-2xl font-bold">{data.queue_length.running}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Failed</p>
            <p className="text-2xl font-bold text-red-600">{data.queue_length.failed}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Total</p>
            <p className="text-2xl font-bold">{data.queue_length.total}</p>
          </div>
        </div>
      </div>

      {/* Recent Errors Widget */}
      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
          <AlertCircle className="h-5 w-5" />
          Recent Errors (24h: {data.recent_errors.total_errors_24h})
        </h2>
        {data.recent_errors.errors.length > 0 ? (
          <div className="space-y-3">
            {data.recent_errors.errors.map((error) => (
              <div key={error.id} className="border-l-4 border-red-500 bg-red-50 p-3">
                <div className="flex justify-between">
                  <span className="font-medium text-sm">{error.error_type}</span>
                  <span className="text-xs text-gray-500">
                    {new Date(error.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-sm text-gray-700 mt-1">{error.message}</p>
                {error.file_id && (
                  <p className="text-xs text-gray-500 mt-1">File: {error.file_id}</p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500">No errors in recent data</p>
        )}
      </div>

      {/* Throughput Widget */}
      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
          <BarChart3 className="h-5 w-5" />
          Throughput (24h Average: {data.throughput.average_files_per_hour.toFixed(2)} files/hour)
        </h2>
        <div className="space-y-2">
          {data.throughput.metrics.length > 0 ? (
            data.throughput.metrics.slice(-12).map((metric) => (
              <div key={metric.timestamp} className="flex items-center gap-4">
                <span className="text-xs text-gray-500 w-20">
                  {new Date(metric.timestamp).toLocaleTimeString()}
                </span>
                <div className="flex-1 bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full"
                    style={{
                      width: `${(metric.files_processed / 100) * 100}%`,
                    }}
                  ></div>
                </div>
                <span className="text-sm font-medium w-12">{metric.files_processed}</span>
              </div>
            ))
          ) : (
            <p className="text-gray-500">No throughput data available</p>
          )}
        </div>
      </div>
    </div>
  );
}
