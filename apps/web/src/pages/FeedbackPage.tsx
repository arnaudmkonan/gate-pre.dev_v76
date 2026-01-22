/**
 * Feedback Analytics Page
 *
 * Displays learning analytics from human corrections:
 * - Overall system stats
 * - Correction patterns
 * - Template accuracy reports
 * - Few-shot examples generated
 */

import { useState, useEffect } from 'react';
import axios from 'axios';
import {
  useFeedbackStats,
  useCorrectionPatterns,
  useTemplateAccuracyReport,
  useFewShotExamples,
  useCorrections,
  useRecalibrateThreshold,
  useSyncExamples,
} from '../hooks/useFeedback';

const API_URL = 'http://localhost:8000';

interface Template {
  id: string;
  name: string;
  document_type: string;
}

export function FeedbackPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  // Hooks
  const { data: stats, loading: statsLoading } = useFeedbackStats();
  const { data: patterns, loading: patternsLoading } = useCorrectionPatterns(
    selectedTemplateId || undefined,
    undefined,
    days
  );
  const { data: report, loading: reportLoading, refetch: refetchReport } = useTemplateAccuracyReport(
    selectedTemplateId
  );
  const { data: examples, loading: examplesLoading } = useFewShotExamples(selectedTemplateId);
  const { data: corrections, loading: correctionsLoading } = useCorrections({
    templateId: selectedTemplateId || undefined,
    limit: 20,
  });
  const { recalibrate, loading: recalibrating } = useRecalibrateThreshold();
  const { sync, loading: syncing } = useSyncExamples();

  // Load templates list
  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/templates`);
        setTemplates(response.data.templates || []);
      } catch (err) {
        console.error('Failed to load templates:', err);
      }
    };
    loadTemplates();
  }, []);

  const handleRecalibrate = async () => {
    if (!selectedTemplateId) return;
    try {
      await recalibrate(selectedTemplateId);
      refetchReport();
    } catch (err) {
      console.error('Recalibration failed:', err);
    }
  };

  const handleSyncExamples = async () => {
    try {
      await sync();
      alert('Few-shot examples synced to templates');
    } catch (err) {
      console.error('Sync failed:', err);
    }
  };

  // Stat Card component
  const StatCard = ({
    title,
    value,
    subtitle,
    color = 'blue',
  }: {
    title: string;
    value: string | number;
    subtitle?: string;
    color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple';
  }) => {
    const colorClasses = {
      blue: 'text-blue-600 bg-blue-50',
      green: 'text-green-600 bg-green-50',
      yellow: 'text-yellow-600 bg-yellow-50',
      red: 'text-red-600 bg-red-50',
      purple: 'text-purple-600 bg-purple-50',
    };

    return (
      <div className="bg-white border rounded-lg p-4">
        <p className="text-sm text-gray-600 mb-1">{title}</p>
        <p className={`text-2xl font-bold ${colorClasses[color].split(' ')[0]}`}>{value}</p>
        {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
      </div>
    );
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold">Feedback Analytics</h1>
          <p className="text-gray-600 mt-1">
            Learn from human corrections to improve extraction accuracy
          </p>
        </div>
        <button
          onClick={handleSyncExamples}
          disabled={syncing}
          className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
        >
          {syncing ? 'Syncing...' : 'Sync Examples'}
        </button>
      </div>

      {/* Overall Stats */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold mb-4">System Overview</h2>
        {statsLoading ? (
          <p className="text-gray-500">Loading stats...</p>
        ) : stats ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              title="Total Corrections"
              value={stats.total_corrections}
              subtitle="Human-reviewed fixes"
              color="blue"
            />
            <StatCard
              title="Learning Examples"
              value={stats.total_examples}
              subtitle="Active few-shot examples"
              color="green"
            />
            <StatCard
              title="Templates with Feedback"
              value={stats.templates_with_feedback}
              subtitle="Templates using learned patterns"
              color="purple"
            />
            <StatCard
              title="Most Corrected Field"
              value={stats.most_corrected_fields?.[0]?.field || 'N/A'}
              subtitle={
                stats.most_corrected_fields?.[0]
                  ? `${stats.most_corrected_fields[0].corrections} corrections`
                  : ''
              }
              color="yellow"
            />
          </div>
        ) : (
          <p className="text-gray-500">No feedback data available yet</p>
        )}
      </div>

      {/* Template Selector and Time Range */}
      <div className="bg-white border rounded-lg p-4 mb-8">
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Filter by Template
            </label>
            <select
              value={selectedTemplateId || ''}
              onChange={(e) => setSelectedTemplateId(e.target.value || null)}
              className="w-full border rounded px-3 py-2"
            >
              <option value="">All Templates</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} ({t.document_type})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Time Period</label>
            <select
              value={days}
              onChange={(e) => setDays(parseInt(e.target.value))}
              className="border rounded px-3 py-2"
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
              <option value={365}>Last year</option>
            </select>
          </div>
          {selectedTemplateId && (
            <button
              onClick={handleRecalibrate}
              disabled={recalibrating}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {recalibrating ? 'Recalibrating...' : 'Recalibrate Threshold'}
            </button>
          )}
        </div>
      </div>

      {/* Template Accuracy Report (when template selected) */}
      {selectedTemplateId && (
        <div className="bg-white border rounded-lg p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Template Accuracy Report</h2>
          {reportLoading ? (
            <p className="text-gray-500">Loading report...</p>
          ) : report ? (
            <div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <StatCard
                  title="Overall Accuracy"
                  value={`${(report.overall_accuracy * 100).toFixed(1)}%`}
                  color={report.overall_accuracy > 0.9 ? 'green' : report.overall_accuracy > 0.7 ? 'yellow' : 'red'}
                />
                <StatCard
                  title="Total Extractions"
                  value={report.total_extractions}
                  color="blue"
                />
                <StatCard
                  title="Correct (No edits)"
                  value={report.total_correct}
                  color="green"
                />
                <StatCard
                  title="Corrected by Humans"
                  value={report.total_corrected}
                  color="yellow"
                />
              </div>

              {/* Fields needing improvement */}
              {report.fields_needing_improvement.length > 0 && (
                <div className="mb-6">
                  <h3 className="text-lg font-medium mb-2">Fields Needing Improvement</h3>
                  <div className="flex flex-wrap gap-2">
                    {report.fields_needing_improvement.map((field) => (
                      <span
                        key={field}
                        className="px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full text-sm"
                      >
                        {field}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Suggestions */}
              {report.suggestions.length > 0 && (
                <div className="mb-6">
                  <h3 className="text-lg font-medium mb-2">Improvement Suggestions</h3>
                  <ul className="list-disc list-inside space-y-1">
                    {report.suggestions.map((suggestion, idx) => (
                      <li key={idx} className="text-gray-700">
                        {suggestion}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Field metrics table */}
              {report.field_metrics.length > 0 && (
                <div>
                  <h3 className="text-lg font-medium mb-2">Field-Level Metrics</h3>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                            Field
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                            Accuracy
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                            Correction Rate
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                            Avg Confidence
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                            Extractions
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {report.field_metrics.map((metric) => (
                          <tr key={metric.field_name}>
                            <td className="px-4 py-2 text-sm font-medium text-gray-900">
                              {metric.field_name}
                            </td>
                            <td className="px-4 py-2 text-sm">
                              <span
                                className={`px-2 py-1 rounded ${
                                  (metric.accuracy_rate || 0) > 0.9
                                    ? 'bg-green-100 text-green-800'
                                    : (metric.accuracy_rate || 0) > 0.7
                                    ? 'bg-yellow-100 text-yellow-800'
                                    : 'bg-red-100 text-red-800'
                                }`}
                              >
                                {((metric.accuracy_rate || 0) * 100).toFixed(1)}%
                              </span>
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-500">
                              {((metric.correction_rate || 0) * 100).toFixed(1)}%
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-500">
                              {((metric.avg_model_confidence || 0) * 100).toFixed(0)}%
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-500">
                              {metric.total_extractions}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-gray-500">No accuracy data available for this template</p>
          )}
        </div>
      )}

      {/* Correction Patterns */}
      <div className="bg-white border rounded-lg p-6 mb-8">
        <h2 className="text-xl font-semibold mb-4">Correction Patterns</h2>
        {patternsLoading ? (
          <p className="text-gray-500">Analyzing patterns...</p>
        ) : patterns ? (
          <div>
            {/* Correction type breakdown */}
            {Object.keys(patterns.correction_types || {}).length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-medium mb-2">Correction Types</h3>
                <div className="flex flex-wrap gap-3">
                  {Object.entries(patterns.correction_types).map(([type, count]) => (
                    <div
                      key={type}
                      className="px-4 py-2 bg-gray-100 rounded-lg flex items-center gap-2"
                    >
                      <span className="font-medium capitalize">{type.replace('_', ' ')}</span>
                      <span className="text-gray-600 text-sm">({count})</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Fields by correction rate */}
            {patterns.fields_by_correction_rate?.length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-medium mb-2">Fields by Correction Rate</h3>
                <div className="space-y-2">
                  {patterns.fields_by_correction_rate.slice(0, 5).map((item) => (
                    <div key={item.field} className="flex items-center gap-3">
                      <span className="w-32 text-sm font-medium truncate">{item.field}</span>
                      <div className="flex-1 h-4 bg-gray-200 rounded overflow-hidden">
                        <div
                          className="h-full bg-yellow-500"
                          style={{ width: `${Math.min(item.rate * 100, 100)}%` }}
                        />
                      </div>
                      <span className="text-sm text-gray-600 w-20 text-right">
                        {(item.rate * 100).toFixed(1)}% ({item.count})
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Automatable patterns */}
            {patterns.patterns?.filter((p) => p.automatable).length > 0 && (
              <div>
                <h3 className="text-lg font-medium mb-2">Automatable Patterns Detected</h3>
                <div className="space-y-2">
                  {patterns.patterns
                    .filter((p) => p.automatable)
                    .map((pattern, idx) => (
                      <div
                        key={idx}
                        className="p-3 bg-green-50 border border-green-200 rounded-lg"
                      >
                        <div className="flex justify-between items-start">
                          <div>
                            <span className="font-medium text-green-800">
                              {pattern.pattern_type}
                            </span>
                            <p className="text-sm text-green-700 mt-1">{pattern.description}</p>
                          </div>
                          <span className="text-sm text-green-600">{pattern.count} occurrences</span>
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-gray-500">No correction patterns detected yet</p>
        )}
      </div>

      {/* Few-Shot Examples (when template selected) */}
      {selectedTemplateId && (
        <div className="bg-white border rounded-lg p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Learning Examples</h2>
          {examplesLoading ? (
            <p className="text-gray-500">Loading examples...</p>
          ) : examples && examples.examples.length > 0 ? (
            <div className="space-y-3">
              {examples.examples.slice(0, 5).map((example) => (
                <div
                  key={example.id}
                  className="p-4 bg-gray-50 border rounded-lg"
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className="px-2 py-1 bg-purple-100 text-purple-800 text-xs rounded">
                      {example.field_name}
                    </span>
                    <span className="text-xs text-gray-500">
                      Quality: {(example.quality_score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-gray-500 text-xs mb-1">Context</p>
                      <p className="text-gray-700 line-clamp-2">{example.document_context}</p>
                    </div>
                    <div>
                      <p className="text-gray-500 text-xs mb-1">Correct Value</p>
                      <p className="text-gray-900 font-medium">{example.correct_value}</p>
                    </div>
                  </div>
                </div>
              ))}
              {examples.count > 5 && (
                <p className="text-sm text-gray-500 text-center">
                  And {examples.count - 5} more examples...
                </p>
              )}
            </div>
          ) : (
            <p className="text-gray-500">
              No learning examples generated yet. Examples are created automatically when reviewers
              make high-quality corrections.
            </p>
          )}
        </div>
      )}

      {/* Recent Corrections */}
      <div className="bg-white border rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">Recent Corrections</h2>
        {correctionsLoading ? (
          <p className="text-gray-500">Loading corrections...</p>
        ) : corrections && corrections.corrections.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Field
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Original
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Corrected
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Type
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Reviewer
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Used
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {corrections.corrections.map((correction) => (
                  <tr key={correction.id}>
                    <td className="px-4 py-2 text-sm font-medium text-gray-900">
                      {correction.field_name}
                    </td>
                    <td className="px-4 py-2 text-sm text-red-600 line-through max-w-[150px] truncate">
                      {correction.original_value || '(empty)'}
                    </td>
                    <td className="px-4 py-2 text-sm text-green-600 max-w-[150px] truncate">
                      {correction.corrected_value || '(empty)'}
                    </td>
                    <td className="px-4 py-2 text-sm">
                      <span className="px-2 py-1 bg-gray-100 rounded text-xs capitalize">
                        {correction.correction_type?.replace('_', ' ') || 'unknown'}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-500">{correction.reviewer}</td>
                    <td className="px-4 py-2 text-sm">
                      {correction.used_for_training === 'used' ? (
                        <span className="text-green-600">Yes</span>
                      ) : (
                        <span className="text-gray-400">No</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-500">No corrections recorded yet</p>
        )}
      </div>
    </div>
  );
}

export default FeedbackPage;
