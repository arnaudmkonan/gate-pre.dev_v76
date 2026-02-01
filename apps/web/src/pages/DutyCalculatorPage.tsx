/**
 * Duty Calculator Page
 * 
 * Standalone duty calculation tool for quick HTS lookups.
 * 
 * Task 2.6 from ROADMAP_FULL_WORKFLOW.md
 */
import { useState, useCallback } from 'react'
import {
    Calculator,
    Search,
    DollarSign,
    Package,
    AlertTriangle,
    CheckCircle,
    ChevronRight,
    RefreshCw,
    FileDown,
    Info,
    Shield,
    Zap,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Button } from '../components/Button'
import { useDutyCalculator, formatCurrency } from '../hooks/useEntries'

// Country codes with common import origins
const COUNTRIES = [
    { code: 'CN', name: 'China', flag: '🇨🇳', section301: true },
    { code: 'MX', name: 'Mexico', flag: '🇲🇽', fta: 'USMCA' },
    { code: 'CA', name: 'Canada', flag: '🇨🇦', fta: 'USMCA' },
    { code: 'VN', name: 'Vietnam', flag: '🇻🇳' },
    { code: 'IN', name: 'India', flag: '🇮🇳' },
    { code: 'TW', name: 'Taiwan', flag: '🇹🇼' },
    { code: 'KR', name: 'South Korea', flag: '🇰🇷', fta: 'KORUS' },
    { code: 'JP', name: 'Japan', flag: '🇯🇵' },
    { code: 'DE', name: 'Germany', flag: '🇩🇪' },
    { code: 'GB', name: 'United Kingdom', flag: '🇬🇧' },
    { code: 'IT', name: 'Italy', flag: '🇮🇹' },
    { code: 'TH', name: 'Thailand', flag: '🇹🇭' },
    { code: 'MY', name: 'Malaysia', flag: '🇲🇾' },
    { code: 'ID', name: 'Indonesia', flag: '🇮🇩' },
]

const FTA_PROGRAMS = [
    { code: '', name: 'None (MFN Rate)' },
    { code: 'USMCA', name: 'USMCA (US-Mexico-Canada)' },
    { code: 'KORUS', name: 'KORUS (US-Korea FTA)' },
    { code: 'CAFTA', name: 'CAFTA-DR' },
    { code: 'GSP', name: 'GSP (Generalized System of Preferences)' },
    { code: 'ISRAEL', name: 'US-Israel FTA' },
    { code: 'AUSTRALIA', name: 'US-Australia FTA' },
    { code: 'SINGAPORE', name: 'US-Singapore FTA' },
]

interface DutyResult {
    hts_code: string
    entered_value: number
    quantity: number
    country_of_origin: string
    base_duty: {
        rate: number | null
        rate_type: string
        amount: number
    }
    section_301: {
        rate: number | null
        amount: number
        list: string | null
    }
    section_232: {
        rate: number | null
        amount: number
        product: string | null
    }
    add_cvd: {
        add_rate: number | null
        add_amount: number
        add_case_number: string | null
        cvd_rate: number | null
        cvd_amount: number
        cvd_case_number: string | null
    }
    fta: {
        code: string | null
        rate: number | null
        eligible: boolean
        savings: number
    }
    total_duty: number
    hts_description: string | null
}

interface FeeResult {
    mpf: {
        rate: number
        amount: number
        min: number
        max: number
    }
    hmf: {
        rate: number
        amount: number
    }
    total_fees: number
}

export const DutyCalculatorPage = () => {
    // Form state
    const [htsCode, setHtsCode] = useState('')
    const [value, setValue] = useState<number>(10000)
    const [quantity, setQuantity] = useState<number>(1)
    const [country, setCountry] = useState('CN')
    const [ftaCode, setFtaCode] = useState('')
    const [entryType, setEntryType] = useState('formal')

    // Results
    const [dutyResult, setDutyResult] = useState<DutyResult | null>(null)
    const [feeResult, setFeeResult] = useState<FeeResult | null>(null)

    const { loading, error, calculateDuty, calculateFees } = useDutyCalculator()

    const handleCalculate = useCallback(async () => {
        if (!htsCode) {
            alert('Please enter an HTS code')
            return
        }

        // Calculate duty
        const duty = await calculateDuty(htsCode, value, quantity, country, ftaCode || undefined)
        if (duty) {
            setDutyResult(duty)
        }

        // Calculate fees
        const fees = await calculateFees(value, 1, entryType)
        if (fees) {
            setFeeResult(fees)
        }
    }, [htsCode, value, quantity, country, ftaCode, entryType, calculateDuty, calculateFees])

    const handleClear = () => {
        setHtsCode('')
        setValue(10000)
        setQuantity(1)
        setCountry('CN')
        setFtaCode('')
        setDutyResult(null)
        setFeeResult(null)
    }

    const selectedCountry = COUNTRIES.find(c => c.code === country)
    const grandTotal = (dutyResult?.total_duty || 0) + (feeResult?.total_fees || 0)
    const effectiveRate = value > 0 ? (grandTotal / value * 100) : 0

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
                        <Calculator className="w-8 h-8 text-blue-600" />
                        Duty Calculator
                    </h1>
                    <p className="text-gray-500 mt-1">
                        Calculate customs duties, tariffs, and fees for imports
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-3 gap-6">
                {/* Left Column - Calculator Input */}
                <div className="col-span-2 space-y-6">
                    {/* Calculator Card */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Search className="w-5 h-5" />
                                Calculate Duty
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            {/* HTS Code Input */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    HTS Code <span className="text-red-500">*</span>
                                </label>
                                <div className="relative">
                                    <input
                                        type="text"
                                        value={htsCode}
                                        onChange={(e) => setHtsCode(e.target.value.replace(/[^\d.]/g, ''))}
                                        placeholder="8471.30.0100"
                                        className="w-full px-4 py-3 text-lg font-mono border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                        maxLength={14}
                                    />
                                    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm text-gray-400">
                                        10 digits
                                    </span>
                                </div>
                                {dutyResult?.hts_description && (
                                    <p className="mt-2 text-sm text-gray-600 bg-gray-50 p-2 rounded">
                                        {dutyResult.hts_description}
                                    </p>
                                )}
                            </div>

                            {/* Value and Quantity */}
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Entered Value (USD)
                                    </label>
                                    <div className="relative">
                                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">$</span>
                                        <input
                                            type="number"
                                            value={value}
                                            onChange={(e) => setValue(parseFloat(e.target.value) || 0)}
                                            className="w-full pl-8 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                                            min={0}
                                            step="100"
                                        />
                                    </div>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Quantity
                                    </label>
                                    <input
                                        type="number"
                                        value={quantity}
                                        onChange={(e) => setQuantity(parseFloat(e.target.value) || 1)}
                                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                                        min={1}
                                        step="1"
                                    />
                                </div>
                            </div>

                            {/* Country and FTA */}
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Country of Origin
                                    </label>
                                    <select
                                        value={country}
                                        onChange={(e) => setCountry(e.target.value)}
                                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                                    >
                                        {COUNTRIES.map(c => (
                                            <option key={c.code} value={c.code}>
                                                {c.flag} {c.name} ({c.code})
                                            </option>
                                        ))}
                                    </select>
                                    {selectedCountry?.section301 && (
                                        <p className="mt-1 text-xs text-orange-600 flex items-center gap-1">
                                            <AlertTriangle className="w-3 h-3" />
                                            Section 301 tariffs may apply
                                        </p>
                                    )}
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Free Trade Agreement
                                    </label>
                                    <select
                                        value={ftaCode}
                                        onChange={(e) => setFtaCode(e.target.value)}
                                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                                    >
                                        {FTA_PROGRAMS.map(fta => (
                                            <option key={fta.code} value={fta.code}>
                                                {fta.name}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            </div>

                            {/* Entry Type */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Entry Type
                                </label>
                                <div className="flex gap-4">
                                    <label className="flex items-center gap-2">
                                        <input
                                            type="radio"
                                            name="entryType"
                                            value="formal"
                                            checked={entryType === 'formal'}
                                            onChange={(e) => setEntryType(e.target.value)}
                                            className="text-blue-600"
                                        />
                                        <span className="text-sm">Formal (&gt; $2,500)</span>
                                    </label>
                                    <label className="flex items-center gap-2">
                                        <input
                                            type="radio"
                                            name="entryType"
                                            value="informal"
                                            checked={entryType === 'informal'}
                                            onChange={(e) => setEntryType(e.target.value)}
                                            className="text-blue-600"
                                        />
                                        <span className="text-sm">Informal (&lt; $2,500)</span>
                                    </label>
                                </div>
                            </div>

                            {/* Error Display */}
                            {error && (
                                <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
                                    {error}
                                </div>
                            )}

                            {/* Action Buttons */}
                            <div className="flex gap-3 pt-4 border-t">
                                <Button
                                    onClick={handleCalculate}
                                    disabled={loading || !htsCode}
                                    className="flex-1"
                                >
                                    {loading ? (
                                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                                    ) : (
                                        <Calculator className="w-4 h-4 mr-2" />
                                    )}
                                    Calculate Duty
                                </Button>
                                <Button variant="secondary" onClick={handleClear}>
                                    Clear
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Results Card */}
                    {dutyResult && (
                        <Card>
                            <CardHeader>
                                <div className="flex items-center justify-between">
                                    <CardTitle className="flex items-center gap-2">
                                        <DollarSign className="w-5 h-5" />
                                        Duty Breakdown
                                    </CardTitle>
                                    <Button variant="secondary" size="sm">
                                        <FileDown className="w-4 h-4 mr-2" />
                                        Export PDF
                                    </Button>
                                </div>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-4">
                                    {/* Base Duty */}
                                    <div className="flex items-center justify-between py-3 border-b">
                                        <div className="flex items-center gap-3">
                                            <Package className="w-5 h-5 text-gray-400" />
                                            <div>
                                                <p className="font-medium">Base Duty</p>
                                                <p className="text-sm text-gray-500">
                                                    {dutyResult.base_duty.rate !== null
                                                        ? `${(dutyResult.base_duty.rate * 100).toFixed(2)}% ${dutyResult.base_duty.rate_type}`
                                                        : 'Free'}
                                                </p>
                                            </div>
                                        </div>
                                        <span className="font-medium">
                                            {formatCurrency(dutyResult.base_duty.amount)}
                                        </span>
                                    </div>

                                    {/* Section 301 */}
                                    <div className={`flex items-center justify-between py-3 border-b ${dutyResult.section_301.amount > 0 ? 'bg-orange-50 -mx-6 px-6' : ''
                                        }`}>
                                        <div className="flex items-center gap-3">
                                            <Shield className={`w-5 h-5 ${dutyResult.section_301.amount > 0 ? 'text-orange-500' : 'text-gray-400'}`} />
                                            <div>
                                                <p className="font-medium">Section 301 (China Tariffs)</p>
                                                <p className="text-sm text-gray-500">
                                                    {dutyResult.section_301.list
                                                        ? `List ${dutyResult.section_301.list} - ${(dutyResult.section_301.rate || 0) * 100}%`
                                                        : 'Not applicable'}
                                                </p>
                                            </div>
                                        </div>
                                        <span className={`font-medium ${dutyResult.section_301.amount > 0 ? 'text-orange-600' : ''}`}>
                                            {formatCurrency(dutyResult.section_301.amount)}
                                        </span>
                                    </div>

                                    {/* Section 232 */}
                                    <div className="flex items-center justify-between py-3 border-b">
                                        <div className="flex items-center gap-3">
                                            <Zap className={`w-5 h-5 ${dutyResult.section_232.amount > 0 ? 'text-red-500' : 'text-gray-400'}`} />
                                            <div>
                                                <p className="font-medium">Section 232 (Steel/Aluminum)</p>
                                                <p className="text-sm text-gray-500">
                                                    {dutyResult.section_232.product || 'Not applicable'}
                                                </p>
                                            </div>
                                        </div>
                                        <span className={`font-medium ${dutyResult.section_232.amount > 0 ? 'text-red-600' : ''}`}>
                                            {formatCurrency(dutyResult.section_232.amount)}
                                        </span>
                                    </div>

                                    {/* ADD/CVD */}
                                    <div className="flex items-center justify-between py-3 border-b">
                                        <div className="flex items-center gap-3">
                                            <AlertTriangle className={`w-5 h-5 ${(dutyResult.add_cvd.add_amount + dutyResult.add_cvd.cvd_amount) > 0 ? 'text-red-500' : 'text-gray-400'
                                                }`} />
                                            <div>
                                                <p className="font-medium">ADD/CVD</p>
                                                <p className="text-sm text-gray-500">
                                                    {dutyResult.add_cvd.add_case_number || dutyResult.add_cvd.cvd_case_number
                                                        ? 'Active case applies'
                                                        : 'No active orders'}
                                                </p>
                                            </div>
                                        </div>
                                        <span className="font-medium">
                                            {formatCurrency(dutyResult.add_cvd.add_amount + dutyResult.add_cvd.cvd_amount)}
                                        </span>
                                    </div>

                                    {/* FTA Savings */}
                                    {dutyResult.fta.eligible && (
                                        <div className="flex items-center justify-between py-3 border-b bg-green-50 -mx-6 px-6">
                                            <div className="flex items-center gap-3">
                                                <CheckCircle className="w-5 h-5 text-green-500" />
                                                <div>
                                                    <p className="font-medium text-green-700">FTA Savings ({dutyResult.fta.code})</p>
                                                    <p className="text-sm text-green-600">
                                                        Preferential rate applied
                                                    </p>
                                                </div>
                                            </div>
                                            <span className="font-medium text-green-600">
                                                -{formatCurrency(dutyResult.fta.savings)}
                                            </span>
                                        </div>
                                    )}

                                    {/* Duty Subtotal */}
                                    <div className="flex items-center justify-between py-3 font-medium">
                                        <span>Total Duty</span>
                                        <span className="text-lg">{formatCurrency(dutyResult.total_duty)}</span>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {/* Fees Card */}
                    {feeResult && (
                        <Card>
                            <CardHeader>
                                <CardTitle>CBP Fees</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-4">
                                    {/* MPF */}
                                    <div className="flex items-center justify-between py-3 border-b">
                                        <div>
                                            <p className="font-medium">Merchandise Processing Fee (MPF)</p>
                                            <p className="text-sm text-gray-500">
                                                {(feeResult.mpf.rate * 100).toFixed(4)}% (min ${feeResult.mpf.min}, max ${feeResult.mpf.max})
                                            </p>
                                        </div>
                                        <span className="font-medium">{formatCurrency(feeResult.mpf.amount)}</span>
                                    </div>

                                    {/* HMF */}
                                    <div className="flex items-center justify-between py-3 border-b">
                                        <div>
                                            <p className="font-medium">Harbor Maintenance Fee (HMF)</p>
                                            <p className="text-sm text-gray-500">
                                                {(feeResult.hmf.rate * 100).toFixed(3)}% of value
                                            </p>
                                        </div>
                                        <span className="font-medium">{formatCurrency(feeResult.hmf.amount)}</span>
                                    </div>

                                    {/* Fee Total */}
                                    <div className="flex items-center justify-between py-3 font-medium">
                                        <span>Total Fees</span>
                                        <span className="text-lg">{formatCurrency(feeResult.total_fees)}</span>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </div>

                {/* Right Column - Summary */}
                <div className="space-y-6">
                    {/* Quick Summary */}
                    <Card className={dutyResult ? 'bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200' : ''}>
                        <CardHeader>
                            <CardTitle>Summary</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {dutyResult ? (
                                <div className="space-y-4">
                                    <div>
                                        <p className="text-sm text-gray-600">Entered Value</p>
                                        <p className="text-2xl font-bold">{formatCurrency(value)}</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-gray-600">Total Duty & Taxes</p>
                                        <p className="text-2xl font-bold">{formatCurrency(dutyResult.total_duty)}</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-gray-600">CBP Fees</p>
                                        <p className="text-2xl font-bold">{formatCurrency(feeResult?.total_fees || 0)}</p>
                                    </div>
                                    <hr className="border-blue-200" />
                                    <div className="pt-2">
                                        <p className="text-sm text-gray-600">Grand Total</p>
                                        <p className="text-3xl font-bold text-blue-700">{formatCurrency(grandTotal)}</p>
                                        <p className="text-sm text-gray-500 mt-1">
                                            Effective rate: {effectiveRate.toFixed(2)}%
                                        </p>
                                    </div>
                                    <div className="pt-2">
                                        <p className="text-sm text-gray-600">Landed Cost</p>
                                        <p className="text-xl font-bold text-gray-700">
                                            {formatCurrency(value + grandTotal)}
                                        </p>
                                        <p className="text-sm text-gray-500">
                                            Per unit: {formatCurrency((value + grandTotal) / quantity)}
                                        </p>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-center py-8 text-gray-400">
                                    <Calculator className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                    <p>Enter product details to calculate duties</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Info Card */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Info className="w-5 h-5" />
                                Quick Tips
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="text-sm text-gray-600 space-y-3">
                            <p className="flex items-start gap-2">
                                <ChevronRight className="w-4 h-4 mt-0.5 flex-shrink-0 text-blue-500" />
                                Enter the full 10-digit HTS code for accurate duty rates
                            </p>
                            <p className="flex items-start gap-2">
                                <ChevronRight className="w-4 h-4 mt-0.5 flex-shrink-0 text-blue-500" />
                                Section 301 tariffs add 7.5-25% on China origin goods
                            </p>
                            <p className="flex items-start gap-2">
                                <ChevronRight className="w-4 h-4 mt-0.5 flex-shrink-0 text-blue-500" />
                                FTA programs can eliminate or reduce base duty
                            </p>
                            <p className="flex items-start gap-2">
                                <ChevronRight className="w-4 h-4 mt-0.5 flex-shrink-0 text-blue-500" />
                                MPF is capped at $575.35 per entry
                            </p>
                        </CardContent>
                    </Card>

                    {/* Recent Calculations */}
                    <Card>
                        <CardHeader>
                            <CardTitle>Common HTS Codes</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-2">
                                {[
                                    { hts: '8471.30.01', desc: 'Laptops' },
                                    { hts: '8517.12.00', desc: 'Cell Phones' },
                                    { hts: '6204.62.40', desc: 'Cotton Trousers' },
                                    { hts: '9403.20.00', desc: 'Metal Furniture' },
                                    { hts: '8523.51.00', desc: 'Solid-State Storage' },
                                ].map(item => (
                                    <button
                                        key={item.hts}
                                        onClick={() => setHtsCode(item.hts)}
                                        className="w-full flex items-center justify-between p-2 rounded hover:bg-gray-50 text-left"
                                    >
                                        <span className="font-mono text-sm">{item.hts}</span>
                                        <span className="text-sm text-gray-500">{item.desc}</span>
                                    </button>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    )
}

export default DutyCalculatorPage
