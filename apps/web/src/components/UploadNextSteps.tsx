import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  Clock,
  Package,
  RefreshCw,
  Ship,
} from 'lucide-react'
import { authFetch } from '../lib/authFetch'
import { Button } from './Button'

interface JobStatus {
  id: string
  filename: string
  status: string
  progress_percentage?: number
  error_message?: string | null
}

interface UploadNextStepsProps {
  jobId: string
  fileId?: string
  filename?: string
  onDismiss?: () => void
  onShowAdvanced?: () => void
}

const PIPELINE = [
  { id: 'ingest', label: 'Ingest & extract', hint: 'OCR, classify, pull trade fields' },
  { id: 'exceptions', label: 'Doc exceptions', hint: 'HITL only if confidence is low' },
  { id: 'shipment', label: 'Shipment assembly', hint: 'Link CI / B/L / packing list' },
  { id: 'entry', label: '7501 → Broker OK → ACE', hint: 'Entry prep and filing' },
]

function statusTone(status: string) {
  const s = (status || '').toLowerCase()
  if (s === 'completed') return 'text-emerald-700 bg-emerald-50 border-emerald-200'
  if (s === 'failed') return 'text-red-700 bg-red-50 border-red-200'
  if (s === 'processing' || s === 'queued') return 'text-sky-800 bg-sky-50 border-sky-200'
  return 'text-slate-700 bg-slate-50 border-slate-200'
}

function humanStatus(status: string) {
  switch ((status || '').toLowerCase()) {
    case 'pending':
      return 'Waiting to start'
    case 'queued':
      return 'Queued for processing'
    case 'processing':
      return 'Extracting now'
    case 'completed':
      return 'Extraction finished'
    case 'failed':
      return 'Processing failed'
    default:
      return status || 'Unknown'
  }
}

export function UploadNextSteps({
  jobId,
  filename: filenameProp,
  onDismiss,
  onShowAdvanced,
}: UploadNextStepsProps) {
  const [job, setJob] = useState<JobStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const resp = await authFetch(`/api/ingest/jobs/${jobId}`)
      if (!resp.ok) {
        throw new Error(`Could not load job (${resp.status})`)
      }
      const data = await resp.json()
      setJob({
        id: data.id,
        filename: data.filename,
        status: data.status,
        progress_percentage: data.progress_percentage,
        error_message: data.error_message,
      })
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load job')
    } finally {
      setLoading(false)
    }
  }, [jobId])

  useEffect(() => {
    load()
    const id = setInterval(load, 3000)
    return () => clearInterval(id)
  }, [load])

  const status = (job?.status || 'queued').toLowerCase()
  const done = status === 'completed'
  const failed = status === 'failed'
  const inFlight = ['pending', 'queued', 'processing'].includes(status)
  const displayName = job?.filename || filenameProp || 'Your document'

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-5 py-4 sm:flex sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Where it went
          </p>
          <h2 className="mt-1 text-lg font-semibold text-slate-900">{displayName}</h2>
          <p className="mt-1 text-sm text-slate-600">
            Saved to the ingest queue and running through extraction automatically — you do not need
            to pick a mode.
          </p>
        </div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="mt-3 text-sm text-slate-500 hover:text-slate-800 sm:mt-0"
          >
            Dismiss
          </button>
        )}
      </div>

      <div className="space-y-5 px-5 py-5">
        <div
          className={`flex flex-wrap items-center gap-3 rounded-lg border px-4 py-3 ${statusTone(status)}`}
        >
          {loading ? (
            <RefreshCw className="h-5 w-5 animate-spin" />
          ) : failed ? (
            <AlertCircle className="h-5 w-5" />
          ) : done ? (
            <CheckCircle2 className="h-5 w-5" />
          ) : (
            <Clock className={`h-5 w-5 ${inFlight ? 'animate-pulse' : ''}`} />
          )}
          <div className="min-w-0 flex-1">
            <p className="font-medium">{humanStatus(status)}</p>
            {typeof job?.progress_percentage === 'number' && inFlight && (
              <p className="text-xs opacity-80">{job.progress_percentage}% complete</p>
            )}
            {failed && job?.error_message && (
              <p className="mt-1 text-xs">{job.error_message}</p>
            )}
          </div>
          <button
            type="button"
            onClick={load}
            className="inline-flex items-center gap-1 text-xs font-medium underline-offset-2 hover:underline"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
        </div>

        {error && (
          <p className="text-sm text-amber-800">
            Live status unavailable ({error}). Your file is still in the queue below.
          </p>
        )}

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            What to do next
          </p>
          <ol className="mt-3 space-y-3">
            {PIPELINE.map((step, idx) => {
              const active =
                (step.id === 'ingest' && inFlight) ||
                (step.id === 'exceptions' && done) ||
                (step.id === 'shipment' && done)
              return (
                <li key={step.id} className="flex gap-3">
                  <span
                    className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                      step.id === 'ingest' && done
                        ? 'bg-emerald-600 text-white'
                        : active
                          ? 'bg-slate-900 text-white'
                          : 'bg-slate-100 text-slate-500'
                    }`}
                  >
                    {step.id === 'ingest' && done ? '✓' : idx + 1}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-slate-900">{step.label}</p>
                    <p className="text-xs text-slate-500">{step.hint}</p>
                  </div>
                </li>
              )
            })}
          </ol>
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          {inFlight && (
            <a
              href="#live-pipeline"
              className="inline-flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
            >
              Watch this job in the pipeline
              <ArrowRight className="h-4 w-4 text-slate-400" />
            </a>
          )}
          {done && (
            <>
              <Link
                to="/review"
                className="inline-flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
              >
                <span className="inline-flex items-center gap-2">
                  <ClipboardCheck className="h-4 w-4" />
                  Check doc exceptions
                </span>
                <ArrowRight className="h-4 w-4 text-slate-400" />
              </Link>
              <Link
                to="/shipments/assembly"
                className="inline-flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
              >
                <span className="inline-flex items-center gap-2">
                  <Package className="h-4 w-4" />
                  Open shipment assembly
                </span>
                <ArrowRight className="h-4 w-4 text-slate-400" />
              </Link>
            </>
          )}
          {failed && (
            <a
              href="#live-pipeline"
              className="inline-flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm font-medium text-red-800 hover:bg-red-100"
            >
              Retry from the pipeline list
              <ArrowRight className="h-4 w-4" />
            </a>
          )}
          <Link
            to="/dashboard"
            className="inline-flex items-center justify-between rounded-lg border border-slate-900 bg-slate-900 px-3 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
          >
            <span className="inline-flex items-center gap-2">
              <Ship className="h-4 w-4" />
              Go to Workbench Continue
            </span>
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        {onShowAdvanced && (
          <div className="border-t border-slate-100 pt-3">
            <Button type="button" variant="secondary" size="sm" onClick={onShowAdvanced}>
              Advanced: change extraction mode
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
