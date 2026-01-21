import React, { useState, useEffect } from 'react'
import { Download, AlertCircle, Loader } from 'lucide-react'
import { Card } from './Card'

interface FileVersion {
  version_id: string
  version_number: number
  file_hash: string
  is_deduplicated: boolean
  storage_path: string
  created_at: string
  content_hash: string
  storage_size: number
}

interface FileVersionsListProps {
  fileId: string
}

export const FileVersionsList: React.FC<FileVersionsListProps> = ({ fileId }) => {
  const [versions, setVersions] = useState<FileVersion[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchVersions = async () => {
      setLoading(true)
      setError(null)

      try {
        const response = await fetch(`/api/files/${fileId}/versions`)

        if (!response.ok) {
          throw new Error('Failed to fetch versions')
        }

        const data = await response.json()
        setVersions(data.versions || [])
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load versions')
      } finally {
        setLoading(false)
      }
    }

    if (fileId) {
      fetchVersions()
    }
  }, [fileId])

  if (loading) {
    return (
      <Card>
        <div className="p-6 flex items-center justify-center gap-2">
          <Loader className="w-5 h-5 animate-spin" />
          <span>Loading versions...</span>
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <div className="p-6 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-600">{error}</p>
        </div>
      </Card>
    )
  }

  if (versions.length === 0) {
    return (
      <Card>
        <div className="p-6 text-center text-gray-500">
          <p>No versions available</p>
        </div>
      </Card>
    )
  }

  return (
    <Card>
      <div className="p-6 space-y-4">
        <h2 className="text-lg font-semibold">File Versions</h2>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left py-3 px-4 font-semibold">Version</th>
                <th className="text-left py-3 px-4 font-semibold">Size</th>
                <th className="text-left py-3 px-4 font-semibold">Hash</th>
                <th className="text-left py-3 px-4 font-semibold">Dedup</th>
                <th className="text-left py-3 px-4 font-semibold">Created</th>
                <th className="text-left py-3 px-4 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((version) => (
                <tr key={version.version_id} className="border-b hover:bg-gray-50">
                  <td className="py-3 px-4"># {version.version_number}</td>
                  <td className="py-3 px-4">
                    {(version.storage_size / 1024).toFixed(2)} KB
                  </td>
                  <td className="py-3 px-4">
                    <code className="text-xs bg-gray-100 px-2 py-1 rounded">
                      {version.file_hash.substring(0, 8)}...
                    </code>
                  </td>
                  <td className="py-3 px-4">
                    {version.is_deduplicated ? (
                      <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                        Yes
                      </span>
                    ) : (
                      <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
                        No
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-4">
                    {new Date(version.created_at).toLocaleString()}
                  </td>
                  <td className="py-3 px-4">
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-200 transition text-sm"
                      title="Download version"
                    >
                      <Download className="w-4 h-4" />
                      Download
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  )
}
