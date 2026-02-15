import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
    ArrowLeft, RefreshCw, Ship, Package,
    CheckCircle, AlertTriangle, AlertCircle, Download,
    User, MapPin, DollarSign, Truck
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'

interface LineItem {
    line_number: number
    hts_number: string
    description: string
    quantity: number
    unit: string
    gross_weight: number
    country_of_origin: string
    entered_value: number
    duty_rate: number
    duty_amount: number
}

interface EntryPrepData {
    entry_number: string | null
    entry_type: string
    entry_date: string | null
    filer_code: string | null
    port_code: string | null
    importer: {
        ior_number: string | null
        name: string | null
        address: string | null
        city: string | null
        state: string | null
        zip: string | null
    }
    consignee: {
        name: string | null
        address: string | null
    }
    transport: {
        carrier_code: string | null
        vessel_name: string | null
        voyage_number: string | null
        port_of_unlading: string | null
        port_of_entry: string | null
        importing_carrier: string | null
        foreign_port: string | null
        export_date: string | null
        import_date: string | null
        master_bill: string | null
        house_bill: string | null
        scac_code: string | null
    }
    bond: {
        type: string
        surety_code: string | null
    }
    origin: {
        country_of_origin: string | null
        exporting_country: string | null
    }
    totals: {
        entered_value: number
        duty: number
        mpf: number
        hmf: number
        taxes: number
        other: number
        grand_total: number
    }
    line_items: LineItem[]
    metadata: {
        source_shipment_id: string | null
        source_documents: string[]
        validation_warnings: string[]
        completeness_score: number
    }
}

interface ValidationResult {
    is_valid: boolean
    completeness_score: number
    errors: string[]
    warnings: string[]
    field_issues: Record<string, string>
}

import { API_BASE } from '../config/api'

const ENTRY_TYPES = {
    '01': 'Consumption Entry',
    '02': 'Consumption - Quota',
    '03': 'Consumption - AD/CVD',
    '06': 'Consumption - FTZ',
    '21': 'Warehouse Entry',
    '22': 'Re-warehouse Entry',
    '11': 'Informal Entry',
}

export const EntryPrepPage = () => {
    const { shipmentId } = useParams<{ shipmentId: string }>()
    const navigate = useNavigate()
    const [entryData, setEntryData] = useState<EntryPrepData | null>(null)
    const [validation, setValidation] = useState<ValidationResult | null>(null)
    const [loading, setLoading] = useState(true)
    const [validating, setValidating] = useState(false)
    const [exporting, setExporting] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (shipmentId) {
            fetchEntryData()
        }
    }, [shipmentId])

    const fetchEntryData = async () => {
        setLoading(true)
        setError(null)
        try {
            const response = await fetch(`${API_BASE}/api/entries/prep/${shipmentId}`)
            if (!response.ok) throw new Error('Failed to fetch entry data')
            const data = await response.json()
            setEntryData(data)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred')
        } finally {
            setLoading(false)
        }
    }

    const validateEntry = async () => {
        setValidating(true)
        try {
            const response = await fetch(`${API_BASE}/api/entries/prep/${shipmentId}/validate`, {
                method: 'POST'
            })
            if (!response.ok) throw new Error('Validation failed')
            const data = await response.json()
            setValidation(data)
        } catch (err) {
            console.error('Validation error:', err)
        } finally {
            setValidating(false)
        }
    }

    const exportEntry = async (format: 'ace' | 'json') => {
        setExporting(true)
        try {
            const response = await fetch(
                `${API_BASE}/api/entries/prep/${shipmentId}/export?format=${format}`,
                { method: 'POST' }
            )
            if (!response.ok) throw new Error('Export failed')
            const data = await response.json()

            // Download as file
            const blob = new Blob([JSON.stringify(data.data, null, 2)], { type: 'application/json' })
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `entry_${shipmentId}_${format}.json`
            a.click()
            URL.revokeObjectURL(url)
        } catch (err) {
            console.error('Export error:', err)
        } finally {
            setExporting(false)
        }
    }

    const getCompletionColor = (score: number) => {
        if (score >= 0.8) return 'text-green-600 bg-green-100'
        if (score >= 0.5) return 'text-yellow-600 bg-yellow-100'
        return 'text-red-600 bg-red-100'
    }

    const formatCurrency = (amount: number) => {
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount)
    }

    const formatDate = (dateStr: string | null) => {
        if (!dateStr) return '-'
        return new Date(dateStr).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        })
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-96">
                <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
            </div>
        )
    }

    if (error || !entryData) {
        return (
            <div className="space-y-4">
                <Button onClick={() => navigate(-1)} variant="secondary">
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Back
                </Button>
                <div className="flex gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
                    <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                    <p className="text-red-600">{error || 'Entry data not found'}</p>
                </div>
            </div>
        )
    }

    const { metadata } = entryData

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Button onClick={() => navigate(-1)} variant="secondary" size="sm">
                        <ArrowLeft className="w-4 h-4" />
                    </Button>
                    <div>
                        <div className="flex items-center gap-3">
                            <h1 className="text-2xl font-bold">Entry Preparation</h1>
                            <span className={`px-3 py-1 rounded-full text-sm font-medium ${getCompletionColor(metadata.completeness_score)}`}>
                                {Math.round(metadata.completeness_score * 100)}% Complete
                            </span>
                        </div>
                        <p className="text-gray-500 mt-1">
                            CBP 7501 Entry Summary • Shipment: {shipmentId?.substring(0, 8)}...
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button onClick={fetchEntryData} variant="secondary">
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Refresh
                    </Button>
                    <Button onClick={validateEntry} variant="secondary" disabled={validating}>
                        {validating ? (
                            <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                            <CheckCircle className="w-4 h-4 mr-2" />
                        )}
                        Validate
                    </Button>
                    <Button onClick={() => exportEntry('ace')} disabled={exporting}>
                        {exporting ? (
                            <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                            <Download className="w-4 h-4 mr-2" />
                        )}
                        Export ACE
                    </Button>
                </div>
            </div>

            {/* Validation Warnings */}
            {metadata.validation_warnings.length > 0 && (
                <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle className="w-5 h-5 text-yellow-600" />
                        <h3 className="font-medium text-yellow-800">Validation Warnings ({metadata.validation_warnings.length})</h3>
                    </div>
                    <ul className="text-sm text-yellow-700 space-y-1 ml-7">
                        {metadata.validation_warnings.map((warning, idx) => (
                            <li key={idx}>• {warning}</li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Validation Result */}
            {validation && (
                <div className={`p-4 border rounded-lg ${validation.is_valid ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                    <div className="flex items-center gap-2 mb-2">
                        {validation.is_valid ? (
                            <>
                                <CheckCircle className="w-5 h-5 text-green-600" />
                                <h3 className="font-medium text-green-800">Entry is valid and ready for submission</h3>
                            </>
                        ) : (
                            <>
                                <AlertCircle className="w-5 h-5 text-red-600" />
                                <h3 className="font-medium text-red-800">{validation.errors.length} error(s) must be fixed</h3>
                            </>
                        )}
                    </div>
                    {validation.errors.length > 0 && (
                        <ul className="text-sm text-red-700 space-y-1 ml-7">
                            {validation.errors.map((err, idx) => (
                                <li key={idx}>• {err}</li>
                            ))}
                        </ul>
                    )}
                </div>
            )}

            {/* CBP 7501 Form Layout */}
            <div className="bg-white border-2 border-gray-300 rounded-lg overflow-hidden">
                {/* Form Header */}
                <div className="bg-gray-100 p-4 border-b-2 border-gray-300">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <span className="text-2xl font-bold">CBP Form 7501</span>
                            <span className="text-gray-600">Entry Summary</span>
                        </div>
                        <div className="flex items-center gap-4 text-sm">
                            <div>
                                <span className="text-gray-500">Entry Type:</span>
                                <span className="ml-2 font-medium">{ENTRY_TYPES[entryData.entry_type as keyof typeof ENTRY_TYPES] || entryData.entry_type}</span>
                            </div>
                            <div>
                                <span className="text-gray-500">Entry #:</span>
                                <span className="ml-2 font-mono font-medium">{entryData.entry_number || '[Pending]'}</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="p-6 space-y-6">
                    {/* Row 1: Filer & Port Info */}
                    <div className="grid grid-cols-4 gap-4">
                        <div className="border p-3 rounded">
                            <label className="text-xs text-gray-500 block mb-1">1. Filer Code</label>
                            <span className="font-mono text-lg">{entryData.filer_code || '-'}</span>
                        </div>
                        <div className="border p-3 rounded">
                            <label className="text-xs text-gray-500 block mb-1">2. Entry Date</label>
                            <span className="text-lg">{formatDate(entryData.entry_date)}</span>
                        </div>
                        <div className="border p-3 rounded">
                            <label className="text-xs text-gray-500 block mb-1">3. Port Code</label>
                            <span className="font-mono text-lg">{entryData.port_code || entryData.transport.port_of_entry || '-'}</span>
                        </div>
                        <div className="border p-3 rounded">
                            <label className="text-xs text-gray-500 block mb-1">4. Bond Type</label>
                            <span className="text-lg">{entryData.bond.type === '9' ? 'Continuous' : 'Single Transaction'}</span>
                        </div>
                    </div>

                    {/* Row 2: Importer Information */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="flex items-center gap-2 text-base">
                                <User className="w-4 h-4" />
                                Importer of Record
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="text-xs text-gray-500 block mb-1">5. IOR Number</label>
                                    <span className="font-mono">{entryData.importer.ior_number || '-'}</span>
                                </div>
                                <div>
                                    <label className="text-xs text-gray-500 block mb-1">6. Importer Name</label>
                                    <span className="font-medium">{entryData.importer.name || '-'}</span>
                                </div>
                                <div className="col-span-2">
                                    <label className="text-xs text-gray-500 block mb-1">7. Address</label>
                                    <span>{entryData.importer.address || '-'}</span>
                                    {(entryData.importer.city || entryData.importer.state || entryData.importer.zip) && (
                                        <span className="block">
                                            {[entryData.importer.city, entryData.importer.state, entryData.importer.zip].filter(Boolean).join(', ')}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Row 3: Transport Information */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="flex items-center gap-2 text-base">
                                <Truck className="w-4 h-4" />
                                Transport Information
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="grid grid-cols-4 gap-4">
                                <div>
                                    <label className="text-xs text-gray-500 block mb-1">8. Mode of Transport</label>
                                    <span>Ocean</span>
                                </div>
                                <div>
                                    <label className="text-xs text-gray-500 block mb-1">9. Carrier Code</label>
                                    <span className="font-mono">{entryData.transport.carrier_code || entryData.transport.scac_code || '-'}</span>
                                </div>
                                <div>
                                    <label className="text-xs text-gray-500 block mb-1">10. Vessel Name</label>
                                    <span>{entryData.transport.vessel_name || '-'}</span>
                                </div>
                                <div>
                                    <label className="text-xs text-gray-500 block mb-1">11. Voyage Number</label>
                                    <span className="font-mono">{entryData.transport.voyage_number || '-'}</span>
                                </div>
                                <div>
                                    <label className="text-xs text-gray-500 block mb-1">12. Foreign Port</label>
                                    <span>{entryData.transport.foreign_port || '-'}</span>
                                </div>
                                <div>
                                    <label className="text-xs text-gray-500 block mb-1">13. Port of Unlading</label>
                                    <span>{entryData.transport.port_of_unlading || entryData.transport.port_of_entry || '-'}</span>
                                </div>
                                <div>
                                    <label className="text-xs text-gray-500 block mb-1">14. Export Date</label>
                                    <span>{formatDate(entryData.transport.export_date)}</span>
                                </div>
                                <div>
                                    <label className="text-xs text-gray-500 block mb-1">15. Import Date</label>
                                    <span>{formatDate(entryData.transport.import_date)}</span>
                                </div>
                                <div className="col-span-2">
                                    <label className="text-xs text-gray-500 block mb-1">16. Master Bill of Lading</label>
                                    <span className="font-mono font-medium">{entryData.transport.master_bill || '-'}</span>
                                </div>
                                <div className="col-span-2">
                                    <label className="text-xs text-gray-500 block mb-1">17. House Bill</label>
                                    <span className="font-mono">{entryData.transport.house_bill || '-'}</span>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Row 4: Origin Information */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="flex items-center gap-2 text-base">
                                <MapPin className="w-4 h-4" />
                                Country of Origin
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="grid grid-cols-3 gap-4">
                                <div>
                                    <label className="text-xs text-gray-500 block mb-1">18. Country of Origin</label>
                                    <span className="font-medium">{entryData.origin.country_of_origin || '-'}</span>
                                </div>
                                <div>
                                    <label className="text-xs text-gray-500 block mb-1">19. Exporting Country</label>
                                    <span>{entryData.origin.exporting_country || entryData.origin.country_of_origin || '-'}</span>
                                </div>
                                <div>
                                    <label className="text-xs text-gray-500 block mb-1">20. Consignee</label>
                                    <span>{entryData.consignee.name || '-'}</span>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Line Items */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="flex items-center gap-2 text-base">
                                <Package className="w-4 h-4" />
                                Line Items ({entryData.line_items.length})
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {entryData.line_items.length === 0 ? (
                                <div className="text-center py-8 text-gray-500">
                                    <Package className="w-10 h-10 mx-auto mb-3 opacity-30" />
                                    <p>No line items found</p>
                                    <p className="text-sm">Add commercial invoice data to populate line items</p>
                                </div>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead className="bg-gray-50">
                                            <tr>
                                                <th className="px-3 py-2 text-left font-medium text-gray-600">#</th>
                                                <th className="px-3 py-2 text-left font-medium text-gray-600">HTS Number</th>
                                                <th className="px-3 py-2 text-left font-medium text-gray-600">Description</th>
                                                <th className="px-3 py-2 text-right font-medium text-gray-600">Qty</th>
                                                <th className="px-3 py-2 text-left font-medium text-gray-600">Origin</th>
                                                <th className="px-3 py-2 text-right font-medium text-gray-600">Value</th>
                                                <th className="px-3 py-2 text-right font-medium text-gray-600">Duty Rate</th>
                                                <th className="px-3 py-2 text-right font-medium text-gray-600">Duty</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y">
                                            {entryData.line_items.map((item) => (
                                                <tr key={item.line_number} className="hover:bg-gray-50">
                                                    <td className="px-3 py-2 text-gray-500">{item.line_number}</td>
                                                    <td className="px-3 py-2 font-mono">{item.hts_number || <span className="text-red-500">[Missing]</span>}</td>
                                                    <td className="px-3 py-2 max-w-xs truncate">{item.description || '-'}</td>
                                                    <td className="px-3 py-2 text-right">{item.quantity} {item.unit}</td>
                                                    <td className="px-3 py-2">{item.country_of_origin || '-'}</td>
                                                    <td className="px-3 py-2 text-right font-mono">{formatCurrency(item.entered_value)}</td>
                                                    <td className="px-3 py-2 text-right">{(item.duty_rate * 100).toFixed(1)}%</td>
                                                    <td className="px-3 py-2 text-right font-mono">{formatCurrency(item.duty_amount)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Totals */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="flex items-center gap-2 text-base">
                                <DollarSign className="w-4 h-4" />
                                Entry Summary Totals
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="grid grid-cols-2 gap-8">
                                <div className="space-y-3">
                                    <div className="flex justify-between py-2 border-b">
                                        <span className="text-gray-600">Total Entered Value</span>
                                        <span className="font-mono font-medium">{formatCurrency(entryData.totals.entered_value)}</span>
                                    </div>
                                    <div className="flex justify-between py-2 border-b">
                                        <span className="text-gray-600">Estimated Duty</span>
                                        <span className="font-mono">{formatCurrency(entryData.totals.duty)}</span>
                                    </div>
                                    <div className="flex justify-between py-2 border-b">
                                        <span className="text-gray-600">Merchandise Processing Fee (MPF)</span>
                                        <span className="font-mono">{formatCurrency(entryData.totals.mpf)}</span>
                                    </div>
                                </div>
                                <div className="space-y-3">
                                    <div className="flex justify-between py-2 border-b">
                                        <span className="text-gray-600">Harbor Maintenance Fee (HMF)</span>
                                        <span className="font-mono">{formatCurrency(entryData.totals.hmf)}</span>
                                    </div>
                                    <div className="flex justify-between py-2 border-b">
                                        <span className="text-gray-600">Taxes</span>
                                        <span className="font-mono">{formatCurrency(entryData.totals.taxes)}</span>
                                    </div>
                                    <div className="flex justify-between py-2 border-b">
                                        <span className="text-gray-600">Other</span>
                                        <span className="font-mono">{formatCurrency(entryData.totals.other)}</span>
                                    </div>
                                </div>
                            </div>
                            <div className="mt-6 pt-4 border-t-2 border-gray-300 flex justify-between items-center">
                                <span className="text-lg font-medium">Grand Total (Duties + Fees)</span>
                                <span className="text-2xl font-bold font-mono text-blue-600">
                                    {formatCurrency(entryData.totals.grand_total)}
                                </span>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>

            {/* Metadata Footer */}
            <Card>
                <CardContent className="py-4">
                    <div className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-4 text-gray-500">
                            <span>Source Shipment: <code className="font-mono">{metadata.source_shipment_id?.substring(0, 8)}...</code></span>
                            <span>•</span>
                            <span>{metadata.source_documents.length} source documents</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Button variant="secondary" onClick={() => exportEntry('json')}>
                                <Download className="w-4 h-4 mr-2" />
                                Export JSON
                            </Button>
                            <Button variant="secondary" onClick={() => navigate(`/shipments/${metadata.source_shipment_id}`)}>
                                <Ship className="w-4 h-4 mr-2" />
                                View Shipment
                            </Button>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
