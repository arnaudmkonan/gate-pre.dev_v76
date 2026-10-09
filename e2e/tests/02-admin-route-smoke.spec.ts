import { test } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ADMIN_ONLY_ROUTES, AUTHENTICATED_ROUTES } from '../helpers/routes';
import { expectAuthenticatedPageLoaded } from '../helpers/assertions';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const adminAuth = path.join(__dirname, '../.auth/admin.json');

test.describe('Admin authenticated route smoke', () => {
  test.use({ storageState: adminAuth });

  for (const route of AUTHENTICATED_ROUTES) {
    test(`loads ${route}`, async ({ page }) => {
      await page.goto(route);
      await page.waitForLoadState('networkidle');
      await expectAuthenticatedPageLoaded(page, route);
    });
  }

  for (const route of ADMIN_ONLY_ROUTES) {
    test(`admin can load ${route}`, async ({ page }) => {
      await page.goto(route);
      await page.waitForLoadState('networkidle');
      await expectAuthenticatedPageLoaded(page, route);
    });
  }
});
