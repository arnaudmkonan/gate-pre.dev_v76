import { useState } from 'react';
import { ArrowRightLeft, Clock, DollarSign, Calendar, FileCheck, ArrowRight, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Card } from '../components/Card';
import { Input } from '../components/Input';
import { Button } from '../components/Button';

interface EligibilityResult {
    import_date: string;
    deadline: string;
    days_remaining: number;
    eligible: boolean;
    eligibility_expires: string;
}

interface RefundEstimate {
    duty_paid: number;
    quantity_imported: number;
    quantity_exported: number;
    eligible_quantity: number;
    match_type: string;
    refund_rate_percent: number;
    quantity_ratio: number;
    potential_refund: number;
    retained_by_cbp: number;
}

interface ReconciliationResult {
    matches: any[];
    unmatched_imports: any[];
    unmatched_exports: any[];
    summary: {
        total_matches: number;
        total_potential_refund: number;
        direct_matches: number;
        substitution_matches: number;
    };
}

type Tab = 'eligibility' | 'calculator' | 'reconcile' | 'info';

export const DrawbackPage = () => {
    const [activeTab, setActiveTab] = useState<Tab>('eligibility');
    const [loading, setLoading] = useState(false);

    // Eligibility state
    const [importDate, setImportDate] = useState('');
    const [exportDate, setExportDate] = useState('');
    const [eligibilityResult, setEligibilityResult] = useState<EligibilityResult | null>(null);

    // Calculator state
    const [dutyPaid, setDutyPaid] = useState('');
    const [qtyImported, setQtyImported] = useState('');
    const [qtyExported, setQtyExported] = useState('');
    const [matchType, setMatchType] = useState('direct');
    const [refundEstimate, setRefundEstimate] = useState<RefundEstimate | null>(null);

    // Reconciliation state
    const [reconcileJson, setReconcileJson] = useState('');
    const [reconcileResult, setReconcileResult] = useState<ReconciliationResult | null>(null);

    const checkEligibility = async () => {
        if (!importDate) return;
        setLoading(true);
        try {
            const params = new URLSearchParams({ import_date: importDate });
            if (exportDate) params.append('export_date', exportDate);

            const res = await fetch(`/api/entry-reconciliation/eligibility?${params}`);
            const data = await res.json();
            setEligibilityResult(data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const calculateRefund = async () => {
        if (!dutyPaid || !qtyImported || !qtyExported) return;
        setLoading(true);
        try {
            const params = new URLSearchParams({
                duty_paid: dutyPaid,
                quantity_imported: qtyImported,
                quantity_exported: qtyExported,
                match_type: matchType
            });

            const res = await fetch(`/api/entry-reconciliation/estimate-refund?${params}`);
            const data = await res.json();
            setRefundEstimate(data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const runReconciliation = async () => {
        if (!reconcileJson) return;
        setLoading(true);
        try {
            const data = JSON.parse(reconcileJson);
            const res = await fetch('/api/entry-reconciliation/reconcile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await res.json();
            setReconcileResult(result);
        } catch (e) {
            console.error(e);
            alert('Invalid JSON format');
        } finally {
            setLoading(false);
        }
    };

    const tabs = [
        { id: 'eligibility' as Tab, label: 'Check Eligibility', icon: Clock },
        { id: 'calculator' as Tab, label: 'Refund Calculator', icon: DollarSign },
        { id: 'reconcile' as Tab, label: 'Reconcile Entries', icon: ArrowRightLeft },
        { id: 'info' as Tab, label: 'Program Info', icon: FileCheck },
    ];

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Duty Drawback</h1>
                    <p className="text-gray-400 mt-1">Match imports to exports and calculate potential duty refunds</p>
                </div>
            </div>

            {/* Tab Navigation */}
            <div className="flex gap-2 border-b border-gray-700 pb-2 overflow-x-auto">
                {tabs.map(({ id, label, icon: Icon }) => (
                    <button
                        key={id}
                        onClick={() => setActiveTab(id)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-t-lg transition-colors whitespace-nowrap ${activeTab === id
                                ? 'bg-green-600 text-white'
                                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                            }`}
                    >
                        <Icon className="w-4 h-4" />
                        {label}
                    </button>
                ))}
            </div>

            {/* Eligibility Tab */}
            {activeTab === 'eligibility' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <Card className="p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Calendar className="w-5 h-5 text-blue-400" />
                            Drawback Eligibility Check
                        </h2>
                        <p className="text-sm text-gray-400 mb-4">
                            Per 19 USC 1313, drawback must be claimed within 5 years of import entry.
                        </p>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Import Entry Date</label>
                                <Input
                                    type="date"
                                    value={importDate}
                                    onChange={(e) => setImportDate(e.target.value)}
                                />
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Export Date (optional)</label>
                                <Input
                                    type="date"
                                    value={exportDate}
                                    onChange={(e) => setExportDate(e.target.value)}
                                />
                            </div>
                            <Button
                                onClick={checkEligibility}
                                disabled={loading || !importDate}
                                className="w-full"
                            >
                                {loading ? 'Checking...' : 'Check Eligibility'}
                            </Button>
                        </div>
                    </Card>

                    <Card className="p-6">
                        <h2 className="text-lg font-semibold text-white mb-4">Result</h2>

                        {!eligibilityResult ? (
                            <div className="text-center text-gray-500 py-12">
                                <Clock className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                <p>Enter import date to check eligibility</p>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                <div className={`p-4 rounded-lg ${eligibilityResult.eligible
                                        ? 'bg-green-500/10 border border-green-500/30'
                                        : 'bg-red-500/10 border border-red-500/30'
                                    }`}>
                                    <div className="flex items-center gap-2 mb-2">
                                        {eligibilityResult.eligible ? (
                                            <>
                                                <CheckCircle2 className="w-5 h-5 text-green-400" />
                                                <span className="font-semibold text-green-400">Eligible for Drawback</span>
                                            </>
                                        ) : (
                                            <>
                                                <AlertTriangle className="w-5 h-5 text-red-400" />
                                                <span className="font-semibold text-red-400">Expired</span>
                                            </>
                                        )}
                                    </div>
                                    <p className="text-3xl font-bold text-white">
                                        {eligibilityResult.days_remaining} days
                                    </p>
                                    <p className="text-sm text-gray-400">
                                        {eligibilityResult.eligible ? 'remaining until deadline' : 'past deadline'}
                                    </p>
                                </div>

                                <div className="p-3 bg-gray-800 rounded-lg space-y-2">
                                    <div className="flex justify-between text-sm">
                                        <span className="text-gray-400">Import Date</span>
                                        <span className="text-white">{eligibilityResult.import_date.split('T')[0]}</span>
                                    </div>
                                    <div className="flex justify-between text-sm">
                                        <span className="text-gray-400">Deadline</span>
                                        <span className="text-white">{eligibilityResult.eligibility_expires}</span>
                                    </div>
                                </div>
                            </div>
                        )}
                    </Card>
                </div>
            )}

            {/* Calculator Tab */}
            {activeTab === 'calculator' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <Card className="p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <DollarSign className="w-5 h-5 text-green-400" />
                            Refund Calculator
                        </h2>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Duty Paid (USD)</label>
                                <Input
                                    type="number"
                                    placeholder="e.g., 10000"
                                    value={dutyPaid}
                                    onChange={(e) => setDutyPaid(e.target.value)}
                                />
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Quantity Imported</label>
                                <Input
                                    type="number"
                                    placeholder="e.g., 100"
                                    value={qtyImported}
                                    onChange={(e) => setQtyImported(e.target.value)}
                                />
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Quantity Exported</label>
                                <Input
                                    type="number"
                                    placeholder="e.g., 75"
                                    value={qtyExported}
                                    onChange={(e) => setQtyExported(e.target.value)}
                                />
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Match Type</label>
                                <select
                                    value={matchType}
                                    onChange={(e) => setMatchType(e.target.value)}
                                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                                >
                                    <option value="direct">Direct Identification (Same goods)</option>
                                    <option value="substitution">Substitution (Same kind/quality)</option>
                                </select>
                            </div>
                            <Button
                                onClick={calculateRefund}
                                disabled={loading || !dutyPaid || !qtyImported || !qtyExported}
                                className="w-full"
                            >
                                {loading ? 'Calculating...' : 'Calculate Refund'}
                            </Button>
                        </div>
                    </Card>

                    <Card className="p-6">
                        <h2 className="text-lg font-semibold text-white mb-4">Refund Estimate</h2>

                        {!refundEstimate ? (
                            <div className="text-center text-gray-500 py-12">
                                <DollarSign className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                <p>Enter values to calculate refund</p>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                <div className="p-4 bg-green-500/10 rounded-lg border border-green-500/30 text-center">
                                    <p className="text-sm text-gray-400">Potential Refund</p>
                                    <p className="text-4xl font-bold text-green-400">
                                        ${refundEstimate.potential_refund.toLocaleString()}
                                    </p>
                                    <p className="text-sm text-gray-400 mt-1">
                                        {refundEstimate.refund_rate_percent}% refund rate
                                    </p>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="p-3 bg-gray-800 rounded-lg text-center">
                                        <p className="text-xs text-gray-400">Eligible Qty</p>
                                        <p className="text-lg font-semibold text-white">{refundEstimate.eligible_quantity}</p>
                                    </div>
                                    <div className="p-3 bg-gray-800 rounded-lg text-center">
                                        <p className="text-xs text-gray-400">CBP Retains</p>
                                        <p className="text-lg font-semibold text-yellow-400">${refundEstimate.retained_by_cbp}</p>
                                    </div>
                                </div>

                                <div className="p-3 bg-gray-800 rounded-lg">
                                    <div className="flex justify-between text-sm">
                                        <span className="text-gray-400">Match Type</span>
                                        <span className="text-white capitalize">{refundEstimate.match_type}</span>
                                    </div>
                                    <div className="flex justify-between text-sm mt-2">
                                        <span className="text-gray-400">Quantity Ratio</span>
                                        <span className="text-white">{(refundEstimate.quantity_ratio * 100).toFixed(1)}%</span>
                                    </div>
                                </div>
                            </div>
                        )}
                    </Card>
                </div>
            )}

            {/* Reconcile Tab */}
            {activeTab === 'reconcile' && (
                <div className="grid grid-cols-1 gap-6">
                    <Card className="p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <ArrowRightLeft className="w-5 h-5 text-purple-400" />
                            Import/Export Reconciliation
                        </h2>
                        <p className="text-sm text-gray-400 mb-4">
                            Paste JSON with import_entries and export_records arrays to find matches.
                        </p>
                        <textarea
                            className="w-full h-48 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white font-mono text-sm"
                            placeholder={`{
  "import_entries": [
    {"id": "1", "hts_code": "8471.30.01", "description": "Laptop computers", "quantity": 100, "duty_paid": 5000, "entry_date": "2024-01-15"}
  ],
  "export_records": [
    {"id": "2", "hts_code": "8471.30.01", "description": "Laptop computers", "quantity": 75, "export_date": "2024-06-01"}
  ]
}`}
                            value={reconcileJson}
                            onChange={(e) => setReconcileJson(e.target.value)}
                        />
                        <Button
                            onClick={runReconciliation}
                            disabled={loading || !reconcileJson}
                            className="w-full mt-4"
                        >
                            {loading ? 'Running...' : 'Run Reconciliation'}
                        </Button>
                    </Card>

                    {reconcileResult && (
                        <Card className="p-6">
                            <h2 className="text-lg font-semibold text-white mb-4">Reconciliation Results</h2>

                            {/* Summary */}
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                                <div className="p-4 bg-green-500/10 rounded-lg text-center">
                                    <p className="text-2xl font-bold text-green-400">{reconcileResult.summary.total_matches}</p>
                                    <p className="text-sm text-gray-400">Matches</p>
                                </div>
                                <div className="p-4 bg-blue-500/10 rounded-lg text-center">
                                    <p className="text-2xl font-bold text-blue-400">
                                        ${reconcileResult.summary.total_potential_refund.toLocaleString()}
                                    </p>
                                    <p className="text-sm text-gray-400">Potential Refund</p>
                                </div>
                                <div className="p-4 bg-purple-500/10 rounded-lg text-center">
                                    <p className="text-2xl font-bold text-purple-400">{reconcileResult.summary.direct_matches}</p>
                                    <p className="text-sm text-gray-400">Direct</p>
                                </div>
                                <div className="p-4 bg-yellow-500/10 rounded-lg text-center">
                                    <p className="text-2xl font-bold text-yellow-400">{reconcileResult.summary.substitution_matches}</p>
                                    <p className="text-sm text-gray-400">Substitution</p>
                                </div>
                            </div>

                            {/* Matches */}
                            {reconcileResult.matches.map((match, idx) => (
                                <div key={idx} className="p-4 bg-gray-800 rounded-lg mb-3">
                                    <div className="flex items-center justify-between mb-2">
                                        <span className={`px-2 py-1 text-xs rounded ${match.match_type === 'direct'
                                                ? 'bg-green-500/20 text-green-400'
                                                : 'bg-yellow-500/20 text-yellow-400'
                                            }`}>
                                            {match.match_type.toUpperCase()}
                                        </span>
                                        <span className="text-sm text-gray-400">
                                            {(match.match_confidence * 100).toFixed(0)}% confidence
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-4 text-sm">
                                        <div className="flex-1">
                                            <p className="text-gray-400">Import</p>
                                            <p className="text-white">{match.import_entry.hts_code}</p>
                                        </div>
                                        <ArrowRight className="w-4 h-4 text-gray-500" />
                                        <div className="flex-1">
                                            <p className="text-gray-400">Export</p>
                                            <p className="text-white">{match.export_record.hts_code || 'N/A'}</p>
                                        </div>
                                        <div className="text-right">
                                            <p className="text-gray-400">Refund</p>
                                            <p className="text-green-400 font-semibold">${match.potential_refund.toLocaleString()}</p>
                                        </div>
                                    </div>
                                    <p className="text-xs text-gray-500 mt-2">{match.reasoning}</p>
                                </div>
                            ))}
                        </Card>
                    )}
                </div>
            )}

            {/* Info Tab */}
            {activeTab === 'info' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <Card className="p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">Drawback Types</h3>
                        <div className="space-y-4">
                            <div className="p-4 bg-green-500/10 rounded-lg border border-green-500/30">
                                <h4 className="font-semibold text-green-400">Direct Identification (1313(a))</h4>
                                <p className="text-sm text-gray-300 mt-1">Same goods imported are exported</p>
                                <p className="text-xs text-gray-400 mt-2">Requires: Exact HTS match, export within 5 years</p>
                            </div>
                            <div className="p-4 bg-yellow-500/10 rounded-lg border border-yellow-500/30">
                                <h4 className="font-semibold text-yellow-400">Substitution (1313(b))</h4>
                                <p className="text-sm text-gray-300 mt-1">Commercially interchangeable goods exported</p>
                                <p className="text-xs text-gray-400 mt-2">Requires: Same 8-digit HTS, same kind and quality</p>
                            </div>
                            <div className="p-4 bg-blue-500/10 rounded-lg border border-blue-500/30">
                                <h4 className="font-semibold text-blue-400">Manufacturing (1313(a))</h4>
                                <p className="text-sm text-gray-300 mt-1">Imported goods used in manufacturing exports</p>
                                <p className="text-xs text-gray-400 mt-2">Requires: Proof of use in production process</p>
                            </div>
                        </div>
                    </Card>

                    <Card className="p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">Key Facts</h3>
                        <div className="space-y-3">
                            <div className="flex items-center gap-3 p-3 bg-gray-800 rounded-lg">
                                <DollarSign className="w-5 h-5 text-green-400" />
                                <div>
                                    <p className="text-white font-semibold">99% Refund Rate</p>
                                    <p className="text-xs text-gray-400">CBP retains 1% of eligible drawback</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-3 p-3 bg-gray-800 rounded-lg">
                                <Clock className="w-5 h-5 text-blue-400" />
                                <div>
                                    <p className="text-white font-semibold">5-Year Window</p>
                                    <p className="text-xs text-gray-400">Claims must be filed within 5 years of import</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-3 p-3 bg-gray-800 rounded-lg">
                                <AlertTriangle className="w-5 h-5 text-yellow-400" />
                                <div>
                                    <p className="text-white font-semibold">Exclusions</p>
                                    <p className="text-xs text-gray-400">Section 301/232 tariffs not eligible for drawback</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-3 p-3 bg-gray-800 rounded-lg">
                                <FileCheck className="w-5 h-5 text-purple-400" />
                                <div>
                                    <p className="text-white font-semibold">Required Documents</p>
                                    <p className="text-xs text-gray-400">CBP Form 7551, Entry Summary (7501), Export proof</p>
                                </div>
                            </div>
                        </div>
                    </Card>
                </div>
            )}
        </div>
    );
};
