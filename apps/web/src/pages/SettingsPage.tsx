import React, { useState, useEffect, useCallback } from 'react'
import { apiGet, apiPost, apiDelete } from '../lib/apiClient'
import {
    Settings, Key, Webhook, Plus, Trash2, Copy, Check,
    AlertCircle, RefreshCw, Clock, Shield,
    ChevronRight, ExternalLink, X, Loader2, CheckCircle2
} from 'lucide-react'

// ============================================================================
// Types
// ============================================================================

interface ApiKey {
    id: string
    name: string
    key_prefix: string
    key?: string // Only on create
    permissions: string[]
    rate_limit_tier: string
    is_active: boolean
    created_at: string
    expires_at: string | null
    last_used_at: string | null
    revoked_at: string | null
}

interface WebhookEndpoint {
    id: string
    url: string
    name: string
    events: string[]
    secret?: string
    is_active: boolean
    failure_count: number
    created_at: string
    last_triggered_at: string | null
}

interface WebhookDelivery {
    id: string
    event_type: string
    status: string
    response_code: number | null
    error_message: string | null
    attempt_count: number
    created_at: string
    delivered_at: string | null
}

type SettingsTab = 'api-keys' | 'webhooks'

// ============================================================================
// Utility
// ============================================================================

function timeAgo(dateStr: string | null): string {
    if (!dateStr) return 'Never'
    const date = new Date(dateStr)
    const now = new Date()
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000)
    if (seconds < 60) return 'Just now'
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
    return `${Math.floor(seconds / 86400)}d ago`
}

function StatusBadge({ active }: { active: boolean }) {
    return (
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${active
            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
            : 'bg-red-50 text-red-700 border border-red-200'
            }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${active ? 'bg-emerald-500' : 'bg-red-500'}`} />
            {active ? 'Active' : 'Revoked'}
        </span>
    )
}

// ============================================================================
// API Key Management Tab
// ============================================================================

const PERMISSION_LABELS: Record<string, string> = {
    'entries:read': 'Read Entries',
    'entries:write': 'Write Entries',
    'shipments:read': 'Read Shipments',
    'shipments:write': 'Write Shipments',
    'documents:read': 'Read Documents',
    'documents:write': 'Write Documents',
    'clients:read': 'Read Clients',
    'compliance:read': 'Read Compliance',
    'reference:read': 'Read Reference Data',
    'webhooks:manage': 'Manage Webhooks',
}

function ApiKeysTab() {
    const [keys, setKeys] = useState<ApiKey[]>([])
    const [loading, setLoading] = useState(true)
    const [showCreate, setShowCreate] = useState(false)
    const [newKeyName, setNewKeyName] = useState('')
    const [selectedPerms, setSelectedPerms] = useState<string[]>(
        Object.keys(PERMISSION_LABELS).filter(k => k.endsWith(':read'))
    )
    const [createdKey, setCreatedKey] = useState<string | null>(null)
    const [copied, setCopied] = useState(false)
    const [creating, setCreating] = useState(false)
    const [revoking, setRevoking] = useState<string | null>(null)

    const loadKeys = useCallback(async () => {
        try {
            setLoading(true)
            const data = await apiGet<{ api_keys: ApiKey[] }>('/api/settings/api-keys?include_revoked=true')
            setKeys(data.api_keys || [])
        } catch (err) {
            console.error('Failed to load API keys:', err)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { loadKeys() }, [loadKeys])

    const handleCreate = async () => {
        if (!newKeyName.trim()) return
        setCreating(true)
        try {
            const data = await apiPost<ApiKey & { key: string }>('/api/settings/api-keys', {
                name: newKeyName,
                permissions: selectedPerms,
            })
            setCreatedKey(data.key)
            setNewKeyName('')
            await loadKeys()
        } catch (err) {
            console.error('Failed to create API key:', err)
        } finally {
            setCreating(false)
        }
    }

    const handleRevoke = async (id: string) => {
        if (!confirm('Revoke this API key? This action cannot be undone.')) return
        setRevoking(id)
        try {
            await apiDelete(`/api/settings/api-keys/${id}`)
            await loadKeys()
        } catch (err) {
            console.error('Failed to revoke key:', err)
        } finally {
            setRevoking(null)
        }
    }

    const copyKey = () => {
        if (createdKey) {
            navigator.clipboard.writeText(createdKey)
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        }
    }

    const togglePerm = (perm: string) => {
        setSelectedPerms(prev =>
            prev.includes(perm) ? prev.filter(p => p !== perm) : [...prev, perm]
        )
    }

    return (
        <div className="space-y-6">
            {/* Created key banner */}
            {createdKey && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                    <div className="flex items-start gap-3">
                        <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-amber-900">Save your API key now — it won't be shown again!</p>
                            <div className="mt-2 flex items-center gap-2">
                                <code className="block bg-white px-3 py-2 rounded-lg border border-amber-300 text-sm font-mono text-amber-900 break-all flex-1">
                                    {createdKey}
                                </code>
                                <button onClick={copyKey} className="p-2 bg-white rounded-lg border border-amber-300 hover:bg-amber-100 transition-colors">
                                    {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4 text-amber-700" />}
                                </button>
                            </div>
                            <button onClick={() => setCreatedKey(null)} className="mt-2 text-xs text-amber-700 hover:text-amber-900">
                                I've saved it — dismiss
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Create form */}
            {showCreate ? (
                <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-semibold text-slate-900">Create API Key</h3>
                        <button onClick={() => setShowCreate(false)} className="p-1 text-slate-400 hover:text-slate-600">
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">Key Name</label>
                            <input
                                type="text"
                                value={newKeyName}
                                onChange={(e) => setNewKeyName(e.target.value)}
                                placeholder="e.g. CargoWise Integration"
                                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">Permissions</label>
                            <div className="grid grid-cols-2 gap-2">
                                {Object.entries(PERMISSION_LABELS).map(([key, label]) => (
                                    <label key={key} className="flex items-center gap-2 p-2 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={selectedPerms.includes(key)}
                                            onChange={() => togglePerm(key)}
                                            className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500"
                                        />
                                        <span className="text-sm text-slate-700">{label}</span>
                                    </label>
                                ))}
                            </div>
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                            <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800">
                                Cancel
                            </button>
                            <button
                                onClick={handleCreate}
                                disabled={!newKeyName.trim() || creating}
                                className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                            >
                                {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Key className="w-4 h-4" />}
                                Create Key
                            </button>
                        </div>
                    </div>
                </div>
            ) : (
                <button
                    onClick={() => setShowCreate(true)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 border-2 border-dashed border-slate-300 rounded-xl text-sm text-slate-500 hover:border-indigo-400 hover:text-indigo-600 transition-colors"
                >
                    <Plus className="w-4 h-4" /> Create New API Key
                </button>
            )}

            {/* Key list */}
            {loading ? (
                <div className="flex justify-center py-12">
                    <Loader2 className="w-6 h-6 text-slate-400 animate-spin" />
                </div>
            ) : keys.length === 0 ? (
                <div className="text-center py-12">
                    <Key className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                    <p className="text-sm text-slate-500">No API keys yet. Create one to get started.</p>
                </div>
            ) : (
                <div className="space-y-3">
                    {keys.map((key) => (
                        <div key={key.id} className={`bg-white border rounded-xl p-4 shadow-sm transition-all ${key.is_active ? 'border-slate-200 hover:shadow-md' : 'border-red-100 opacity-60'
                            }`}>
                            <div className="flex items-start justify-between">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                        <h4 className="text-sm font-semibold text-slate-900">{key.name}</h4>
                                        <StatusBadge active={key.is_active} />
                                        <span className="text-xs text-slate-400 font-mono">{key.key_prefix}…</span>
                                    </div>
                                    <div className="flex items-center gap-4 text-xs text-slate-500">
                                        <span className="flex items-center gap-1">
                                            <Clock className="w-3 h-3" /> Created {timeAgo(key.created_at)}
                                        </span>
                                        <span className="flex items-center gap-1">
                                            <RefreshCw className="w-3 h-3" /> Used {timeAgo(key.last_used_at)}
                                        </span>
                                        <span className="flex items-center gap-1">
                                            <Shield className="w-3 h-3" /> {(key.permissions || []).length} perms
                                        </span>
                                    </div>
                                </div>
                                {key.is_active && (
                                    <button
                                        onClick={() => handleRevoke(key.id)}
                                        disabled={revoking === key.id}
                                        className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                        title="Revoke key"
                                    >
                                        {revoking === key.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                                    </button>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

// ============================================================================
// Webhook Management Tab
// ============================================================================

const WEBHOOK_EVENT_GROUPS: Record<string, string[]> = {
    'Entries': ['entry.created', 'entry.updated', 'entry.filed', 'entry.accepted', 'entry.rejected', 'entry.liquidated'],
    'Shipments': ['shipment.created', 'shipment.updated'],
    'Documents': ['document.processed', 'document.extracted'],
    'Compliance': ['compliance.alert'],
    'ISF': ['isf.filed', 'isf.accepted'],
    'Other': ['client.created', 'invoice.created'],
}

function WebhooksTab() {
    const [webhooks, setWebhooks] = useState<WebhookEndpoint[]>([])
    const [loading, setLoading] = useState(true)
    const [showCreate, setShowCreate] = useState(false)
    const [newName, setNewName] = useState('')
    const [newUrl, setNewUrl] = useState('')
    const [selectedEvents, setSelectedEvents] = useState<string[]>([])
    const [createdSecret, setCreatedSecret] = useState<string | null>(null)
    const [creating, setCreating] = useState(false)
    const [testing, setTesting] = useState<string | null>(null)
    const [testResult, setTestResult] = useState<Record<string, { success: boolean; message: string }>>({})
    const [expandedDeliveries, setExpandedDeliveries] = useState<string | null>(null)
    const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([])

    const loadWebhooks = useCallback(async () => {
        try {
            setLoading(true)
            const data = await apiGet<{ webhooks: WebhookEndpoint[] }>('/api/settings/webhooks?active_only=false')
            setWebhooks(data.webhooks || [])
        } catch (err) {
            console.error('Failed to load webhooks:', err)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { loadWebhooks() }, [loadWebhooks])

    const handleCreate = async () => {
        if (!newName.trim() || !newUrl.trim() || selectedEvents.length === 0) return
        setCreating(true)
        try {
            const data = await apiPost<WebhookEndpoint & { secret: string }>('/api/settings/webhooks', {
                name: newName,
                url: newUrl,
                events: selectedEvents,
            })
            setCreatedSecret(data.secret || null)
            setNewName('')
            setNewUrl('')
            setSelectedEvents([])
            setShowCreate(false)
            await loadWebhooks()
        } catch (err) {
            console.error('Failed to create webhook:', err)
        } finally {
            setCreating(false)
        }
    }

    const handleTest = async (id: string) => {
        setTesting(id)
        try {
            const data = await apiPost<{ success: boolean; status_code?: number; error?: string }>(
                `/api/settings/webhooks/${id}/test`
            )
            setTestResult(prev => ({
                ...prev,
                [id]: {
                    success: data.success,
                    message: data.success ? `✓ ${data.status_code}` : data.error || 'Failed'
                }
            }))
        } catch (err) {
            setTestResult(prev => ({
                ...prev,
                [id]: { success: false, message: 'Connection failed' }
            }))
        } finally {
            setTesting(null)
        }
    }

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this webhook? Delivery history will also be removed.')) return
        try {
            await apiDelete(`/api/settings/webhooks/${id}`)
            await loadWebhooks()
        } catch (err) {
            console.error('Failed to delete webhook:', err)
        }
    }

    const loadDeliveries = async (id: string) => {
        if (expandedDeliveries === id) {
            setExpandedDeliveries(null)
            return
        }
        try {
            const data = await apiGet<{ deliveries: WebhookDelivery[] }>(`/api/settings/webhooks/${id}/deliveries`)
            setDeliveries(data.deliveries || [])
            setExpandedDeliveries(id)
        } catch (err) {
            console.error('Failed to load deliveries:', err)
        }
    }

    const toggleEvent = (event: string) => {
        setSelectedEvents(prev =>
            prev.includes(event) ? prev.filter(e => e !== event) : [...prev, event]
        )
    }

    const toggleGroup = (events: string[]) => {
        const allSelected = events.every(e => selectedEvents.includes(e))
        if (allSelected) {
            setSelectedEvents(prev => prev.filter(e => !events.includes(e)))
        } else {
            setSelectedEvents(prev => [...new Set([...prev, ...events])])
        }
    }

    return (
        <div className="space-y-6">
            {/* Created secret banner */}
            {createdSecret && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                    <div className="flex items-start gap-3">
                        <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-amber-900">Signing secret — save it now!</p>
                            <p className="text-xs text-amber-700 mt-1">Use this to verify webhook signatures (HMAC-SHA256).</p>
                            <code className="mt-2 block bg-white px-3 py-2 rounded-lg border border-amber-300 text-sm font-mono text-amber-900 break-all">
                                {createdSecret}
                            </code>
                            <button onClick={() => setCreatedSecret(null)} className="mt-2 text-xs text-amber-700 hover:text-amber-900">
                                Dismiss
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Create form */}
            {showCreate ? (
                <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-semibold text-slate-900">Add Webhook Endpoint</h3>
                        <button onClick={() => setShowCreate(false)} className="p-1 text-slate-400 hover:text-slate-600">
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                    <div className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Name</label>
                                <input
                                    type="text"
                                    value={newName}
                                    onChange={(e) => setNewName(e.target.value)}
                                    placeholder="e.g. TMS Webhook"
                                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Endpoint URL</label>
                                <input
                                    type="url"
                                    value={newUrl}
                                    onChange={(e) => setNewUrl(e.target.value)}
                                    placeholder="https://example.com/webhooks/gate"
                                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                                />
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">Events to subscribe</label>
                            <div className="space-y-3">
                                {Object.entries(WEBHOOK_EVENT_GROUPS).map(([group, events]) => (
                                    <div key={group}>
                                        <button
                                            onClick={() => toggleGroup(events)}
                                            className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1 hover:text-indigo-600"
                                        >
                                            {group} ({events.filter(e => selectedEvents.includes(e)).length}/{events.length})
                                        </button>
                                        <div className="flex flex-wrap gap-2">
                                            {events.map(event => (
                                                <button
                                                    key={event}
                                                    onClick={() => toggleEvent(event)}
                                                    className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${selectedEvents.includes(event)
                                                        ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                                                        : 'bg-white border-slate-200 text-slate-500 hover:border-slate-300'
                                                        }`}
                                                >
                                                    {event}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                            <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800">
                                Cancel
                            </button>
                            <button
                                onClick={handleCreate}
                                disabled={!newName.trim() || !newUrl.trim() || selectedEvents.length === 0 || creating}
                                className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                            >
                                {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Webhook className="w-4 h-4" />}
                                Create Webhook
                            </button>
                        </div>
                    </div>
                </div>
            ) : (
                <button
                    onClick={() => setShowCreate(true)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 border-2 border-dashed border-slate-300 rounded-xl text-sm text-slate-500 hover:border-indigo-400 hover:text-indigo-600 transition-colors"
                >
                    <Plus className="w-4 h-4" /> Add Webhook Endpoint
                </button>
            )}

            {/* Webhook list */}
            {loading ? (
                <div className="flex justify-center py-12">
                    <Loader2 className="w-6 h-6 text-slate-400 animate-spin" />
                </div>
            ) : webhooks.length === 0 ? (
                <div className="text-center py-12">
                    <Webhook className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                    <p className="text-sm text-slate-500">No webhooks registered. Add one to start receiving events.</p>
                </div>
            ) : (
                <div className="space-y-3">
                    {webhooks.map((wh) => (
                        <div key={wh.id} className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                            <div className="p-4">
                                <div className="flex items-start justify-between">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h4 className="text-sm font-semibold text-slate-900">{wh.name}</h4>
                                            <StatusBadge active={wh.is_active} />
                                            {wh.failure_count > 0 && (
                                                <span className="text-xs bg-red-50 text-red-700 px-1.5 py-0.5 rounded-md">
                                                    {wh.failure_count} failures
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-xs text-slate-500 font-mono truncate">{wh.url}</p>
                                        <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
                                            <span>{(wh.events || []).length} events subscribed</span>
                                            <span>•</span>
                                            <span>Last triggered {timeAgo(wh.last_triggered_at)}</span>
                                        </div>
                                        {/* Events preview */}
                                        <div className="flex flex-wrap gap-1 mt-2">
                                            {(wh.events || []).slice(0, 5).map(ev => (
                                                <span key={ev} className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded-md">{ev}</span>
                                            ))}
                                            {(wh.events || []).length > 5 && (
                                                <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded-md">
                                                    +{(wh.events || []).length - 5} more
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-1 ml-3">
                                        <button
                                            onClick={() => handleTest(wh.id)}
                                            disabled={testing === wh.id}
                                            className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                                            title="Send test event"
                                        >
                                            {testing === wh.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <ExternalLink className="w-4 h-4" />}
                                        </button>
                                        <button
                                            onClick={() => loadDeliveries(wh.id)}
                                            className={`p-2 rounded-lg transition-colors ${expandedDeliveries === wh.id
                                                ? 'text-indigo-600 bg-indigo-50'
                                                : 'text-slate-400 hover:text-slate-600 hover:bg-slate-50'
                                                }`}
                                            title="View deliveries"
                                        >
                                            <ChevronRight className={`w-4 h-4 transition-transform ${expandedDeliveries === wh.id ? 'rotate-90' : ''}`} />
                                        </button>
                                        <button
                                            onClick={() => handleDelete(wh.id)}
                                            className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                            title="Delete webhook"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>
                                {/* Test result */}
                                {testResult[wh.id] && (
                                    <div className={`mt-2 text-xs px-3 py-1.5 rounded-lg ${testResult[wh.id].success ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
                                        }`}>
                                        {testResult[wh.id].message}
                                    </div>
                                )}
                            </div>

                            {/* Delivery history */}
                            {expandedDeliveries === wh.id && (
                                <div className="border-t border-slate-100 bg-slate-50 p-3">
                                    <h5 className="text-xs font-semibold text-slate-600 mb-2">Recent Deliveries</h5>
                                    {deliveries.length === 0 ? (
                                        <p className="text-xs text-slate-400 py-2">No deliveries yet.</p>
                                    ) : (
                                        <div className="space-y-1.5">
                                            {deliveries.slice(0, 10).map(d => (
                                                <div key={d.id} className="flex items-center justify-between bg-white rounded-lg px-3 py-2 text-xs">
                                                    <div className="flex items-center gap-2">
                                                        {d.status === 'delivered' ? (
                                                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                                                        ) : (
                                                            <AlertCircle className="w-3.5 h-3.5 text-red-500" />
                                                        )}
                                                        <span className="font-mono text-slate-700">{d.event_type}</span>
                                                    </div>
                                                    <div className="flex items-center gap-3 text-slate-500">
                                                        {d.response_code && <span>{d.response_code}</span>}
                                                        <span>{timeAgo(d.created_at)}</span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

// ============================================================================
// Settings Page (Main)
// ============================================================================

export function SettingsPage() {
    const [activeTab, setActiveTab] = useState<SettingsTab>('api-keys')

    const tabs: { id: SettingsTab; label: string; icon: React.ElementType; description: string }[] = [
        { id: 'api-keys', label: 'API Keys', icon: Key, description: 'Manage programmatic access keys for integrations' },
        { id: 'webhooks', label: 'Webhooks', icon: Webhook, description: 'Configure event notifications to external systems' },
    ]

    return (
        <div className="max-w-5xl mx-auto">
            {/* Header */}
            <div className="mb-8">
                <div className="flex items-center gap-3 mb-2">
                    <div className="p-2.5 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl shadow-lg shadow-indigo-200">
                        <Settings className="w-6 h-6 text-white" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900">Platform Settings</h1>
                        <p className="text-sm text-slate-500">Manage API keys, webhooks, and integrations</p>
                    </div>
                </div>
            </div>

            {/* Tab bar */}
            <div className="flex gap-1 p-1 bg-slate-100 rounded-xl mb-6">
                {tabs.map(tab => {
                    const Icon = tab.icon
                    return (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${activeTab === tab.id
                                ? 'bg-white text-slate-900 shadow-sm'
                                : 'text-slate-500 hover:text-slate-700'
                                }`}
                        >
                            <Icon className="w-4 h-4" />
                            {tab.label}
                        </button>
                    )
                })}
            </div>

            {/* Tab content */}
            {activeTab === 'api-keys' && <ApiKeysTab />}
            {activeTab === 'webhooks' && <WebhooksTab />}
        </div>
    )
}
