import { test, expect } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const adminAuth = path.join(__dirname, '../.auth/admin.json');
const sampleDoc = path.join(__dirname, '../../data/demo_documents/packing_list_TECH0892.txt');

test.describe('Document ingestion golden path', () => {
  test.use({ storageState: adminAuth });

  test('uploads a sample document from ingest UI', async ({ page }) => {
    await page.goto('/ingest-ui');
    await expect(page.getByText('Story 1: Upload Documents')).toBeVisible();

    await page.locator('input[type="file"]').setInputFiles(sampleDoc);
    await page.getByRole('button', { name: 'Upload' }).click();
    await expect(page.getByText('File uploaded successfully')).toBeVisible({ timeout: 60_000 });
  });
});
