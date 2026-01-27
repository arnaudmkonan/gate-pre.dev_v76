/**
 * New Client Page
 * 
 * Form for creating a new importer client.
 * 
 * Task 4.2 from ROADMAP_FULL_WORKFLOW.md
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    ArrowLeft,
    Building2,
    Save,
    X,
    AlertCircle,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import {
    useClientActions,
    ClientCreate,
    CLIENT_TYPES,
} from '../hooks/useClients'

export const NewClientPage = () => {
    const navigate = useNavigate()
    const { createClient, loading, error } = useClientActions()

    const [formData, setFormData] = useState<ClientCreate>({
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
    })

    const [validationErrors, setValidationErrors] = useState<Record<string, string>>({})

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

        const result = await createClient(formData)
        if (result) {
            navigate(`/clients/${result.id}`)
        }
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
                                    className={validationErrors.name ? 'border-red-300' : ''}
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
                                    className={validationErrors.ior_number ? 'border-red-300' : ''}
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
                                    className={validationErrors.ein ? 'border-red-300' : ''}
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
                    <Button type="submit" disabled={loading}>
                        <Save className="w-4 h-4 mr-2" />
                        {loading ? 'Creating...' : 'Create Client'}
                    </Button>
                </div>
            </form>
        </div>
    )
}

export default NewClientPage
