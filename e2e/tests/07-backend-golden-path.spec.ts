import { test, expect } from '@playwright/test';
import { GateApiClient, listDemoFiles } from '../helpers/api-client';
import { DEMO_ADMIN } from '../helpers/routes';
import { SCENARIO_1_DIR } from '../helpers/demo-scenarios';

const API_BASE = process.env.E2E_API_URL || 'http://localhost:8000';

test.describe.configure({ mode: 'serial', timeout: 360_000 });

test.describe('Backend API golden path (scenario_1 demo documents)', () => {
  let token: string;
  let jobIds: string[] = [];

  test.beforeAll(async ({ request }) => {
    const api = new GateApiClient(request, API_BASE);
    const session = await api.login(DEMO_ADMIN.email, DEMO_ADMIN.password);
    token = session.token;
    expect(session.user.role).toBe('admin');
  });

  test('authenticate portal user', async () => {
    expect(token).toBeTruthy();
  });

  test('upload all scenario_1 documents', async ({ request }) => {
    const api = new GateApiClient(request, API_BASE);
    const files = listDemoFiles(SCENARIO_1_DIR);
    expect(files.length).toBeGreaterThanOrEqual(4);

    for (const filePath of files) {
      const result = await api.uploadDocument(token, filePath, 'e2e_scenario_1');
      expect(result.job_id).toBeTruthy();
      jobIds.push(result.job_id);
    }
    expect(jobIds.length).toBe(files.length);
  });

  test('wait for Celery ingest pipeline to finish', async ({ request }) => {
    const api = new GateApiClient(request, API_BASE);
    const { completed, failed } = await api.pollIngestJobs(token, jobIds, {
      timeoutMs: 300_000,
    });
    expect(completed).toBeGreaterThan(0);
    expect(failed).toBeLessThan(jobIds.length);
  });

  test('review queue and stats respond', async ({ request }) => {
    const api = new GateApiClient(request, API_BASE);
    const queue = await api.getReviewQueue(token);
    expect(Array.isArray(queue.items)).toBeTruthy();
    const statsRes = await request.get(`${API_BASE}/api/review/stats`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(statsRes.ok()).toBeTruthy();
  });

  test('shipments and assembly suggestions', async ({ request }) => {
    const api = new GateApiClient(request, API_BASE);
    const shipments = await api.getShipments(token);
    const list = shipments.shipments ?? shipments.items ?? shipments;
    expect(Array.isArray(list)).toBeTruthy();
    const suggestions = await api.getShipmentSuggestions(token);
    expect(suggestions).toBeTruthy();
  });

  test('customs entries list', async ({ request }) => {
    const api = new GateApiClient(request, API_BASE);
    const entries = await api.getEntries(token);
    const list = entries.entries ?? entries.items ?? entries;
    expect(Array.isArray(list)).toBeTruthy();
  });

  test('queue status and validation endpoint', async ({ request }) => {
    const api = new GateApiClient(request, API_BASE);
    const status = await api.getQueueStatus(token);
    expect(status).toBeTruthy();

    const validation = await api.validateNormalization(token, {
      batch_id: crypto.randomUUID(),
      records: [
        {
          record_id: 'rec-e2e-1',
          document_id: 'doc-e2e-1',
          title: 'E2E Valid Doc',
          author: 'Tester',
          content: 'Structured content for validation.',
          metadata: { source: 'playwright' },
        },
      ],
      custom_rules: null,
    });
    expect(validation.status ?? validation.valid_count).toBeDefined();
  });

  test('public leads + landing analytics', async ({ request }) => {
    const api = new GateApiClient(request, API_BASE);
    const email = `lead-${Date.now()}@gate-test.local`;
    const lead = await api.createLead({
      first_name: 'Lead',
      last_name: 'E2E',
      email,
      company: 'Broker Co',
      source: 'playwright',
    });
    expect(lead.email).toBe(email);

    const event = await api.trackLandingEvent({
      session_id: `pw_${Date.now()}`,
      event_type: 'page_view',
      page_path: '/',
    });
    expect(event.session_id).toBeTruthy();
  });

  test('admin can list captured leads', async ({ request }) => {
    const res = await request.get(`${API_BASE}/api/leads?page=1&page_size=5`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.total).toBeGreaterThan(0);
  });
});
