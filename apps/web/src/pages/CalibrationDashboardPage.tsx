/**
 * Calibration Dashboard Page
 *
 * Shows model confidence vs actual accuracy - the core view for the active learning loop.
 * Identifies templates that need attention and tracks learning progress.
 */

import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

import { API_URL } from '../config/api';

interface TemplateHealth {
  template_id: string;
  template_name: string;
  document_type: string;
  total_extractions: number;
  accuracy: number;
  correction_rate: number;
  avg_model_confidence: number;
  calibration_error: number;
  health: 'excellent' | 'good' | 'needs_attention' | 'critical';
  field_count: number;
  few_shot_count: number;
  usage_count: number;
}

interface CalibrationCurvePoint {
  confidence_bucket: string;
  bucket_center: number;
  predicted_accuracy: number;
  actual_accuracy: number | null;
  sample_count: number;
}

interface DashboardData {
  period_days: number;
  total_templates: number;
  total_extractions: number;
  overall_accuracy: number;
  overall_confidence: number;
  overall_calibration_error: number;
  templates_by_health: {
    excellent: number;
    good: number;
    needs_attention: number;
    critical: number;
  };
  template_details: TemplateHealth[];
  calibration_curve: CalibrationCurvePoint[];
}

interface LearningSummary {
  period_days: number;
  corrections_logged: number;
  examples_generated: number;
  corrections_used_for_training: number;
  training_utilization: number;
  active_reviewers: number;
  correction_types: Record<string, number>;
}

interface AutoCorrectionSuggestion {
  field_name: string;
  original_pattern: string;
  suggested_correction: string;
  frequency: number;
  confidence: number;
  recommendation: 'auto_correct' | 'suggest';
}

export function CalibrationDashboardPage() {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [learningSummary, setLearningSummary] = useState<LearningSummary | null>(null);
  const [autoCorrections, setAutoCorrections] = useState<AutoCorrectionSuggestion[]>([]);
  const [templatesNeedingRetraining, setTemplatesNeedingRetraining] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [triggeringCycle, setTriggeringCycle] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [dashboardRes, summaryRes, suggestionsRes, retrainingRes] = await Promise.all([
        axios.get(`${API_URL}/api/feedback/dashboard/calibration?days=${days}`),
        axios.get(`${API_URL}/api/feedback/learning/summary?days=7`),
        axios.get(`${API_URL}/api/feedback/dashboard/auto-correction-suggestions`),
        axios.get(`${API_URL}/api/feedback/dashboard/templates-needing-retraining`),
      ]);

      setDashboardData(dashboardRes.data);
      setLearningSummary(summaryRes.data);
      setAutoCorrections(suggestionsRes.data.suggestions || []);
      setTemplatesNeedingRetraining(retrainingRes.data.templates || []);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleTriggerLearningCycle = async () => {
    setTriggeringCycle(true);
    try {
      await axios.post(`${API_URL}/api/feedback/learning/trigger-cycle`);
      alert('Learning cycle triggered successfully');
      loadData();
    } catch (err) {
      console.error('Failed to trigger learning cycle:', err);
      alert('Failed to trigger learning cycle');
    } finally {
      setTriggeringCycle(false);
    }
  };

  const getHealthColor = (health: string) => {
    switch (health) {
      case 'excellent':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'good':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'needs_attention':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'critical':
        return 'bg-red-100 text-red-800 border-red-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getHealthIcon = (health: string) => {
    switch (health) {
      case 'excellent':
        return '✓';
      case 'good':
        return '●';
      case 'needs_attention':
        return '⚠';
      case 'critical':
        return '✗';
      default:
        return '?';
    }
  };

  if (loading) {
    return (
      <div className="p-6 max-w-6xl mx-auto">
        <p className="text-gray-500">Loading calibration dashboard...</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold">Calibration Dashboard</h1>
          <p className="text-gray-600 mt-1">
            Model confidence vs actual accuracy - Active Learning Loop
          </p>
        </div>
        <div className="flex gap-3">
          <select
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value))}
            className="border rounded-lg px-3 py-2"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button
            onClick={handleTriggerLearningCycle}
            disabled={triggeringCycle}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
          >
            {triggeringCycle ? 'Running...' : 'Trigger Learning Cycle'}
          </button>
        </div>
      </div>

      {/* Overall Stats */}
      {dashboardData && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white border rounded-lg p-4">
            <p className="text-sm text-gray-600">Overall Accuracy</p>
            <p className={`text-3xl font-bold ${
              dashboardData.overall_accuracy >= 0.9 ? 'text-green-600' :
              dashboardData.overall_accuracy >= 0.7 ? 'text-yellow-600' : 'text-red-600'
            }`}>
              {(dashboardData.overall_accuracy * 100).toFixed(1)}%
            </p>
          </div>
          <div className="bg-white border rounded-lg p-4">
            <p className="text-sm text-gray-600">Model Confidence</p>
            <p className="text-3xl font-bold text-blue-600">
              {(dashboardData.overall_confidence * 100).toFixed(1)}%
            </p>
          </div>
          <div className="bg-white border rounded-lg p-4">
            <p className="text-sm text-gray-600">Calibration Error</p>
            <p className={`text-3xl font-bold ${
              Math.abs(dashboardData.overall_calibration_error) <= 0.05 ? 'text-green-600' :
              Math.abs(dashboardData.overall_calibration_error) <= 0.1 ? 'text-yellow-600' : 'text-red-600'
            }`}>
              {dashboardData.overall_calibration_error > 0 ? '+' : ''}
              {(dashboardData.overall_calibration_error * 100).toFixed(1)}%
            </p>
            <p className="text-xs text-gray-500">
              {dashboardData.overall_calibration_error > 0.05 ? 'Model is overconfident' :
               dashboardData.overall_calibration_error < -0.05 ? 'Model is underconfident' : 'Well calibrated'}
            </p>
          </div>
          <div className="bg-white border rounded-lg p-4">
            <p className="text-sm text-gray-600">Total Extractions</p>
            <p className="text-3xl font-bold text-gray-700">
              {dashboardData.total_extractions.toLocaleString()}
            </p>
          </div>
        </div>
      )}

      {/* Learning Summary (Last 7 Days) */}
      {learningSummary && (
        <div className="bg-white border rounded-lg p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Learning Activity (Last 7 Days)</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div>
              <p className="text-2xl font-bold text-blue-600">{learningSummary.corrections_logged}</p>
              <p className="text-sm text-gray-600">Corrections Logged</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-green-600">{learningSummary.examples_generated}</p>
              <p className="text-sm text-gray-600">Examples Generated</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-purple-600">
                {(learningSummary.training_utilization * 100).toFixed(0)}%
              </p>
              <p className="text-sm text-gray-600">Training Utilization</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-600">{learningSummary.active_reviewers}</p>
              <p className="text-sm text-gray-600">Active Reviewers</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-yellow-600">
                {learningSummary.corrections_used_for_training}
              </p>
              <p className="text-sm text-gray-600">Used for Training</p>
            </div>
          </div>
        </div>
      )}

      {/* Health Summary */}
      {dashboardData && (
        <div className="bg-white border rounded-lg p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Template Health Overview</h2>
          <div className="flex flex-wrap gap-4">
            <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${getHealthColor('excellent')}`}>
              <span className="text-lg">{getHealthIcon('excellent')}</span>
              <span className="font-medium">{dashboardData.templates_by_health.excellent} Excellent</span>
            </div>
            <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${getHealthColor('good')}`}>
              <span className="text-lg">{getHealthIcon('good')}</span>
              <span className="font-medium">{dashboardData.templates_by_health.good} Good</span>
            </div>
            <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${getHealthColor('needs_attention')}`}>
              <span className="text-lg">{getHealthIcon('needs_attention')}</span>
              <span className="font-medium">{dashboardData.templates_by_health.needs_attention} Needs Attention</span>
            </div>
            <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${getHealthColor('critical')}`}>
              <span className="text-lg">{getHealthIcon('critical')}</span>
              <span className="font-medium">{dashboardData.templates_by_health.critical} Critical</span>
            </div>
          </div>
        </div>
      )}

      {/* Calibration Curve Visualization */}
      {dashboardData && dashboardData.calibration_curve.length > 0 && (
        <div className="bg-white border rounded-lg p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Calibration Curve</h2>
          <p className="text-sm text-gray-600 mb-4">
            Ideal: Actual accuracy should match predicted confidence (diagonal line)
          </p>
          <div className="relative h-64 bg-gray-50 rounded-lg p-4">
            {/* Y-axis labels */}
            <div className="absolute left-0 top-0 bottom-0 w-12 flex flex-col justify-between py-2 text-xs text-gray-500">
              <span>100%</span>
              <span>75%</span>
              <span>50%</span>
              <span>25%</span>
              <span>0%</span>
            </div>

            {/* Chart area */}
            <div className="ml-12 h-full relative">
              {/* Diagonal line (perfect calibration) */}
              <div className="absolute inset-0">
                <svg className="w-full h-full">
                  <line
                    x1="0%"
                    y1="100%"
                    x2="100%"
                    y2="0%"
                    stroke="#ddd"
                    strokeWidth="2"
                    strokeDasharray="5,5"
                  />
                </svg>
              </div>

              {/* Data points */}
              <div className="absolute inset-0 flex items-end justify-around">
                {dashboardData.calibration_curve.map((point, idx) => (
                  <div key={idx} className="flex flex-col items-center">
                    {/* Actual accuracy bar */}
                    {point.actual_accuracy !== null && (
                      <div
                        className="w-8 bg-blue-500 rounded-t"
                        style={{ height: `${point.actual_accuracy * 100}%` }}
                        title={`${point.confidence_bucket}: ${(point.actual_accuracy * 100).toFixed(1)}% actual`}
                      />
                    )}
                    {/* Confidence bucket label */}
                    <span className="text-xs text-gray-500 mt-1 transform -rotate-45 origin-top-left">
                      {point.confidence_bucket}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="flex justify-center gap-6 mt-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-blue-500 rounded" />
              <span>Actual Accuracy</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-1 bg-gray-400" style={{ borderStyle: 'dashed' }} />
              <span>Perfect Calibration</span>
            </div>
          </div>
        </div>
      )}

      {/* Templates Needing Retraining */}
      {templatesNeedingRetraining.length > 0 && (
        <div className="bg-white border rounded-lg p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4 text-red-600">
            Templates Needing Attention ({templatesNeedingRetraining.length})
          </h2>
          <div className="space-y-3">
            {templatesNeedingRetraining.map((template) => (
              <div
                key={template.template_id}
                className="border border-red-200 bg-red-50 rounded-lg p-4"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-semibold">{template.template_name}</h3>
                    <p className="text-sm text-gray-600">{template.document_type}</p>
                  </div>
                  <span className="px-3 py-1 bg-red-200 text-red-800 rounded-full text-sm">
                    {(template.accuracy * 100).toFixed(1)}% accuracy
                  </span>
                </div>
                <div className="mt-2 text-sm text-gray-600">
                  {template.total_extractions} extractions |{' '}
                  {(template.correction_rate * 100).toFixed(1)}% correction rate
                </div>
                {template.suggestions?.length > 0 && (
                  <div className="mt-2">
                    <p className="text-sm font-medium text-red-700">Suggestions:</p>
                    <ul className="text-sm text-gray-600 list-disc list-inside">
                      {template.suggestions.map((s: any, idx: number) => (
                        <li key={idx}>{s.suggestion}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Auto-Correction Suggestions */}
      {autoCorrections.length > 0 && (
        <div className="bg-white border rounded-lg p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Auto-Correction Candidates</h2>
          <p className="text-sm text-gray-600 mb-4">
            These patterns have been corrected consistently and could be automated
          </p>
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
                    Suggested
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Frequency
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Confidence
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {autoCorrections.map((suggestion, idx) => (
                  <tr key={idx}>
                    <td className="px-4 py-2 text-sm font-medium text-gray-900">
                      {suggestion.field_name}
                    </td>
                    <td className="px-4 py-2 text-sm text-red-600 line-through">
                      {suggestion.original_pattern}
                    </td>
                    <td className="px-4 py-2 text-sm text-green-600">
                      {suggestion.suggested_correction}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-500">
                      {suggestion.frequency}x
                    </td>
                    <td className="px-4 py-2 text-sm">
                      <span className={`px-2 py-1 rounded ${
                        suggestion.confidence >= 0.95 ? 'bg-green-100 text-green-800' :
                        'bg-yellow-100 text-yellow-800'
                      }`}>
                        {(suggestion.confidence * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm">
                      <span className={`px-2 py-1 rounded ${
                        suggestion.recommendation === 'auto_correct'
                          ? 'bg-green-100 text-green-800'
                          : 'bg-blue-100 text-blue-800'
                      }`}>
                        {suggestion.recommendation === 'auto_correct' ? 'Auto-correct' : 'Suggest'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Template Details Table */}
      {dashboardData && dashboardData.template_details.length > 0 && (
        <div className="bg-white border rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">All Templates</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Template
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Health
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Accuracy
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Confidence
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Calibration
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Extractions
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Examples
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {dashboardData.template_details.map((template) => (
                  <tr key={template.template_id} className="hover:bg-gray-50">
                    <td className="px-4 py-2">
                      <div className="font-medium text-gray-900">{template.template_name}</div>
                      <div className="text-xs text-gray-500">{template.document_type}</div>
                    </td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${getHealthColor(template.health)}`}>
                        {template.health}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm">
                      <span className={`font-medium ${
                        template.accuracy >= 0.9 ? 'text-green-600' :
                        template.accuracy >= 0.7 ? 'text-yellow-600' : 'text-red-600'
                      }`}>
                        {(template.accuracy * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {(template.avg_model_confidence * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-2 text-sm">
                      <span className={`${
                        Math.abs(template.calibration_error) <= 0.05 ? 'text-green-600' :
                        Math.abs(template.calibration_error) <= 0.1 ? 'text-yellow-600' : 'text-red-600'
                      }`}>
                        {template.calibration_error > 0 ? '+' : ''}
                        {(template.calibration_error * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {template.total_extractions.toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {template.few_shot_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default CalibrationDashboardPage;
