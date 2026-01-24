import { useState, useEffect } from 'react';
import { Upload, FileText, Search, BarChart3, RefreshCw, Download, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Card } from '../components/Card';
import { Input } from '../components/Input';
import { Button } from '../components/Button';

interface ACEEntry {
    id: string;
    entry_number: string;
    entry_date: string | null;
    importer_name: string;
    port_name: string;
    hts_code: string;
    description: string;
    country_of_origin: string;
    entered_value: number | null;
    duty_amount: number | null;
}

interface Statistics {
    total_entries: number;
    unique_entry_numbers: number;
    total_value: number;
    total_duty: number;
    avg_duty_rate: number;
    importers: string[];
    ports: string[];
    countries: string[];
    date_range: { earliest: string | null; latest: string | null };
}

interface ImportResult {
    success: boolean;
    batch_id: string;
    entries_parsed: number;
    entries_saved: number;
    total_value: number;
    total_duty: number;
    errors: string[];
    warnings: string[];
}

type Tab = 'upload' | 'browse' | 'statistics';

export const ACEImportPage = () => {
    const [activeTab, setActiveTab] = useState<Tab>('upload');
    const [loading, setLoading] = useState(false);

    // Upload state
    const [csvContent, setCsvContent] = useState('');
    const [importResult, setImportResult] = useState<ImportResult | null>(null);

    // Browse state
    const [entries, setEntries] = useState<ACEEntry[]>([]);
    const [total, setTotal] = useState(0);
    const [searchImporter, setSearchImporter] = useState('');
    const [searchHts, setSearchHts] = useState('');

    // Statistics state
    const [stats, setStats] = useState<Statistics | null>(null);

    const loadSampleData = async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/ace/import/sample', { method: 'POST' });
            const data = await res.json();
            setImportResult(data);
            // Refresh entries and stats
            await fetchEntries();
            await fetchStatistics();
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const importCSV = async () => {
        if (!csvContent.trim()) return;
        setLoading(true);
        try {
            const res = await fetch('/api/ace/import/csv', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ csv_content: csvContent })
            });
            const data = await res.json();
            setImportResult(data);
            if (data.success) {
                await fetchEntries();
                await fetchStatistics();
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const fetchEntries = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (searchImporter) params.set('importer', searchImporter);
            if (searchHts) params.set('hts_code', searchHts);
            params.set('limit', '50');

            const res = await fetch(`/api/ace/entries?${params}`);
            const data = await res.json();
            setEntries(data.entries || []);
            setTotal(data.total || 0);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const fetchStatistics = async () => {
        try {
            const res = await fetch('/api/ace/statistics');
            const data = await res.json();
            setStats(data);
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => {
        if (activeTab === 'browse') {
            fetchEntries();
        } else if (activeTab === 'statistics') {
            fetchStatistics();
        }
    }, [activeTab]);

    const tabs = [
        { id: 'upload' as Tab, label: 'Import Data', icon: Upload },
        { id: 'browse' as Tab, label: 'Browse Entries', icon: FileText },
        { id: 'statistics' as Tab, label: 'Statistics', icon: BarChart3 },
    ];

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">ACE Import</h1>
                    <p className="text-gray-400 mt-1">Import and manage CBP entry data from ACE exports</p>
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

            {/* Upload Tab */}
            {activeTab === 'upload' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <Card className="p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Upload className="w-5 h-5 text-purple-400" />
                            Import ACE Data
                        </h2>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Paste CSV Content</label>
                                <textarea
                                    className="w-full h-40 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white font-mono text-sm"
                                    placeholder="entry_number,entry_date,importer_name,hts_code,entered_value..."
                                    value={csvContent}
                                    onChange={(e) => setCsvContent(e.target.value)}
                                />
                            </div>

                            <div className="flex gap-2">
                                <Button
                                    onClick={importCSV}
                                    disabled={loading || !csvContent.trim()}
                                    className="flex-1"
                                >
                                    {loading ? 'Importing...' : 'Import CSV'}
                                </Button>
                                <Button
                                    onClick={loadSampleData}
                                    disabled={loading}
                                    variant="secondary"
                                >
                                    <Download className="w-4 h-4 mr-2" />
                                    Load Sample
                                </Button>
                            </div>
                        </div>

                        <div className="mt-6 p-4 bg-gray-800/50 rounded-lg border border-gray-700">
                            <h3 className="text-sm font-medium text-gray-300 mb-2">Supported Columns</h3>
                            <p className="text-xs text-gray-400">
                                entry_number, entry_date, importer_name, port_name, hts_code, description,
                                country_of_origin, quantity, unit, entered_value, duty_rate, duty_amount
                            </p>
                        </div>
                    </Card>

                    <Card className="p-6">
                        <h2 className="text-lg font-semibold text-white mb-4">Import Result</h2>

                        {!importResult ? (
                            <div className="text-center text-gray-500 py-12">
                                <Upload className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                <p>Import CSV data or load sample to see results</p>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                <div className={`p-4 rounded-lg ${importResult.success
                                        ? 'bg-green-500/10 border border-green-500/30'
                                        : 'bg-red-500/10 border border-red-500/30'
                                    }`}>
                                    <div className="flex items-center gap-2 mb-2">
                                        {importResult.success ? (
                                            <CheckCircle2 className="w-5 h-5 text-green-400" />
                                        ) : (
                                            <AlertTriangle className="w-5 h-5 text-red-400" />
                                        )}
                                        <span className={`font-semibold ${importResult.success ? 'text-green-400' : 'text-red-400'
                                            }`}>
                                            {importResult.success ? 'Import Successful' : 'Import Failed'}
                                        </span>
                                    </div>
                                    <p className="text-sm text-gray-400">Batch: {importResult.batch_id}</p>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="p-3 bg-gray-800 rounded-lg text-center">
                                        <p className="text-2xl font-bold text-white">{importResult.entries_saved}</p>
                                        <p className="text-xs text-gray-400">Entries Saved</p>
                                    </div>
                                    <div className="p-3 bg-gray-800 rounded-lg text-center">
                                        <p className="text-2xl font-bold text-blue-400">
                                            ${importResult.total_value.toLocaleString()}
                                        </p>
                                        <p className="text-xs text-gray-400">Total Value</p>
                                    </div>
                                </div>

                                {importResult.warnings.length > 0 && (
                                    <div className="p-3 bg-yellow-500/10 rounded-lg">
                                        <p className="text-sm text-yellow-400">Warnings:</p>
                                        {importResult.warnings.map((w, i) => (
                                            <p key={i} className="text-xs text-gray-400">{w}</p>
                                        ))}
                                    </div>
                                )}

                                {importResult.errors.length > 0 && (
                                    <div className="p-3 bg-red-500/10 rounded-lg">
                                        <p className="text-sm text-red-400">Errors:</p>
                                        {importResult.errors.map((e, i) => (
                                            <p key={i} className="text-xs text-gray-400">{e}</p>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </Card>
                </div>
            )}

            {/* Browse Tab */}
            {activeTab === 'browse' && (
                <Card className="p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                            <FileText className="w-5 h-5 text-blue-400" />
                            ACE Entries ({total} total)
                        </h2>
                        <Button onClick={fetchEntries} disabled={loading} variant="secondary">
                            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                            Refresh
                        </Button>
                    </div>

                    <div className="flex gap-4 mb-4">
                        <Input
                            placeholder="Filter by importer..."
                            value={searchImporter}
                            onChange={(e) => setSearchImporter(e.target.value)}
                            className="flex-1"
                        />
                        <Input
                            placeholder="Filter by HTS..."
                            value={searchHts}
                            onChange={(e) => setSearchHts(e.target.value)}
                            className="w-40"
                        />
                        <Button onClick={fetchEntries}>
                            <Search className="w-4 h-4" />
                        </Button>
                    </div>

                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-gray-400 border-b border-gray-700">
                                    <th className="pb-2 px-2">Entry #</th>
                                    <th className="pb-2 px-2">Date</th>
                                    <th className="pb-2 px-2">Importer</th>
                                    <th className="pb-2 px-2">HTS</th>
                                    <th className="pb-2 px-2">Country</th>
                                    <th className="pb-2 px-2 text-right">Value</th>
                                    <th className="pb-2 px-2 text-right">Duty</th>
                                </tr>
                            </thead>
                            <tbody>
                                {entries.map((entry) => (
                                    <tr key={entry.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                                        <td className="py-2 px-2 text-white font-mono">{entry.entry_number}</td>
                                        <td className="py-2 px-2 text-gray-300">
                                            {entry.entry_date?.split('T')[0] || '-'}
                                        </td>
                                        <td className="py-2 px-2 text-gray-300">{entry.importer_name}</td>
                                        <td className="py-2 px-2 text-blue-400 font-mono">{entry.hts_code}</td>
                                        <td className="py-2 px-2 text-gray-300">{entry.country_of_origin}</td>
                                        <td className="py-2 px-2 text-right text-white">
                                            ${entry.entered_value?.toLocaleString() || '-'}
                                        </td>
                                        <td className="py-2 px-2 text-right text-yellow-400">
                                            ${entry.duty_amount?.toLocaleString() || '-'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </Card>
            )}

            {/* Statistics Tab */}
            {activeTab === 'statistics' && (
                <div className="space-y-6">
                    {!stats ? (
                        <Card className="p-6 text-center text-gray-500">
                            <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-50" />
                            <p>Loading statistics...</p>
                        </Card>
                    ) : (
                        <>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <Card className="p-4 text-center">
                                    <p className="text-3xl font-bold text-white">{stats.total_entries}</p>
                                    <p className="text-sm text-gray-400">Total Entries</p>
                                </Card>
                                <Card className="p-4 text-center">
                                    <p className="text-3xl font-bold text-purple-400">{stats.unique_entry_numbers}</p>
                                    <p className="text-sm text-gray-400">Unique Entry Numbers</p>
                                </Card>
                                <Card className="p-4 text-center">
                                    <p className="text-3xl font-bold text-blue-400">
                                        ${(stats.total_value / 1000).toFixed(0)}K
                                    </p>
                                    <p className="text-sm text-gray-400">Total Value</p>
                                </Card>
                                <Card className="p-4 text-center">
                                    <p className="text-3xl font-bold text-yellow-400">
                                        ${(stats.total_duty / 1000).toFixed(0)}K
                                    </p>
                                    <p className="text-sm text-gray-400">Total Duty</p>
                                </Card>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                <Card className="p-4">
                                    <h3 className="text-sm font-semibold text-gray-400 mb-2">Importers</h3>
                                    <div className="space-y-1">
                                        {stats.importers.slice(0, 5).map((imp, i) => (
                                            <p key={i} className="text-sm text-white truncate">{imp}</p>
                                        ))}
                                    </div>
                                </Card>
                                <Card className="p-4">
                                    <h3 className="text-sm font-semibold text-gray-400 mb-2">Countries</h3>
                                    <div className="flex flex-wrap gap-1">
                                        {stats.countries.map((c, i) => (
                                            <span key={i} className="px-2 py-1 bg-gray-800 rounded text-xs text-white">{c}</span>
                                        ))}
                                    </div>
                                </Card>
                                <Card className="p-4">
                                    <h3 className="text-sm font-semibold text-gray-400 mb-2">Date Range</h3>
                                    <p className="text-sm text-white">
                                        {stats.date_range.earliest?.split('T')[0] || '-'} to {stats.date_range.latest?.split('T')[0] || '-'}
                                    </p>
                                    <p className="text-xs text-gray-400 mt-2">Avg Duty Rate: {stats.avg_duty_rate}%</p>
                                </Card>
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    );
};
