import { useMemo, useState } from 'react'
import { Edit2, Check, AlertTriangle, ChevronDown, ChevronRight, Search } from 'lucide-react'
import { ConfidenceBadge } from './ConfidenceBadge'
import { ExtractionEditor } from './ExtractionEditor'

interface Extraction {
  id: string
  field_name: string
  field_value: unknown
  raw_value?: string
  normalized_value?: string
  confidence: number
  status: string
  correction_value?: unknown
  agent_name?: string
  context_snippet?: string
}

interface ExtractionsListProps {
  extractions: Extraction[]
  onCorrect: (extractionId: string, correctedValue: unknown, notes?: string) => void
  isLoading?: boolean
}

type FieldGroupId = 'parties' | 'transport' | 'commercial' | 'codes' | 'dates' | 'other'

const GROUP_META: Record<FieldGroupId, { label: string; order: number }> = {
  parties: { label: 'Parties', order: 1 },
  transport: { label: 'Transport & routing', order: 2 },
  commercial: { label: 'Commercial / values', order: 3 },
  codes: { label: 'Codes (HTS, MID, …)', order: 4 },
  dates: { label: 'Dates', order: 5 },
  other: { label: 'Other', order: 6 },
}

interface DedupedField {
  key: string
  label: string
  group: FieldGroupId
  primary: Extraction
  duplicates: Extraction[]
  uniqueValues: string[]
  needsAttention: boolean
}

function normalizeFieldKey(name: string): string {
  return name
    .toLowerCase()
    .replace(/([a-z])([A-Z])/g, '$1_$2')
    .replace(/[\s\-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '')
}

function humanizeField(name: string): string {
  return name
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function categorize(fieldKey: string): FieldGroupId {
  if (/(importer|exporter|consignee|seller|buyer|shipper|manufacturer|party|vendor|carrier|broker)/.test(fieldKey)) {
    return 'parties'
  }
  if (/(bol|bill_of_lading|awb|air.?way|container|vessel|voyage|flight|port|origin|destination|mode|scac|seal)/.test(fieldKey)) {
    return 'transport'
  }
  if (/(hts|hs_?code|mid|ein|entry_?number|tariff|spi|fta)/.test(fieldKey)) {
    return 'codes'
  }
  if (/(date|eta|etd|ship_date|arrival|departure)/.test(fieldKey)) {
    return 'dates'
  }
  if (/(value|amount|price|quantity|qty|weight|currency|invoice|total|duty|unit)/.test(fieldKey)) {
    return 'commercial'
  }
  return 'other'
}

function displayValue(extraction: Extraction): string {
  const value = extraction.correction_value ?? extraction.normalized_value ?? extraction.field_value
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

function valuesEqual(a: string, b: string): boolean {
  return a.trim().toLowerCase() === b.trim().toLowerCase()
}

function scoreExtraction(e: Extraction): number {
  let score = e.confidence || 0
  if (e.correction_value !== undefined && e.correction_value !== null) score += 2
  if (e.status === 'corrected' || e.status === 'reviewed') score += 0.5
  if (e.normalized_value) score += 0.05
  return score
}

function dedupeExtractions(extractions: Extraction[]): DedupedField[] {
  const buckets = new Map<string, Extraction[]>()
  for (const e of extractions) {
    const key = normalizeFieldKey(e.field_name || 'unknown')
    const list = buckets.get(key) || []
    list.push(e)
    buckets.set(key, list)
  }

  const fields: DedupedField[] = []
  for (const [key, list] of buckets) {
    const sorted = [...list].sort((a, b) => scoreExtraction(b) - scoreExtraction(a))
    const primary = sorted[0]
    const duplicates = sorted.slice(1)
    const uniqueValues: string[] = []
    for (const item of sorted) {
      const v = displayValue(item)
      if (v !== '—' && !uniqueValues.some((u) => valuesEqual(u, v))) {
        uniqueValues.push(v)
      }
    }
    const needsAttention =
      primary.confidence < 0.7 ||
      uniqueValues.length > 1 ||
      (primary.correction_value === undefined && duplicates.some((d) => !valuesEqual(displayValue(d), displayValue(primary))))

    fields.push({
      key,
      label: humanizeField(primary.field_name),
      group: categorize(key),
      primary,
      duplicates,
      uniqueValues,
      needsAttention,
    })
  }

  return fields.sort((a, b) => {
    const go = GROUP_META[a.group].order - GROUP_META[b.group].order
    if (go !== 0) return go
    if (a.needsAttention !== b.needsAttention) return a.needsAttention ? -1 : 1
    return a.label.localeCompare(b.label)
  })
}

export const ExtractionsList = ({
  extractions,
  onCorrect,
  isLoading = false,
}: ExtractionsListProps) => {
  const [editingExtraction, setEditingExtraction] = useState<Extraction | null>(null)
  const [query, setQuery] = useState('')
  const [needsOnly, setNeedsOnly] = useState(true)
  const [expandedKey, setExpandedKey] = useState<string | null>(null)
  const [activeGroup, setActiveGroup] = useState<FieldGroupId | 'all'>('all')

  const deduped = useMemo(() => dedupeExtractions(extractions), [extractions])
  const duplicateCount = useMemo(
    () => deduped.reduce((n, f) => n + f.duplicates.length, 0),
    [deduped]
  )
  const attentionCount = useMemo(
    () => deduped.filter((f) => f.needsAttention).length,
    [deduped]
  )

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return deduped.filter((f) => {
      if (needsOnly && !f.needsAttention) return false
      if (activeGroup !== 'all' && f.group !== activeGroup) return false
      if (!q) return true
      const hay = `${f.label} ${f.primary.field_name} ${displayValue(f.primary)}`.toLowerCase()
      return hay.includes(q)
    })
  }, [deduped, query, needsOnly, activeGroup])

  const grouped = useMemo(() => {
    const map = new Map<FieldGroupId, DedupedField[]>()
    for (const f of filtered) {
      const list = map.get(f.group) || []
      list.push(f)
      map.set(f.group, list)
    }
    return [...map.entries()].sort(
      (a, b) => GROUP_META[a[0]].order - GROUP_META[b[0]].order
    )
  }, [filtered])

  const handleSave = (extractionId: string, correctedValue: unknown, notes?: string) => {
    onCorrect(extractionId, correctedValue, notes)
    setEditingExtraction(null)
  }

  const scrollToGroup = (group: FieldGroupId | 'all') => {
    setActiveGroup(group)
    if (group === 'all') return
    requestAnimationFrame(() => {
      document.getElementById(`ext-group-${group}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

  if (extractions.length === 0) {
    return <p className="py-4 text-center text-sm text-gray-500">No extractions available</p>
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
        <span className="rounded bg-slate-100 px-2 py-1 font-medium text-slate-800">
          {deduped.length} unique fields
        </span>
        {duplicateCount > 0 && (
          <span className="rounded bg-amber-50 px-2 py-1 text-amber-800">
            {duplicateCount} duplicate row{duplicateCount === 1 ? '' : 's'} hidden
          </span>
        )}
        {attentionCount > 0 && (
          <span className="rounded bg-yellow-100 px-2 py-1 text-yellow-900">
            {attentionCount} need attention
          </span>
        )}
        <span className="text-slate-400">· {extractions.length} raw</span>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter fields…"
            className="w-full rounded-md border border-slate-300 py-1.5 pl-8 pr-3 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          />
        </div>
        <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={needsOnly}
            onChange={(e) => setNeedsOnly(e.target.checked)}
            className="rounded border-slate-300"
          />
          Needs attention only
        </label>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => scrollToGroup('all')}
          className={`rounded-full px-2.5 py-1 text-xs font-medium ${
            activeGroup === 'all' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          }`}
        >
          All
        </button>
        {(Object.keys(GROUP_META) as FieldGroupId[]).map((g) => {
          const count = deduped.filter((f) => f.group === g && (!needsOnly || f.needsAttention)).length
          if (count === 0 && activeGroup !== g) return null
          return (
            <button
              key={g}
              type="button"
              onClick={() => scrollToGroup(g)}
              className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                activeGroup === g ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {GROUP_META[g].label} ({count})
            </button>
          )
        })}
      </div>

      {filtered.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-500">
          {needsOnly
            ? 'Nothing needs attention — turn off the filter to browse all fields.'
            : 'No fields match this filter.'}
        </p>
      ) : (
        <div className="max-h-[28rem] space-y-4 overflow-y-auto pr-1">
          {grouped.map(([groupId, fields]) => (
            <section key={groupId} id={`ext-group-${groupId}`} className="scroll-mt-2">
              <h4 className="sticky top-0 z-10 mb-1.5 bg-white/95 py-1 text-xs font-semibold uppercase tracking-wide text-slate-500 backdrop-blur">
                {GROUP_META[groupId].label}
              </h4>
              <div className="overflow-hidden rounded-lg border border-slate-200">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-3 py-2 font-medium">Field</th>
                      <th className="px-3 py-2 font-medium">Value</th>
                      <th className="w-20 px-2 py-2 font-medium">Conf</th>
                      <th className="w-10 px-2 py-2" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {fields.map((field) => {
                      const expanded = expandedKey === field.key
                      const value = displayValue(field.primary)
                      return (
                        <tr
                          key={field.key}
                          className={field.needsAttention ? 'bg-amber-50/60' : 'bg-white'}
                        >
                          <td className="align-top px-3 py-2">
                            <div className="flex items-start gap-1.5">
                              {field.needsAttention ? (
                                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
                              ) : field.primary.correction_value != null ? (
                                <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
                              ) : null}
                              <div>
                                <div className="font-medium text-slate-900">{field.label}</div>
                                <div className="font-mono text-[10px] text-slate-400">{field.primary.field_name}</div>
                                {field.duplicates.length > 0 && (
                                  <button
                                    type="button"
                                    onClick={() => setExpandedKey(expanded ? null : field.key)}
                                    className="mt-0.5 inline-flex items-center gap-0.5 text-[11px] text-slate-500 hover:text-slate-800"
                                  >
                                    {expanded ? (
                                      <ChevronDown className="h-3 w-3" />
                                    ) : (
                                      <ChevronRight className="h-3 w-3" />
                                    )}
                                    {field.duplicates.length} other source
                                    {field.duplicates.length === 1 ? '' : 's'}
                                    {field.uniqueValues.length > 1
                                      ? ` · ${field.uniqueValues.length} values`
                                      : ''}
                                  </button>
                                )}
                                {expanded && (
                                  <ul className="mt-1 space-y-1 border-l border-slate-200 pl-2 text-[11px] text-slate-600">
                                    {field.duplicates.map((d) => (
                                      <li key={d.id} className="flex items-center justify-between gap-2">
                                        <span className="truncate">
                                          {displayValue(d)}
                                          {d.agent_name ? ` · ${d.agent_name}` : ''}
                                        </span>
                                        <button
                                          type="button"
                                          className="shrink-0 text-slate-500 underline-offset-2 hover:underline"
                                          onClick={() => setEditingExtraction(d)}
                                        >
                                          use / edit
                                        </button>
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                            </div>
                          </td>
                          <td className="align-top px-3 py-2">
                            <div className="max-w-[18rem] break-words text-slate-800">{value}</div>
                            {field.uniqueValues.length > 1 && (
                              <div className="mt-1 text-[11px] text-amber-700">
                                Conflict: {field.uniqueValues.slice(0, 3).join(' vs ')}
                                {field.uniqueValues.length > 3 ? '…' : ''}
                              </div>
                            )}
                            {field.primary.agent_name && (
                              <div className="mt-0.5 text-[10px] text-slate-400">{field.primary.agent_name}</div>
                            )}
                          </td>
                          <td className="align-top px-2 py-2">
                            <ConfidenceBadge confidence={field.primary.confidence} size="sm" />
                          </td>
                          <td className="align-top px-2 py-2">
                            <button
                              type="button"
                              onClick={() => setEditingExtraction(field.primary)}
                              className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                              title="Edit field"
                            >
                              <Edit2 className="h-3.5 w-3.5" />
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
        </div>
      )}

      {editingExtraction && (
        <ExtractionEditor
          extraction={editingExtraction}
          onSave={handleSave}
          onClose={() => setEditingExtraction(null)}
          isLoading={isLoading}
        />
      )}
    </div>
  )
}
