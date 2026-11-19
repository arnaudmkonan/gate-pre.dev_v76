/**
 * Centralized White-Label Branding & Feature Gating Configuration.
 *
 * Allows a single-tenant boutique broker copy to override branding and disable
 * demo/simulation UI surfaces via Vite environment variables without code edits.
 */
const rawBrandName = (import.meta.env.VITE_BRAND_NAME as string | undefined)?.trim();
const rawBrandSubtitle = (import.meta.env.VITE_BRAND_SUBTITLE as string | undefined)?.trim();
const rawDemoLogin = (import.meta.env.VITE_ENABLE_DEMO_LOGIN as string | undefined)?.trim().toLowerCase();
const rawAceSim = (import.meta.env.VITE_ENABLE_ACE_SIMULATION as string | undefined)?.trim().toLowerCase();
const isProdEnv =
  import.meta.env.PROD ||
  (import.meta.env.VITE_ENV as string | undefined)?.toLowerCase() === 'production';

export const BRAND_NAME = rawBrandName || 'GATE Platform';
export const BRAND_SHORT_NAME = rawBrandName ? rawBrandName.split(/\s+/)[0] : 'GATE';
export const BRAND_SUBTITLE = rawBrandSubtitle || 'Customs Brokerage';

// Enabled in local dev/E2E by default unless explicitly set to 'false'; disabled in production builds unless 'true'.
export const ENABLE_DEMO_LOGIN =
  rawDemoLogin !== undefined ? rawDemoLogin === 'true' : !isProdEnv;

export const ENABLE_ACE_SIMULATION =
  rawAceSim !== undefined ? rawAceSim === 'true' : !isProdEnv;
