import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test, expect } from '@playwright/test';
import { GateApiClient } from '../helpers/api-client';
import { DEMO_ADMIN } from '../helpers/routes';
import { QUICK_TEXT_DOCS } from '../helpers/demo-scenarios';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const adminAuth = path.join(__dirname, '../.auth/admin.json');
const repoRoot = path.join(__dirname, '../..');
const API_BASE = process.env.E2E_API_URL || 'http://localhost:8000';

test.describe.configure({ mode: 'serial', timeout: 360_000 });

test.describe('Platform UI pipeline (upload → review → operations)', () => {
  test.use({ storageState: adminAuth });

  const uploadedJobIds: string[] = [];

  test('upload one demo document through ingest UI', async ({ page, request }) => {
    await page.goto('/ingest-ui');
    const filePath = path.join(repoRoot, QUICK_TEXT_DOCS[0]);
    await page.locator('input[type="file"]').setInputFiles(filePath);
    await page.getByRole('button', { name: 'Upload' }).click();
    await expect(page.getByText('File uploaded successfully')).toBeVisible({
      timeout: 60_000,
    });

    const jobIdText = await page.locator('code').first().innerText();
    uploadedJobIds.push(jobIdText.trim());
  });

  test('poll backend until UI upload completes', async ({ request }) => {
    expect(uploadedJobIds.length).toBe(1);
    const api = new GateApiClient(request, API_BASE);
    const { token } = await api.login(DEMO_ADMIN.email, DEMO_ADMIN.password);
    const { completed } = await api.pollIngestJobs(token, uploadedJobIds, {
      timeoutMs: 240_000,
    });
    expect(completed).toBe(1);
  });

  test('review queue page shows items or empty state without crash', async ({ page, request }) => {
    await page.goto('/review');
    await expect(page.getByRole('heading', { name: 'Review Queue' })).toBeVisible();
    await expect(page.getByText('Something went wrong')).toHaveCount(0);

    const api = new GateApiClient(request, API_BASE);
    const { token } = await api.login(DEMO_ADMIN.email, DEMO_ADMIN.password);
    const queue = await api.getReviewQueue(token);
    if (queue.items?.length > 0) {
      const itemId = queue.items[0].id;
      await page.goto(`/review/${itemId}`);
      await expect(page.getByText('Something went wrong')).toHaveCount(0);
    }
  });

  test('trade compliance and shipment assembly pages load after ingest', async ({ page }) => {
    await page.goto('/trade-compliance');
    await expect(page.getByText('Something went wrong')).toHaveCount(0);

    await page.goto('/shipments/assembly');
    await expect(page.getByText('Something went wrong')).toHaveCount(0);

    await page.goto('/entries');
    await expect(page.getByText('Something went wrong')).toHaveCount(0);
  });
});
