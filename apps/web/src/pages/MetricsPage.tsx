/**
 * Metrics Dashboard Page
 */

import { useState, useEffect } from "react";
import { metricsApi, MetricsData } from "../lib/api/metrics";

export default function MetricsPage() {
  const [metrics, setMetrics] = useState<MetricsData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState("24h");

  useEffect(() => {
    loadMetrics();
  }, [timeRange]);

  const loadMetrics = async () => {
    try {
      setLoading(true);
      const data = await metricsApi.query({ time_range: timeRange });
      setMetrics(data.metrics || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load metrics");
    } finally {
      setLoading(false);
    }
  };

  const calculateAverages = () => {
    if (metrics.length === 0) {
      return {
        throughput: 0,
        latencyP50: 0,
        latencyP95: 0,
        latencyP99: 0,
        errorRate: 0,
      };
    }

    const sum = metrics.reduce(
      (acc, m) => ({
        throughput: acc.throughput + (m.throughput || 0),
        latencyP50: acc.latencyP50 + (m.latency_p50 || 0),
        latencyP95: acc.latencyP95 + (m.latency_p95 || 0),
        latencyP99: acc.latencyP99 + (m.latency_p99 || 0),
        errorRate: acc.errorRate + (m.error_rate || 0),
      }),
      {
        throughput: 0,
        latencyP50: 0,
        latencyP95: 0,
        latencyP99: 0,
        errorRate: 0,
      }
    );

    const count = metrics.length;
    return {
      throughput: Math.round(sum.throughput / count),
      latencyP50: Math.round(sum.latencyP50 / count),
      latencyP95: Math.round(sum.latencyP95 / count),
      latencyP99: Math.round(sum.latencyP99 / count),
      errorRate: (sum.errorRate / count).toFixed(2),
    };
  };

  const averages = calculateAverages();

  const StatCard = ({
    title,
    value,
    unit,
  }: {
    title: string;
    value: string | number;
    unit: string;
  }) => (
    <div className="bg-white border rounded-lg p-4">
      <p className="text-sm text-gray-600 mb-2">{title}</p>
      <p className="text-2xl font-bold text-blue-600">
        {value} <span className="text-sm text-gray-500">{unit}</span>
      </p>
    </div>
  );

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Metrics Dashboard</h1>
        <select
          value={timeRange}
          onChange={(e) => setTimeRange(e.target.value)}
          className="border rounded px-3 py-2"
        >
          <option value="1h">Last 1 Hour</option>
          <option value="24h">Last 24 Hours</option>
          <option value="7d">Last 7 Days</option>
          <option value="30d">Last 30 Days</option>
        </select>
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-gray-600">Loading metrics...</p>
      ) : metrics.length === 0 ? (
        <p className="text-gray-600">No metrics available for selected time range</p>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
            <StatCard title="Throughput" value={averages.throughput} unit="docs/sec" />
            <StatCard title="Latency P50" value={averages.latencyP50} unit="ms" />
            <StatCard title="Latency P95" value={averages.latencyP95} unit="ms" />
            <StatCard title="Latency P99" value={averages.latencyP99} unit="ms" />
            <StatCard title="Error Rate" value={averages.errorRate} unit="%" />
          </div>

          {/* Simple text-based metrics visualization */}
          <div className="bg-white border rounded-lg p-6 mb-8">
            <h2 className="text-xl font-semibold mb-4">Throughput Trend</h2>
            <div className="space-y-2">
              {metrics.slice(-10).map((m, idx) => (
                <div key={idx} className="flex items-center">
                  <div className="w-24 text-sm text-gray-600">
                    {new Date(m.timestamp).toLocaleTimeString()}
                  </div>
                  <div className="flex-1 h-6 bg-blue-200 rounded" style={{width: `${Math.max((m.throughput || 0) / 10, 2)}%`}}>
                    <div className="h-full bg-blue-500 rounded flex items-center justify-end px-2 text-xs text-white">
                      {m.throughput?.toFixed(1) || 0}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white border rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Error Rate Trend</h2>
            <div className="space-y-2">
              {metrics.slice(-10).map((m, idx) => (
                <div key={idx} className="flex items-center">
                  <div className="w-24 text-sm text-gray-600">
                    {new Date(m.timestamp).toLocaleTimeString()}
                  </div>
                  <div
                    className={`flex-1 h-6 rounded px-2 flex items-center justify-end text-xs text-white ${
                      (m.error_rate || 0) > 5 ? "bg-red-500" : "bg-green-500"
                    }`}
                    style={{ width: `${Math.max((m.error_rate || 0) * 20, 2)}%` }}
                  >
                    {m.error_rate?.toFixed(2) || 0}%
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
