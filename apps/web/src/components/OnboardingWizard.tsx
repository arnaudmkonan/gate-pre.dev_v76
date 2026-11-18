import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle, Upload, ClipboardCheck, Link2, Shield, ChevronRight, X } from 'lucide-react'
import { Button } from './Button'

const STORAGE_KEY = 'gates_onboarding_complete'

const STEPS = [
  { id: 'upload', label: 'Upload customs documents', path: '/ingest-ui', icon: Upload },
  { id: 'review', label: 'Review extracted data', path: '/review', icon: ClipboardCheck },
  { id: 'shipments', label: 'Assemble shipments', path: '/shipments/assembly', icon: Link2 },
  { id: 'compliance', label: 'Check compliance score', path: '/compliance-dashboard', icon: Shield },
] as const

export function OnboardingWizard() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!localStorage.getItem(STORAGE_KEY)) {
      setOpen(true)
    }
  }, [])

  const complete = () => {
    localStorage.setItem(STORAGE_KEY, 'true')
    setOpen(false)
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-md rounded-xl border border-gray-700 bg-gray-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-800 px-5 py-4">
          <h2 className="text-lg font-semibold text-white">Welcome to GATE</h2>
          <button type="button" onClick={complete} className="text-gray-400 hover:text-white" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="space-y-4 px-5 py-4">
          <p className="text-sm text-gray-400">
            Follow these steps to run your first document through the pipeline.
          </p>
          <div className="space-y-2">
            {STEPS.map((step) => {
              const Icon = step.icon
              return (
                <Link
                  key={step.id}
                  to={step.path}
                  onClick={complete}
                  className="flex items-center gap-3 rounded-lg border border-gray-800 bg-gray-800/40 p-3 transition-colors hover:border-blue-500/40 hover:bg-gray-800"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10 text-blue-400">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="flex-1 text-sm font-medium text-gray-100">{step.label}</div>
                  <ChevronRight className="h-4 w-4 text-gray-500" />
                </Link>
              )
            })}
          </div>
        </div>
        <div className="flex justify-between border-t border-gray-800 px-5 py-4">
          <Button variant="ghost" onClick={complete}>
            Skip for now
          </Button>
          <Button onClick={complete}>
            <CheckCircle className="mr-2 h-4 w-4" />
            Got it
          </Button>
        </div>
      </div>
    </div>
  )
}
