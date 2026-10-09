import { expect, type Page } from '@playwright/test';

/** Fails if the React error boundary or login redirect appears unexpectedly. */
export async function expectAuthenticatedPageLoaded(page: Page, path: string) {
  await expect(page).not.toHaveURL(/\/login$/);
  await expect(page.getByText('Something went wrong')).toHaveCount(0);
  await expect(page.getByText('Access Denied')).toHaveCount(0);
  // Basic sanity: body has content
  const text = await page.locator('body').innerText();
  expect(text.length).toBeGreaterThan(20);
  expect(page.url()).toContain(path.split('?')[0]);
}
