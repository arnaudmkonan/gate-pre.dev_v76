import { useState } from 'react'
import { UploadForm } from '../components/UploadForm'
import { ModeSelector } from '../components/ModeSelector'
import { GuidedMapping } from '../components/GuidedMapping'
import { AdvancedBatch } from '../components/AdvancedBatch'
import { JobsDashboard } from '../components/JobsDashboard'
import { RetryPanel } from '../components/RetryPanel'

interface SelectedJob {
  id: string
}

type ModePanel = 'none' | 'mode' | 'guided' | 'advanced'
type ActionPanel = 'none' | 'retry'

export const IngestUIPage: React.FC = () => {
  const [_uploadedJobId, setUploadedJobId] = useState<string | null>(null)
  const [selectedJob, setSelectedJob] = useState<SelectedJob | null>(null)
  const [modePanel, setModePanel] = useState<ModePanel>('none')
  const [actionPanel, setActionPanel] = useState<ActionPanel>('none')
  const [refreshKey, setRefreshKey] = useState(0)

  const handleUploadSuccess = (_fileId: string, jobId: string) => {
    setUploadedJobId(jobId)
    setSelectedJob({ id: jobId })
    setModePanel('mode')
    // Trigger dashboard refresh
    setRefreshKey((k) => k + 1)
  }

  const handleJobSelect = (job: any) => {
    setSelectedJob({ id: job.id })
    setModePanel('none')
    setActionPanel('none')
  }

  const handleRetryClick = (jobId: string) => {
    setSelectedJob({ id: jobId })
    setActionPanel('retry')
  }

  const handleModeSelect = (mode: string) => {
    if (selectedJob) {
      if (mode === 'guided_mapping') {
        setModePanel('guided')
      } else if (mode === 'advanced_batch') {
        setModePanel('advanced')
      } else {
        setModePanel('none')
      }
    }
  }

  const handleRetrySuccess = (newJobId: string) => {
    setSelectedJob({ id: newJobId })
    setActionPanel('none')
    setRefreshKey((k) => k + 1)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Trade Document Ingestion</h1>
        <p className="text-gray-600 mt-1">
          Upload Commercial Invoices, Bills of Lading, Packing Lists, and Arrival Notices for automated AI extraction and shipment assembly
        </p>
      </div>

      {/* Upload Form */}
      <section className="bg-white rounded-lg border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Upload Trade Documents</h2>
          <p className="text-sm text-gray-600 mt-1">
            Drag and drop PDFs, spreadsheets, or customs packets to start automated extraction
          </p>
        </div>
        <UploadForm onUploadSuccess={handleUploadSuccess} />
      </section>

      {/* Mode Selection */}
      {_uploadedJobId && selectedJob && modePanel !== 'none' && (
        <section className="bg-white rounded-lg border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">Extraction Mode</h2>
            <p className="text-sm text-gray-600 mt-1">
              Choose how to process the uploaded document
            </p>
          </div>

          {modePanel === 'mode' && (
            <div className="p-6">
              <ModeSelector
                jobId={selectedJob.id}
                onModeSelect={handleModeSelect}
                onSuccess={() => {
                  setModePanel('none')
                  setRefreshKey((k) => k + 1)
                }}
              />
            </div>
          )}

          {modePanel === 'guided' && (
            <div className="p-6">
              <GuidedMapping
                jobId={selectedJob.id}
                onMappingApply={() => {
                  setModePanel('none')
                  setRefreshKey((k) => k + 1)
                }}
                onClose={() => {
                  setModePanel('none')
                  setRefreshKey((k) => k + 1)
                }}
              />
            </div>
          )}

          {modePanel === 'advanced' && (
            <div className="p-6">
              <AdvancedBatch
                jobId={selectedJob.id}
                onBatchApply={() => {
                  setModePanel('none')
                  setRefreshKey((k) => k + 1)
                }}
                onClose={() => {
                  setModePanel('none')
                  setRefreshKey((k) => k + 1)
                }}
              />
            </div>
          )}
        </section>
      )}

      {/* Monitor Processing */}
      <section className="bg-white rounded-lg border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Live Ingestion Pipeline</h2>
          <p className="text-sm text-gray-600 mt-1">
            Real-time OCR, classification, entity extraction, and shipment auto-linking status
          </p>
        </div>
        <div className="p-6">
          <JobsDashboard
            key={refreshKey}
            onJobSelect={handleJobSelect}
            onRetryClick={handleRetryClick}
          />
        </div>
      </section>

      {/* Retry Failed Jobs */}
      {selectedJob && actionPanel === 'retry' && (
        <section className="bg-white rounded-lg border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">Retry Failed Document</h2>
            <p className="text-sm text-gray-600 mt-1">
              Re-queue failed ingestion jobs with optional extractor overrides
            </p>
          </div>
          <div className="p-6">
            <RetryPanel
              jobId={selectedJob.id}
              onRetrySuccess={handleRetrySuccess}
              onClose={() => {
                setActionPanel('none')
                setRefreshKey((k) => k + 1)
              }}
            />
          </div>
        </section>
      )}

      {/* Info Footer */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-sm text-blue-800">
          <span className="font-medium">Workflow:</span> Upload → Select Mode → Monitor → (Optional) Retry Failed
        </p>
      </div>
    </div>
  )
}
