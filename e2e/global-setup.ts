import { chromium, type FullConfig } from '@playwright/test';
import { execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { DEMO_ADMIN, DEMO_USER } from './helpers/routes';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.join(__dirname, '..');
const authDir = path.join(__dirname, '.auth');

async function waitForHealth(url: string, label: string, attempts = 30) {
  for (let i = 0; i < attempts; i++) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error(`${label} not ready at ${url}`);
}

function seedDemoUsers() {
  const scriptPath = path.join(__dirname, 'scripts', 'seed_demo_users.py');
  const script = fs.readFileSync(scriptPath, 'utf8');
  execSync('docker compose exec -T api python -', {
    cwd: repoRoot,
    input: script,
    stdio: ['pipe', 'inherit', 'inherit'],
  });
}

async function saveAuthState(
  baseURL: string,
  email: string,
  password: string,
  outfile: string,
  useDemoButton: boolean,
) {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(`${baseURL}/login`);
  if (useDemoButton && email === DEMO_ADMIN.email) {
    await page.getByRole('button', { name: 'Admin User' }).click();
  } else if (useDemoButton && email === DEMO_USER.email) {
    await page.getByRole('button', { name: 'Standard User' }).click();
  } else {
    await page.locator('#email').fill(email);
    await page.locator('#password').fill(password);
  }
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL(/\/(dashboard|ingest-ui|admin\/dashboard)/, { timeout: 30_000 });
  const gotItBtn = page.getByRole('button', { name: 'Got it' });
  if (await gotItBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await gotItBtn.click();
  }
  fs.mkdirSync(authDir, { recursive: true });
  await context.storageState({ path: outfile });
  await browser.close();
}

export default async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0]?.use?.baseURL || 'http://localhost:3000';
  const apiURL = process.env.E2E_API_URL || 'http://localhost:8000';

  await waitForHealth(`${apiURL}/health`, 'API');
  await waitForHealth(`${baseURL}/login`, 'Web app');

  const landingURL = process.env.E2E_LANDING_URL || 'http://localhost:8080';
  let landingReady = false;
  try {
    const res = await fetch(`${landingURL}/health`);
    landingReady = res.ok;
  } catch {
    landingReady = false;
  }
  if (!landingReady) {
    try {
      execSync('docker compose up -d landing', { cwd: repoRoot, stdio: 'inherit' });
      await waitForHealth(`${landingURL}/health`, 'Landing page');
    } catch (e) {
      console.warn('Landing start failed; landing tests may fail:', e);
    }
  }

  try {
    execSync('docker compose exec -T api alembic upgrade head', {
      cwd: repoRoot,
      stdio: 'inherit',
    });
  } catch (e) {
    console.warn('Alembic upgrade in API container failed (continuing):', e);
  }

  try {
    seedDemoUsers();
  } catch (e) {
    console.warn('User seed fallback failed (API SEED_DEMO_USERS may have already run):', e);
  }

  await saveAuthState(
    baseURL,
    DEMO_ADMIN.email,
    DEMO_ADMIN.password,
    path.join(authDir, 'admin.json'),
    true,
  );
  await saveAuthState(
    baseURL,
    DEMO_USER.email,
    DEMO_USER.password,
    path.join(authDir, 'user.json'),
    true,
  );
}
