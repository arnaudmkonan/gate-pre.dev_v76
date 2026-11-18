import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test, expect } from '@playwright/test';
import { GateApiClient } from '../helpers/api-client';
import { DEMO_ADMIN } from '../helpers/routes';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const adminAuth = path.join(__dirname, '../.auth/admin.json');
const API_BASE = process.env.E2E_API_URL || 'http://localhost:8000';

test.describe.configure({ mode: 'serial', timeout: 120_000 });

async function dismissOnboardingIfVisible(page: import('@playwright/test').Page) {
  const gotItBtn = page.getByRole('button', { name: 'Got it' });
  if (await gotItBtn.isVisible({ timeout: 2500 }).catch(() => false)) {
    await gotItBtn.click();
  }
}

test.describe('Beta MVP Broker UI Workflows (Review -> Shipment -> 7501 Prep -> Official Entry)', () => {
  test.use({ storageState: adminAuth });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('gates_onboarding_complete', 'true');
    });
  });

  let shipmentId = '';
  let entryId = '';

  test('1. Review Item Detail renders upgraded DocumentViewer (Original / Extracted Text / Download)', async ({
    page,
    request,
  }) => {
    const api = new GateApiClient(request, API_BASE);
    const { token } = await api.login(DEMO_ADMIN.email, DEMO_ADMIN.password);
    const queue = await api.getReviewQueue(token);
    expect(queue.items?.length).toBeGreaterThan(0);

    const itemId = queue.items[0].id;
    await page.goto(`/review/${itemId}`);
    await dismissOnboardingIfVisible(page);
    await expect(page.getByText('Something went wrong')).toHaveCount(0);

    // Verify new DocumentViewer toolbar buttons exist
    await expect(page.getByRole('button', { name: 'Original' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Extracted Text' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Download' })).toBeVisible();

    // Toggle between Original and Extracted Text views
    await page.getByRole('button', { name: 'Extracted Text' }).click();
    await page.getByRole('button', { name: 'Original' }).click();
    await expect(page.getByText('Something went wrong')).toHaveCount(0);
  });

  test('2. Shipment Detail: Generate ISF (10+2), Request Missing Doc modal, and navigate to Prepare 7501', async ({
    page,
    request,
  }) => {
    const api = new GateApiClient(request, API_BASE);
    const { token } = await api.login(DEMO_ADMIN.email, DEMO_ADMIN.password);

    const shipRes = await request.get(`${API_BASE}/api/shipments?limit=5`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(shipRes.ok()).toBeTruthy();
    const shipments = await shipRes.json();
    const list = Array.isArray(shipments) ? shipments : shipments.shipments || shipments.items || [];
    expect(list.length).toBeGreaterThan(0);
    shipmentId = list[0].id;

    await page.goto(`/shipments/${shipmentId}`);
    await dismissOnboardingIfVisible(page);
    await expect(page.getByText('Something went wrong')).toHaveCount(0);

    // Verify new action buttons on Shipment Detail
    await expect(page.getByRole('button', { name: /Generate ISF \(10\+2\)/i })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Prepare 7501' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Create Official Entry' }).first()).toBeVisible();

    // Click Generate ISF (10+2) and verify ISF card appears
    await page.getByRole('button', { name: /Generate ISF \(10\+2\)/i }).click();
    await expect(page.getByText('ISF (10+2 Importer Security Filing) Prepared')).toBeVisible();

    // Click Request Doc and test Request Missing Document modal
    await page.getByRole('button', { name: 'Request Doc' }).click();
    await expect(page.getByText('Request Missing Document from Importer')).toBeVisible();
    await page.getByRole('button', { name: 'Send Request' }).click();
    await expect(page.getByText(/Requested commercial invoice from importer/i)).toBeVisible();

    // Navigate to Prepare 7501
    await page.getByRole('button', { name: 'Prepare 7501' }).click();
    await expect(page).toHaveURL(new RegExp(`/entries/prep/${shipmentId}`));
  });

  test('3. Entry Preparation (Form 7501): Verify PDF/Excel exports and Save as Official Entry handoff', async ({
    page,
  }) => {
    await page.goto(`/entries/prep/${shipmentId}`);
    await dismissOnboardingIfVisible(page);
    await expect(page.getByText('CBP Form 7501')).toBeVisible();

    await expect(page.getByRole('button', { name: '7501 PDF' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Excel' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Export ACE' })).toBeVisible();
    const saveBtn = page.getByRole('button', { name: 'Save as Official Entry' });
    await expect(saveBtn).toBeVisible();

    // Click Save as Official Entry -> should navigate to /entries/:entryId
    await saveBtn.click();
    await page.waitForURL(/\/entries\/[0-9a-f-]{36}$/, { timeout: 30_000 });
    const url = page.url();
    entryId = url.split('/entries/')[1];
    expect(entryId).toBeTruthy();
  });

  test('4. Entry Detail: Verify PGA & Compliance Check, Export buttons, and Edit Entry Header modal', async ({
    page,
  }) => {
    await page.goto(`/entries/${entryId}`);
    await dismissOnboardingIfVisible(page);
    await expect(page.getByText('Something went wrong')).toHaveCount(0);

    // Verify Export buttons in Actions panel
    await expect(page.getByRole('button', { name: 'Export Form 7501 (PDF)' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Export Summary (Excel)' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Export CargoWise (XML)' })).toBeVisible();

    // Verify PGA & Compliance Check card
    await expect(page.getByText('PGA & Compliance Check')).toBeVisible();

    // Open Edit Entry Modal, update Broker Notes, and save
    await page.getByRole('button', { name: 'Edit Entry' }).click();
    await expect(page.getByText('Edit CBP Form 7501 Entry Header')).toBeVisible();

    const uniqueNote = `Playwright UI Verified ${Date.now()}`;
    const notesTextarea = page.locator('form textarea');
    await notesTextarea.fill(uniqueNote);
    await page.getByRole('button', { name: 'Save Changes' }).click();

    // Modal closes and updated note is visible on the Entry Detail page
    await expect(page.getByText('Edit CBP Form 7501 Entry Header')).toHaveCount(0);
    await expect(page.getByText(uniqueNote)).toBeVisible();
  });
});
