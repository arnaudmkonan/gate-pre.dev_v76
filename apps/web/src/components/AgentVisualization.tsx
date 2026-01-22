import { useState, useEffect } from 'react'
import {
    Bot,
    Play,
    CheckCircle,
    XCircle,
    AlertCircle,
    FileText,
    Tag,
    Users,
    FileCheck,
    Lightbulb,
    HelpCircle,
    Shield,
    Loader2,
    ChevronDown,
    ChevronUp,
    RefreshCw,
    Sparkles
} from 'lucide-react'
import { Card } from './Card'
import { Button } from './Button'

interface Agent {
    name: string
    description: string
    capabilities: string[]
}

interface AgentResult {
    success: boolean
    output: Record<string, any>
    confidence: number
    execution_time_ms: number
    error?: string
}

interface AgentProcessingResult {
    document_id: string
    pipeline_type: string
    execution_time_seconds: number
    agents_executed: number
    results: Record<string, AgentResult>
}

interface Document {
    id: string
    filename: string
    file_type: string
    size: number
    status: string
    has_agent_results: boolean
    classification?: string
}

const AGENT_ICONS: Record<string, React.ComponentType<any>> = {
    document_classifier: FileText,
    multi_label_classifier: Tag,
    entity_extractor: Users,
    relationship_extractor: Users,
    summarizer: FileCheck,
    insights_extractor: Lightbulb,
    qa_generator: HelpCircle,
    quality_reviewer: CheckCircle,
    compliance_checker: Shield,
}

const AGENT_COLORS: Record<string, string> = {
    document_classifier: 'bg-blue-500',
    multi_label_classifier: 'bg-purple-500',
    entity_extractor: 'bg-green-500',
    relationship_extractor: 'bg-teal-500',
    summarizer: 'bg-orange-500',
    insights_extractor: 'bg-yellow-500',
    qa_generator: 'bg-pink-500',
    quality_reviewer: 'bg-indigo-500',
    compliance_checker: 'bg-red-500',
}

export const AgentVisualization: React.FC = () => {
    const [documents, setDocuments] = useState<Document[]>([])
    const [availableAgents, setAvailableAgents] = useState<Agent[]>([])
    const [selectedDocument, setSelectedDocument] = useState<string | null>(null)
    const [pipelineType, setPipelineType] = useState<'standard' | 'analysis'>('standard')
    const [processing, setProcessing] = useState(false)
    const [taskId, setTaskId] = useState<string | null>(null)
    const [results, setResults] = useState<AgentProcessingResult | null>(null)
    const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set())
    const [error, setError] = useState<string | null>(null)
    const [polling, setPolling] = useState(false)

    useEffect(() => {
        fetchDocuments()
        fetchAgents()
    }, [])

    useEffect(() => {
        let interval: ReturnType<typeof setInterval>
        if (taskId && polling) {
            interval = setInterval(() => checkTaskStatus(taskId), 2000)
        }
        return () => {
            if (interval) clearInterval(interval)
        }
    }, [taskId, polling])

    const fetchDocuments = async () => {
        try {
            const response = await fetch('/api/ingest/jobs?page=1&page_size=20')
            const data = await response.json()

            // Get agent results for each document
            const docs = await Promise.all(
                data.jobs.slice(0, 10).map(async (job: any) => {
                    try {
                        // Get document metadata
                        const metaResponse = await fetch(`/agents/results/${job.id}`)
                        const metaData = await metaResponse.json()
                        return {
                            id: job.id,
                            filename: job.filename,
                            file_type: job.file_type,
                            size: job.size,
                            status: job.status,
                            has_agent_results: metaData.has_results || false,
                            classification: metaData.classification,
                        }
                    } catch {
                        return {
                            id: job.id,
                            filename: job.filename,
                            file_type: job.file_type,
                            size: job.size,
                            status: job.status,
                            has_agent_results: false,
                        }
                    }
                })
            )

            setDocuments(docs)
        } catch (err) {
            console.error('Failed to fetch documents:', err)
        }
    }

    const fetchAgents = async () => {
        try {
            const response = await fetch('/agents/available')
            const data = await response.json()
            setAvailableAgents(data.agents)
        } catch (err) {
            console.error('Failed to fetch agents:', err)
        }
    }

    const startProcessing = async () => {
        if (!selectedDocument) return

        setProcessing(true)
        setError(null)
        setResults(null)

        try {
            const response = await fetch('/agents/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    document_id: selectedDocument,
                    pipeline_type: pipelineType,
                }),
            })

            const data = await response.json()

            if (!response.ok) {
                throw new Error(data.detail || 'Processing failed')
            }

            setTaskId(data.task_id)
            setPolling(true)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Processing failed')
            setProcessing(false)
        }
    }

    const checkTaskStatus = async (id: string) => {
        try {
            const response = await fetch(`/agents/status/${id}`)
            const data = await response.json()

            if (data.ready) {
                setPolling(false)
                setProcessing(false)

                if (data.result) {
                    setResults(data.result)
                }
                if (data.error) {
                    setError(data.error)
                }

                // Refresh documents list
                fetchDocuments()
            }
        } catch (err) {
            console.error('Failed to check status:', err)
        }
    }

    const toggleAgentExpand = (agentName: string) => {
        const newExpanded = new Set(expandedAgents)
        if (newExpanded.has(agentName)) {
            newExpanded.delete(agentName)
        } else {
            newExpanded.add(agentName)
        }
        setExpandedAgents(newExpanded)
    }

    const formatBytes = (bytes: number): string => {
        if (bytes < 1024) return `${bytes} B`
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-3">
                <div className="p-3 bg-gradient-to-br from-violet-500 to-purple-600 rounded-xl">
                    <Sparkles className="w-6 h-6 text-white" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold text-gray-800">AI Agent Analysis</h1>
                    <p className="text-gray-500">Intelligent document processing with LLM-powered agents</p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Document Selection */}
                <Card className="lg:col-span-1">
                    <div className="p-4">
                        <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                            <FileText className="w-4 h-4" />
                            Select Document
                        </h3>

                        <div className="space-y-2 max-h-96 overflow-y-auto">
                            {documents.map((doc) => (
                                <button
                                    key={doc.id}
                                    onClick={() => setSelectedDocument(doc.id)}
                                    className={`w-full p-3 rounded-lg border text-left transition-all ${selectedDocument === doc.id
                                            ? 'border-violet-500 bg-violet-50'
                                            : 'border-gray-200 hover:border-violet-300 hover:bg-gray-50'
                                        }`}
                                >
                                    <div className="flex items-center justify-between">
                                        <span className="font-medium text-sm truncate">{doc.filename}</span>
                                        {doc.has_agent_results && (
                                            <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2 mt-1">
                                        <span className="text-xs px-2 py-0.5 bg-gray-100 rounded uppercase">
                                            {doc.file_type}
                                        </span>
                                        <span className="text-xs text-gray-500">{formatBytes(doc.size)}</span>
                                        {doc.classification && (
                                            <span className="text-xs px-2 py-0.5 bg-violet-100 text-violet-700 rounded">
                                                {doc.classification}
                                            </span>
                                        )}
                                    </div>
                                </button>
                            ))}
                        </div>

                        <Button
                            onClick={fetchDocuments}
                            variant="outline"
                            className="w-full mt-4"
                        >
                            <RefreshCw className="w-4 h-4 mr-2" />
                            Refresh List
                        </Button>
                    </div>
                </Card>

                {/* Pipeline Configuration & Results */}
                <Card className="lg:col-span-2">
                    <div className="p-4">
                        <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                            <Bot className="w-4 h-4" />
                            Agent Pipeline
                        </h3>

                        {/* Pipeline Type Selection */}
                        <div className="flex gap-4 mb-6">
                            <button
                                onClick={() => setPipelineType('standard')}
                                className={`flex-1 p-4 rounded-xl border-2 transition-all ${pipelineType === 'standard'
                                        ? 'border-violet-500 bg-violet-50'
                                        : 'border-gray-200 hover:border-violet-300'
                                    }`}
                            >
                                <div className="font-semibold text-gray-800">Standard Pipeline</div>
                                <div className="text-sm text-gray-500 mt-1">4 agents • Quick analysis</div>
                                <div className="flex gap-1 mt-2">
                                    {['document_classifier', 'entity_extractor', 'summarizer', 'quality_reviewer'].map((a) => {
                                        const Icon = AGENT_ICONS[a] || Bot
                                        return (
                                            <div key={a} className={`w-8 h-8 rounded-full ${AGENT_COLORS[a]} flex items-center justify-center`}>
                                                <Icon className="w-4 h-4 text-white" />
                                            </div>
                                        )
                                    })}
                                </div>
                            </button>

                            <button
                                onClick={() => setPipelineType('analysis')}
                                className={`flex-1 p-4 rounded-xl border-2 transition-all ${pipelineType === 'analysis'
                                        ? 'border-violet-500 bg-violet-50'
                                        : 'border-gray-200 hover:border-violet-300'
                                    }`}
                            >
                                <div className="font-semibold text-gray-800">Deep Analysis</div>
                                <div className="text-sm text-gray-500 mt-1">9 agents • Comprehensive</div>
                                <div className="flex gap-1 mt-2 flex-wrap">
                                    {Object.keys(AGENT_ICONS).map((a) => {
                                        const Icon = AGENT_ICONS[a] || Bot
                                        return (
                                            <div key={a} className={`w-6 h-6 rounded-full ${AGENT_COLORS[a]} flex items-center justify-center`}>
                                                <Icon className="w-3 h-3 text-white" />
                                            </div>
                                        )
                                    })}
                                </div>
                            </button>
                        </div>

                        {/* Start Button */}
                        <Button
                            onClick={startProcessing}
                            disabled={!selectedDocument || processing}
                            className="w-full mb-6"
                        >
                            {processing ? (
                                <>
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    Processing with AI Agents...
                                </>
                            ) : (
                                <>
                                    <Play className="w-4 h-4 mr-2" />
                                    Start Agent Analysis
                                </>
                            )}
                        </Button>

                        {/* Error Display */}
                        {error && (
                            <div className="p-4 bg-red-50 border border-red-200 rounded-xl mb-4">
                                <div className="flex items-center gap-2 text-red-600">
                                    <AlertCircle className="w-5 h-5" />
                                    <span className="font-medium">Error</span>
                                </div>
                                <p className="text-sm text-red-600 mt-1">{error}</p>
                            </div>
                        )}

                        {/* Results Display */}
                        {results && (
                            <div className="space-y-4">
                                <div className="flex items-center justify-between p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl border border-green-200">
                                    <div>
                                        <div className="font-semibold text-green-700">Analysis Complete</div>
                                        <div className="text-sm text-green-600">
                                            {results.agents_executed} agents • {results.execution_time_seconds.toFixed(2)}s
                                        </div>
                                    </div>
                                    <CheckCircle className="w-8 h-8 text-green-500" />
                                </div>

                                {/* Agent Results */}
                                <div className="space-y-3">
                                    {Object.entries(results.results).map(([agentName, result]) => {
                                        const Icon = AGENT_ICONS[agentName] || Bot
                                        const color = AGENT_COLORS[agentName] || 'bg-gray-500'
                                        const isExpanded = expandedAgents.has(agentName)

                                        return (
                                            <div
                                                key={agentName}
                                                className="border rounded-xl overflow-hidden"
                                            >
                                                <button
                                                    onClick={() => toggleAgentExpand(agentName)}
                                                    className="w-full p-4 flex items-center justify-between hover:bg-gray-50 transition"
                                                >
                                                    <div className="flex items-center gap-3">
                                                        <div className={`w-10 h-10 rounded-lg ${color} flex items-center justify-center`}>
                                                            <Icon className="w-5 h-5 text-white" />
                                                        </div>
                                                        <div className="text-left">
                                                            <div className="font-medium text-gray-800">
                                                                {agentName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                                                            </div>
                                                            <div className="text-sm text-gray-500">
                                                                {result.execution_time_ms}ms
                                                                {result.confidence > 0 && ` • ${(result.confidence * 100).toFixed(0)}% confidence`}
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        {result.success ? (
                                                            <CheckCircle className="w-5 h-5 text-green-500" />
                                                        ) : (
                                                            <XCircle className="w-5 h-5 text-red-500" />
                                                        )}
                                                        {isExpanded ? (
                                                            <ChevronUp className="w-5 h-5 text-gray-400" />
                                                        ) : (
                                                            <ChevronDown className="w-5 h-5 text-gray-400" />
                                                        )}
                                                    </div>
                                                </button>

                                                {isExpanded && (
                                                    <div className="p-4 pt-0 border-t bg-gray-50">
                                                        {result.error ? (
                                                            <div className="text-red-600 text-sm">{result.error}</div>
                                                        ) : (
                                                            <pre className="text-xs bg-white p-3 rounded-lg overflow-x-auto border">
                                                                {JSON.stringify(result.output, null, 2)}
                                                            </pre>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        )
                                    })}
                                </div>
                            </div>
                        )}
                    </div>
                </Card>
            </div>

            {/* Available Agents */}
            <Card>
                <div className="p-4">
                    <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                        <Bot className="w-4 h-4" />
                        Available AI Agents
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        {availableAgents.map((agent) => (
                            <div
                                key={agent.name}
                                className="p-4 border rounded-xl hover:shadow-md transition-shadow"
                            >
                                <div className="font-medium text-gray-800 text-sm">{agent.name}</div>
                                <div className="text-xs text-gray-500 mt-1">{agent.description}</div>
                                <div className="flex flex-wrap gap-1 mt-2">
                                    {agent.capabilities.map((cap) => (
                                        <span
                                            key={cap}
                                            className="text-xs px-2 py-0.5 bg-violet-100 text-violet-700 rounded"
                                        >
                                            {cap}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </Card>
        </div>
    )
}
