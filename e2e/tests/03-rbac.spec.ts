import { test, expect } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ADMIN_ONLY_ROUTES } from '../helpers/routes';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const userAuth = path.join(__dirname, '../.auth/user.json');

test.describe('Role-based access', () => {
  test.use({ storageState: userAuth });

  for (const route of ADMIN_ONLY_ROUTES) {
    test(`standard user denied on ${route}`, async ({ page }) => {
      await page.goto(route);
      await expect(page.getByText('Access Denied')).toBeVisible();
    });
  }

  test('standard user can access operational ingest UI', async ({ page }) => {
    await page.goto('/ingest-ui');
    await expect(page.getByText('Document Ingestion UI')).toBeVisible();
    await expect(page.getByText('Something went wrong')).toHaveCount(0);
  });
});
