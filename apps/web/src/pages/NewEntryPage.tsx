/**
 * New Entry Wizard Page
 * 
 * Step-by-step wizard for manual entry creation.
 * Guides brokers through entry creation with validation at each step.
 * 
 * Task 1.8 from ROADMAP_FULL_WORKFLOW.md
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    ArrowLeft,
    ArrowRight,
    Save,
    Check,
    FileText,
    Building2,
    Package,
    ClipboardList,
    Plus,
    Trash2,
    Ship,
    Truck,
    Plane,
    Train,
    RefreshCw,
    AlertCircle,
    Search,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import { useEntryActions, ENTRY_TYPES } from '../hooks/useEntries'
import { useClients, ClientListItem } from '../hooks/useClients'

// Wizard step type
type WizardStep = 1 | 2 | 3 | 4

// Line item type for step 3
interface LineItem {
    id: string
    hts_code: string
    description: string
    quantity: number
    unit: string
    unit_value: number
    country_of_origin: string
    gross_weight?: number
    net_weight?: number
}

// Form data for entire wizard
interface WizardFormData {
    // Step 1: Entry Type & Port
    entry_type: string
    port_of_entry: string
    entry_date: string
    mode_of_transport: string
    bill_of_lading: string
    vessel_name: string
    voyage_number: string

    // Step 2: Importer & Consignee
    client_id?: string
    importer_of_record_name: string
    importer_of_record_number: string
    consignee_name: string
    consignee_number: string
    exporter_name: string
    exporter_country: string

    // Step 3: Line Items
    line_items: LineItem[]

    // Additional
    internal_reference: string
    notes: string
}

// Step indicator component
const StepIndicator = ({ currentStep, steps }: { currentStep: WizardStep; steps: { num: number; label: string; icon: any }[] }) => {
    return (
        <div className="flex items-center justify-center mb-8">
            {steps.map((step, index) => (
                <div key={step.num} className="flex items-center">
                    <div className="flex flex-col items-center">
                        <div
                            className={`w-10 h-10 rounded-full flex items-center justify-center font-medium text-sm transition-all ${currentStep >= step.num
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-200 text-gray-500'
                                }`}
                        >
                            {currentStep > step.num ? (
                                <Check className="w-5 h-5" />
                            ) : (
                                <step.icon className="w-5 h-5" />
                            )}
                        </div>
                        <span className={`text-xs mt-1 ${currentStep >= step.num ? 'text-blue-600 font-medium' : 'text-gray-500'}`}>
                            {step.label}
                        </span>
                    </div>
                    {index < steps.length - 1 && (
                        <div
                            className={`w-16 h-1 mx-2 rounded transition-all ${currentStep > step.num ? 'bg-blue-600' : 'bg-gray-200'
                                }`}
                        />
                    )}
                </div>
            ))}
        </div>
    )
}

// Transport mode icon
const TransportIcon = ({ mode }: { mode: string }) => {
    switch (mode) {
        case '10':
            return <Ship className="w-5 h-5" />
        case '20':
            return <Train className="w-5 h-5" />
        case '30':
            return <Truck className="w-5 h-5" />
        case '40':
            return <Plane className="w-5 h-5" />
        default:
            return <Package className="w-5 h-5" />
    }
}

// Format currency
const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
    }).format(value)
}

export const NewEntryPage = () => {
    const navigate = useNavigate()
    const { createEntry, loading, error } = useEntryActions()
    const { clients } = useClients({ limit: 100 })

    const [currentStep, setCurrentStep] = useState<WizardStep>(1)
    const [stepErrors, setStepErrors] = useState<Record<number, string[]>>({})
    const [showClientSearch, setShowClientSearch] = useState(false)
    const [clientSearch, setClientSearch] = useState('')

    const [formData, setFormData] = useState<WizardFormData>({
        entry_type: '01',
        port_of_entry: '',
        entry_date: new Date().toISOString().split('T')[0],
        mode_of_transport: '10',
        bill_of_lading: '',
        vessel_name: '',
        voyage_number: '',
        client_id: undefined,
        importer_of_record_name: '',
        importer_of_record_number: '',
        consignee_name: '',
        consignee_number: '',
        exporter_name: '',
        exporter_country: '',
        line_items: [],
        internal_reference: '',
        notes: '',
    })

    const steps = [
        { num: 1, label: 'Entry Info', icon: FileText },
        { num: 2, label: 'Parties', icon: Building2 },
        { num: 3, label: 'Line Items', icon: Package },
        { num: 4, label: 'Review', icon: ClipboardList },
    ]

    // Validate current step
    const validateStep = (step: WizardStep): string[] => {
        const errors: string[] = []

        switch (step) {
            case 1:
                if (!formData.port_of_entry) errors.push('Port of Entry is required')
                if (formData.port_of_entry && formData.port_of_entry.length !== 4) {
                    errors.push('Port code must be 4 digits')
                }
                break
            case 2:
                if (!formData.importer_of_record_name) errors.push('Importer name is required')
                break
            case 3:
                if (formData.line_items.length === 0) {
                    errors.push('At least one line item is required')
                }
                formData.line_items.forEach((item, i) => {
                    if (!item.hts_code) errors.push(`Line ${i + 1}: HTS code is required`)
                    if (!item.description) errors.push(`Line ${i + 1}: Description is required`)
                    if (item.quantity <= 0) errors.push(`Line ${i + 1}: Quantity must be greater than 0`)
                    if (item.unit_value <= 0) errors.push(`Line ${i + 1}: Unit value must be greater than 0`)
                })
                break
        }

        return errors
    }

    // Handle next step
    const handleNext = () => {
        const errors = validateStep(currentStep)
        if (errors.length > 0) {
            setStepErrors({ ...stepErrors, [currentStep]: errors })
            return
        }
        setStepErrors({ ...stepErrors, [currentStep]: [] })

        if (currentStep < 4) {
            setCurrentStep((currentStep + 1) as WizardStep)
        }
    }

    // Handle back step
    const handleBack = () => {
        if (currentStep > 1) {
            setCurrentStep((currentStep - 1) as WizardStep)
        }
    }

    // Handle save as draft
    const handleSaveDraft = async () => {
        const result = await createEntry({
            entry_type: formData.entry_type,
            port_of_entry: formData.port_of_entry,
            importer_of_record_name: formData.importer_of_record_name,
            importer_of_record_number: formData.importer_of_record_number,
            bill_of_lading: formData.bill_of_lading,
            mode_of_transport: formData.mode_of_transport,
            internal_reference: formData.internal_reference,
            notes: formData.notes,
            client_id: formData.client_id,
        })

        if (result) {
            navigate(`/entries/${result.id}`)
        }
    }

    // Handle submit
    const handleSubmit = async () => {
        // Validate all steps
        let hasErrors = false
        const allErrors: Record<number, string[]> = {}

        for (let step = 1; step <= 3; step++) {
            const errors = validateStep(step as WizardStep)
            if (errors.length > 0) {
                allErrors[step] = errors
                hasErrors = true
            }
        }

        if (hasErrors) {
            setStepErrors(allErrors)
            // Go to first step with errors
            const firstErrorStep = Object.keys(allErrors).sort()[0]
            setCurrentStep(parseInt(firstErrorStep) as WizardStep)
            return
        }

        const result = await createEntry({
            entry_type: formData.entry_type,
            port_of_entry: formData.port_of_entry,
            importer_of_record_name: formData.importer_of_record_name,
            importer_of_record_number: formData.importer_of_record_number,
            bill_of_lading: formData.bill_of_lading,
            mode_of_transport: formData.mode_of_transport,
            internal_reference: formData.internal_reference,
            notes: formData.notes,
            client_id: formData.client_id,
            line_items: formData.line_items.map((item, index) => ({
                line_number: index + 1,
                hts_code: item.hts_code,
                hts_description: item.description,
                quantity: item.quantity,
                unit_of_measure: item.unit,
                unit_value: item.unit_value,
                entered_value: item.quantity * item.unit_value,
                country_of_origin: item.country_of_origin,
                gross_weight: item.gross_weight,
                net_weight: item.net_weight,
            })),
        })

        if (result) {
            navigate(`/entries/${result.id}`)
        }
    }

    // Add new line item
    const addLineItem = () => {
        setFormData(prev => ({
            ...prev,
            line_items: [
                ...prev.line_items,
                {
                    id: crypto.randomUUID(),
                    hts_code: '',
                    description: '',
                    quantity: 1,
                    unit: 'PCS',
                    unit_value: 0,
                    country_of_origin: 'CN',
                },
            ],
        }))
    }

    // Remove line item
    const removeLineItem = (id: string) => {
        setFormData(prev => ({
            ...prev,
            line_items: prev.line_items.filter(item => item.id !== id),
        }))
    }

    // Update line item
    const updateLineItem = (id: string, field: keyof LineItem, value: any) => {
        setFormData(prev => ({
            ...prev,
            line_items: prev.line_items.map(item =>
                item.id === id ? { ...item, [field]: value } : item
            ),
        }))
    }

    // Select client from list
    const selectClient = (client: ClientListItem) => {
        setFormData(prev => ({
            ...prev,
            client_id: client.id,
            importer_of_record_name: client.name,
            importer_of_record_number: client.ior_number || client.ein || '',
        }))
        setShowClientSearch(false)
        setClientSearch('')
    }

    // Filter clients for search
    const filteredClients = clients.filter(c =>
        c.name.toLowerCase().includes(clientSearch.toLowerCase()) ||
        c.ior_number?.includes(clientSearch) ||
        c.ein?.includes(clientSearch)
    )

    // Calculate totals
    const totals = {
        lines: formData.line_items.length,
        value: formData.line_items.reduce((sum, item) => sum + (item.quantity * item.unit_value), 0),
        quantity: formData.line_items.reduce((sum, item) => sum + item.quantity, 0),
    }

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <button
                        onClick={() => navigate('/entries')}
                        className="flex items-center gap-1 text-gray-500 hover:text-gray-700 mb-2"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        <span className="text-sm">Back to Entries</span>
                    </button>
                    <h1 className="text-3xl font-bold text-gray-900">New Entry Wizard</h1>
                    <p className="text-gray-500 mt-1">Create a customs entry step by step</p>
                </div>
                <Button variant="secondary" onClick={handleSaveDraft} disabled={loading}>
                    <Save className="w-4 h-4 mr-2" />
                    Save Draft
                </Button>
            </div>

            {/* Step Indicator */}
            <StepIndicator currentStep={currentStep} steps={steps} />

            {/* Error Display */}
            {error && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-600 flex items-center gap-2">
                    <AlertCircle className="w-5 h-5 flex-shrink-0" />
                    {error}
                </div>
            )}

            {stepErrors[currentStep]?.length > 0 && (
                <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                    <p className="font-medium text-yellow-800 mb-2">Please fix the following:</p>
                    <ul className="list-disc list-inside text-sm text-yellow-700">
                        {stepErrors[currentStep].map((err, i) => (
                            <li key={i}>{err}</li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Step 1: Entry Type & Port */}
            {currentStep === 1 && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <FileText className="w-5 h-5" />
                            Step 1: Entry Information
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Entry Type <span className="text-red-500">*</span>
                                </label>
                                <select
                                    value={formData.entry_type}
                                    onChange={(e) => setFormData(prev => ({ ...prev, entry_type: e.target.value }))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                                >
                                    {Object.entries(ENTRY_TYPES).map(([code, name]) => (
                                        <option key={code} value={code}>
                                            {code} - {name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Port of Entry <span className="text-red-500">*</span>
                                </label>
                                <Input
                                    value={formData.port_of_entry}
                                    onChange={(e) => setFormData(prev => ({ ...prev, port_of_entry: e.target.value }))}
                                    placeholder="4-digit port code (e.g., 2704)"
                                    maxLength={4}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Entry Date
                                </label>
                                <Input
                                    type="date"
                                    value={formData.entry_date}
                                    onChange={(e) => setFormData(prev => ({ ...prev, entry_date: e.target.value }))}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Mode of Transport
                                </label>
                                <select
                                    value={formData.mode_of_transport}
                                    onChange={(e) => setFormData(prev => ({ ...prev, mode_of_transport: e.target.value }))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                                >
                                    <option value="10">10 - Vessel</option>
                                    <option value="20">20 - Rail</option>
                                    <option value="30">30 - Truck</option>
                                    <option value="40">40 - Air</option>
                                </select>
                            </div>
                        </div>

                        <div className="pt-4 border-t border-gray-100">
                            <h4 className="font-medium text-gray-900 mb-3">Transport Details</h4>
                            <div className="grid grid-cols-3 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Bill of Lading
                                    </label>
                                    <Input
                                        value={formData.bill_of_lading}
                                        onChange={(e) => setFormData(prev => ({ ...prev, bill_of_lading: e.target.value }))}
                                        placeholder="BOL/AWB number"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Vessel/Carrier Name
                                    </label>
                                    <Input
                                        value={formData.vessel_name}
                                        onChange={(e) => setFormData(prev => ({ ...prev, vessel_name: e.target.value }))}
                                        placeholder="Vessel or carrier"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Voyage/Flight #
                                    </label>
                                    <Input
                                        value={formData.voyage_number}
                                        onChange={(e) => setFormData(prev => ({ ...prev, voyage_number: e.target.value }))}
                                        placeholder="Voyage or flight"
                                    />
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Step 2: Importer & Consignee */}
            {currentStep === 2 && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Building2 className="w-5 h-5" />
                            Step 2: Parties
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        {/* Client Selection */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Select Existing Client
                            </label>
                            <div className="relative">
                                <div
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg cursor-pointer flex items-center justify-between"
                                    onClick={() => setShowClientSearch(!showClientSearch)}
                                >
                                    {formData.client_id ? (
                                        <span className="text-gray-900">{formData.importer_of_record_name}</span>
                                    ) : (
                                        <span className="text-gray-400">Click to search clients...</span>
                                    )}
                                    <Search className="w-4 h-4 text-gray-400" />
                                </div>

                                {showClientSearch && (
                                    <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                                        <div className="p-2 border-b border-gray-100">
                                            <Input
                                                value={clientSearch}
                                                onChange={(e) => setClientSearch(e.target.value)}
                                                placeholder="Search by name, IOR, EIN..."
                                                autoFocus
                                            />
                                        </div>
                                        {filteredClients.length === 0 ? (
                                            <div className="p-3 text-sm text-gray-500 text-center">
                                                No clients found
                                            </div>
                                        ) : (
                                            filteredClients.map(client => (
                                                <div
                                                    key={client.id}
                                                    className="px-3 py-2 hover:bg-gray-50 cursor-pointer flex items-center justify-between"
                                                    onClick={() => selectClient(client)}
                                                >
                                                    <div>
                                                        <p className="font-medium text-gray-900">{client.name}</p>
                                                        <p className="text-xs text-gray-500">
                                                            IOR: {client.ior_number || '-'} • EIN: {client.ein || '-'}
                                                        </p>
                                                    </div>
                                                </div>
                                            ))
                                        )}
                                        <div
                                            className="px-3 py-2 border-t border-gray-100 text-blue-600 hover:bg-blue-50 cursor-pointer text-sm font-medium"
                                            onClick={() => {
                                                setShowClientSearch(false)
                                                // Allow manual entry
                                            }}
                                        >
                                            + Enter manually instead
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="pt-4 border-t border-gray-100">
                            <h4 className="font-medium text-gray-900 mb-3">Importer of Record <span className="text-red-500">*</span></h4>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Importer Name
                                    </label>
                                    <Input
                                        value={formData.importer_of_record_name}
                                        onChange={(e) => setFormData(prev => ({ ...prev, importer_of_record_name: e.target.value }))}
                                        placeholder="Company name"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        IOR Number
                                    </label>
                                    <Input
                                        value={formData.importer_of_record_number}
                                        onChange={(e) => setFormData(prev => ({ ...prev, importer_of_record_number: e.target.value }))}
                                        placeholder="EIN or CBP Number"
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="pt-4 border-t border-gray-100">
                            <h4 className="font-medium text-gray-900 mb-3">Consignee (if different)</h4>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Consignee Name
                                    </label>
                                    <Input
                                        value={formData.consignee_name}
                                        onChange={(e) => setFormData(prev => ({ ...prev, consignee_name: e.target.value }))}
                                        placeholder="Consignee company"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Consignee Number
                                    </label>
                                    <Input
                                        value={formData.consignee_number}
                                        onChange={(e) => setFormData(prev => ({ ...prev, consignee_number: e.target.value }))}
                                        placeholder="EIN or CBP Number"
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="pt-4 border-t border-gray-100">
                            <h4 className="font-medium text-gray-900 mb-3">Exporter/Shipper</h4>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Exporter Name
                                    </label>
                                    <Input
                                        value={formData.exporter_name}
                                        onChange={(e) => setFormData(prev => ({ ...prev, exporter_name: e.target.value }))}
                                        placeholder="Foreign supplier"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Exporter Country
                                    </label>
                                    <Input
                                        value={formData.exporter_country}
                                        onChange={(e) => setFormData(prev => ({ ...prev, exporter_country: e.target.value }))}
                                        placeholder="2-letter code (e.g., CN)"
                                        maxLength={2}
                                    />
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Step 3: Line Items */}
            {currentStep === 3 && (
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between">
                        <CardTitle className="flex items-center gap-2">
                            <Package className="w-5 h-5" />
                            Step 3: Line Items
                        </CardTitle>
                        <Button onClick={addLineItem}>
                            <Plus className="w-4 h-4 mr-2" />
                            Add Line
                        </Button>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {formData.line_items.length === 0 ? (
                            <div className="text-center py-8">
                                <Package className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                                <p className="text-gray-500 mb-4">No line items yet</p>
                                <Button onClick={addLineItem}>
                                    <Plus className="w-4 h-4 mr-2" />
                                    Add First Line Item
                                </Button>
                            </div>
                        ) : (
                            <>
                                {formData.line_items.map((item, index) => (
                                    <div key={item.id} className="p-4 border border-gray-200 rounded-lg bg-gray-50">
                                        <div className="flex items-center justify-between mb-3">
                                            <span className="font-medium text-gray-900">Line {index + 1}</span>
                                            <button
                                                onClick={() => removeLineItem(item.id)}
                                                className="text-red-500 hover:text-red-700 p-1"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </div>
                                        <div className="grid grid-cols-4 gap-3">
                                            <div>
                                                <label className="block text-xs font-medium text-gray-500 mb-1">HTS Code *</label>
                                                <Input
                                                    value={item.hts_code}
                                                    onChange={(e) => updateLineItem(item.id, 'hts_code', e.target.value)}
                                                    placeholder="0000.00.0000"
                                                />
                                            </div>
                                            <div className="col-span-2">
                                                <label className="block text-xs font-medium text-gray-500 mb-1">Description *</label>
                                                <Input
                                                    value={item.description}
                                                    onChange={(e) => updateLineItem(item.id, 'description', e.target.value)}
                                                    placeholder="Product description"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs font-medium text-gray-500 mb-1">Country of Origin</label>
                                                <Input
                                                    value={item.country_of_origin}
                                                    onChange={(e) => updateLineItem(item.id, 'country_of_origin', e.target.value)}
                                                    placeholder="CN"
                                                    maxLength={2}
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs font-medium text-gray-500 mb-1">Quantity *</label>
                                                <Input
                                                    type="number"
                                                    value={item.quantity}
                                                    onChange={(e) => updateLineItem(item.id, 'quantity', parseFloat(e.target.value) || 0)}
                                                    min={0}
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs font-medium text-gray-500 mb-1">Unit</label>
                                                <select
                                                    value={item.unit}
                                                    onChange={(e) => updateLineItem(item.id, 'unit', e.target.value)}
                                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                                                >
                                                    <option value="PCS">PCS - Pieces</option>
                                                    <option value="KG">KG - Kilograms</option>
                                                    <option value="LB">LB - Pounds</option>
                                                    <option value="DOZ">DOZ - Dozens</option>
                                                    <option value="M">M - Meters</option>
                                                    <option value="SQM">SQM - Square Meters</option>
                                                </select>
                                            </div>
                                            <div>
                                                <label className="block text-xs font-medium text-gray-500 mb-1">Unit Value (USD) *</label>
                                                <Input
                                                    type="number"
                                                    value={item.unit_value}
                                                    onChange={(e) => updateLineItem(item.id, 'unit_value', parseFloat(e.target.value) || 0)}
                                                    min={0}
                                                    step="0.01"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs font-medium text-gray-500 mb-1">Line Value</label>
                                                <div className="px-3 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium">
                                                    {formatCurrency(item.quantity * item.unit_value)}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ))}

                                {/* Summary */}
                                <div className="flex justify-between items-center p-4 bg-blue-50 border border-blue-200 rounded-lg">
                                    <span className="font-medium text-blue-900">{totals.lines} line(s) • {totals.quantity} total units</span>
                                    <span className="text-lg font-bold text-blue-900">Total: {formatCurrency(totals.value)}</span>
                                </div>
                            </>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Step 4: Review */}
            {currentStep === 4 && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <ClipboardList className="w-5 h-5" />
                            Step 4: Review & Create
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        {/* Entry Info Summary */}
                        <div className="grid grid-cols-2 gap-6">
                            <div>
                                <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                                    <FileText className="w-4 h-4" /> Entry Information
                                </h4>
                                <dl className="space-y-2 text-sm">
                                    <div className="flex justify-between">
                                        <dt className="text-gray-500">Entry Type:</dt>
                                        <dd className="font-medium">{formData.entry_type} - {ENTRY_TYPES[formData.entry_type as keyof typeof ENTRY_TYPES]}</dd>
                                    </div>
                                    <div className="flex justify-between">
                                        <dt className="text-gray-500">Port of Entry:</dt>
                                        <dd className="font-medium">{formData.port_of_entry}</dd>
                                    </div>
                                    <div className="flex justify-between">
                                        <dt className="text-gray-500">Entry Date:</dt>
                                        <dd className="font-medium">{formData.entry_date}</dd>
                                    </div>
                                    <div className="flex justify-between">
                                        <dt className="text-gray-500">Transport:</dt>
                                        <dd className="font-medium flex items-center gap-1">
                                            <TransportIcon mode={formData.mode_of_transport} />
                                            {formData.mode_of_transport === '10' && 'Vessel'}
                                            {formData.mode_of_transport === '20' && 'Rail'}
                                            {formData.mode_of_transport === '30' && 'Truck'}
                                            {formData.mode_of_transport === '40' && 'Air'}
                                        </dd>
                                    </div>
                                    {formData.bill_of_lading && (
                                        <div className="flex justify-between">
                                            <dt className="text-gray-500">BOL:</dt>
                                            <dd className="font-medium">{formData.bill_of_lading}</dd>
                                        </div>
                                    )}
                                </dl>
                            </div>

                            <div>
                                <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                                    <Building2 className="w-4 h-4" /> Parties
                                </h4>
                                <dl className="space-y-2 text-sm">
                                    <div className="flex justify-between">
                                        <dt className="text-gray-500">Importer:</dt>
                                        <dd className="font-medium">{formData.importer_of_record_name}</dd>
                                    </div>
                                    <div className="flex justify-between">
                                        <dt className="text-gray-500">IOR #:</dt>
                                        <dd className="font-mono">{formData.importer_of_record_number || '-'}</dd>
                                    </div>
                                    {formData.consignee_name && (
                                        <div className="flex justify-between">
                                            <dt className="text-gray-500">Consignee:</dt>
                                            <dd className="font-medium">{formData.consignee_name}</dd>
                                        </div>
                                    )}
                                    {formData.exporter_name && (
                                        <div className="flex justify-between">
                                            <dt className="text-gray-500">Exporter:</dt>
                                            <dd className="font-medium">{formData.exporter_name} ({formData.exporter_country})</dd>
                                        </div>
                                    )}
                                </dl>
                            </div>
                        </div>

                        {/* Line Items Summary */}
                        <div className="pt-4 border-t border-gray-100">
                            <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                                <Package className="w-4 h-4" /> Line Items ({formData.line_items.length})
                            </h4>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="border-b border-gray-200">
                                            <th className="text-left py-2 px-2 font-medium text-gray-500">Line</th>
                                            <th className="text-left py-2 px-2 font-medium text-gray-500">HTS Code</th>
                                            <th className="text-left py-2 px-2 font-medium text-gray-500">Description</th>
                                            <th className="text-center py-2 px-2 font-medium text-gray-500">Qty</th>
                                            <th className="text-left py-2 px-2 font-medium text-gray-500">Origin</th>
                                            <th className="text-right py-2 px-2 font-medium text-gray-500">Value</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {formData.line_items.map((item, index) => (
                                            <tr key={item.id} className="border-b border-gray-100">
                                                <td className="py-2 px-2">{index + 1}</td>
                                                <td className="py-2 px-2 font-mono">{item.hts_code}</td>
                                                <td className="py-2 px-2 truncate max-w-[200px]">{item.description}</td>
                                                <td className="py-2 px-2 text-center">{item.quantity} {item.unit}</td>
                                                <td className="py-2 px-2">{item.country_of_origin}</td>
                                                <td className="py-2 px-2 text-right font-medium">{formatCurrency(item.quantity * item.unit_value)}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                    <tfoot>
                                        <tr className="bg-gray-50">
                                            <td colSpan={5} className="py-2 px-2 font-medium text-right">Total Entered Value:</td>
                                            <td className="py-2 px-2 text-right font-bold text-lg">{formatCurrency(totals.value)}</td>
                                        </tr>
                                    </tfoot>
                                </table>
                            </div>
                        </div>

                        {/* Additional Info */}
                        <div className="pt-4 border-t border-gray-100 grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Internal Reference
                                </label>
                                <Input
                                    value={formData.internal_reference}
                                    onChange={(e) => setFormData(prev => ({ ...prev, internal_reference: e.target.value }))}
                                    placeholder="Your reference number"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Notes
                                </label>
                                <Input
                                    value={formData.notes}
                                    onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                                    placeholder="Additional notes..."
                                />
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Navigation */}
            <div className="flex items-center justify-between pt-4">
                <Button
                    variant="secondary"
                    onClick={handleBack}
                    disabled={currentStep === 1}
                >
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Back
                </Button>

                <div className="flex items-center gap-2 text-sm text-gray-500">
                    Step {currentStep} of 4
                </div>

                {currentStep < 4 ? (
                    <Button onClick={handleNext}>
                        Next
                        <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                ) : (
                    <Button onClick={handleSubmit} disabled={loading}>
                        {loading ? (
                            <>
                                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                                Creating...
                            </>
                        ) : (
                            <>
                                <Check className="w-4 h-4 mr-2" />
                                Create Entry
                            </>
                        )}
                    </Button>
                )}
            </div>
        </div>
    )
}

export default NewEntryPage
