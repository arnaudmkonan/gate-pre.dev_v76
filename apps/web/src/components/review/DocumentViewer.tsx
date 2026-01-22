import { FileText, File } from 'lucide-react'

interface DocumentViewerProps {
  content?: string
  filename?: string
  fileType?: string
  className?: string
}

export const DocumentViewer = ({
  content,
  filename,
  fileType,
  className = ''
}: DocumentViewerProps) => {
  const getFileIcon = () => {
    if (!fileType) return <File className="w-6 h-6" />
    const type = fileType.toLowerCase()
    if (['pdf', 'doc', 'docx', 'txt', 'md'].includes(type)) {
      return <FileText className="w-6 h-6" />
    }
    return <File className="w-6 h-6" />
  }

  if (!content) {
    return (
      <div className={`flex flex-col items-center justify-center py-12 text-gray-400 ${className}`}>
        {getFileIcon()}
        <p className="mt-2 text-sm">No preview available</p>
      </div>
    )
  }

  return (
    <div className={`bg-gray-50 rounded-lg ${className}`}>
      {filename && (
        <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-200 bg-white rounded-t-lg">
          {getFileIcon()}
          <span className="font-medium text-gray-900 truncate">{filename}</span>
          {fileType && (
            <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded uppercase">
              {fileType}
            </span>
          )}
        </div>
      )}
      <div className="p-4 max-h-[500px] overflow-auto">
        <pre className="text-sm text-gray-700 whitespace-pre-wrap font-mono">
          {content}
        </pre>
      </div>
    </div>
  )
}
