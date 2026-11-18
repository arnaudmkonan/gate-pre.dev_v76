import { useState, useEffect } from 'react'
import { FileText, File, Download, Eye, AlignLeft, Loader } from 'lucide-react'
import { authFetch } from '../../lib/authFetch'

interface DocumentViewerProps {
  documentId?: string
  content?: string
  filename?: string
  fileType?: string
  className?: string
}

export const DocumentViewer = ({
  documentId,
  content,
  filename,
  fileType,
  className = ''
}: DocumentViewerProps) => {
  const normalizedType = (fileType || filename?.split('.').pop() || '').toLowerCase()
  const isVisualFile = ['pdf', 'png', 'jpg', 'jpeg', 'html'].includes(normalizedType)

  const [viewMode, setViewMode] = useState<'original' | 'text'>(
    documentId && isVisualFile ? 'original' : 'text'
  )
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [loadingFile, setLoadingFile] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)

  useEffect(() => {
    setViewMode(documentId && isVisualFile ? 'original' : 'text')
  }, [documentId, isVisualFile])

  useEffect(() => {
    if (!documentId) {
      setBlobUrl(null)
      return
    }

    let active = true
    let createdUrl: string | null = null

    const fetchOriginalFile = async () => {
      setLoadingFile(true)
      setFileError(null)
      try {
        const resp = await authFetch(`/api/files/document/${documentId}/content`)
        if (!resp.ok) {
          throw new Error(`Original file unavailable (HTTP ${resp.status})`)
        }
        const blob = await resp.blob()
        if (!active) return
        createdUrl = URL.createObjectURL(blob)
        setBlobUrl(createdUrl)
      } catch (err) {
        if (!active) return
        setFileError(err instanceof Error ? err.message : 'Could not load original file')
        if (content) {
          setViewMode('text')
        }
      } finally {
        if (active) {
          setLoadingFile(false)
        }
      }
    }

    fetchOriginalFile()

    return () => {
      active = false
      if (createdUrl) {
        URL.revokeObjectURL(createdUrl)
      }
    }
  }, [documentId])

  const handleDownload = async () => {
    if (!documentId) return
    try {
      const resp = await authFetch(`/api/files/document/${documentId}/content?download=true`)
      if (!resp.ok) return
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename || `document_${documentId.slice(0, 8)}.${normalizedType || 'bin'}`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      // ignore download error
    }
  }

  const getFileIcon = () => {
    if (!normalizedType) return <File className="w-5 h-5 text-blue-600" />
    if (['pdf', 'doc', 'docx', 'txt', 'md'].includes(normalizedType)) {
      return <FileText className="w-5 h-5 text-blue-600" />
    }
    return <File className="w-5 h-5 text-blue-600" />
  }

  if (!content && !documentId) {
    return (
      <div className={`flex flex-col items-center justify-center py-12 text-gray-400 ${className}`}>
        {getFileIcon()}
        <p className="mt-2 text-sm">No preview available</p>
      </div>
    )
  }

  return (
    <div className={`bg-gray-50 rounded-lg border border-gray-200 overflow-hidden ${className}`}>
      {/* Toolbar Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-2 min-w-0">
          {getFileIcon()}
          <span className="font-medium text-sm text-gray-900 truncate">
            {filename || 'Document'}
          </span>
          {normalizedType && (
            <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded uppercase">
              {normalizedType}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          {documentId && (
            <div className="inline-flex rounded-md border border-gray-200 bg-gray-50 p-0.5">
              <button
                type="button"
                onClick={() => setViewMode('original')}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  viewMode === 'original'
                    ? 'bg-white text-blue-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <Eye className="w-3.5 h-3.5" />
                Original
              </button>
              <button
                type="button"
                onClick={() => setViewMode('text')}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  viewMode === 'text'
                    ? 'bg-white text-blue-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <AlignLeft className="w-3.5 h-3.5" />
                Extracted Text
              </button>
            </div>
          )}

          {documentId && (
            <button
              type="button"
              onClick={handleDownload}
              title="Download original file"
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-gray-700 bg-white border border-gray-200 rounded hover:bg-gray-50"
            >
              <Download className="w-3.5 h-3.5" />
              Download
            </button>
          )}
        </div>
      </div>

      {/* Viewer Body */}
      {viewMode === 'original' && documentId ? (
        <div className="min-h-[550px] bg-gray-100 flex flex-col">
          {loadingFile ? (
            <div className="flex flex-col items-center justify-center flex-1 py-20 text-gray-500">
              <Loader className="w-6 h-6 animate-spin mb-2 text-blue-500" />
              <p className="text-sm">Loading original document...</p>
            </div>
          ) : fileError || !blobUrl ? (
            <div className="flex flex-col items-center justify-center flex-1 py-16 px-4 text-center">
              <p className="text-sm text-gray-600 mb-2">
                {fileError || 'Original file preview unavailable'}
              </p>
              {content && (
                <button
                  type="button"
                  onClick={() => setViewMode('text')}
                  className="text-xs text-blue-600 hover:underline font-medium"
                >
                  Switch to Extracted Text View
                </button>
              )}
            </div>
          ) : normalizedType === 'pdf' || normalizedType === 'html' ? (
            <iframe
              src={blobUrl}
              title={filename || 'Document Preview'}
              className="w-full h-[640px] border-0 bg-white"
            />
          ) : ['png', 'jpg', 'jpeg'].includes(normalizedType) ? (
            <div className="p-4 flex items-center justify-center overflow-auto max-h-[640px]">
              <img
                src={blobUrl}
                alt={filename || 'Document'}
                className="max-w-full h-auto rounded shadow-sm"
              />
            </div>
          ) : (
            <div className="p-6 text-center space-y-3">
              <p className="text-sm text-gray-600">
                Direct browser rendering is not supported for <strong>.{normalizedType}</strong> files.
              </p>
              <div className="flex justify-center gap-3">
                <button
                  type="button"
                  onClick={handleDownload}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded hover:bg-blue-700"
                >
                  <Download className="w-4 h-4" />
                  Download .{normalizedType.toUpperCase()} File
                </button>
                {content && (
                  <button
                    type="button"
                    onClick={() => setViewMode('text')}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50"
                  >
                    <AlignLeft className="w-4 h-4" />
                    View Extracted Content
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="p-4 max-h-[640px] overflow-auto bg-gray-50">
          {content ? (
            <pre className="text-sm text-gray-800 whitespace-pre-wrap font-mono leading-relaxed">
              {content}
            </pre>
          ) : (
            <p className="text-sm text-gray-400 text-center py-12">
              No extracted text snippet available
            </p>
          )}
        </div>
      )}
    </div>
  )
}
