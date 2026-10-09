import { test, expect } from '@playwright/test';

const LANDING_URL = process.env.E2E_LANDING_URL || 'http://localhost:8080';
const PLATFORM_URL = process.env.E2E_BASE_URL || 'http://localhost:3000';

test.describe('Commercial landing site (port 8080)', () => {
  test.use({ baseURL: LANDING_URL });

  test('homepage hero and primary sections render', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/GATES/i);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.locator('#features')).toBeVisible();
    await expect(page.locator('#documents')).toBeVisible();
    await expect(page.locator('#how-it-works')).toBeVisible();
    await expect(page.locator('#demo')).toBeVisible();
  });

  test('watch demo modal opens and closes', async ({ page }) => {
    await page.goto('/');
    await page.locator('#watch-demo-btn').click();
    await expect(page.locator('#demo-modal')).toBeVisible();
    await expect(page.locator('#demo-video')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('#demo-modal')).toBeHidden();
  });

  test('demo request form submits via proxied /api/leads', async ({ page }) => {
    const unique = `e2e-${Date.now()}@gate-test.local`;
    await page.goto('/#demo');

    await page.locator('#demo-name').fill('Playwright Tester');
    await page.locator('#demo-email').fill(unique);
    await page.locator('#demo-company').fill('E2E Customs LLC');

    const leadResponse = page.waitForResponse(
      (r) => r.url().includes('/api/leads') && r.request().method() === 'POST',
    );
    await page.locator('#demo-request-form button[type="submit"]').click();
    const res = await leadResponse;
    expect(res.status()).toBeGreaterThanOrEqual(200);
    expect(res.status()).toBeLessThan(300);

    await expect(page.locator('#demo-success')).toBeVisible();
  });

  test('register.html trial page loads', async ({ page }) => {
    await page.goto('/register.html');
    await expect(page).toHaveTitle(/Free Trial/i);
    await expect(page.locator('body')).not.toBeEmpty();
  });

  test('landing health endpoint', async ({ request }) => {
    const res = await request.get(`${LANDING_URL}/health`);
    expect(res.ok()).toBeTruthy();
    expect(await res.text()).toContain('OK');
  });
});

test.describe('Platform app vs landing (distinct UIs)', () => {
  test('platform login is separate from marketing site', async ({ page }) => {
    await page.goto(`${PLATFORM_URL}/login`);
    await expect(page.getByRole('heading', { name: 'GATE Platform' })).toBeVisible();
    await expect(page.getByText('Demo Accounts')).toBeVisible();
  });

  test('marketing site does not show platform ingest UI', async ({ page }) => {
    await page.goto(`${LANDING_URL}/`);
    await expect(page.getByText('Document Ingestion UI')).toHaveCount(0);
  });
});
