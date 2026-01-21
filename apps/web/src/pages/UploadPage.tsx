import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { UploadForm } from '../components/UploadForm'
import { FileVersionsList } from '../components/FileVersionsList'

export const UploadPage: React.FC = () => {
  const { fileId } = useParams<{ fileId: string }>()
  const [uploadedFileId, setUploadedFileId] = useState<string | null>(fileId || null)

  const handleUploadSuccess = (fileId: string) => {
    setUploadedFileId(fileId)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Document Upload</h1>
        <p className="text-gray-600 mt-2">
          Upload documents for ingestion and processing. Supported formats: txt, docx, xlsx, pptx, html, md, json, csv, yml, xml
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6">
        <UploadForm onUploadSuccess={handleUploadSuccess} />

        {uploadedFileId && <FileVersionsList fileId={uploadedFileId} />}
      </div>
    </div>
  )
}
