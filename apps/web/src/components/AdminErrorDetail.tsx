import React, { useState, useEffect } from "react";
import { Toast } from "./Toast";
import { Button } from "./Button";
import { Card } from "./Card";

interface ErrorDetail {
  id: string;
  file_id: string;
  agent_id: string;
  error_type: string;
  error_classification: string;
  stack_trace: string | null;
  processing_step: string;
  retry_count: number;
  max_retries: number;
  error_timestamp: string;
  last_attempt_ts: string | null;
}

interface AdminErrorDetailProps {
  errorId: string;
  onClose?: () => void;
  onRetry?: (errorId: string) => void;
}

export const AdminErrorDetail: React.FC<AdminErrorDetailProps> = ({
  errorId,
  onClose,
  onRetry,
}) => {
  const [error, setError] = useState<ErrorDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRetrying, setIsRetrying] = useState(false);
  const [toast, setToast] = useState<{
    id: string;
    message: string;
    type: "success" | "error";
  } | null>(null);

  useEffect(() => {
    const fetchError = async () => {
      setIsLoading(true);
      try {
        const response = await fetch(`/api/admin/errors/${errorId}`);
        if (!response.ok) throw new Error("Failed to load error details");
        const data = await response.json();
        setError(data);
      } catch (error) {
        setToast({
          id: "load-error",
          message: "Failed to load error details",
          type: "error",
        });
      } finally {
        setIsLoading(false);
      }
    };

    fetchError();
  }, [errorId]);

  const handleRetry = async () => {
    setIsRetrying(true);
    try {
      const response = await fetch(`/api/admin/errors/${errorId}/retry`, {
        method: "POST",
      });

      if (!response.ok) throw new Error("Retry request failed");

      setToast({
        id: `retry-success-${Date.now()}`,
        message: "File queued for retry",
        type: "success",
      });

      onRetry?.(errorId);

      // Refresh error details
      const refreshResponse = await fetch(`/api/admin/errors/${errorId}`);
      if (refreshResponse.ok) {
        const data = await refreshResponse.json();
        setError(data);
      }
    } catch (error) {
      setToast({
        id: `retry-error-${Date.now()}`,
        message: `Failed to retry: ${error instanceof Error ? error.message : "Unknown error"}`,
        type: "error",
      });
    } finally {
      setIsRetrying(false);
    }
  };

  if (isLoading) {
    return (
      <Card className="p-4">
        <div className="text-center py-8 text-gray-500">Loading...</div>
      </Card>
    );
  }

  if (!error) {
    return (
      <Card className="p-4">
        <div className="text-center py-8 text-gray-500">Error not found</div>
      </Card>
    );
  }

  const canRetry =
    error.error_classification === "transient" &&
    error.retry_count < error.max_retries;

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

      <Card className="p-4">
        <div className="flex justify-between items-start mb-4">
          <h2 className="text-lg font-semibold">Error Details</h2>
          {onClose && (
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          )}
        </div>

        {/* Error metadata */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <p className="text-xs text-gray-500">File ID</p>
            <p className="font-mono text-sm">{error.file_id}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Agent ID</p>
            <p className="text-sm">{error.agent_id}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Error Type</p>
            <p className="text-sm font-medium">{error.error_type}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Processing Step</p>
            <p className="text-sm">{error.processing_step}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Classification</p>
            <span
              className={`text-xs px-2 py-1 rounded inline-block ${
                error.error_classification === "transient"
                  ? "bg-yellow-100 text-yellow-800"
                  : "bg-red-100 text-red-800"
              }`}
            >
              {error.error_classification}
            </span>
          </div>
          <div>
            <p className="text-xs text-gray-500">Retries</p>
            <p className="text-sm">
              {error.retry_count} / {error.max_retries}
            </p>
          </div>
        </div>

        {/* Timestamps */}
        <div className="grid grid-cols-2 gap-4 mb-4 p-3 bg-gray-50 rounded-md">
          <div>
            <p className="text-xs text-gray-500">Error Time</p>
            <p className="text-xs">
              {new Date(error.error_timestamp).toLocaleString()}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Last Attempt</p>
            <p className="text-xs">
              {error.last_attempt_ts
                ? new Date(error.last_attempt_ts).toLocaleString()
                : "Not attempted"}
            </p>
          </div>
        </div>

        {/* Stack trace */}
        {error.stack_trace && (
          <div className="mb-4">
            <p className="text-sm font-medium mb-2">Stack Trace</p>
            <pre className="bg-gray-800 text-gray-100 p-3 rounded-md text-xs overflow-x-auto max-h-64 overflow-y-auto">
              {error.stack_trace}
            </pre>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          {canRetry && (
            <Button
              onClick={handleRetry}
              isLoading={isRetrying}
              size="sm"
              variant="primary"
            >
              {isRetrying ? "Retrying..." : "Retry Processing"}
            </Button>
          )}
          {!canRetry && (
            <p className="text-xs text-gray-500">
              {error.error_classification === "permanent"
                ? "This is a permanent error and cannot be retried"
                : "Maximum retries exceeded"}
            </p>
          )}
          {onClose && (
            <Button
              onClick={onClose}
              size="sm"
              variant="secondary"
            >
              Close
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
};
