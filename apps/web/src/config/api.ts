/**
 * API Configuration
 * 
 * Centralized API URL configuration.
 * Uses empty string for relative paths (works with nginx proxy in Docker).
 *
 * API_BASE    — unversioned (backward compat, will be sunset 2026-12-31)
 * API_V1      — versioned (preferred for new integrations)
 */

export const API_URL = import.meta.env.VITE_API_URL || '';
export const API_BASE = API_URL; // Alias for compatibility

/** Versioned API base — use for new endpoints */
export const API_V1 = `${API_URL}/api/v1`;

/** Current API version */
export const API_VERSION = 'v1';
