import { useState } from 'react';
import { Shield, AlertTriangle, CheckCircle2, Search, DollarSign, Globe, FileText, Calculator } from 'lucide-react';
import { Card } from '../components/Card';
import { Input } from '../components/Input';
import { Button } from '../components/Button';

interface ScreeningResult {
    hts_code: string;
    country_of_origin: string;
    entered_value: number;
    adcvd: any[];
    section_301: any;
    section_232: any;
    fta_eligibility: any;
    alerts: any[];
    estimated_additional_duties: number;
}

interface PenaltyResult {
    duty_loss: number;
    violation_type: string;
    base_penalty: number;
    penalty_without_disclosure: number;
    penalty_with_disclosure: number;
    savings_from_disclosure: number;
    savings_percent: number;
}

type Tab = 'screening' | 'penalty' | 'reference';

export const TradeCompliancePage = () => {
    const [activeTab, setActiveTab] = useState<Tab>('screening');
    const [loading, setLoading] = useState(false);

    // Screening state
    const [htsCode, setHtsCode] = useState('');
    const [country, setCountry] = useState('');
    const [value, setValue] = useState('');
    const [screeningResult, setScreeningResult] = useState<ScreeningResult | null>(null);

    // Penalty state
    const [dutyLoss, setDutyLoss] = useState('');
    const [violationType, setViolationType] = useState('negligence');
    const [entryValue, setEntryValue] = useState('');
    const [penaltyResult, setPenaltyResult] = useState<PenaltyResult | null>(null);

    const handleScreening = async () => {
        if (!htsCode || !country) return;
        setLoading(true);
        try {
            const res = await fetch('/api/trade-compliance/screen', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    hts_code: htsCode,
                    country_of_origin: country,
                    entered_value: parseFloat(value) || 0
                })
            });
            const data = await res.json();
            setScreeningResult(data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handlePenaltyCalculation = async () => {
        if (!dutyLoss) return;
        setLoading(true);
        try {
            const res = await fetch('/api/trade-compliance/penalty/calculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    duty_loss: parseFloat(dutyLoss),
                    violation_type: violationType,
                    entry_value: parseFloat(entryValue) || 0,
                    is_first_offense: true,
                    full_cooperation: true
                })
            });
            const data = await res.json();
            setPenaltyResult(data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const tabs = [
        { id: 'screening' as Tab, label: 'Duty Screening', icon: Shield },
        { id: 'penalty' as Tab, label: 'Penalty Calculator', icon: Calculator },
        { id: 'reference' as Tab, label: 'Reference Data', icon: FileText },
    ];

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Trade Compliance</h1>
                    <p className="text-gray-400 mt-1">Screen shipments for AD/CVD, Section 301/232, and FTA eligibility</p>
                </div>
            </div>

            {/* Tab Navigation */}
            <div className="flex gap-2 border-b border-gray-700 pb-2">
                {tabs.map(({ id, label, icon: Icon }) => (
                    <button
                        key={id}
                        onClick={() => setActiveTab(id)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-t-lg transition-colors ${activeTab === id
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                            }`}
                    >
                        <Icon className="w-4 h-4" />
                        {label}
                    </button>
                ))}
            </div>

            {/* Screening Tab */}
            {activeTab === 'screening' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Input Form */}
                    <Card className="p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Search className="w-5 h-5 text-blue-400" />
                            Comprehensive Duty Screening
                        </h2>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">HTS Code</label>
                                <Input
                                    placeholder="e.g., 7604.21.00"
                                    value={htsCode}
                                    onChange={(e) => setHtsCode(e.target.value)}
                                />
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Country of Origin</label>
                                <Input
                                    placeholder="e.g., China, Mexico, Germany"
                                    value={country}
                                    onChange={(e) => setCountry(e.target.value)}
                                />
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Entered Value (USD)</label>
                                <Input
                                    type="number"
                                    placeholder="e.g., 50000"
                                    value={value}
                                    onChange={(e) => setValue(e.target.value)}
                                />
                            </div>
                            <Button
                                onClick={handleScreening}
                                disabled={loading || !htsCode || !country}
                                className="w-full"
                            >
                                {loading ? 'Screening...' : 'Run Compliance Screen'}
                            </Button>
                        </div>

                        {/* Info Box */}
                        <div className="mt-6 p-4 bg-gray-800/50 rounded-lg border border-gray-700">
                            <h3 className="text-sm font-medium text-gray-300 mb-2">Screens Include:</h3>
                            <ul className="text-sm text-gray-400 space-y-1">
                                <li>• AD/CVD Orders (Antidumping/Countervailing Duties)</li>
                                <li>• Section 301 Tariffs (China Lists 1-4)</li>
                                <li>• Section 232 Tariffs (Steel & Aluminum)</li>
                                <li>• FTA Eligibility (USMCA, CAFTA-DR, etc.)</li>
                            </ul>
                        </div>
                    </Card>

                    {/* Results */}
                    <Card className="p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <AlertTriangle className="w-5 h-5 text-yellow-400" />
                            Screening Results
                        </h2>

                        {!screeningResult ? (
                            <div className="text-center text-gray-500 py-12">
                                <Shield className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                <p>Enter HTS code and country to run screening</p>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {/* Summary */}
                                <div className={`p-4 rounded-lg ${screeningResult.alerts.length > 0
                                        ? 'bg-red-500/10 border border-red-500/30'
                                        : 'bg-green-500/10 border border-green-500/30'
                                    }`}>
                                    <div className="flex items-center gap-2 mb-2">
                                        {screeningResult.alerts.length > 0 ? (
                                            <AlertTriangle className="w-5 h-5 text-red-400" />
                                        ) : (
                                            <CheckCircle2 className="w-5 h-5 text-green-400" />
                                        )}
                                        <span className={`font-semibold ${screeningResult.alerts.length > 0 ? 'text-red-400' : 'text-green-400'
                                            }`}>
                                            {screeningResult.alerts.length > 0
                                                ? `${screeningResult.alerts.length} Alert(s) Found`
                                                : 'No Alerts'}
                                        </span>
                                    </div>
                                    {screeningResult.estimated_additional_duties > 0 && (
                                        <p className="text-2xl font-bold text-red-400">
                                            +${screeningResult.estimated_additional_duties.toLocaleString()} Est. Additional Duties
                                        </p>
                                    )}
                                </div>

                                {/* Alerts List */}
                                {screeningResult.alerts.map((alert, idx) => (
                                    <div key={idx} className="p-3 bg-gray-800 rounded-lg">
                                        <div className="flex items-center justify-between">
                                            <span className={`px-2 py-1 text-xs rounded ${alert.severity === 'high'
                                                    ? 'bg-red-500/20 text-red-400'
                                                    : 'bg-yellow-500/20 text-yellow-400'
                                                }`}>
                                                {alert.type}
                                            </span>
                                            <span className="text-white font-semibold">
                                                {alert.rate}% Rate
                                            </span>
                                        </div>
                                        <p className="text-gray-300 mt-2">{alert.message}</p>
                                    </div>
                                ))}

                                {/* FTA Eligibility */}
                                {screeningResult.fta_eligibility?.eligible && (
                                    <div className="p-3 bg-green-500/10 rounded-lg border border-green-500/30">
                                        <div className="flex items-center gap-2">
                                            <Globe className="w-4 h-4 text-green-400" />
                                            <span className="text-green-400 font-medium">
                                                FTA Eligible: {screeningResult.fta_eligibility.agreement}
                                            </span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </Card>
                </div>
            )}

            {/* Penalty Calculator Tab */}
            {activeTab === 'penalty' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <Card className="p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Calculator className="w-5 h-5 text-purple-400" />
                            CBP Penalty Calculator (19 USC 1592)
                        </h2>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Duty Loss Amount (USD)</label>
                                <Input
                                    type="number"
                                    placeholder="e.g., 10000"
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
                                    <option value="negligence">Negligence (2x duty loss)</option>
                                    <option value="gross_negligence">Gross Negligence (4x duty loss)</option>
                                    <option value="fraud">Fraud (Entry Value)</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Entry Value (USD, for fraud)</label>
                                <Input
                                    type="number"
                                    placeholder="e.g., 100000"
                                    value={entryValue}
                                    onChange={(e) => setEntryValue(e.target.value)}
                                />
                            </div>
                            <Button
                                onClick={handlePenaltyCalculation}
                                disabled={loading || !dutyLoss}
                                className="w-full"
                            >
                                {loading ? 'Calculating...' : 'Calculate Penalty'}
                            </Button>
                        </div>

                        <div className="mt-6 p-4 bg-purple-500/10 rounded-lg border border-purple-500/30">
                            <h3 className="text-sm font-medium text-purple-300 mb-2">Prior Disclosure Benefits</h3>
                            <p className="text-sm text-gray-400">
                                Filing a voluntary prior disclosure before CBP discovers the violation can significantly reduce penalties.
                            </p>
                        </div>
                    </Card>

                    <Card className="p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <DollarSign className="w-5 h-5 text-green-400" />
                            Penalty Estimate
                        </h2>

                        {!penaltyResult ? (
                            <div className="text-center text-gray-500 py-12">
                                <Calculator className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                <p>Enter duty loss to calculate penalty</p>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="p-4 bg-red-500/10 rounded-lg text-center">
                                        <p className="text-sm text-gray-400">Without Disclosure</p>
                                        <p className="text-2xl font-bold text-red-400">
                                            ${penaltyResult.penalty_without_disclosure.toLocaleString()}
                                        </p>
                                    </div>
                                    <div className="p-4 bg-green-500/10 rounded-lg text-center">
                                        <p className="text-sm text-gray-400">With Prior Disclosure</p>
                                        <p className="text-2xl font-bold text-green-400">
                                            ${penaltyResult.penalty_with_disclosure.toLocaleString()}
                                        </p>
                                    </div>
                                </div>

                                <div className="p-4 bg-blue-500/10 rounded-lg border border-blue-500/30">
                                    <div className="flex items-center justify-between">
                                        <span className="text-gray-300">Potential Savings</span>
                                        <span className="text-xl font-bold text-blue-400">
                                            ${penaltyResult.savings_from_disclosure.toLocaleString()}
                                            <span className="text-sm ml-1">({penaltyResult.savings_percent.toFixed(1)}%)</span>
                                        </span>
                                    </div>
                                </div>

                                <div className="p-3 bg-gray-800 rounded-lg">
                                    <div className="flex justify-between text-sm">
                                        <span className="text-gray-400">Duty Loss</span>
                                        <span className="text-white">${penaltyResult.duty_loss.toLocaleString()}</span>
                                    </div>
                                    <div className="flex justify-between text-sm mt-2">
                                        <span className="text-gray-400">Violation Type</span>
                                        <span className="text-white capitalize">{penaltyResult.violation_type.replace('_', ' ')}</span>
                                    </div>
                                    <div className="flex justify-between text-sm mt-2">
                                        <span className="text-gray-400">Base Penalty</span>
                                        <span className="text-white">${penaltyResult.base_penalty.toLocaleString()}</span>
                                    </div>
                                </div>
                            </div>
                        )}
                    </Card>
                </div>
            )}

            {/* Reference Data Tab */}
            {activeTab === 'reference' && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <Card className="p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">AD/CVD Orders</h3>
                        <p className="text-3xl font-bold text-blue-400">17</p>
                        <p className="text-sm text-gray-400 mt-1">Active orders tracked</p>
                        <p className="text-xs text-gray-500 mt-3">China, Vietnam, Korea, Taiwan, India</p>
                    </Card>

                    <Card className="p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">Section 301 Lists</h3>
                        <p className="text-3xl font-bold text-yellow-400">4</p>
                        <p className="text-sm text-gray-400 mt-1">China tariff lists</p>
                        <p className="text-xs text-gray-500 mt-3">25% on Lists 1-3, 7.5% on List 4A</p>
                    </Card>

                    <Card className="p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">FTA Agreements</h3>
                        <p className="text-3xl font-bold text-green-400">4</p>
                        <p className="text-sm text-gray-400 mt-1">Active agreements</p>
                        <p className="text-xs text-gray-500 mt-3">USMCA, CAFTA-DR, Korea, Australia</p>
                    </Card>
                </div>
            )}
        </div>
    );
};
