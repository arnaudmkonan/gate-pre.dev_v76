/**
 * New Client Page
 * 
 * Form for creating a new importer client.
 * 
 * Task 4.2 from ROADMAP_FULL_WORKFLOW.md
 */
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    ArrowLeft,
    Building2,
    Save,
    X,
    AlertCircle,
    FileText,
    Upload,
    Loader2,
    Sparkles,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import {
    useClientActions,
    ClientCreate,
    CLIENT_TYPES,
} from '../hooks/useClients'
import { uploadDocumentForClient } from '../lib/clientDocumentUpload'
import {
    extractClientFieldsFromPdf,
    mergeClientSuggestions,
    type ClientPdfEntityOption,
} from '../lib/clientExtractFromPdf'

const EMPTY_CLIENT_FORM: ClientCreate = {
    name: '',
    legal_name: '',
    dba_name: '',
    client_type: 'corporation',
    ior_number: '',
    ein: '',
    duns: '',
    address_line_1: '',
    address_line_2: '',
    city: '',
    state_province: '',
    postal_code: '',
    country: 'US',
    phone: '',
    email: '',
    website: '',
    primary_port: '',
    c_tpat_member: false,
    notes: '',
    internal_code: '',
}

export const NewClientPage = () => {
    const navigate = useNavigate()
    const { createClient, loading, error } = useClientActions()

    const [formData, setFormData] = useState<ClientCreate>({ ...EMPTY_CLIENT_FORM })

    const [validationErrors, setValidationErrors] = useState<Record<string, string>>({})
    const [onboardingPdf, setOnboardingPdf] = useState<File | null>(null)
    const [uploadWarning, setUploadWarning] = useState<string | null>(null)
    const [submitting, setSubmitting] = useState(false)
    const [extracting, setExtracting] = useState(false)
    const [extractMessage, setExtractMessage] = useState<string | null>(null)
    const [pdfEntities, setPdfEntities] = useState<ClientPdfEntityOption[]>([])
    const [selectedPdfEntityId, setSelectedPdfEntityId] = useState<string>('')
    const [autofilledFields, setAutofilledFields] = useState<Set<string>>(new Set())
    const pdfInputRef = useRef<HTMLInputElement>(null)

    const aiFieldClass = (field: string) =>
        autofilledFields.has(field) ? 'ring-2 ring-blue-200 border-blue-300' : ''

    const validate = (): boolean => {
        const errors: Record<string, string> = {}

        if (!formData.name.trim()) {
            errors.name = 'Company name is required'
        }

        // Validate IOR format if provided (XX-XXXXXXX)
        if (formData.ior_number && !/^\d{2}-\d{7}$/.test(formData.ior_number)) {
            errors.ior_number = 'IOR should be in format XX-XXXXXXX'
        }

        // Validate EIN format if provided (XX-XXXXXXX)
        if (formData.ein && !/^\d{2}-\d{7}$/.test(formData.ein)) {
            errors.ein = 'EIN should be in format XX-XXXXXXX'
        }

        setValidationErrors(errors)
        return Object.keys(errors).length === 0
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()

        if (!validate()) return

        setSubmitting(true)
        setUploadWarning(null)
        try {
            const result = await createClient(formData)
            if (!result) return

            if (onboardingPdf) {
                try {
                    const upload = await uploadDocumentForClient(
                        onboardingPdf,
                        result.id,
                        { tags: 'client_onboarding' },
                    )
                    navigate(
                        `/clients/${result.id}?doc_job=${encodeURIComponent(upload.job_id)}`,
                    )
                    return
                } catch (err) {
                    setUploadWarning(
                        err instanceof Error
                            ? `Client created, but document upload failed: ${err.message}`
                            : 'Client created, but document upload failed.',
                    )
                    navigate(`/clients/${result.id}`)
                    return
                }
            }

            navigate(`/clients/${result.id}`)
        } finally {
            setSubmitting(false)
        }
    }

    const handlePdfSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) {
            setOnboardingPdf(null)
            return
        }
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            setValidationErrors((prev) => ({
                ...prev,
                onboarding_pdf: 'Only PDF files are supported here',
            }))
            setOnboardingPdf(null)
            return
        }
        const maxMb = 50
        if (file.size > maxMb * 1024 * 1024) {
            setValidationErrors((prev) => ({
                ...prev,
                onboarding_pdf: `PDF must be under ${maxMb}MB`,
            }))
            setOnboardingPdf(null)
            return
        }
        setValidationErrors((prev) => {
            const next = { ...prev }
            delete next.onboarding_pdf
            return next
        })
        setOnboardingPdf(file)
        void runPdfExtraction(file)
    }

    const applyPdfEntity = (entity: ClientPdfEntityOption) => {
        const merged = mergeClientSuggestions(
            { ...EMPTY_CLIENT_FORM },
            entity.suggestions,
            false,
        )
        setFormData(merged.next)
        setAutofilledFields(new Set(merged.appliedFields))
        return merged.appliedFields
    }

    const runPdfExtraction = async (file: File) => {
        setExtracting(true)
        setExtractMessage(null)
        setAutofilledFields(new Set())
        setPdfEntities([])
        setSelectedPdfEntityId('')
        try {
            const result = await extractClientFieldsFromPdf(file)
            const entities = result.entities?.length
                ? result.entities
                : result.suggestions && Object.keys(result.suggestions).length
                  ? [
                        {
                            entity_id: 'default',
                            display_name: result.document_hint || 'Extracted profile',
                            suggestions: result.suggestions,
                            filled_fields: result.filled_fields,
                        },
                    ]
                  : []

            setPdfEntities(entities)

            let appliedFields: string[] = []
            if (entities.length > 0) {
                const first = entities[0]
                setSelectedPdfEntityId(first.entity_id)
                appliedFields = applyPdfEntity(first)
            } else {
                setFormData((prev) => {
                    const merged = mergeClientSuggestions(prev, result.suggestions, true)
                    appliedFields = merged.appliedFields
                    return merged.next
                })
                setAutofilledFields(new Set(appliedFields))
            }

            const warnText = result.warnings?.length ? result.warnings.join(' ') : ''
            const multiHint =
                entities.length > 1
                    ? ` Found ${entities.length} profiles — choose which one to import below.`
                    : ''
            if (appliedFields.length > 0) {
                setExtractMessage(
                    `Pre-filled ${appliedFields.length} field(s) from your PDF ` +
                        `(${result.document_hint || 'document'}, ${result.method}). Review before saving.` +
                        multiHint +
                        (warnText ? ` ${warnText}` : ''),
                )
            } else if (warnText) {
                setExtractMessage(warnText + multiHint)
            } else {
                setExtractMessage(
                    'PDF attached. No fields were detected automatically — complete the form manually.',
                )
            }
        } catch (err) {
            setExtractMessage(
                err instanceof Error
                    ? `Could not auto-fill from PDF: ${err.message}`
                    : 'Could not auto-fill from PDF.',
            )
        } finally {
            setExtracting(false)
        }
    }

    const handlePdfEntityChange = (entityId: string) => {
        const entity = pdfEntities.find((e) => e.entity_id === entityId)
        if (!entity) return
        setSelectedPdfEntityId(entityId)
        const appliedFields = applyPdfEntity(entity)
        setExtractMessage(
            `Loaded profile “${entity.display_name}” (${appliedFields.length} fields). Review before saving.`,
        )
    }

    const updateField = (field: keyof ClientCreate, value: any) => {
        setFormData(prev => ({ ...prev, [field]: value }))
        // Clear validation error when user starts typing
        if (validationErrors[field]) {
            setValidationErrors(prev => {
                const next = { ...prev }
                delete next[field]
                return next
            })
        }
        if (autofilledFields.has(field)) {
            setAutofilledFields((prev) => {
                const next = new Set(prev)
                next.delete(field)
                return next
            })
        }
    }

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Button variant="secondary" onClick={() => navigate('/clients')}>
                        <ArrowLeft className="w-4 h-4 mr-2" />
                        Back
                    </Button>
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">New Client</h1>
                        <p className="text-gray-500">Add a new importer client</p>
                    </div>
                </div>
            </div>

            {/* Error Banner */}
            {error && (
                <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
                    <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                    <p className="text-sm text-red-600">{error}</p>
                </div>
            )}
            {uploadWarning && (
                <div className="flex items-center gap-2 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                    <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0" />
                    <p className="text-sm text-amber-800">{uploadWarning}</p>
                </div>
            )}

            <form onSubmit={handleSubmit}>
                {/* Company Information */}
                <Card className="mb-6">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Building2 className="w-5 h-5" />
                            Company Information
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Company Name <span className="text-red-500">*</span>
                                </label>
                                <Input
                                    value={formData.name}
                                    onChange={(e) => updateField('name', e.target.value)}
                                    placeholder="Acme Importers LLC"
                                    className={`${validationErrors.name ? 'border-red-300' : ''} ${aiFieldClass('name')}`}
                                />
                                {validationErrors.name && (
                                    <p className="text-xs text-red-500 mt-1">{validationErrors.name}</p>
                                )}
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Entity Type
                                </label>
                                <select
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                    value={formData.client_type}
                                    onChange={(e) => updateField('client_type', e.target.value)}
                                >
                                    {CLIENT_TYPES.map(type => (
                                        <option key={type.value} value={type.value}>{type.label}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Legal Name
                                </label>
                                <Input
                                    value={formData.legal_name || ''}
                                    onChange={(e) => updateField('legal_name', e.target.value)}
                                    placeholder="Full legal name if different"
                                    className={aiFieldClass('legal_name')}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    DBA Name
                                </label>
                                <Input
                                    value={formData.dba_name || ''}
                                    onChange={(e) => updateField('dba_name', e.target.value)}
                                    placeholder="Doing business as..."
                                    className={aiFieldClass('dba_name')}
                                />
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Identifiers */}
                <Card className="mb-6">
                    <CardHeader>
                        <CardTitle>Customs Identifiers</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-3 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    IOR Number
                                </label>
                                <Input
                                    value={formData.ior_number || ''}
                                    onChange={(e) => updateField('ior_number', e.target.value)}
                                    placeholder="XX-XXXXXXX"
                                    className={`${validationErrors.ior_number ? 'border-red-300' : ''} ${aiFieldClass('ior_number')}`}
                                />
                                {validationErrors.ior_number && (
                                    <p className="text-xs text-red-500 mt-1">{validationErrors.ior_number}</p>
                                )}
                                <p className="text-xs text-gray-500 mt-1">Importer of Record Number</p>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    EIN
                                </label>
                                <Input
                                    value={formData.ein || ''}
                                    onChange={(e) => updateField('ein', e.target.value)}
                                    placeholder="XX-XXXXXXX"
                                    className={`${validationErrors.ein ? 'border-red-300' : ''} ${aiFieldClass('ein')}`}
                                />
                                {validationErrors.ein && (
                                    <p className="text-xs text-red-500 mt-1">{validationErrors.ein}</p>
                                )}
                                <p className="text-xs text-gray-500 mt-1">Employer ID Number</p>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    DUNS
                                </label>
                                <Input
                                    value={formData.duns || ''}
                                    onChange={(e) => updateField('duns', e.target.value)}
                                    placeholder="9-digit DUNS"
                                    className={aiFieldClass('duns')}
                                />
                                <p className="text-xs text-gray-500 mt-1">D&B D-U-N-S Number</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Address */}
                <Card className="mb-6">
                    <CardHeader>
                        <CardTitle>Address</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="col-span-2">
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Address Line 1
                                </label>
                                <Input
                                    value={formData.address_line_1 || ''}
                                    onChange={(e) => updateField('address_line_1', e.target.value)}
                                    placeholder="Street address"
                                    className={aiFieldClass('address_line_1')}
                                />
                            </div>
                            <div className="col-span-2">
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Address Line 2
                                </label>
                                <Input
                                    value={formData.address_line_2 || ''}
                                    onChange={(e) => updateField('address_line_2', e.target.value)}
                                    placeholder="Suite, floor, etc."
                                    className={aiFieldClass('address_line_2')}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    City
                                </label>
                                <Input
                                    value={formData.city || ''}
                                    onChange={(e) => updateField('city', e.target.value)}
                                    placeholder="City"
                                    className={aiFieldClass('city')}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    State/Province
                                </label>
                                <Input
                                    value={formData.state_province || ''}
                                    onChange={(e) => updateField('state_province', e.target.value)}
                                    placeholder="State"
                                    className={aiFieldClass('state_province')}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Postal Code
                                </label>
                                <Input
                                    value={formData.postal_code || ''}
                                    onChange={(e) => updateField('postal_code', e.target.value)}
                                    placeholder="ZIP/Postal code"
                                    className={aiFieldClass('postal_code')}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Country
                                </label>
                                <Input
                                    value={formData.country || 'US'}
                                    onChange={(e) => updateField('country', e.target.value)}
                                    placeholder="US"
                                    maxLength={2}
                                />
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Contact Information */}
                <Card className="mb-6">
                    <CardHeader>
                        <CardTitle>Contact Information</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-3 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Phone
                                </label>
                                <Input
                                    value={formData.phone || ''}
                                    onChange={(e) => updateField('phone', e.target.value)}
                                    placeholder="+1 (555) 000-0000"
                                    className={aiFieldClass('phone')}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Email
                                </label>
                                <Input
                                    type="email"
                                    value={formData.email || ''}
                                    onChange={(e) => updateField('email', e.target.value)}
                                    placeholder="contact@company.com"
                                    className={aiFieldClass('email')}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Website
                                </label>
                                <Input
                                    value={formData.website || ''}
                                    onChange={(e) => updateField('website', e.target.value)}
                                    placeholder="https://www.company.com"
                                    className={aiFieldClass('website')}
                                />
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Customs Preferences */}
                <Card className="mb-6">
                    <CardHeader>
                        <CardTitle>Customs Preferences</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-3 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Primary Port
                                </label>
                                <Input
                                    value={formData.primary_port || ''}
                                    onChange={(e) => updateField('primary_port', e.target.value)}
                                    placeholder="4-digit port code"
                                    maxLength={4}
                                    className={aiFieldClass('primary_port')}
                                />
                                <p className="text-xs text-gray-500 mt-1">Most frequently used entry port</p>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Internal Code
                                </label>
                                <Input
                                    value={formData.internal_code || ''}
                                    onChange={(e) => updateField('internal_code', e.target.value)}
                                    placeholder="Your reference code"
                                    className={aiFieldClass('internal_code')}
                                />
                                <p className="text-xs text-gray-500 mt-1">Internal tracking reference</p>
                            </div>
                            <div className="flex items-center pt-6">
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={formData.c_tpat_member}
                                        onChange={(e) => updateField('c_tpat_member', e.target.checked)}
                                        className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                                    />
                                    <span className="text-sm font-medium text-gray-700">C-TPAT Member</span>
                                </label>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Onboarding document */}
                <Card className="mb-6">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <FileText className="w-5 h-5" />
                            Onboarding document (optional)
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <p className="text-sm text-gray-600">
                            Import a PDF (POA, W-9, 5106, bond letter). We read the file to
                            suggest form values, then queue it for ingestion when you save.
                        </p>
                        {extracting && (
                            <div className="flex items-center gap-2 text-sm text-blue-700">
                                <Loader2 className="w-4 h-4 animate-spin" />
                                Reading PDF and suggesting fields…
                            </div>
                        )}
                        {extractMessage && !extracting && (
                            <div className="flex items-start gap-2 text-sm text-blue-900 bg-blue-50 border border-blue-100 rounded-lg p-3">
                                <Sparkles className="w-4 h-4 mt-0.5 flex-shrink-0" />
                                <span>{extractMessage}</span>
                            </div>
                        )}
                        {pdfEntities.length > 1 && !extracting && (
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Profile from PDF
                                </label>
                                <select
                                    className="w-full max-w-md px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                    value={selectedPdfEntityId}
                                    onChange={(e) => handlePdfEntityChange(e.target.value)}
                                >
                                    {pdfEntities.map((entity) => (
                                        <option key={entity.entity_id} value={entity.entity_id}>
                                            {entity.display_name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}
                        <input
                            ref={pdfInputRef}
                            type="file"
                            accept=".pdf,application/pdf"
                            className="hidden"
                            onChange={handlePdfSelect}
                        />
                        <div className="flex flex-wrap items-center gap-3">
                            <Button
                                type="button"
                                variant="secondary"
                                onClick={() => pdfInputRef.current?.click()}
                            >
                                <Upload className="w-4 h-4 mr-2" />
                                {onboardingPdf ? 'Change PDF' : 'Choose PDF'}
                            </Button>
                            {onboardingPdf && (
                                <>
                                    <span className="text-sm text-gray-700">
                                        {onboardingPdf.name} (
                                        {(onboardingPdf.size / (1024 * 1024)).toFixed(2)} MB)
                                    </span>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        onClick={() => {
                                            setOnboardingPdf(null)
                                            setPdfEntities([])
                                            setSelectedPdfEntityId('')
                                            setExtractMessage(null)
                                            setAutofilledFields(new Set())
                                            if (pdfInputRef.current) pdfInputRef.current.value = ''
                                        }}
                                    >
                                        Remove
                                    </Button>
                                </>
                            )}
                        </div>
                        {validationErrors.onboarding_pdf && (
                            <p className="text-xs text-red-500">{validationErrors.onboarding_pdf}</p>
                        )}
                    </CardContent>
                </Card>

                {/* Notes */}
                <Card className="mb-6">
                    <CardHeader>
                        <CardTitle>Notes</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <textarea
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            rows={4}
                            value={formData.notes || ''}
                            onChange={(e) => updateField('notes', e.target.value)}
                            placeholder="Add any notes about this client..."
                        />
                    </CardContent>
                </Card>

                {/* Actions */}
                <div className="flex items-center justify-end gap-3 py-4 border-t border-gray-200">
                    <Button variant="secondary" onClick={() => navigate('/clients')} type="button">
                        <X className="w-4 h-4 mr-2" />
                        Cancel
                    </Button>
                    <Button type="submit" disabled={loading || submitting}>
                        <Save className="w-4 h-4 mr-2" />
                        {loading || submitting
                            ? onboardingPdf
                                ? 'Creating & importing…'
                                : 'Creating...'
                            : onboardingPdf
                              ? 'Create client & import PDF'
                              : 'Create Client'}
                    </Button>
                </div>
            </form>
        </div>
    )
}

export default NewClientPage
