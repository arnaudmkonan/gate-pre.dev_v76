import { Check, Circle, Minus } from 'lucide-react'
import { Link } from 'react-router-dom'

export interface PipelineStage {
  id: string
  label: string
  state: 'done' | 'current' | 'todo' | 'skipped'
  detail?: string
  href?: string | null
}

export interface PipelineNextAction {
  label: string
  action: string
  path: string
}

export interface ShipmentPipeline {
  shipment_id: string
  needs_isf: boolean
  current_stage: string
  stages: PipelineStage[]
  next_action: PipelineNextAction
  links?: {
    entry_id?: string | null
    entry_number?: string | null
    isf_id?: string | null
    review_pending?: number
  }
}

interface ShipmentJobTimelineProps {
  pipeline: ShipmentPipeline
  compact?: boolean
  onActionClick?: (action: PipelineNextAction) => void
}

function stageClass(state: PipelineStage['state']) {
  if (state === 'done') return 'border-emerald-500 bg-emerald-50 text-emerald-800'
  if (state === 'current') return 'border-slate-800 bg-slate-900 text-white'
  if (state === 'skipped') return 'border-slate-200 bg-slate-50 text-slate-400'
  return 'border-slate-200 bg-white text-slate-500'
}

function StageIcon({ state }: { state: PipelineStage['state'] }) {
  if (state === 'done') return <Check className="h-3.5 w-3.5" />
  if (state === 'skipped') return <Minus className="h-3.5 w-3.5" />
  return <Circle className="h-3.5 w-3.5" />
}

export function ShipmentJobTimeline({
  pipeline,
  compact = false,
  onActionClick,
}: ShipmentJobTimelineProps) {
  const next = pipeline.next_action

  return (
    <div className={compact ? 'space-y-2' : 'space-y-4'}>
      {!compact && (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-slate-900">Job progress</p>
            <p className="text-xs text-slate-500">
              Current: {pipeline.stages.find((s) => s.id === pipeline.current_stage)?.label || pipeline.current_stage}
              {!pipeline.needs_isf ? ' · ISF not required (air)' : ''}
            </p>
          </div>
          {next && (
            onActionClick ? (
              <button
                type="button"
                onClick={() => onActionClick(next)}
                className="inline-flex items-center justify-center rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800"
              >
                Next: {next.label}
              </button>
            ) : (
              <Link
                to={next.path}
                className="inline-flex items-center justify-center rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800"
              >
                Next: {next.label}
              </Link>
            )
          )}
        </div>
      )}

      <ol className="flex flex-wrap items-stretch gap-2">
        {pipeline.stages.map((stage, idx) => {
          const body = (
            <div
              className={`flex min-w-[7.5rem] flex-1 flex-col gap-1 rounded-lg border px-2.5 py-2 ${stageClass(stage.state)}`}
            >
              <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide">
                <StageIcon state={stage.state} />
                <span>{stage.label}</span>
              </div>
              {!compact && stage.detail && (
                <p className={`text-[11px] leading-snug ${stage.state === 'current' ? 'text-slate-200' : 'opacity-80'}`}>
                  {stage.detail}
                </p>
              )}
            </div>
          )

          return (
            <li key={stage.id} className="flex min-w-0 flex-1 items-center gap-2">
              {stage.href ? (
                <Link to={stage.href} className="min-w-0 flex-1 hover:opacity-90">
                  {body}
                </Link>
              ) : (
                <div className="min-w-0 flex-1">{body}</div>
              )}
              {idx < pipeline.stages.length - 1 && (
                <span className="hidden h-px w-3 shrink-0 bg-slate-200 sm:block" aria-hidden />
              )}
            </li>
          )
        })}
      </ol>

      {compact && next && (
        <p className="text-[11px] text-slate-500">
          Next:{' '}
          <Link to={next.path} className="font-medium text-slate-800 underline-offset-2 hover:underline">
            {next.label}
          </Link>
        </p>
      )}
    </div>
  )
}
