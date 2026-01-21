import React, { useState, useEffect } from "react";
import { Toast } from "./Toast";
import { Button } from "./Button";
import { Card } from "./Card";
import { Input } from "./Input";

interface QueuedFile {
  file_id: string;
  filename: string;
  status: string;
  file_type: string;
  current_agent_id: string;
  upload_timestamp: string;
  dispatched_at: string;
  file_size: number;
}

interface OverridePanelProps {
  onOverrideSuccess?: () => void;
}

export const AdminOverridePanel: React.FC<OverridePanelProps> = ({
  onOverrideSuccess,
}) => {
  const [queuedFiles, setQueuedFiles] = useState<QueuedFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<QueuedFile | null>(null);
  const [newAgentId, setNewAgentId] = useState("");
  const [reason, setReason] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [toast, setToast] = useState<{
    id: string;
    message: string;
    type: "success" | "error";
  } | null>(null);

  // Fetch queued files on mount
  useEffect(() => {
    const fetchQueuedFiles = async () => {
      setIsLoading(true);
      try {
        const response = await fetch("/api/admin/queues?page=1&page_size=50");
        if (!response.ok) throw new Error("Failed to fetch queued files");
        const data = await response.json();
        setQueuedFiles(data.items);
      } catch (error) {
        setToast({
          id: "load-error",
          message: "Failed to load queued files",
          type: "error",
        });
      } finally {
        setIsLoading(false);
      }
    };

    fetchQueuedFiles();
  }, []);

  const handleOverride = async () => {
    if (!selectedFile || !newAgentId.trim()) {
      setToast({
        id: "validation-error",
        message: "Please select a file and enter an agent ID",
        type: "error",
      });
      return;
    }

    setIsSubmitting(true);
    const startTime = Date.now();

    try {
      const adminId = localStorage.getItem("user_id") || "admin";

      const response = await fetch("/api/admin/override", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_id: selectedFile.file_id,
          new_agent_id: newAgentId,
          reason: reason || undefined,
          admin_id: adminId,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Override failed");
      }

      await response.json();
      const elapsed = Date.now() - startTime;

      setToast({
        id: `override-success-${Date.now()}`,
        message: `✓ File reassigned to ${newAgentId} (${elapsed}ms)`,
        type: "success",
      });

      // Reset form
      setSelectedFile(null);
      setNewAgentId("");
      setReason("");

      // Refresh queued files
      const refreshResponse = await fetch(
        "/api/admin/queues?page=1&page_size=50"
      );
      if (refreshResponse.ok) {
        const data = await refreshResponse.json();
        setQueuedFiles(data.items);
      }

      onOverrideSuccess?.();
    } catch (error) {
      setToast({
        id: `override-error-${Date.now()}`,
        message: `Error: ${error instanceof Error ? error.message : "Unknown error"}`,
        type: "error",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

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
        <h2 className="text-lg font-semibold mb-4">File Routing Override</h2>

        {isLoading ? (
          <div className="text-center py-8 text-gray-500">Loading files...</div>
        ) : queuedFiles.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No queued or failed files
          </div>
        ) : (
          <>
            {/* File selector */}
            <div className="space-y-2 mb-4">
              <label className="block text-sm font-medium">
                Select Queued File
              </label>
              <select
                value={selectedFile?.file_id || ""}
                onChange={(e) => {
                  const file = queuedFiles.find((f) => f.file_id === e.target.value);
                  setSelectedFile(file || null);
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">-- Select a file --</option>
                {queuedFiles.map((file) => (
                  <option key={file.file_id} value={file.file_id}>
                    {file.filename} ({file.status})
                  </option>
                ))}
              </select>
            </div>

            {/* File details */}
            {selectedFile && (
              <div className="mb-4 p-3 bg-blue-50 rounded-md text-sm">
                <p>
                  <strong>Current Agent:</strong> {selectedFile.current_agent_id}
                </p>
                <p>
                  <strong>Type:</strong> {selectedFile.file_type}
                </p>
                <p>
                  <strong>Size:</strong>{" "}
                  {(selectedFile.file_size / 1024).toFixed(2)} KB
                </p>
              </div>
            )}

            {/* Agent input */}
            <div className="space-y-2 mb-4">
              <label className="block text-sm font-medium">Target Agent ID</label>
              <Input
                type="text"
                value={newAgentId}
                onChange={(e) => setNewAgentId(e.target.value)}
                placeholder="e.g., pdf-extractor-v1"
                disabled={!selectedFile}
              />
            </div>

            {/* Reason */}
            <div className="space-y-2 mb-4">
              <label className="block text-sm font-medium">
                Reason (optional)
              </label>
              <Input
                type="text"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Why are you reassigning this file?"
                disabled={!selectedFile}
              />
            </div>

            {/* Submit button */}
            <Button
              onClick={handleOverride}
              disabled={!selectedFile || !newAgentId.trim() || isSubmitting}
              isLoading={isSubmitting}
              className="w-full"
            >
              {isSubmitting ? "Processing..." : "Override & Requeue"}
            </Button>
          </>
        )}
      </Card>
    </div>
  );
};
