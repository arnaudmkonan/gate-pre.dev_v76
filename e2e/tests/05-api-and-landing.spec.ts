import { test, expect } from '@playwright/test';

const API_BASE = process.env.E2E_API_URL || 'http://localhost:8000';
const LANDING_URL = process.env.E2E_LANDING_URL || 'http://localhost:8080';

test.describe('API & landing page', () => {
  test('API health returns ok', async ({ request }) => {
    const res = await request.get(`${API_BASE}/health`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.status ?? body).toBeTruthy();
  });

  test('OpenAPI docs are served', async ({ request }) => {
    const res = await request.get(`${API_BASE}/docs`);
    expect(res.status()).toBe(200);
  });

  test('portal login API accepts demo admin', async ({ request }) => {
    const res = await request.post(`${API_BASE}/api/portal/login`, {
      data: { email: 'admin@example.com', password: 'adminpassword' },
    });
    expect(res.ok()).toBeTruthy();
    const json = await res.json();
    expect(json.session_token).toBeTruthy();
    expect(json.user.email).toBe('admin@example.com');
  });

  test('landing page loads', async ({ page }) => {
    const res = await page.goto(LANDING_URL);
    expect(res?.ok()).toBeTruthy();
    await expect(page.locator('body')).not.toBeEmpty();
  });
});
