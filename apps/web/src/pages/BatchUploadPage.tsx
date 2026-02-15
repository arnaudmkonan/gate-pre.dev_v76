/**
 * Batch Upload Page
 *
 * Allows uploading ZIP files or multiple files for batch processing.
 * Shows batch job progress and status.
 */

import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

// API URL - empty string uses relative path (works with nginx proxy)
const API_URL = import.meta.env.VITE_API_URL || '';

interface BatchJob {
  id: string;
  name: string;
  description?: string;
  status: string;
  total_documents: number;
  processed_documents: number;
  successful_documents: number;
  failed_documents: number;
  pending_review: number;
  approved_documents: number;
  progress_percent: number;
  started_at?: string;
  completed_at?: string;
  processing_time_seconds?: number;
  export_status?: string;
  created_at: string;
}

interface DuplicateMatch {
  document_id: string;
  filename: string;
  match_type: string;
  confidence: number;
  match_details: Record<string, any>;
  created_at: string;
}

interface DuplicateCheckResult {
  is_duplicate: boolean;
  highest_confidence: number;
  matches: DuplicateMatch[];
  checks_performed: string[];
}

export function BatchUploadPage() {
  const [batchJobs, setBatchJobs] = useState<BatchJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [batchName, setBatchName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null);
  const [uploadMode, setUploadMode] = useState<'zip' | 'multi'>('zip');

  // Duplicate detection state
  const [checkingDuplicates, setCheckingDuplicates] = useState(false);
  const [duplicateResults, setDuplicateResults] = useState<Map<string, DuplicateCheckResult>>(new Map());
  const [showDuplicateWarning, setShowDuplicateWarning] = useState(false);

  const loadBatchJobs = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/batch/jobs?limit=20`);
      setBatchJobs(response.data.jobs || []);
    } catch (err) {
      console.error('Failed to load batch jobs:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBatchJobs();
    // Poll for updates every 5 seconds
    const interval = setInterval(loadBatchJobs, 5000);
    return () => clearInterval(interval);
  }, [loadBatchJobs]);

  // Check for duplicates before uploading
  const checkDuplicates = async () => {
    if (!selectedFiles || selectedFiles.length === 0 || uploadMode === 'zip') {
      return;
    }

    setCheckingDuplicates(true);
    const results = new Map<string, DuplicateCheckResult>();

    for (let i = 0; i < selectedFiles.length; i++) {
      const file = selectedFiles[i];
      try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await axios.post<DuplicateCheckResult>(
          `${API_URL}/api/duplicates/check-file`,
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' } }
        );

        if (response.data.is_duplicate) {
          results.set(file.name, response.data);
        }
      } catch (err) {
        console.error(`Failed to check duplicate for ${file.name}:`, err);
      }
    }

    setDuplicateResults(results);
    setShowDuplicateWarning(results.size > 0);
    setCheckingDuplicates(false);
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedFiles || selectedFiles.length === 0) {
      setError('Please select files to upload');
      return;
    }

    if (!batchName.trim()) {
      setError('Please enter a batch name');
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    setError(null);
    setShowDuplicateWarning(false);

    try {
      const formData = new FormData();

      if (uploadMode === 'zip') {
        // Single ZIP file upload
        formData.append('file', selectedFiles[0]);
        formData.append('name', batchName);
        if (description) formData.append('description', description);

        await axios.post(`${API_URL}/batch/upload?name=${encodeURIComponent(batchName)}`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (progressEvent) => {
            const percent = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1));
            setUploadProgress(percent);
          },
        });
      } else {
        // Multi-file upload
        for (let i = 0; i < selectedFiles.length; i++) {
          formData.append('files', selectedFiles[i]);
        }

        await axios.post(
          `${API_URL}/batch/upload/multifile?name=${encodeURIComponent(batchName)}${description ? `&description=${encodeURIComponent(description)}` : ''}`,
          formData,
          {
            headers: { 'Content-Type': 'multipart/form-data' },
            onUploadProgress: (progressEvent) => {
              const percent = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1));
              setUploadProgress(percent);
            },
          }
        );
      }

      // Reset form and reload
      setBatchName('');
      setDescription('');
      setSelectedFiles(null);
      loadBatchJobs();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleExport = async (batchJobId: string) => {
    try {
      const response = await axios.get(`${API_URL}/batch/jobs/${batchJobId}/export`, {
        responseType: 'blob',
      });

      // Download the file
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `batch_${batchJobId.slice(0, 8)}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error('Export failed:', err);
      alert('Export failed. Make sure reviewed documents are available.');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'processing':
        return 'bg-blue-100 text-blue-800';
      case 'reviewing':
        return 'bg-yellow-100 text-yellow-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Batch Upload</h1>
        <p className="text-gray-600 mt-1">
          Upload multiple documents at once for batch processing
        </p>
      </div>

      {/* Upload Form */}
      <div className="bg-white border rounded-lg p-6 mb-8">
        <h2 className="text-xl font-semibold mb-4">New Batch Upload</h2>

        <form onSubmit={handleUpload} className="space-y-4">
          {/* Upload Mode Toggle */}
          <div className="flex gap-4 mb-4">
            <button
              type="button"
              onClick={() => setUploadMode('zip')}
              className={`px-4 py-2 rounded-lg ${uploadMode === 'zip'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
            >
              ZIP File
            </button>
            <button
              type="button"
              onClick={() => setUploadMode('multi')}
              className={`px-4 py-2 rounded-lg ${uploadMode === 'multi'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
            >
              Multiple Files
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Batch Name *
              </label>
              <input
                type="text"
                value={batchName}
                onChange={(e) => setBatchName(e.target.value)}
                placeholder="e.g., January 2026 Invoices"
                className="w-full border rounded-lg px-3 py-2"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                className="w-full border rounded-lg px-3 py-2"
              />
            </div>
          </div>

          {/* File Input */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {uploadMode === 'zip' ? 'ZIP File' : 'Files'} *
            </label>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
              <input
                type="file"
                accept={uploadMode === 'zip' ? '.zip' : undefined}
                multiple={uploadMode === 'multi'}
                onChange={(e) => setSelectedFiles(e.target.files)}
                className="hidden"
                id="file-input"
              />
              <label
                htmlFor="file-input"
                className="cursor-pointer flex flex-col items-center"
              >
                <svg
                  className="w-12 h-12 text-gray-400 mb-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
                <span className="text-gray-600">
                  {selectedFiles
                    ? `${selectedFiles.length} file(s) selected`
                    : `Drop ${uploadMode === 'zip' ? 'a ZIP file' : 'files'} here or click to browse`}
                </span>
                <span className="text-sm text-gray-400 mt-1">
                  {uploadMode === 'zip'
                    ? 'Maximum 100 files per ZIP, 50MB per file'
                    : 'Supports PDF, DOCX, XLSX, TXT, and more'}
                </span>
              </label>
            </div>
          </div>

          {/* Duplicate Check Button (for multi-file mode) */}
          {uploadMode === 'multi' && selectedFiles && selectedFiles.length > 0 && (
            <button
              type="button"
              onClick={checkDuplicates}
              disabled={checkingDuplicates}
              className="px-4 py-2 bg-yellow-100 text-yellow-800 rounded-lg hover:bg-yellow-200 disabled:opacity-50"
            >
              {checkingDuplicates ? 'Checking for duplicates...' : 'Check for Duplicates'}
            </button>
          )}

          {/* Duplicate Warning */}
          {showDuplicateWarning && duplicateResults.size > 0 && (
            <div className="p-4 bg-yellow-50 border border-yellow-300 rounded-lg">
              <div className="flex items-start gap-2">
                <svg className="w-5 h-5 text-yellow-600 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <div className="flex-1">
                  <h4 className="font-semibold text-yellow-800">Potential Duplicates Detected</h4>
                  <p className="text-sm text-yellow-700 mb-2">
                    {duplicateResults.size} file(s) may already exist in the system:
                  </p>
                  <ul className="text-sm space-y-2">
                    {Array.from(duplicateResults.entries()).map(([filename, result]) => (
                      <li key={filename} className="bg-white p-2 rounded border border-yellow-200">
                        <span className="font-medium">{filename}</span>
                        <span className="text-yellow-600 ml-2">
                          ({Math.round(result.highest_confidence * 100)}% match)
                        </span>
                        {result.matches[0] && (
                          <div className="text-xs text-gray-500 mt-1">
                            Matches: {result.matches[0].filename} ({result.matches[0].match_type})
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                  <p className="text-xs text-yellow-600 mt-2">
                    You can still upload these files. They will be flagged for review.
                  </p>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg">
              {error}
            </div>
          )}

          {/* Progress Bar */}
          {uploading && (
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          )}

          <button
            type="submit"
            disabled={uploading || !selectedFiles}
            className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {uploading ? `Uploading... ${uploadProgress}%` : 'Upload Batch'}
          </button>
        </form>
      </div>

      {/* Batch Jobs List */}
      <div className="bg-white border rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">Batch Jobs</h2>

        {loading ? (
          <p className="text-gray-500">Loading...</p>
        ) : batchJobs.length === 0 ? (
          <p className="text-gray-500">No batch jobs yet. Upload your first batch above.</p>
        ) : (
          <div className="space-y-4">
            {batchJobs.map((job) => (
              <div
                key={job.id}
                className="border rounded-lg p-4 hover:bg-gray-50"
              >
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="font-semibold text-lg">{job.name}</h3>
                    {job.description && (
                      <p className="text-sm text-gray-500">{job.description}</p>
                    )}
                  </div>
                  <span
                    className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(job.status)}`}
                  >
                    {job.status}
                  </span>
                </div>

                {/* Progress Bar */}
                <div className="w-full bg-gray-200 rounded-full h-2 mb-3">
                  <div
                    className={`h-2 rounded-full transition-all ${job.status === 'completed' ? 'bg-green-500' : 'bg-blue-500'
                      }`}
                    style={{ width: `${job.progress_percent}%` }}
                  />
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">Total:</span>{' '}
                    <span className="font-medium">{job.total_documents}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Processed:</span>{' '}
                    <span className="font-medium">{job.processed_documents}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Success:</span>{' '}
                    <span className="font-medium text-green-600">{job.successful_documents}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Failed:</span>{' '}
                    <span className="font-medium text-red-600">{job.failed_documents}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Pending Review:</span>{' '}
                    <span className="font-medium text-yellow-600">{job.pending_review}</span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-2 mt-4">
                  <a
                    href={`/review?batch=${job.id}`}
                    className="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                  >
                    View Documents
                  </a>
                  {(job.status === 'completed' || job.status === 'reviewing') && (
                    <button
                      onClick={() => handleExport(job.id)}
                      className="px-3 py-1 text-sm bg-green-100 text-green-700 rounded hover:bg-green-200"
                    >
                      Export CSV
                    </button>
                  )}
                </div>

                {/* Timing */}
                {job.processing_time_seconds && (
                  <p className="text-xs text-gray-400 mt-2">
                    Processed in {job.processing_time_seconds.toFixed(1)}s
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default BatchUploadPage;
