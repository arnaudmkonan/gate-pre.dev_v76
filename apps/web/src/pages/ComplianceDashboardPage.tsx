import { useState, useEffect } from 'react';
import { Globe, FileText, AlertTriangle, CheckCircle2, Clock, BarChart3, RefreshCw } from 'lucide-react';
import { Card } from '../components/Card';
import { Input } from '../components/Input';
import { Button } from '../components/Button';

interface Scorecard {
    entity_name: string;
    grade: string;
    overall_score: number;
    total_entries_analyzed: number;
    classification_score: number;
    valuation_score: number;
    origin_score: number;
    sanctions_score: number;
    documentation_score: number;
    period_start: string;
    period_end: string;
}

interface CountryRisk {
    country: string;
    entries: number;
    total_value: number;
    risk_score: number;
}

interface DisclosurePreview {
    duty_loss: number;
    max_penalty: number;
    mitigated_penalty: number;
    savings_with_disclosure: number;
    savings_percentage: number;
    statute_expiration: string;
    days_remaining: number;
    urgency: string;
    interest_estimate: number;
    total_owed: number;
}

type Tab = 'scorecard' | 'countries' | 'disclosure' | 'statute';

const gradeColors: Record<string, string> = {
    'A': 'text-green-400 bg-green-500/20',
    'B': 'text-blue-400 bg-blue-500/20',
    'C': 'text-yellow-400 bg-yellow-500/20',
    'D': 'text-orange-400 bg-orange-500/20',
    'F': 'text-red-400 bg-red-500/20',
    'N/A': 'text-gray-400 bg-gray-500/20'
};

export const ComplianceDashboardPage = () => {
    const [activeTab, setActiveTab] = useState<Tab>('scorecard');
    const [loading, setLoading] = useState(false);

    // Scorecard state
    const [scorecard, setScorecard] = useState<Scorecard | null>(null);
    const [importerFilter, setImporterFilter] = useState('');

    // Country risk state
    const [countries, setCountries] = useState<CountryRisk[]>([]);

    // Disclosure state
    const [dutyLoss, setDutyLoss] = useState('25000');
    const [violationType, setViolationType] = useState('negligence');
    const [entryDate, setEntryDate] = useState('2024-01-15');
    const [disclosurePreview, setDisclosurePreview] = useState<DisclosurePreview | null>(null);

    // Statute state
    const [statuteDate, setStatuteDate] = useState('');
    const [statuteResult, setStatuteResult] = useState<any>(null);

    const fetchScorecard = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (importerFilter) params.set('importer', importerFilter);
            const res = await fetch(`/api/compliance/scorecard?${params}`);
            const data = await res.json();
            setScorecard(data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const fetchCountries = async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/compliance/country-risk?limit=15');
            const data = await res.json();
            setCountries(data.countries || []);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const fetchDisclosurePreview = async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/compliance/disclosure/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    duty_loss: parseFloat(dutyLoss) || 0,
                    violation_type: violationType,
                    oldest_entry_date: entryDate
                })
            });
            const data = await res.json();
            setDisclosurePreview(data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const checkStatute = async () => {
        if (!statuteDate) return;
        setLoading(true);
        try {
            const res = await fetch(`/api/compliance/statute-check?entry_date=${statuteDate}`);
            const data = await res.json();
            setStatuteResult(data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (activeTab === 'scorecard') fetchScorecard();
        else if (activeTab === 'countries') fetchCountries();
    }, [activeTab]);

    const tabs = [
        { id: 'scorecard' as Tab, label: 'Scorecard', icon: BarChart3 },
        { id: 'countries' as Tab, label: 'Country Risk', icon: Globe },
        { id: 'disclosure' as Tab, label: 'Prior Disclosure', icon: FileText },
        { id: 'statute' as Tab, label: 'Statute Check', icon: Clock },
    ];

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Compliance Dashboard</h1>
                    <p className="text-gray-400 mt-1">Scorecard, risk analysis, and prior disclosure tools</p>
                </div>
            </div>

            {/* Tab Navigation */}
            <div className="flex gap-2 border-b border-gray-700 pb-2">
                {tabs.map(({ id, label, icon: Icon }) => (
                    <button
                        key={id}
                        onClick={() => setActiveTab(id)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-t-lg transition-colors ${activeTab === id
                            ? 'bg-purple-600 text-white'
                            : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                            }`}
                    >
                        <Icon className="w-4 h-4" />
                        {label}
                    </button>
                ))}
            </div>

            {/* Scorecard Tab */}
            {activeTab === 'scorecard' && (
                <div className="space-y-6">
                    <div className="flex gap-4">
                        <Input
                            placeholder="Filter by importer name..."
                            value={importerFilter}
                            onChange={(e) => setImporterFilter(e.target.value)}
                            className="flex-1"
                        />
                        <Button onClick={fetchScorecard} disabled={loading}>
                            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                            Refresh
                        </Button>
                    </div>

                    {scorecard && (
                        <>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <Card className="p-6 text-center">
                                    <div className={`inline-block px-6 py-3 rounded-xl text-5xl font-bold ${gradeColors[scorecard.grade]}`}>
                                        {scorecard.grade}
                                    </div>
                                    <p className="text-gray-400 mt-2">Overall Grade</p>
                                </Card>
                                <Card className="p-4 text-center">
                                    <p className="text-3xl font-bold text-white">{scorecard.overall_score}</p>
                                    <p className="text-sm text-gray-400">Overall Score</p>
                                </Card>
                                <Card className="p-4 text-center">
                                    <p className="text-3xl font-bold text-blue-400">{scorecard.total_entries_analyzed}</p>
                                    <p className="text-sm text-gray-400">Entries Analyzed</p>
                                </Card>
                                <Card className="p-4 text-center">
                                    <p className="text-sm text-gray-400">{scorecard.entity_name}</p>
                                    <p className="text-xs text-gray-500">{scorecard.period_start} to {scorecard.period_end}</p>
                                </Card>
                            </div>

                            <Card className="p-6">
                                <h3 className="text-lg font-semibold text-white mb-4">Score Breakdown</h3>
                                <div className="space-y-4">
                                    {[
                                        { label: 'Classification (30%)', score: scorecard.classification_score },
                                        { label: 'Valuation (25%)', score: scorecard.valuation_score },
                                        { label: 'Sanctions (20%)', score: scorecard.sanctions_score },
                                        { label: 'Origin (15%)', score: scorecard.origin_score },
                                        { label: 'Documentation (10%)', score: scorecard.documentation_score },
                                    ].map(({ label, score }) => (
                                        <div key={label} className="flex items-center gap-4">
                                            <span className="text-gray-300 w-40">{label}</span>
                                            <div className="flex-1 bg-gray-700 rounded-full h-3">
                                                <div
                                                    className={`h-3 rounded-full ${score >= 80 ? 'bg-green-500' :
                                                        score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
                                                        }`}
                                                    style={{ width: `${score}%` }}
                                                />
                                            </div>
                                            <span className="text-white w-12 text-right">{score}</span>
                                        </div>
                                    ))}
                                </div>
                            </Card>
                        </>
                    )}
                </div>
            )}

            {/* Country Risk Tab */}
            {activeTab === 'countries' && (
                <Card className="p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                            <Globe className="w-5 h-5 text-blue-400" />
                            Country Risk Rankings
                        </h2>
                        <Button onClick={fetchCountries} disabled={loading} variant="secondary">
                            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                        </Button>
                    </div>

                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-gray-400 border-b border-gray-700">
                                    <th className="pb-2 px-2">Country</th>
                                    <th className="pb-2 px-2 text-right">Entries</th>
                                    <th className="pb-2 px-2 text-right">Value</th>
                                    <th className="pb-2 px-2 text-right">Risk Score</th>
                                </tr>
                            </thead>
                            <tbody>
                                {countries.map((c, i) => (
                                    <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/50">
                                        <td className="py-2 px-2 text-white font-semibold">{c.country}</td>
                                        <td className="py-2 px-2 text-right text-gray-300">{c.entries}</td>
                                        <td className="py-2 px-2 text-right text-gray-300">
                                            ${c.total_value.toLocaleString()}
                                        </td>
                                        <td className="py-2 px-2 text-right">
                                            <span className={`px-2 py-1 rounded ${c.risk_score >= 30 ? 'bg-red-500/20 text-red-400' :
                                                c.risk_score >= 15 ? 'bg-yellow-500/20 text-yellow-400' :
                                                    'bg-green-500/20 text-green-400'
                                                }`}>
                                                {c.risk_score}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </Card>
            )}

            {/* Prior Disclosure Tab */}
            {activeTab === 'disclosure' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <Card className="p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <FileText className="w-5 h-5 text-purple-400" />
                            Prior Disclosure Calculator
                        </h2>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Duty Loss ($)</label>
                                <Input
                                    type="number"
                                    value={dutyLoss}
                                    onChange={(e) => setDutyLoss(e.target.value)}
                                />
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Violation Type</label>
                                <select
                                    value={violationType}
                                    onChange={(e) => setViolationType(e.target.value)}
                                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                                >
                                    <option value="negligence">Negligence (2x penalty)</option>
                                    <option value="gross_negligence">Gross Negligence (4x penalty)</option>
                                    <option value="fraud">Fraud (4x + domestic value)</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Oldest Entry Date</label>
                                <Input
                                    type="date"
                                    value={entryDate}
                                    onChange={(e) => setEntryDate(e.target.value)}
                                />
                            </div>
                            <Button onClick={fetchDisclosurePreview} disabled={loading} className="w-full">
                                Calculate Disclosure Benefits
                            </Button>
                        </div>
                    </Card>

                    <Card className="p-6">
                        <h2 className="text-lg font-semibold text-white mb-4">Results</h2>

                        {!disclosurePreview ? (
                            <div className="text-center text-gray-500 py-12">
                                <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                <p>Enter disclosure details to see benefits</p>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                                    <div className="flex items-center gap-2 mb-2">
                                        <CheckCircle2 className="w-5 h-5 text-green-400" />
                                        <span className="font-semibold text-green-400">
                                            {disclosurePreview.savings_percentage}% Savings
                                        </span>
                                    </div>
                                    <p className="text-2xl font-bold text-white">
                                        ${disclosurePreview.savings_with_disclosure.toLocaleString()}
                                    </p>
                                    <p className="text-sm text-gray-400">potential penalty reduction</p>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="p-3 bg-gray-800 rounded-lg">
                                        <p className="text-sm text-gray-400">Max Penalty</p>
                                        <p className="text-lg font-bold text-red-400">
                                            ${disclosurePreview.max_penalty.toLocaleString()}
                                        </p>
                                    </div>
                                    <div className="p-3 bg-gray-800 rounded-lg">
                                        <p className="text-sm text-gray-400">With Disclosure</p>
                                        <p className="text-lg font-bold text-green-400">
                                            ${disclosurePreview.mitigated_penalty.toLocaleString()}
                                        </p>
                                    </div>
                                </div>

                                <div className={`p-3 rounded-lg ${disclosurePreview.urgency === 'high' ? 'bg-red-500/10' : 'bg-gray-800'
                                    }`}>
                                    <p className="text-sm text-gray-400">Statute Expires</p>
                                    <p className="text-white">
                                        {disclosurePreview.statute_expiration}
                                        <span className="text-gray-400 ml-2">
                                            ({disclosurePreview.days_remaining} days)
                                        </span>
                                    </p>
                                </div>
                            </div>
                        )}
                    </Card>
                </div>
            )}

            {/* Statute Check Tab */}
            {activeTab === 'statute' && (
                <div className="max-w-lg">
                    <Card className="p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Clock className="w-5 h-5 text-blue-400" />
                            Statute of Limitations Check
                        </h2>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Entry Date</label>
                                <Input
                                    type="date"
                                    value={statuteDate}
                                    onChange={(e) => setStatuteDate(e.target.value)}
                                />
                            </div>
                            <Button onClick={checkStatute} disabled={loading || !statuteDate} className="w-full">
                                Check Statute
                            </Button>
                        </div>

                        {statuteResult && (
                            <div className="mt-6 space-y-3">
                                <div className={`p-4 rounded-lg ${statuteResult.expired ? 'bg-red-500/10 border border-red-500/30' :
                                    statuteResult.urgency === 'critical' ? 'bg-orange-500/10 border border-orange-500/30' :
                                        'bg-green-500/10 border border-green-500/30'
                                    }`}>
                                    <div className="flex items-center gap-2">
                                        {statuteResult.expired ? (
                                            <AlertTriangle className="w-5 h-5 text-red-400" />
                                        ) : (
                                            <CheckCircle2 className="w-5 h-5 text-green-400" />
                                        )}
                                        <span className={`font-semibold ${statuteResult.expired ? 'text-red-400' : 'text-green-400'
                                            }`}>
                                            {statuteResult.expired ? 'EXPIRED' : statuteResult.urgency.toUpperCase()}
                                        </span>
                                    </div>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="p-3 bg-gray-800 rounded-lg">
                                        <p className="text-sm text-gray-400">Entry Date</p>
                                        <p className="text-white">{statuteResult.entry_date}</p>
                                    </div>
                                    <div className="p-3 bg-gray-800 rounded-lg">
                                        <p className="text-sm text-gray-400">Expires</p>
                                        <p className="text-white">{statuteResult.expiration_date}</p>
                                    </div>
                                </div>

                                {!statuteResult.expired && (
                                    <div className="p-3 bg-gray-800 rounded-lg text-center">
                                        <p className="text-3xl font-bold text-white">{statuteResult.days_remaining}</p>
                                        <p className="text-sm text-gray-400">days remaining</p>
                                    </div>
                                )}
                            </div>
                        )}
                    </Card>
                </div>
            )}
        </div>
    );
};
