import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertCircle,
  ClipboardCheck,
  FileText,
  Package,
  RefreshCw,
  Upload,
  ArrowRight,
  Ship,
  CheckCircle2,
  Clock,
  Building2,
} from 'lucide-react'
import { authFetch } from '../lib/authFetch'
import { API_BASE } from '../config/api'
import { BRAND_NAME } from '../config/brand'
import { useAuth } from '../contexts/AuthContext'
import { Button } from '../components/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'

interface Attention {
  total: number
  review_pending: number
  shipments_partial: number
  shipments_ready_for_prep: number
  entries_draft: number
  entries_ready_to_file: number
  ingest_processing: number
  ingest_failed: number
}

interface WorkbenchSummary {
  generated_at: string
  broker: {
    name: string
    filer_code: string | null
    ace_mode: string
    imap_configured: boolean
    smtp_configured: boolean
  }
  attention: Attention
  recent_review: Array<{
    id: string
    status: string
    priority: number
    reason: string
    created_at: string | null
  }>
  recent_shipments: Array<{
    id: string
    name?: string | null
    status: string
    bol_number?: string | null
    importer_name?: string | null
    document_count: number
    updated_at: string | null
  }>
  recent_entries: Array<{
    id: string
    entry_number?: string | null
    status: string
    importer_of_record_name?: string | null
    port_of_entry?: string | null
    updated_at: string | null
  }>
  quick_actions: Array<{ id: string; label: string; path: string }>
}

function formatWhen(iso: string | null | undefined) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function statusPill(status: string) {
  const s = (status || '').toLowerCase()
  if (['pending', 'partial', 'draft', 'failed', 'in_review'].includes(s)) {
    return 'bg-amber-50 text-amber-800'
  }
  if (['ready_to_file', 'complete', 'ready_for_audit', 'approved'].includes(s)) {
    return 'bg-emerald-50 text-emerald-800'
  }
  return 'bg-slate-100 text-slate-700'
}

export default function WorkbenchDashboardPage() {
  const { user } = useAuth()
  const [data, setData] = useState<WorkbenchSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const resp = await authFetch(`${API_BASE}/api/workbench/summary`)
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(body.detail || `Failed to load workbench (${resp.status})`)
      }
      setData(await resp.json())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 60_000)
    return () => clearInterval(id)
  }, [load])

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-slate-300 border-t-slate-800" />
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
        {error}
        <div className="mt-3">
          <Button size="sm" onClick={load}>
            Retry
          </Button>
        </div>
      </div>
    )
  }

  if (!data) return null

  const a = data.attention
  const greetingName = user?.first_name || 'there'

  const metricCards = [
    {
      label: 'Review queue',
      value: a.review_pending,
      hint: 'Pending / in review',
      to: '/review',
      icon: ClipboardCheck,
      alert: a.review_pending > 0,
    },
    {
      label: 'Shipments incomplete',
      value: a.shipments_partial,
      hint: 'Missing docs / partial',
      to: '/shipments/assembly',
      icon: Package,
      alert: a.shipments_partial > 0,
    },
    {
      label: 'Ready for 7501',
      value: a.shipments_ready_for_prep,
      hint: 'Complete / ready for audit',
      to: '/shipments/assembly',
      icon: Ship,
      alert: false,
    },
    {
      label: 'Entries to finish',
      value: a.entries_draft + a.entries_ready_to_file,
      hint: `${a.entries_draft} draft · ${a.entries_ready_to_file} ready to file`,
      to: '/entries',
      icon: FileText,
      alert: a.entries_draft + a.entries_ready_to_file > 0,
    },
  ]

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 sm:text-3xl">
            Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'},{' '}
            {greetingName}
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            {data.broker.name || BRAND_NAME}
            {data.broker.filer_code ? ` · Filer ${data.broker.filer_code}` : ''}
            {' · '}
            ACE {data.broker.ace_mode.replace('_', ' ')}
            {' · '}
            {a.total > 0 ? `${a.total} items need attention` : 'Inbox clear — no blockers'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Link to="/ingest-ui">
            <Button size="sm">
              <Upload className="mr-1.5 h-3.5 w-3.5" />
              Ingest docs
            </Button>
          </Link>
        </div>
      </div>

      {/* Attention metrics */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metricCards.map((m) => {
          const Icon = m.icon
          return (
            <Link key={m.label} to={m.to} className="group block">
              <Card className="h-full transition-colors group-hover:border-slate-400">
                <CardContent className="p-5">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm text-slate-500">{m.label}</p>
                      <p
                        className={`mt-2 text-3xl font-semibold tabular-nums ${
                          m.alert && m.value > 0 ? 'text-amber-700' : 'text-slate-900'
                        }`}
                      >
                        {m.value}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">{m.hint}</p>
                    </div>
                    <div
                      className={`rounded-lg p-2 ${
                        m.alert && m.value > 0 ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                  </div>
                  <p className="mt-4 flex items-center text-xs font-medium text-slate-600 group-hover:text-slate-900">
                    Open <ArrowRight className="ml-1 h-3 w-3" />
                  </p>
                </CardContent>
              </Card>
            </Link>
          )
        })}
      </div>

      {/* Pipeline pulse + connectivity */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Pipeline pulse</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-slate-600">
                <Clock className="h-4 w-4" /> Ingest in flight
              </span>
              <span className="font-semibold tabular-nums">{a.ingest_processing}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-slate-600">
                <AlertCircle className="h-4 w-4" /> Ingest failed
              </span>
              <span
                className={`font-semibold tabular-nums ${
                  a.ingest_failed > 0 ? 'text-red-600' : 'text-slate-900'
                }`}
              >
                {a.ingest_failed}
              </span>
            </div>
            {a.ingest_failed > 0 && (
              <Link to="/admin/dlq" className="text-xs text-blue-700 hover:underline">
                Review failed jobs in System →
              </Link>
            )}
            <p className="border-t border-slate-100 pt-3 text-xs text-slate-500">
              Updated {formatWhen(data.generated_at)}
            </p>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Quick actions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {data.quick_actions.map((action) => (
                <Link
                  key={action.id}
                  to={action.path}
                  className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
                >
                  {action.label}
                  <ArrowRight className="h-4 w-4 text-slate-400" />
                </Link>
              ))}
              <Link
                to="/clients"
                className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
              >
                <span className="flex items-center gap-2">
                  <Building2 className="h-4 w-4" /> Clients
                </span>
                <ArrowRight className="h-4 w-4 text-slate-400" />
              </Link>
            </div>
            <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1">
                {data.broker.smtp_configured ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                ) : (
                  <AlertCircle className="h-3.5 w-3.5 text-amber-600" />
                )}
                SMTP {data.broker.smtp_configured ? 'ready' : 'not configured'}
              </span>
              <span className="inline-flex items-center gap-1">
                {data.broker.imap_configured ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                ) : (
                  <AlertCircle className="h-3.5 w-3.5 text-amber-600" />
                )}
                IMAP reply ingest {data.broker.imap_configured ? 'on' : 'off'}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Work queues */}
      <div className="grid gap-4 xl:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-base">Review needing action</CardTitle>
            <Link to="/review" className="text-xs font-medium text-blue-700 hover:underline">
              View all
            </Link>
          </CardHeader>
          <CardContent>
            {data.recent_review.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-500">Review queue is clear</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {data.recent_review.map((item) => (
                  <li key={item.id}>
                    <Link
                      to={`/review/${item.id}`}
                      className="block py-3 hover:bg-slate-50 -mx-2 px-2 rounded"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium text-slate-900 line-clamp-2">
                          {item.reason || 'Needs review'}
                        </p>
                        <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${statusPill(item.status)}`}>
                          {item.status}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        Priority {item.priority} · {formatWhen(item.created_at)}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-base">Recent shipments</CardTitle>
            <Link to="/shipments/assembly" className="text-xs font-medium text-blue-700 hover:underline">
              Assembly
            </Link>
          </CardHeader>
          <CardContent>
            {data.recent_shipments.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-500">No shipments yet — ingest documents to start</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {data.recent_shipments.map((s) => (
                  <li key={s.id}>
                    <Link
                      to={`/shipments/${s.id}`}
                      className="block py-3 hover:bg-slate-50 -mx-2 px-2 rounded"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium text-slate-900 truncate">
                          {s.importer_name || s.name || s.bol_number || s.id.slice(0, 8)}
                        </p>
                        <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${statusPill(s.status)}`}>
                          {s.status}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        {s.document_count} docs
                        {s.bol_number ? ` · BOL ${s.bol_number}` : ''}
                        {' · '}
                        {formatWhen(s.updated_at)}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-base">Entries in progress</CardTitle>
            <Link to="/entries" className="text-xs font-medium text-blue-700 hover:underline">
              All entries
            </Link>
          </CardHeader>
          <CardContent>
            {data.recent_entries.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-500">No draft / ready entries</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {data.recent_entries.map((e) => (
                  <li key={e.id}>
                    <Link
                      to={`/entries/${e.id}`}
                      className="block py-3 hover:bg-slate-50 -mx-2 px-2 rounded"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium text-slate-900 truncate">
                          {e.entry_number || e.id.slice(0, 8)}
                        </p>
                        <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${statusPill(e.status)}`}>
                          {e.status.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        {e.importer_of_record_name || 'No IOR'}
                        {e.port_of_entry ? ` · Port ${e.port_of_entry}` : ''}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
