import { test, expect } from '@playwright/test';
import { PUBLIC_ROUTES } from '../helpers/routes';

test.describe('Public pages & authentication', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('login page renders and demo shortcuts work', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'GATE Platform' })).toBeVisible();
    await page.getByRole('button', { name: 'Admin User' }).click();
    await expect(page.locator('#email')).toHaveValue('admin@example.com');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.waitForURL(/\/ingest-ui/);
  });

  test('unauthenticated user is redirected to login from protected route', async ({ page }) => {
    await page.goto('/entries');
    await expect(page).toHaveURL(/\/login/);
  });

  test('forgot password page loads', async ({ page }) => {
    await page.goto('/forgot-password');
    await expect(page.locator('body')).not.toBeEmpty();
    await expect(page.getByText('Something went wrong')).toHaveCount(0);
  });

  test('register without invitation shows disabled message', async ({ page }) => {
    await page.goto('/register');
    await expect(page.getByText(/invitation|Public registration is disabled/i)).toBeVisible();
  });

  for (const route of PUBLIC_ROUTES) {
    test(`public route ${route} does not crash`, async ({ page }) => {
      await page.goto(route);
      await expect(page.getByText('Something went wrong')).toHaveCount(0);
    });
  }
});
