import { useState, useEffect } from 'react';
import { Package, Users, FileText, Search, RefreshCw, Box, GitMerge, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { Card } from '../components/Card';
import { Input } from '../components/Input';
import { Button } from '../components/Button';
import {
    dataFabricApi,
    Party,
    Product,
    Shipment,
    Invoice,
    DuplicateCandidate,
    GoldenRecordStats
} from '../lib/api/data-fabric';

type Tab = 'shipments' | 'invoices' | 'parties' | 'products' | 'duplicates';

export const DataFabricPage = () => {
    const [activeTab, setActiveTab] = useState<Tab>('shipments');
    const [loading, setLoading] = useState(false);
    const [search, setSearch] = useState('');

    const [parties, setParties] = useState<Party[]>([]);
    const [products, setProducts] = useState<Product[]>([]);
    const [shipments, setShipments] = useState<Shipment[]>([]);
    const [invoices, setInvoices] = useState<Invoice[]>([]);

    // Golden Records state
    const [duplicates, setDuplicates] = useState<DuplicateCandidate[]>([]);
    const [stats, setStats] = useState<GoldenRecordStats | null>(null);
    const [merging, setMerging] = useState<string | null>(null);
    const [mergeSuccess, setMergeSuccess] = useState<string | null>(null);

    const fetchData = async () => {
        setLoading(true);
        try {
            if (activeTab === 'parties') {
                const res = await dataFabricApi.listParties(1, 20, search);
                setParties(res.items);
            } else if (activeTab === 'products') {
                const res = await dataFabricApi.listProducts(1, 20, search);
                setProducts(res.items);
            } else if (activeTab === 'shipments') {
                const res = await dataFabricApi.listShipments(1, 20);
                setShipments(res.items);
            } else if (activeTab === 'invoices') {
                const res = await dataFabricApi.listInvoices(1, 20);
                setInvoices(res.items);
            } else if (activeTab === 'duplicates') {
                const [partyDupes, productDupes, statsData] = await Promise.all([
                    dataFabricApi.findPartyDuplicates(25, 0.80),
                    dataFabricApi.findProductDuplicates(25, 0.80),
                    dataFabricApi.getGoldenRecordStats()
                ]);
                setDuplicates([...partyDupes, ...productDupes]);
                setStats(statsData);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [activeTab, search]);

    const handleMerge = async (candidate: DuplicateCandidate) => {
        const pairKey = `${candidate.entity_1.id}-${candidate.entity_2.id}`;
        setMerging(pairKey);
        setMergeSuccess(null);

        try {
            if (candidate.entity_type === 'party') {
                await dataFabricApi.mergeParties(candidate.entity_1.id, candidate.entity_2.id);
            } else {
                await dataFabricApi.mergeProducts(candidate.entity_1.id, candidate.entity_2.id);
            }
            setMergeSuccess(pairKey);
            // Remove from list
            setDuplicates(prev => prev.filter(d =>
                !(d.entity_1.id === candidate.entity_1.id && d.entity_2.id === candidate.entity_2.id)
            ));
            // Refresh stats
            const newStats = await dataFabricApi.getGoldenRecordStats();
            setStats(newStats);
        } catch (e) {
            console.error(e);
        } finally {
            setMerging(null);
        }
    };

    const tabs = [
        { id: 'shipments', label: 'Shipments', icon: Package },
        { id: 'invoices', label: 'Invoices', icon: FileText },
        { id: 'parties', label: 'Parties', icon: Users },
        { id: 'products', label: 'Products', icon: Box },
        { id: 'duplicates', label: 'Duplicates', icon: GitMerge },
    ];

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Data Fabric</h1>
                    <p className="text-gray-500">Explore Silver and Gold layer entities</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" onClick={fetchData} disabled={loading}>
                        <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex space-x-1 bg-white p-1 rounded-lg border border-gray-200 w-fit">
                {tabs.map((tab) => {
                    const Icon = tab.icon;
                    const isActive = activeTab === tab.id;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => {
                                setActiveTab(tab.id as Tab);
                                setSearch('');
                            }}
                            className={`
                        flex items-center px-4 py-2 rounded-md text-sm font-medium transition-colors
                        ${isActive ? 'bg-blue-50 text-blue-700 shadow-sm' : 'text-gray-600 hover:bg-gray-50'}
                    `}
                        >
                            <Icon className="w-4 h-4 mr-2" />
                            {tab.label}
                            {tab.id === 'duplicates' && duplicates.length > 0 && (
                                <span className="ml-2 bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full text-xs">
                                    {duplicates.length}
                                </span>
                            )}
                        </button>
                    )
                })}
            </div>

            {/* Search Bar */}
            {(activeTab === 'parties' || activeTab === 'products') && (
                <Card className="p-4">
                    <div className="relative max-w-md">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
                        <Input
                            placeholder={`Search ${activeTab}...`}
                            className="pl-10"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                </Card>
            )}

            {/* Golden Record Stats */}
            {activeTab === 'duplicates' && stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card className="p-4">
                        <div className="text-sm text-gray-500">Total Parties</div>
                        <div className="text-2xl font-bold text-gray-900">{stats.parties.total}</div>
                        <div className="text-xs text-green-600">{stats.parties.unique} unique</div>
                    </Card>
                    <Card className="p-4">
                        <div className="text-sm text-gray-500">Merged Parties</div>
                        <div className="text-2xl font-bold text-blue-600">{stats.parties.merged}</div>
                    </Card>
                    <Card className="p-4">
                        <div className="text-sm text-gray-500">Total Products</div>
                        <div className="text-2xl font-bold text-gray-900">{stats.products.total}</div>
                        <div className="text-xs text-green-600">{stats.products.unique} unique</div>
                    </Card>
                    <Card className="p-4">
                        <div className="text-sm text-gray-500">Merged Products</div>
                        <div className="text-2xl font-bold text-blue-600">{stats.products.merged}</div>
                    </Card>
                </div>
            )}

            {/* Duplicates View */}
            {activeTab === 'duplicates' && (
                <Card>
                    <div className="p-4 border-b border-gray-200">
                        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                            <AlertTriangle className="w-5 h-5 text-amber-500" />
                            Potential Duplicates ({duplicates.length})
                        </h3>
                        <p className="text-sm text-gray-500 mt-1">
                            Review and merge duplicate entities to maintain clean Golden Records.
                        </p>
                    </div>
                    <div className="divide-y divide-gray-100">
                        {duplicates.map((candidate, idx) => {
                            const pairKey = `${candidate.entity_1.id}-${candidate.entity_2.id}`;
                            const isMerging = merging === pairKey;
                            const isSuccess = mergeSuccess === pairKey;

                            return (
                                <div key={idx} className="p-4 hover:bg-gray-50">
                                    <div className="flex items-start justify-between">
                                        <div className="flex-1 grid grid-cols-2 gap-6">
                                            {/* Entity 1 */}
                                            <div className="bg-blue-50 rounded-lg p-3">
                                                <div className="text-xs text-blue-600 font-medium mb-1">
                                                    {candidate.entity_type === 'party' ? 'Party' : 'Product'} A
                                                </div>
                                                <div className="font-semibold text-gray-900">
                                                    {candidate.entity_1.canonical_name || candidate.entity_1.description}
                                                </div>
                                                {candidate.entity_1.party_type && (
                                                    <div className="text-xs text-gray-500 mt-1">Type: {candidate.entity_1.party_type}</div>
                                                )}
                                                {candidate.entity_1.tax_id && (
                                                    <div className="text-xs text-gray-500">Tax ID: {candidate.entity_1.tax_id}</div>
                                                )}
                                                {candidate.entity_1.hs_code && (
                                                    <div className="text-xs text-gray-500">HS: {candidate.entity_1.hs_code}</div>
                                                )}
                                            </div>

                                            {/* Entity 2 */}
                                            <div className="bg-amber-50 rounded-lg p-3">
                                                <div className="text-xs text-amber-600 font-medium mb-1">
                                                    {candidate.entity_type === 'party' ? 'Party' : 'Product'} B
                                                </div>
                                                <div className="font-semibold text-gray-900">
                                                    {candidate.entity_2.canonical_name || candidate.entity_2.description}
                                                </div>
                                                {candidate.entity_2.party_type && (
                                                    <div className="text-xs text-gray-500 mt-1">Type: {candidate.entity_2.party_type}</div>
                                                )}
                                                {candidate.entity_2.tax_id && (
                                                    <div className="text-xs text-gray-500">Tax ID: {candidate.entity_2.tax_id}</div>
                                                )}
                                                {candidate.entity_2.hs_code && (
                                                    <div className="text-xs text-gray-500">HS: {candidate.entity_2.hs_code}</div>
                                                )}
                                            </div>
                                        </div>

                                        {/* Actions */}
                                        <div className="ml-4 flex flex-col items-end gap-2">
                                            <div className="text-sm">
                                                <span className="text-gray-500">Similarity:</span>
                                                <span className={`ml-1 font-semibold ${candidate.similarity >= 0.95 ? 'text-red-600' : 'text-amber-600'}`}>
                                                    {(candidate.similarity * 100).toFixed(0)}%
                                                </span>
                                            </div>
                                            <div className="text-xs text-gray-400">{candidate.match_reason.replace(/_/g, ' ')}</div>

                                            <Button
                                                variant="primary"
                                                onClick={() => handleMerge(candidate)}
                                                disabled={isMerging}
                                                className="mt-2"
                                            >
                                                {isMerging ? (
                                                    <>
                                                        <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
                                                        Merging...
                                                    </>
                                                ) : isSuccess ? (
                                                    <>
                                                        <CheckCircle2 className="w-4 h-4 mr-1" />
                                                        Merged!
                                                    </>
                                                ) : (
                                                    <>
                                                        <GitMerge className="w-4 h-4 mr-1" />
                                                        Merge (Keep A)
                                                    </>
                                                )}
                                            </Button>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}

                        {!loading && duplicates.length === 0 && (
                            <div className="p-12 text-center text-gray-500">
                                <CheckCircle2 className="w-12 h-12 mx-auto mb-3 text-green-400" />
                                <div className="font-medium">No duplicates found!</div>
                                <div className="text-sm mt-1">Your data is clean.</div>
                            </div>
                        )}
                    </div>
                </Card>
            )}

            {/* Data Table (for other tabs) */}
            {activeTab !== 'duplicates' && (
                <Card>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm text-left">
                            <thead className="bg-gray-50 text-gray-700 font-medium border-b border-gray-200">
                                {activeTab === 'shipments' && (
                                    <tr>
                                        <th className="px-6 py-3">Reference</th>
                                        <th className="px-6 py-3">Origin</th>
                                        <th className="px-6 py-3">Destination</th>
                                        <th className="px-6 py-3">Shipper</th>
                                        <th className="px-6 py-3">Consignee</th>
                                        <th className="px-6 py-3">Status</th>
                                    </tr>
                                )}
                                {activeTab === 'invoices' && (
                                    <tr>
                                        <th className="px-6 py-3">Invoice #</th>
                                        <th className="px-6 py-3">Date</th>
                                        <th className="px-6 py-3">Vendor</th>
                                        <th className="px-6 py-3">Buyer</th>
                                        <th className="px-6 py-3">Total</th>
                                    </tr>
                                )}
                                {activeTab === 'parties' && (
                                    <tr>
                                        <th className="px-6 py-3">Canonical Name</th>
                                        <th className="px-6 py-3">Type</th>
                                        <th className="px-6 py-3">Tax ID</th>
                                        <th className="px-6 py-3">Addresses</th>
                                    </tr>
                                )}
                                {activeTab === 'products' && (
                                    <tr>
                                        <th className="px-6 py-3">Description</th>
                                        <th className="px-6 py-3">HS Code</th>
                                        <th className="px-6 py-3">Origin Country</th>
                                        <th className="px-6 py-3">Unit</th>
                                    </tr>
                                )}
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {activeTab === 'shipments' && shipments.map(item => (
                                    <tr key={item.id} className="hover:bg-gray-50">
                                        <td className="px-6 py-3 font-medium text-gray-900">{item.reference_num || '-'}</td>
                                        <td className="px-6 py-3 text-gray-600">{item.origin || '-'}</td>
                                        <td className="px-6 py-3 text-gray-600">{item.destination || '-'}</td>
                                        <td className="px-6 py-3 text-gray-600">{item.shipper?.canonical_name || '-'}</td>
                                        <td className="px-6 py-3 text-gray-600">{item.consignee?.canonical_name || '-'}</td>
                                        <td className="px-6 py-3">
                                            <span className="bg-blue-100 text-blue-700 px-2 py-1 rounded text-xs">{item.status || 'Draft'}</span>
                                        </td>
                                    </tr>
                                ))}
                                {activeTab === 'invoices' && invoices.map(item => (
                                    <tr key={item.id} className="hover:bg-gray-50">
                                        <td className="px-6 py-3 font-medium text-gray-900">{item.invoice_num}</td>
                                        <td className="px-6 py-3 text-gray-600">{item.invoice_date ? new Date(item.invoice_date).toLocaleDateString() : '-'}</td>
                                        <td className="px-6 py-3 text-gray-600">{item.vendor?.canonical_name || '-'}</td>
                                        <td className="px-6 py-3 text-gray-600">{item.buyer?.canonical_name || '-'}</td>
                                        <td className="px-6 py-3 font-medium">{item.total_amount ? `$${item.total_amount.toFixed(2)}` : '-'}</td>
                                    </tr>
                                ))}
                                {activeTab === 'parties' && parties.map(item => (
                                    <tr key={item.id} className="hover:bg-gray-50">
                                        <td className="px-6 py-3 font-medium text-gray-900">{item.canonical_name}</td>
                                        <td className="px-6 py-3 text-gray-600 capitalize">{item.party_type}</td>
                                        <td className="px-6 py-3 text-gray-600">{item.tax_id || '-'}</td>
                                        <td className="px-6 py-3 text-gray-600">{item.addresses?.length || 0} locations</td>
                                    </tr>
                                ))}
                                {activeTab === 'products' && products.map(item => (
                                    <tr key={item.id} className="hover:bg-gray-50">
                                        <td className="px-6 py-3 font-medium text-gray-900">{item.description}</td>
                                        <td className="px-6 py-3 text-gray-600">{item.hs_code || '-'}</td>
                                        <td className="px-6 py-3 text-gray-600">{item.country_of_origin || '-'}</td>
                                        <td className="px-6 py-3 text-gray-600">{item.unit_of_measure || '-'}</td>
                                    </tr>
                                ))}

                                {!loading && (
                                    (activeTab === 'shipments' && shipments.length === 0) ||
                                    (activeTab === 'invoices' && invoices.length === 0) ||
                                    (activeTab === 'parties' && parties.length === 0) ||
                                    (activeTab === 'products' && products.length === 0)
                                ) && (
                                        <tr>
                                            <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                                                No records found in this view.
                                            </td>
                                        </tr>
                                    )}

                                {loading && (
                                    <tr>
                                        <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                                            Loading data...
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </Card>
            )}
        </div>
    );
};
