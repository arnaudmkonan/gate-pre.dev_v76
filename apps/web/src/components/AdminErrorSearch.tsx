import React, { useState } from "react";
import { Toast } from "./Toast";
import { Button } from "./Button";
import { Card } from "./Card";
import { Input } from "./Input";

interface ErrorRecord {
  id: string;
  file_id: string;
  agent_id: string;
  error_type: string;
  error_classification: string;
  processing_step: string;
  retry_count: number;
  max_retries: number;
  error_timestamp: string;
}

interface ErrorSearchResponse {
  total: number;
  page: number;
  page_size: number;
  items: ErrorRecord[];
}

interface AdminErrorSearchProps {
  onErrorSelect?: (error: ErrorRecord) => void;
}

export const AdminErrorSearch: React.FC<AdminErrorSearchProps> = ({
  onErrorSelect,
}) => {
  const [fileId, setFileId] = useState("");
  const [agentId, setAgentId] = useState("");
  const [errorType, setErrorType] = useState("");
  const [errors, setErrors] = useState<ErrorRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [toast, setToast] = useState<{
    id: string;
    message: string;
    type: "success" | "error";
  } | null>(null);

  const pageSize = 20;

  const handleSearch = async (searchPage = 1) => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      params.append("page", String(searchPage));
      params.append("page_size", String(pageSize));

      if (fileId.trim()) params.append("file_id", fileId);
      if (agentId.trim()) params.append("agent_id", agentId);
      if (errorType.trim()) params.append("error_type", errorType);

      const response = await fetch(
        `/api/admin/errors/search?${params.toString()}`
      );
      if (!response.ok) throw new Error("Search failed");

      const data: ErrorSearchResponse = await response.json();
      setErrors(data.items);
      setTotal(Number(data.total));
      setPage(Number(searchPage));
    } catch (error) {
      setToast({
        id: `search-error-${Date.now()}`,
        message: "Failed to search errors",
        type: "error",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setFileId("");
    setAgentId("");
    setErrorType("");
    setErrors([]);
    setTotal(0);
    setPage(1);
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-4">
      {toast && (
        <Toast
          id={toast.id}
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      {/* Search filters */}
      <Card className="p-4">
        <h2 className="text-lg font-semibold mb-4">Search Errors</h2>

        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="space-y-2">
            <label className="block text-sm font-medium">File ID</label>
            <Input
              type="text"
              value={fileId}
              onChange={(e) => setFileId(e.target.value)}
              placeholder="UUID or file name"
              className="text-sm"
            />
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-medium">Agent ID</label>
            <Input
              type="text"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              placeholder="Agent ID"
              className="text-sm"
            />
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-medium">Error Type</label>
            <Input
              type="text"
              value={errorType}
              onChange={(e) => setErrorType(e.target.value)}
              placeholder="Error type"
              className="text-sm"
            />
          </div>
        </div>

        <div className="flex gap-2">
          <Button
            onClick={() => handleSearch(1)}
            isLoading={isLoading}
            size="sm"
          >
            Search
          </Button>
          <Button onClick={handleReset} variant="secondary" size="sm">
            Reset
          </Button>
        </div>
      </Card>

      {/* Results */}
      {errors.length > 0 && (
        <Card className="p-4">
          <h3 className="text-md font-semibold mb-3">
            Results ({total} total)
          </h3>

          <div className="space-y-2 max-h-96 overflow-y-auto">
            {errors.map((error) => (
              <div
                key={error.id}
                className="p-3 border border-gray-200 rounded-md hover:bg-gray-50 cursor-pointer"
                onClick={() => onErrorSelect?.(error)}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <p className="text-sm font-medium">{error.error_type}</p>
                    <p className="text-xs text-gray-500">
                      File: {error.file_id.slice(0, 8)}... | Agent:{" "}
                      {error.agent_id}
                    </p>
                    <p className="text-xs text-gray-500">
                      Step: {error.processing_step}
                    </p>
                  </div>
                  <div className="text-right">
                    <span
                      className={`text-xs px-2 py-1 rounded ${
                        error.error_classification === "transient"
                          ? "bg-yellow-100 text-yellow-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      {error.error_classification}
                    </span>
                    <p className="text-xs text-gray-500 mt-1">
                      Retry {error.retry_count}/{error.max_retries}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-center gap-2 mt-4">
              <Button
                onClick={() => handleSearch(page - 1)}
                disabled={page === 1}
                size="sm"
                variant="secondary"
              >
                ← Prev
              </Button>
              <span className="text-sm self-center">
                Page {page} of {totalPages}
              </span>
              <Button
                onClick={() => handleSearch(page + 1)}
                disabled={page === totalPages}
                size="sm"
                variant="secondary"
              >
                Next →
              </Button>
            </div>
          )}
        </Card>
      )}

      {!isLoading && errors.length === 0 && (fileId || agentId || errorType) && (
        <Card className="p-4 text-center text-gray-500">
          No errors found matching your criteria
        </Card>
      )}
    </div>
  );
};
