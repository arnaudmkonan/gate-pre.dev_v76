import React, { useEffect, useRef, useState } from 'react'
import { Search, Loader2 } from 'lucide-react'
import { authFetch } from '../lib/authFetch'

export interface HTSSuggestion {
  id: string
  hts_code: string
  description: string
  chapter?: number | null
  duty_rate?: string | null
  duty_rate_percent?: number | null
}

interface HTSAutocompleteInputProps {
  value: string
  onChange: (htsCode: string, suggestion?: HTSSuggestion) => void
  placeholder?: string
  className?: string
}

export const HTSAutocompleteInput: React.FC<HTSAutocompleteInputProps> = ({
  value,
  onChange,
  placeholder = 'Search HTS code or keyword (e.g. 6109, laptop)...',
  className = '',
}) => {
  const [suggestions, setSuggestions] = useState<HTSSuggestion[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const suppressNextFetchRef = useRef(false)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    if (suppressNextFetchRef.current) {
      suppressNextFetchRef.current = false
      return
    }
    const q = (value || '').trim()
    if (q.length < 2) {
      setSuggestions([])
      return
    }

    const timer = window.setTimeout(async () => {
      setLoading(true)
      try {
        const res = await authFetch(
          `/api/reference-data/hts/search?query=${encodeURIComponent(q)}&limit=8`
        )
        if (!res.ok) return
        const data = await res.json()
        setSuggestions(Array.isArray(data.results) ? data.results : [])
      } catch {
        setSuggestions([])
      } finally {
        setLoading(false)
      }
    }, 180)

    return () => window.clearTimeout(timer)
  }, [value])

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <input
          type="text"
          value={value}
          onFocus={() => {
            if (suggestions.length > 0) setOpen(true)
          }}
          onChange={(e) => {
            onChange(e.target.value)
            setOpen(true)
          }}
          placeholder={placeholder}
          className={
            className ||
            'w-full px-3 py-2 pr-8 border border-gray-300 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500'
          }
        />
        <div className="pointer-events-none absolute inset-y-0 right-2.5 flex items-center text-gray-400">
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
        </div>
      </div>

      {open && suggestions.length > 0 && (
        <div className="absolute left-0 right-0 z-50 mt-1 max-h-64 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg min-w-[320px]">
          {suggestions.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                suppressNextFetchRef.current = true
                onChange(item.hts_code, item)
                setOpen(false)
              }}
              className="w-full text-left px-3 py-2 hover:bg-blue-50 border-b border-gray-100 last:border-b-0 transition-colors"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs font-semibold text-blue-700">
                  {item.hts_code}
                </span>
                <span className="text-[11px] font-medium px-1.5 py-0.5 rounded bg-gray-100 text-gray-700 shrink-0">
                  {item.duty_rate || (item.duty_rate_percent != null ? `${item.duty_rate_percent}%` : 'Verify rate')}
                </span>
              </div>
              <p className="text-xs text-gray-600 line-clamp-2 mt-0.5">{item.description}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
