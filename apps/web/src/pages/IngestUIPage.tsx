import { useState } from 'react'
import { Link } from 'react-router-dom'
import { UploadForm, type UploadResponse } from '../components/UploadForm'
import { ModeSelector } from '../components/ModeSelector'
import { GuidedMapping } from '../components/GuidedMapping'
import { AdvancedBatch } from '../components/AdvancedBatch'
import { JobsDashboard } from '../components/JobsDashboard'
import { RetryPanel } from '../components/RetryPanel'
import { UploadNextSteps } from '../components/UploadNextSteps'

interface SelectedJob {
  id: string
}

type ModePanel = 'none' | 'mode' | 'guided' | 'advanced'
type ActionPanel = 'none' | 'retry'

export const IngestUIPage: React.FC = () => {
  const [uploadedJobId, setUploadedJobId] = useState<string | null>(null)
  const [uploadedFileId, setUploadedFileId] = useState<string | null>(null)
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null)
  const [selectedJob, setSelectedJob] = useState<SelectedJob | null>(null)
  const [modePanel, setModePanel] = useState<ModePanel>('none')
  const [actionPanel, setActionPanel] = useState<ActionPanel>('none')
  const [refreshKey, setRefreshKey] = useState(0)

  const handleUploadSuccess = (_fileId: string, jobId: string, meta?: UploadResponse) => {
    setUploadedJobId(jobId)
    setUploadedFileId(_fileId)
    setUploadedFilename(meta?.filename || null)
    setSelectedJob({ id: jobId })
    setModePanel('none')
    setActionPanel('none')
    setRefreshKey((k) => k + 1)
    // Scroll next-steps into view after paint
    requestAnimationFrame(() => {
      document.getElementById('upload-next-steps')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

  const handleJobSelect = (job: { id: string }) => {
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
    setUploadedJobId(newJobId)
    setActionPanel('none')
    setRefreshKey((k) => k + 1)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Ingest documents</h1>
        <p className="mt-1 text-gray-600">
          Upload a commercial invoice, B/L, packing list, or arrival notice. Extraction starts
          automatically — then follow the next steps to shipment and entry.
        </p>
        <p className="mt-2 text-sm text-slate-500">
          Path:{' '}
          <span className="font-medium text-slate-700">
            Upload → Extract → Doc exceptions (if needed) → Shipment assembly → Entry / ACE
          </span>
          {' · '}
          <Link to="/dashboard" className="text-blue-700 hover:underline">
            Workbench
          </Link>
        </p>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white">
        <div className="border-b border-gray-200 p-6">
          <h2 className="text-xl font-semibold text-gray-900">Upload</h2>
          <p className="mt-1 text-sm text-gray-600">
            PDF, spreadsheet, or customs packet — processing is queued as soon as upload succeeds.
          </p>
        </div>
        <UploadForm onUploadSuccess={handleUploadSuccess} hideInlineSuccess />
      </section>

      {uploadedJobId && (
        <div id="upload-next-steps">
          <UploadNextSteps
            jobId={uploadedJobId}
            fileId={uploadedFileId || undefined}
            filename={uploadedFilename || undefined}
            onDismiss={() => {
              setUploadedJobId(null)
              setUploadedFileId(null)
              setUploadedFilename(null)
              setModePanel('none')
            }}
            onShowAdvanced={() => setModePanel('mode')}
          />
        </div>
      )}

      {uploadedJobId && selectedJob && modePanel !== 'none' && (
        <section className="rounded-lg border border-amber-200 bg-amber-50/40">
          <div className="border-b border-amber-100 p-6">
            <h2 className="text-xl font-semibold text-gray-900">Advanced extraction mode</h2>
            <p className="mt-1 text-sm text-gray-600">
              Optional. Most broker packets should stay on automatic extraction.
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

      <section id="live-pipeline" className="scroll-mt-6 rounded-lg border border-gray-200 bg-white">
        <div className="border-b border-gray-200 p-6">
          <h2 className="text-xl font-semibold text-gray-900">Live ingest pipeline</h2>
          <p className="mt-1 text-sm text-gray-600">
            Your upload appears here. Status moves queued → processing → completed (or failed).
            {uploadedJobId ? ' The job you just uploaded is highlighted.' : ''}
          </p>
        </div>
        <div className="p-6">
          <JobsDashboard
            key={refreshKey}
            highlightJobId={uploadedJobId || undefined}
            onJobSelect={handleJobSelect}
            onRetryClick={handleRetryClick}
          />
        </div>
      </section>

      {selectedJob && actionPanel === 'retry' && (
        <section className="rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-200 p-6">
            <h2 className="text-xl font-semibold text-gray-900">Retry failed document</h2>
            <p className="mt-1 text-sm text-gray-600">
              Re-queue failed ingestion with optional extractor overrides
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
    </div>
  )
}
