/**
 * DLQ Management Page
 */

import { useState, useEffect } from "react";
import { dlqApi, DLQEntry } from "../lib/api/dlq";

export default function DLQManagementPage() {
  const [entries, setEntries] = useState<DLQEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterArchived, setFilterArchived] = useState(false);
  const [filterErrorType, setFilterErrorType] = useState("");

  useEffect(() => {
    loadEntries();
  }, [filterArchived, filterErrorType]);

  const loadEntries = async () => {
    try {
      setLoading(true);
      const data = await dlqApi.listEntries({
        archived: filterArchived ? undefined : false,
        error_type: filterErrorType || undefined,
      });
      setEntries(data.entries || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load DLQ entries");
    } finally {
      setLoading(false);
    }
  };

  const handleRequeue = async (entryId: string) => {
    try {
      await dlqApi.requeue(entryId);
      loadEntries();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to requeue entry");
    }
  };

  const handleArchive = async (entryId: string) => {
    try {
      await dlqApi.archive(entryId);
      loadEntries();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to archive entry");
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">Dead Letter Queue Management</h1>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      <div className="mb-6 flex gap-4">
        <div>
          <label className="block text-sm font-medium mb-2">Error Type</label>
          <input
            type="text"
            placeholder="Filter by error type"
            value={filterErrorType}
            onChange={(e) => setFilterErrorType(e.target.value)}
            className="border rounded px-3 py-2"
          />
        </div>
        <div className="flex items-end">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={filterArchived}
              onChange={(e) => setFilterArchived(e.target.checked)}
              className="rounded"
            />
            Show Archived
          </label>
        </div>
      </div>

      {loading ? (
        <p className="text-gray-600">Loading DLQ entries...</p>
      ) : entries.length === 0 ? (
        <p className="text-gray-600">No DLQ entries found</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead className="bg-gray-100">
              <tr>
                <th className="border px-4 py-2 text-left">File ID</th>
                <th className="border px-4 py-2 text-left">Pipeline</th>
                <th className="border px-4 py-2 text-left">Error Type</th>
                <th className="border px-4 py-2 text-left">Error Message</th>
                <th className="border px-4 py-2 text-left">Retries</th>
                <th className="border px-4 py-2 text-left">Created</th>
                <th className="border px-4 py-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id} className="hover:bg-gray-50">
                  <td className="border px-4 py-2 text-sm">{entry.file_id}</td>
                  <td className="border px-4 py-2 text-sm">{entry.pipeline}</td>
                  <td className="border px-4 py-2 text-sm font-medium">{entry.error_type}</td>
                  <td className="border px-4 py-2 text-sm max-w-md truncate">{entry.error_message}</td>
                  <td className="border px-4 py-2 text-center">{entry.retry_count}</td>
                  <td className="border px-4 py-2 text-sm">{new Date(entry.created_at).toLocaleDateString()}</td>
                  <td className="border px-4 py-2 text-sm">
                    {!entry.archived && (
                      <>
                        <button
                          onClick={() => handleRequeue(entry.id)}
                          className="text-blue-600 hover:text-blue-800 mr-2"
                        >
                          Requeue
                        </button>
                        <button
                          onClick={() => handleArchive(entry.id)}
                          className="text-yellow-600 hover:text-yellow-800"
                        >
                          Archive
                        </button>
                      </>
                    )}
                    {entry.archived && <span className="text-gray-500">Archived</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
