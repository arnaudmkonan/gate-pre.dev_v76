import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export function VerifyEmailPage() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const [status, setStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!token) {
      setStatus('error')
      setMessage('Missing verification token.')
      return
    }
    const run = async () => {
      setStatus('loading')
      try {
        const res = await fetch(`${API_BASE}/api/portal/verify-email`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token }),
        })
        const data = await res.json().catch(() => ({}))
        if (!res.ok) {
          throw new Error(data.detail || 'Verification failed')
        }
        setStatus('ok')
        setMessage(data.message || 'Email verified. You can sign in now.')
      } catch (e) {
        setStatus('error')
        setMessage(e instanceof Error ? e.message : 'Verification failed')
      }
    }
    void run()
  }, [token])

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-md rounded-xl border border-gray-800 bg-gray-900 p-8 text-center">
        <h1 className="mb-2 text-xl font-semibold text-white">Email verification</h1>
        {status === 'loading' && <p className="text-gray-400">Confirming your email…</p>}
        {status !== 'loading' && <p className={status === 'ok' ? 'text-green-400' : 'text-red-400'}>{message}</p>}
        <Link to="/login" className="mt-6 inline-block text-sm text-blue-400 hover:underline">
          Go to login
        </Link>
      </div>
    </div>
  )
}
