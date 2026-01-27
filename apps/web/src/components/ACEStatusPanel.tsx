/**
 * ACE Status Panel Component
 * 
 * Displays ACE/CBP filing status for an entry with:
 * - Current status badge
 * - Timeline of status changes
 * - Rejection details with error codes
 * - Action buttons (file, poll, resubmit)
 * 
 * Task 3.4 from ROADMAP_FULL_WORKFLOW.md
 */
import { useState, useEffect } from 'react'
import {
    Send,
    RefreshCw,
    Clock,
    CheckCircle,
    XCircle,
    AlertTriangle,
    FileText,
    Ship,
    Lock,
    Unlock,
    History,
    ChevronDown,
    ChevronUp,
    Info,
    Zap,
    ArrowRight,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from './Card'
import { Button } from './Button'
import {
    useACEStatus,
    useACEStatusActions,
    getACEStatusConfig,
    getEntryStatusConfig,
    formatRelativeTime,
    ACE_STATUS_CONFIG,
} from '../hooks/useACEStatus'

interface ACEStatusPanelProps {
    entryId: string
    onStatusChange?: () => void
}

// Status badge component
const StatusBadge = ({ status, type = 'ace' }: { status: string | null | undefined; type?: 'ace' | 'entry' }) => {
    const config = type === 'ace'
        ? getACEStatusConfig(status ?? null)
        : getEntryStatusConfig(status || '')

    return (
        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${config.color} ${config.bgColor}`}>
            {type === 'ace' && 'icon' in config && <span>{(config as any).icon}</span>}
            {config.label}
        </span>
    )
}

// Status icon based on status
const getStatusIcon = (status: string | null | undefined) => {
    switch (status) {
        case 'accepted':
        case 'released':
        case 'liquidated':
            return <CheckCircle className="w-5 h-5 text-green-600" />
        case 'rejected':
            return <XCircle className="w-5 h-5 text-red-600" />
        case 'hold':
        case 'intensive_exam':
            return <Lock className="w-5 h-5 text-orange-600" />
        case 'submitted':
        case 'received':
        case 'under_review':
            return <Clock className="w-5 h-5 text-blue-600" />
        default:
            return <FileText className="w-5 h-5 text-gray-400" />
    }
}

export const ACEStatusPanel = ({ entryId, onStatusChange }: ACEStatusPanelProps) => {
    const { status, loading, error, refetch } = useACEStatus(entryId)
    const {
        loading: actionLoading,
        error: actionError,
        fileEntry,
        pollStatus,
        resubmitEntry,
        simulateACEResponse,
    } = useACEStatusActions()

    const [showHistory, setShowHistory] = useState(false)
    const [showSimulate, setShowSimulate] = useState(false)

    useEffect(() => {
        refetch()
    }, [refetch])

    const handleFileEntry = async () => {
        const result = await fileEntry(entryId)
        if (result) {
            refetch()
            onStatusChange?.()
        }
    }

    const handlePollStatus = async () => {
        const result = await pollStatus(entryId)
        if (result) {
            refetch()
            onStatusChange?.()
        }
    }

    const handleResubmit = async () => {
        const result = await resubmitEntry(entryId)
        if (result) {
            refetch()
            onStatusChange?.()
        }
    }

    const handleSimulate = async (aceStatus: string) => {
        const result = await simulateACEResponse(entryId, {
            ace_status: aceStatus,
            message: `Simulated ${aceStatus} response`,
            error_codes: aceStatus === 'rejected' ? ['CBP-003', 'CBP-007'] : [],
        })
        if (result) {
            refetch()
            onStatusChange?.()
            setShowSimulate(false)
        }
    }

    if (loading && !status) {
        return (
            <Card>
                <CardContent className="flex items-center justify-center py-8">
                    <RefreshCw className="w-6 h-6 animate-spin text-blue-500" />
                </CardContent>
            </Card>
        )
    }

    if (error && !status) {
        return (
            <Card>
                <CardContent className="py-8">
                    <div className="text-center text-red-500">
                        <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
                        <p>{error}</p>
                        <Button variant="secondary" onClick={refetch} className="mt-4">
                            Retry
                        </Button>
                    </div>
                </CardContent>
            </Card>
        )
    }

    const canFile = status?.entry_status === 'ready_to_file' || status?.entry_status === 'draft'
    const canPoll = ['filed', 'accepted', 'filing'].includes(status?.entry_status || '')
    const canResubmit = status?.can_resubmit

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="flex items-center gap-2">
                    <Ship className="w-5 h-5" />
                    ACE/CBP Status
                </CardTitle>
                <Button
                    variant="secondary"
                    size="sm"
                    onClick={refetch}
                    disabled={loading}
                >
                    <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                </Button>
            </CardHeader>

            <CardContent className="space-y-4">
                {/* Current Status */}
                <div className="bg-gray-50 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                            {getStatusIcon(status?.ace_status)}
                            <div>
                                <p className="text-sm text-gray-500">ACE Status</p>
                                <StatusBadge status={status?.ace_status} type="ace" />
                            </div>
                        </div>
                        <div className="text-right">
                            <p className="text-sm text-gray-500">Entry Status</p>
                            <StatusBadge status={status?.entry_status} type="entry" />
                        </div>
                    </div>

                    {/* ACE Entry ID */}
                    {status?.ace_entry_id && (
                        <div className="flex items-center gap-2 text-sm text-gray-600 mt-3 pt-3 border-t border-gray-200">
                            <FileText className="w-4 h-4" />
                            <span>ACE ID:</span>
                            <code className="bg-white px-2 py-0.5 rounded border font-mono text-xs">
                                {status.ace_entry_id}
                            </code>
                        </div>
                    )}

                    {/* Key Dates */}
                    <div className="grid grid-cols-3 gap-4 mt-3 pt-3 border-t border-gray-200 text-sm">
                        <div>
                            <p className="text-gray-500">Filed</p>
                            <p className="font-medium">
                                {status?.filed_at
                                    ? formatRelativeTime(status.filed_at)
                                    : '-'}
                            </p>
                        </div>
                        <div>
                            <p className="text-gray-500">Released</p>
                            <p className="font-medium">
                                {status?.release_date
                                    ? formatRelativeTime(status.release_date)
                                    : '-'}
                            </p>
                        </div>
                        <div>
                            <p className="text-gray-500">Liquidated</p>
                            <p className="font-medium">
                                {status?.liquidation_date
                                    ? formatRelativeTime(status.liquidation_date)
                                    : '-'}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Rejection Details */}
                {status?.rejection_details && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                        <div className="flex items-start gap-3">
                            <XCircle className="w-5 h-5 text-red-600 mt-0.5" />
                            <div className="flex-1">
                                <p className="font-medium text-red-800">Entry Rejected by CBP</p>
                                <p className="text-sm text-red-700 mt-1">
                                    {status.rejection_details.cbp_message}
                                </p>

                                {/* Error Codes */}
                                {status.rejection_details.error_messages.length > 0 && (
                                    <div className="mt-3 space-y-2">
                                        <p className="text-sm font-medium text-red-800">Error Codes:</p>
                                        {status.rejection_details.error_messages.map((err, idx) => (
                                            <div
                                                key={idx}
                                                className="flex items-start gap-2 text-sm bg-white rounded p-2"
                                            >
                                                <code className="text-red-600 font-mono text-xs bg-red-100 px-1.5 py-0.5 rounded">
                                                    {err.code}
                                                </code>
                                                <span className="text-gray-700">{err.description}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {/* Correction Hints */}
                                {status.rejection_details.correction_hints.length > 0 && (
                                    <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                                        <p className="text-sm font-medium text-yellow-800 flex items-center gap-1">
                                            <Info className="w-4 h-4" />
                                            Suggested Corrections:
                                        </p>
                                        <ul className="mt-2 space-y-1 text-sm text-yellow-700">
                                            {status.rejection_details.correction_hints.map((hint, idx) => (
                                                <li key={idx} className="flex items-start gap-2">
                                                    <ArrowRight className="w-4 h-4 mt-0.5 flex-shrink-0" />
                                                    {hint}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {/* Actions */}
                <div className="flex flex-wrap gap-2">
                    {canFile && (
                        <Button
                            onClick={handleFileEntry}
                            disabled={actionLoading}
                        >
                            {actionLoading ? (
                                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                            ) : (
                                <Send className="w-4 h-4 mr-2" />
                            )}
                            File to ACE
                        </Button>
                    )}

                    {canPoll && (
                        <Button
                            variant="secondary"
                            onClick={handlePollStatus}
                            disabled={actionLoading}
                        >
                            <RefreshCw className={`w-4 h-4 mr-2 ${actionLoading ? 'animate-spin' : ''}`} />
                            Check Status
                        </Button>
                    )}

                    {canResubmit && (
                        <Button
                            onClick={handleResubmit}
                            disabled={actionLoading}
                            className="bg-orange-600 hover:bg-orange-700"
                        >
                            <Unlock className="w-4 h-4 mr-2" />
                            Resubmit Entry
                        </Button>
                    )}

                    {/* Simulate button for testing */}
                    <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setShowSimulate(!showSimulate)}
                        className="ml-auto"
                    >
                        <Zap className="w-4 h-4 mr-1" />
                        Simulate
                    </Button>
                </div>

                {/* Simulate Panel */}
                {showSimulate && (
                    <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                        <p className="text-sm font-medium text-gray-700 mb-3">Simulate ACE Response:</p>
                        <div className="flex flex-wrap gap-2">
                            {['accepted', 'rejected', 'hold', 'released', 'liquidated'].map((s) => (
                                <Button
                                    key={s}
                                    size="sm"
                                    variant="secondary"
                                    onClick={() => handleSimulate(s)}
                                    disabled={actionLoading}
                                    className={`capitalize ${s === 'rejected' ? 'hover:bg-red-100' :
                                        s === 'accepted' || s === 'released' ? 'hover:bg-green-100' :
                                            'hover:bg-yellow-100'
                                        }`}
                                >
                                    {ACE_STATUS_CONFIG[s]?.icon} {s}
                                </Button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Error Display */}
                {actionError && (
                    <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg">
                        {actionError}
                    </div>
                )}

                {/* Status History */}
                <div>
                    <button
                        onClick={() => setShowHistory(!showHistory)}
                        className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
                    >
                        <History className="w-4 h-4" />
                        Status History ({status?.status_history?.length || 0})
                        {showHistory ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>

                    {showHistory && status?.status_history && (
                        <div className="mt-3 space-y-2">
                            {status.status_history.length === 0 ? (
                                <p className="text-sm text-gray-500 italic">No status changes yet</p>
                            ) : (
                                status.status_history.map((item, idx) => (
                                    <div
                                        key={idx}
                                        className="flex items-start gap-3 text-sm p-2 bg-gray-50 rounded-lg"
                                    >
                                        <div className="w-2 h-2 rounded-full bg-blue-400 mt-2" />
                                        <div className="flex-1">
                                            <div className="flex items-center gap-2">
                                                {item.from_status && (
                                                    <>
                                                        <span className="text-gray-500">{item.from_status}</span>
                                                        <ArrowRight className="w-3 h-3 text-gray-400" />
                                                    </>
                                                )}
                                                <span className="font-medium">{item.to_status}</span>
                                            </div>
                                            {item.reason && (
                                                <p className="text-gray-600 mt-1">{item.reason}</p>
                                            )}
                                            <p className="text-xs text-gray-400 mt-1">
                                                {formatRelativeTime(item.changed_at)} • {item.changed_by || 'System'}
                                            </p>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    )
}

export default ACEStatusPanel
