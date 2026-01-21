import { useState } from 'react'
import { AuditLog } from '../components/AuditLog'
import { Input } from '../components/Input'

export const AuditPage: React.FC = () => {
  const [resourceId, setResourceId] = useState<string>('')
  const [resourceType, setResourceType] = useState<string>('')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Audit Log</h1>
        <p className="text-gray-600 mt-2">
          View and export audit logs for compliance and traceability
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input
          label="Resource ID (optional)"
          placeholder="Filter by resource ID"
          value={resourceId}
          onChange={(e) => setResourceId(e.target.value)}
        />
        <select
          value={resourceType}
          onChange={(e) => setResourceType(e.target.value)}
          className="px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Resource Types</option>
          <option value="file">File</option>
          <option value="version">Version</option>
          <option value="upload">Upload</option>
        </select>
      </div>

      <AuditLog
        resourceId={resourceId || undefined}
        resourceType={resourceType || undefined}
      />
    </div>
  )
}
