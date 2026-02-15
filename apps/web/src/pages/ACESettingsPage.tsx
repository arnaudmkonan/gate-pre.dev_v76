/**
 * ACE Settings Page
 * 
 * Configure ACE Portal credentials, filer codes, and filing preferences.
 * Task 3.3 from ROADMAP_FULL_WORKFLOW.md
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    ArrowLeft,
    Settings,
    Shield,
    Plus,
    Edit,
    Trash2,
    Save,
    X,
    Check,
    AlertCircle,
    RefreshCw,
    Star,
    FileText,
    Building2,
    Bell,
    Lock,
    Globe,
    Info,
    Ship,
    Package,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import {
    useACESettings,
    useACESettingsActions,
    ACESettings,
    FilerCodeCreate,
    BOND_TYPES,
    ACE_ENVIRONMENTS,
    isValidFilerCode,
    isValidPortCode,
    isValidSuretyCode,
} from '../hooks/useACESettings'
import { API_BASE } from '../config/api'

// Hardcoded org ID for demo - in production this would come from auth context
const DEFAULT_ORG_ID = 'c2a0e8c4-d6b0-4f5e-a8c2-e4f6b0d8c2a4'

// Add Filer Code Modal
const AddFilerCodeModal = ({
    isOpen,
    onClose,
    onAdd,
    loading,
}: {
    isOpen: boolean
    onClose: () => void
    onAdd: (data: FilerCodeCreate) => Promise<void>
    loading: boolean
}) => {
    const [formData, setFormData] = useState<FilerCodeCreate>({
        filer_code: '',
        name: '',
        port_code: '',
        bond_type: 'continuous',
        bond_number: '',
        surety_code: '',
        is_primary: false,
        notes: '',
    })
    const [errors, setErrors] = useState<Record<string, string>>({})

    const validate = (): boolean => {
        const newErrors: Record<string, string> = {}

        if (!formData.filer_code) {
            newErrors.filer_code = 'Filer code is required'
        } else if (!isValidFilerCode(formData.filer_code)) {
            newErrors.filer_code = 'Must be 3 letters (A-Z)'
        }

        if (formData.port_code && !isValidPortCode(formData.port_code)) {
            newErrors.port_code = 'Must be 4 digits'
        }

        if (formData.surety_code && !isValidSuretyCode(formData.surety_code)) {
            newErrors.surety_code = 'Must be 3 digits'
        }

        setErrors(newErrors)
        return Object.keys(newErrors).length === 0
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!validate()) return

        await onAdd({
            ...formData,
            filer_code: formData.filer_code.toUpperCase(),
        })
        setFormData({
            filer_code: '',
            name: '',
            port_code: '',
            bond_type: 'continuous',
            bond_number: '',
            surety_code: '',
            is_primary: false,
            notes: '',
        })
        onClose()
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4">
                <div className="flex items-center justify-between p-4 border-b">
                    <h2 className="text-lg font-semibold">Add Filer Code</h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-4 space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Filer Code <span className="text-red-500">*</span>
                            </label>
                            <Input
                                value={formData.filer_code}
                                onChange={(e) => setFormData(prev => ({
                                    ...prev,
                                    filer_code: e.target.value.toUpperCase()
                                }))}
                                placeholder="ABC"
                                maxLength={3}
                                className={errors.filer_code ? 'border-red-500' : ''}
                            />
                            {errors.filer_code && (
                                <p className="text-xs text-red-500 mt-1">{errors.filer_code}</p>
                            )}
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Display Name
                            </label>
                            <Input
                                value={formData.name || ''}
                                onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                                placeholder="My Filer Code"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Default Port Code
                            </label>
                            <Input
                                value={formData.port_code || ''}
                                onChange={(e) => setFormData(prev => ({ ...prev, port_code: e.target.value }))}
                                placeholder="2704"
                                maxLength={4}
                                className={errors.port_code ? 'border-red-500' : ''}
                            />
                            {errors.port_code && (
                                <p className="text-xs text-red-500 mt-1">{errors.port_code}</p>
                            )}
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Bond Type
                            </label>
                            <select
                                value={formData.bond_type || 'continuous'}
                                onChange={(e) => setFormData(prev => ({ ...prev, bond_type: e.target.value }))}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                            >
                                {Object.entries(BOND_TYPES).map(([key, label]) => (
                                    <option key={key} value={key}>{label}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Bond Number
                            </label>
                            <Input
                                value={formData.bond_number || ''}
                                onChange={(e) => setFormData(prev => ({ ...prev, bond_number: e.target.value }))}
                                placeholder="Bond number"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Surety Code
                            </label>
                            <Input
                                value={formData.surety_code || ''}
                                onChange={(e) => setFormData(prev => ({ ...prev, surety_code: e.target.value }))}
                                placeholder="123"
                                maxLength={3}
                                className={errors.surety_code ? 'border-red-500' : ''}
                            />
                            {errors.surety_code && (
                                <p className="text-xs text-red-500 mt-1">{errors.surety_code}</p>
                            )}
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Notes
                        </label>
                        <textarea
                            value={formData.notes || ''}
                            onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                            placeholder="Additional notes..."
                            rows={2}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                        />
                    </div>

                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            id="is_primary"
                            checked={formData.is_primary}
                            onChange={(e) => setFormData(prev => ({ ...prev, is_primary: e.target.checked }))}
                            className="rounded border-gray-300"
                        />
                        <label htmlFor="is_primary" className="text-sm text-gray-700">
                            Set as primary filer code
                        </label>
                    </div>

                    <div className="flex justify-end gap-3 pt-4 border-t">
                        <Button type="button" variant="secondary" onClick={onClose}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={loading}>
                            {loading ? (
                                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                            ) : (
                                <Plus className="w-4 h-4 mr-2" />
                            )}
                            Add Filer Code
                        </Button>
                    </div>
                </form>
            </div>
        </div>
    )
}

export const ACESettingsPage = () => {
    const navigate = useNavigate()
    const [orgId] = useState(DEFAULT_ORG_ID)
    const { settings, loading, error, refetch } = useACESettings(orgId)
    const {
        loading: actionLoading,
        error: actionError,
        createSettings,
        updateSettings,
        addFilerCode,
        deleteFilerCode,
    } = useACESettingsActions()

    const [isEditing, setIsEditing] = useState(false)
    const [showAddFilerCode, setShowAddFilerCode] = useState(false)
    const [formData, setFormData] = useState<Partial<ACESettings>>({})

    // Shipment Assembly Settings
    const [assemblyMode, setAssemblyMode] = useState<'auto' | 'manual' | 'assisted'>('manual')
    const [autoAcceptThreshold, setAutoAcceptThreshold] = useState(0.9)
    const [assemblyLoading, setAssemblyLoading] = useState(false)

    // Fetch assembly mode on mount
    useEffect(() => {
        const fetchAssemblyMode = async () => {
            try {
                const response = await fetch(`${API_BASE}/api/shipments/assembly-mode`)
                if (response.ok) {
                    const data = await response.json()
                    setAssemblyMode(data.assembly_mode || 'manual')
                    setAutoAcceptThreshold(data.auto_accept_threshold || 0.9)
                }
            } catch {
                // Default to manual if fetch fails
            }
        }
        fetchAssemblyMode()
    }, [])

    const handleSaveAssemblyMode = async () => {
        setAssemblyLoading(true)
        try {
            const response = await fetch(`${API_BASE}/api/shipments/assembly-mode`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    assembly_mode: assemblyMode,
                    auto_accept_threshold: autoAcceptThreshold
                })
            })
            if (!response.ok) throw new Error('Failed to update')
            // Show success (could add toast notification here)
        } catch (err) {
            console.error('Failed to save assembly mode:', err)
        } finally {
            setAssemblyLoading(false)
        }
    }

    // Initialize form data when settings load
    useEffect(() => {
        if (settings) {
            setFormData({
                primary_filer_code: settings.primary_filer_code,
                primary_port_code: settings.primary_port_code,
                default_bond_type: settings.default_bond_type,
                default_bond_surety_code: settings.default_bond_surety_code,
                ace_portal_username: settings.ace_portal_username,
                ace_environment: settings.ace_environment,
                auto_file_when_ready: settings.auto_file_when_ready,
                require_dual_approval: settings.require_dual_approval,
                notify_on_filing: settings.notify_on_filing,
                notify_on_acceptance: settings.notify_on_acceptance,
                notify_on_rejection: settings.notify_on_rejection,
                notify_on_liquidation: settings.notify_on_liquidation,
                notification_email: settings.notification_email,
            })
        }
    }, [settings])

    const handleSave = async () => {
        // Convert null values to undefined for API compatibility
        const cleanFormData = {
            primary_filer_code: formData.primary_filer_code || undefined,
            primary_port_code: formData.primary_port_code || undefined,
            default_bond_type: formData.default_bond_type || undefined,
            default_bond_surety_code: formData.default_bond_surety_code || undefined,
            ace_portal_username: formData.ace_portal_username || undefined,
            ace_environment: formData.ace_environment || undefined,
            auto_file_when_ready: formData.auto_file_when_ready,
            require_dual_approval: formData.require_dual_approval,
            notify_on_filing: formData.notify_on_filing,
            notify_on_acceptance: formData.notify_on_acceptance,
            notify_on_rejection: formData.notify_on_rejection,
            notify_on_liquidation: formData.notify_on_liquidation,
            notification_email: formData.notification_email || undefined,
        }

        if (!settings?.id) {
            // Create new settings
            const result = await createSettings({
                organization_id: orgId,
                ...cleanFormData,
            })
            if (result) {
                setIsEditing(false)
                refetch()
            }
        } else {
            // Update existing
            const result = await updateSettings(orgId, cleanFormData)
            if (result) {
                setIsEditing(false)
                refetch()
            }
        }
    }

    const handleAddFilerCode = async (data: FilerCodeCreate) => {
        const result = await addFilerCode(orgId, data)
        if (result) {
            refetch()
        }
    }

    const handleDeleteFilerCode = async (id: string) => {
        if (confirm('Are you sure you want to delete this filer code?')) {
            const success = await deleteFilerCode(id)
            if (success) {
                refetch()
            }
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
            </div>
        )
    }

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <button
                        onClick={() => navigate(-1)}
                        className="flex items-center gap-1 text-gray-500 hover:text-gray-700 mb-2"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        <span className="text-sm">Back</span>
                    </button>
                    <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
                        <Shield className="w-8 h-8 text-blue-600" />
                        ACE Portal Settings
                    </h1>
                    <p className="text-gray-500 mt-1">Configure your ACE Portal credentials and filing preferences</p>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="secondary" onClick={refetch}>
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Refresh
                    </Button>
                    {isEditing ? (
                        <>
                            <Button variant="secondary" onClick={() => setIsEditing(false)}>
                                <X className="w-4 h-4 mr-2" />
                                Cancel
                            </Button>
                            <Button onClick={handleSave} disabled={actionLoading}>
                                {actionLoading ? (
                                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                                ) : (
                                    <Save className="w-4 h-4 mr-2" />
                                )}
                                Save Settings
                            </Button>
                        </>
                    ) : (
                        <Button onClick={() => setIsEditing(true)}>
                            <Edit className="w-4 h-4 mr-2" />
                            Edit Settings
                        </Button>
                    )}
                </div>
            </div>

            {/* Error Display */}
            {(error || actionError) && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-600 flex items-center gap-2">
                    <AlertCircle className="w-5 h-5" />
                    {error || actionError}
                </div>
            )}

            {/* Environment Badge */}
            <div className="flex items-center gap-2">
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${settings?.ace_environment === 'production'
                    ? 'bg-green-100 text-green-800'
                    : 'bg-yellow-100 text-yellow-800'
                    }`}>
                    <Globe className="w-4 h-4 inline mr-1" />
                    {ACE_ENVIRONMENTS[settings?.ace_environment as keyof typeof ACE_ENVIRONMENTS] || 'Test'}
                </span>
                {!settings?.id && (
                    <span className="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-600">
                        Not Configured
                    </span>
                )}
            </div>

            {/* Primary Settings */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Settings className="w-5 h-5" />
                        Primary Configuration
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Primary Filer Code
                            </label>
                            {isEditing ? (
                                <Input
                                    value={formData.primary_filer_code || ''}
                                    onChange={(e) => setFormData(prev => ({
                                        ...prev,
                                        primary_filer_code: e.target.value.toUpperCase()
                                    }))}
                                    placeholder="ABC"
                                    maxLength={3}
                                />
                            ) : (
                                <div className="px-3 py-2 bg-gray-50 rounded-lg font-mono">
                                    {settings?.primary_filer_code || '-'}
                                </div>
                            )}
                            <p className="text-xs text-gray-500 mt-1">3-letter CBP assigned code</p>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Primary Port Code
                            </label>
                            {isEditing ? (
                                <Input
                                    value={formData.primary_port_code || ''}
                                    onChange={(e) => setFormData(prev => ({
                                        ...prev,
                                        primary_port_code: e.target.value
                                    }))}
                                    placeholder="2704"
                                    maxLength={4}
                                />
                            ) : (
                                <div className="px-3 py-2 bg-gray-50 rounded-lg font-mono">
                                    {settings?.primary_port_code || '-'}
                                </div>
                            )}
                            <p className="text-xs text-gray-500 mt-1">4-digit port of entry</p>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                ACE Portal Username
                            </label>
                            {isEditing ? (
                                <Input
                                    value={formData.ace_portal_username || ''}
                                    onChange={(e) => setFormData(prev => ({
                                        ...prev,
                                        ace_portal_username: e.target.value
                                    }))}
                                    placeholder="username@company.com"
                                />
                            ) : (
                                <div className="px-3 py-2 bg-gray-50 rounded-lg">
                                    {settings?.ace_portal_username || '-'}
                                </div>
                            )}
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Environment
                            </label>
                            {isEditing ? (
                                <select
                                    value={formData.ace_environment || 'test'}
                                    onChange={(e) => setFormData(prev => ({
                                        ...prev,
                                        ace_environment: e.target.value
                                    }))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                                >
                                    {Object.entries(ACE_ENVIRONMENTS).map(([key, label]) => (
                                        <option key={key} value={key}>{label}</option>
                                    ))}
                                </select>
                            ) : (
                                <div className="px-3 py-2 bg-gray-50 rounded-lg">
                                    {ACE_ENVIRONMENTS[settings?.ace_environment as keyof typeof ACE_ENVIRONMENTS] || 'Test'}
                                </div>
                            )}
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Bond Configuration */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Lock className="w-5 h-5" />
                        Default Bond Configuration
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Bond Type
                            </label>
                            {isEditing ? (
                                <select
                                    value={formData.default_bond_type || 'continuous'}
                                    onChange={(e) => setFormData(prev => ({
                                        ...prev,
                                        default_bond_type: e.target.value
                                    }))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                                >
                                    {Object.entries(BOND_TYPES).map(([key, label]) => (
                                        <option key={key} value={key}>{label}</option>
                                    ))}
                                </select>
                            ) : (
                                <div className="px-3 py-2 bg-gray-50 rounded-lg">
                                    {BOND_TYPES[settings?.default_bond_type as keyof typeof BOND_TYPES] || 'Continuous Bond'}
                                </div>
                            )}
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Surety Code
                            </label>
                            {isEditing ? (
                                <Input
                                    value={formData.default_bond_surety_code || ''}
                                    onChange={(e) => setFormData(prev => ({
                                        ...prev,
                                        default_bond_surety_code: e.target.value
                                    }))}
                                    placeholder="123"
                                    maxLength={3}
                                />
                            ) : (
                                <div className="px-3 py-2 bg-gray-50 rounded-lg font-mono">
                                    {settings?.default_bond_surety_code || '-'}
                                </div>
                            )}
                            <p className="text-xs text-gray-500 mt-1">3-digit surety company code</p>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Filing Preferences */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <FileText className="w-5 h-5" />
                        Filing Preferences
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-3">
                        <div className="flex items-center justify-between py-2 border-b border-gray-100">
                            <div>
                                <p className="font-medium text-gray-900">Auto-file when ready</p>
                                <p className="text-sm text-gray-500">Automatically submit entries when validation passes</p>
                            </div>
                            {isEditing ? (
                                <input
                                    type="checkbox"
                                    checked={formData.auto_file_when_ready}
                                    onChange={(e) => setFormData(prev => ({
                                        ...prev,
                                        auto_file_when_ready: e.target.checked
                                    }))}
                                    className="w-5 h-5 rounded border-gray-300"
                                />
                            ) : (
                                <span className={`px-2 py-1 rounded text-sm ${settings?.auto_file_when_ready ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                                    }`}>
                                    {settings?.auto_file_when_ready ? 'Enabled' : 'Disabled'}
                                </span>
                            )}
                        </div>
                        <div className="flex items-center justify-between py-2 border-b border-gray-100">
                            <div>
                                <p className="font-medium text-gray-900">Require dual approval</p>
                                <p className="text-sm text-gray-500">Require second user approval before filing</p>
                            </div>
                            {isEditing ? (
                                <input
                                    type="checkbox"
                                    checked={formData.require_dual_approval}
                                    onChange={(e) => setFormData(prev => ({
                                        ...prev,
                                        require_dual_approval: e.target.checked
                                    }))}
                                    className="w-5 h-5 rounded border-gray-300"
                                />
                            ) : (
                                <span className={`px-2 py-1 rounded text-sm ${settings?.require_dual_approval ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                                    }`}>
                                    {settings?.require_dual_approval ? 'Required' : 'Not Required'}
                                </span>
                            )}
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Shipment Assembly Settings */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Ship className="w-5 h-5" />
                        Shipment Assembly
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                Assembly Mode
                            </label>
                            <div className="grid grid-cols-3 gap-3">
                                {[
                                    { value: 'auto', label: 'Automatic', desc: 'Auto-accept high confidence matches' },
                                    { value: 'assisted', label: 'Assisted', desc: 'Suggest groupings for review' },
                                    { value: 'manual', label: 'Manual', desc: 'Create shipments manually' },
                                ].map(({ value, label, desc }) => (
                                    <button
                                        key={value}
                                        type="button"
                                        onClick={() => setAssemblyMode(value as 'auto' | 'assisted' | 'manual')}
                                        className={`p-4 border rounded-lg text-left transition-colors ${assemblyMode === value
                                            ? 'border-blue-500 bg-blue-50'
                                            : 'border-gray-200 hover:border-gray-300'
                                            }`}
                                    >
                                        <div className="flex items-center gap-2 mb-1">
                                            <div className={`w-3 h-3 rounded-full ${assemblyMode === value ? 'bg-blue-500' : 'bg-gray-300'
                                                }`} />
                                            <span className="font-medium">{label}</span>
                                        </div>
                                        <p className="text-xs text-gray-500">{desc}</p>
                                    </button>
                                ))}
                            </div>
                        </div>

                        {assemblyMode === 'auto' && (
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Auto-Accept Threshold: {Math.round(autoAcceptThreshold * 100)}%
                                </label>
                                <input
                                    type="range"
                                    min="0.5"
                                    max="1"
                                    step="0.05"
                                    value={autoAcceptThreshold}
                                    onChange={(e) => setAutoAcceptThreshold(parseFloat(e.target.value))}
                                    className="w-full"
                                />
                                <p className="text-xs text-gray-500 mt-1">
                                    Suggestions with confidence above this threshold will be auto-accepted
                                </p>
                            </div>
                        )}

                        <div className="flex items-center justify-between pt-4 border-t">
                            <div className="flex items-center gap-2 text-sm text-gray-500">
                                <Package className="w-4 h-4" />
                                <span>Currently: <strong className="capitalize">{assemblyMode}</strong> mode</span>
                            </div>
                            <Button
                                onClick={handleSaveAssemblyMode}
                                disabled={assemblyLoading}
                                size="sm"
                            >
                                {assemblyLoading ? (
                                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                                ) : (
                                    <Save className="w-4 h-4 mr-2" />
                                )}
                                Save Assembly Settings
                            </Button>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Notifications */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Bell className="w-5 h-5" />
                        Notifications
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Notification Email
                        </label>
                        {isEditing ? (
                            <Input
                                type="email"
                                value={formData.notification_email || ''}
                                onChange={(e) => setFormData(prev => ({
                                    ...prev,
                                    notification_email: e.target.value
                                }))}
                                placeholder="notifications@company.com"
                            />
                        ) : (
                            <div className="px-3 py-2 bg-gray-50 rounded-lg">
                                {settings?.notification_email || '-'}
                            </div>
                        )}
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        {[
                            { key: 'notify_on_filing', label: 'Entry Filed' },
                            { key: 'notify_on_acceptance', label: 'Entry Accepted' },
                            { key: 'notify_on_rejection', label: 'Entry Rejected' },
                            { key: 'notify_on_liquidation', label: 'Entry Liquidated' },
                        ].map(({ key, label }) => (
                            <div key={key} className="flex items-center gap-2">
                                {isEditing ? (
                                    <input
                                        type="checkbox"
                                        checked={formData[key as keyof typeof formData] as boolean}
                                        onChange={(e) => setFormData(prev => ({
                                            ...prev,
                                            [key]: e.target.checked
                                        }))}
                                        className="rounded border-gray-300"
                                    />
                                ) : (
                                    settings?.[key as keyof ACESettings] ? (
                                        <Check className="w-4 h-4 text-green-600" />
                                    ) : (
                                        <X className="w-4 h-4 text-gray-400" />
                                    )
                                )}
                                <span className="text-sm text-gray-700">{label}</span>
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>

            {/* Filer Codes */}
            <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                        <Building2 className="w-5 h-5" />
                        Filer Codes ({settings?.filer_codes?.length || 0})
                    </CardTitle>
                    <Button onClick={() => setShowAddFilerCode(true)}>
                        <Plus className="w-4 h-4 mr-2" />
                        Add Filer Code
                    </Button>
                </CardHeader>
                <CardContent>
                    {!settings?.filer_codes?.length ? (
                        <div className="text-center py-8">
                            <Building2 className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                            <p className="text-gray-500 mb-4">No filer codes configured</p>
                            <Button variant="secondary" onClick={() => setShowAddFilerCode(true)}>
                                <Plus className="w-4 h-4 mr-2" />
                                Add First Filer Code
                            </Button>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {settings.filer_codes.map((fc) => (
                                <div
                                    key={fc.id}
                                    className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50"
                                >
                                    <div className="flex items-center gap-4">
                                        <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                                            <span className="text-blue-600 font-bold font-mono">{fc.filer_code}</span>
                                        </div>
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <p className="font-medium text-gray-900">
                                                    {fc.name || fc.filer_code}
                                                </p>
                                                {fc.is_primary && (
                                                    <span className="px-2 py-0.5 bg-yellow-100 text-yellow-800 text-xs rounded-full flex items-center gap-1">
                                                        <Star className="w-3 h-3" />
                                                        Primary
                                                    </span>
                                                )}
                                                {!fc.is_active && (
                                                    <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">
                                                        Inactive
                                                    </span>
                                                )}
                                            </div>
                                            <p className="text-sm text-gray-500">
                                                Port: {fc.port_code || '-'} • Bond: {fc.bond_type || '-'} • Surety: {fc.surety_code || '-'}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={() => handleDeleteFilerCode(fc.id)}
                                            className="p-2 text-red-500 hover:bg-red-50 rounded-lg"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Info Box */}
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-start gap-3">
                <Info className="w-5 h-5 text-blue-600 mt-0.5" />
                <div className="text-sm text-blue-800">
                    <p className="font-medium mb-1">About ACE Portal Integration</p>
                    <p>
                        The Automated Commercial Environment (ACE) is CBP's system for processing imports.
                        Your filer code is assigned by CBP when you register as a customs broker.
                        Contact CBP Client Representative if you need to obtain a filer code.
                    </p>
                </div>
            </div>

            {/* Add Filer Code Modal */}
            <AddFilerCodeModal
                isOpen={showAddFilerCode}
                onClose={() => setShowAddFilerCode(false)}
                onAdd={handleAddFilerCode}
                loading={actionLoading}
            />
        </div>
    )
}

export default ACESettingsPage
