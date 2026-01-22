/**
 * Feedback API hooks for fetching learning analytics data.
 */

import { useState, useCallback, useEffect } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000';

// Types
export interface FeedbackStats {
  total_corrections: number;
  total_examples: number;
  templates_with_feedback: number;
  avg_accuracy_improvement: number | null;
  most_corrected_fields: { field: string; corrections: number }[];
}

export interface CorrectionPattern {
  total_corrections: number;
  correction_types: Record<string, number>;
  fields_by_correction_rate: { field: string; rate: number; count: number }[];
  patterns: {
    pattern_type: string;
    description: string;
    count: number;
    automatable: boolean;
  }[];
  period_days: number;
}

export interface FieldMetric {
  id: string;
  template_id: string;
  field_name: string;
  total_extractions: number;
  correct_extractions: number;
  corrected_extractions: number;
  accuracy_rate: number | null;
  correction_rate: number | null;
  avg_model_confidence: number | null;
  confidence_calibration: number | null;
  common_corrections: Record<string, number> | null;
}

export interface TemplateAccuracyReport {
  template_id: string;
  template_name: string;
  overall_accuracy: number;
  total_extractions: number;
  total_correct: number;
  total_corrected: number;
  field_metrics: FieldMetric[];
  fields_needing_improvement: string[];
  correction_patterns: Record<string, unknown>;
  suggestions: string[];
  few_shot_count: number;
}

export interface FewShotExample {
  id: string;
  template_id: string;
  field_name: string;
  document_context: string;
  correct_value: string;
  quality_score: number;
  source_type: string;
  is_active: string;
  created_at: string;
}

export interface CorrectionLog {
  id: string;
  review_item_id: string;
  extraction_id: string;
  field_name: string;
  original_value: string;
  corrected_value: string;
  correction_type: string;
  reviewer: string;
  used_for_training: string;
  created_at: string;
}

// Hook for feedback stats
export function useFeedbackStats() {
  const [data, setData] = useState<FeedbackStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get(`${API_URL}/api/feedback/stats`);
      setData(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch feedback stats');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

// Hook for correction patterns
export function useCorrectionPatterns(templateId?: string, fieldName?: string, days: number = 30) {
  const [data, setData] = useState<CorrectionPattern | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (templateId) params.append('template_id', templateId);
      if (fieldName) params.append('field_name', fieldName);
      params.append('days', days.toString());

      const response = await axios.get(`${API_URL}/api/feedback/patterns?${params}`);
      setData(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch correction patterns');
    } finally {
      setLoading(false);
    }
  }, [templateId, fieldName, days]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

// Hook for template accuracy report
export function useTemplateAccuracyReport(templateId: string | null) {
  const [data, setData] = useState<TemplateAccuracyReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!templateId) return;
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get(`${API_URL}/api/feedback/template/${templateId}/report`);
      setData(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch accuracy report');
    } finally {
      setLoading(false);
    }
  }, [templateId]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

// Hook for template field metrics
export function useTemplateFieldMetrics(templateId: string | null) {
  const [data, setData] = useState<{ fields: FieldMetric[]; field_count: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!templateId) return;
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get(`${API_URL}/api/feedback/template/${templateId}/metrics`);
      setData(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch field metrics');
    } finally {
      setLoading(false);
    }
  }, [templateId]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

// Hook for few-shot examples
export function useFewShotExamples(templateId: string | null, fieldName?: string) {
  const [data, setData] = useState<{ examples: FewShotExample[]; count: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!templateId) return;
    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (fieldName) params.append('field_name', fieldName);

      const response = await axios.get(
        `${API_URL}/api/feedback/template/${templateId}/examples?${params}`
      );
      setData(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch examples');
    } finally {
      setLoading(false);
    }
  }, [templateId, fieldName]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

// Hook for corrections list
export function useCorrections(filters: {
  templateId?: string;
  fieldName?: string;
  correctionType?: string;
  limit?: number;
  offset?: number;
} = {}) {
  const [data, setData] = useState<{ corrections: CorrectionLog[]; count: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (filters.templateId) params.append('template_id', filters.templateId);
      if (filters.fieldName) params.append('field_name', filters.fieldName);
      if (filters.correctionType) params.append('correction_type', filters.correctionType);
      if (filters.limit) params.append('limit', filters.limit.toString());
      if (filters.offset) params.append('offset', filters.offset.toString());

      const response = await axios.get(`${API_URL}/api/feedback/corrections?${params}`);
      setData(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch corrections');
    } finally {
      setLoading(false);
    }
  }, [filters.templateId, filters.fieldName, filters.correctionType, filters.limit, filters.offset]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

// Mutation: Recalibrate confidence threshold
export function useRecalibrateThreshold() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recalibrate = useCallback(async (templateId: string) => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.post(`${API_URL}/api/feedback/template/${templateId}/recalibrate`);
      return response.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to recalibrate';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { recalibrate, loading, error };
}

// Mutation: Deactivate example
export function useDeactivateExample() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const deactivate = useCallback(async (templateId: string, exampleId: string) => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.delete(
        `${API_URL}/api/feedback/template/${templateId}/examples/${exampleId}`
      );
      return response.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to deactivate example';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { deactivate, loading, error };
}

// Mutation: Sync few-shot examples
export function useSyncExamples() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sync = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.post(`${API_URL}/api/feedback/sync-examples`);
      return response.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to sync examples';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { sync, loading, error };
}
