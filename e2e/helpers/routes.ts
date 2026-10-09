/** Static app routes (no dynamic path segments). */
export const PUBLIC_ROUTES = [
  '/login',
  '/forgot-password',
  '/reset-password',
  '/register',
] as const;

/** Routes any authenticated user can open (smoke: page loads without app crash). */
export const AUTHENTICATED_ROUTES = [
  '/ingest-ui',
  '/upload',
  '/ingest',
  '/metadata',
  '/review',
  '/templates',
  '/feedback',
  '/batch-upload',
  '/calibration',
  '/data-fabric',
  '/trade-compliance',
  '/drawback',
  '/ace-import',
  '/compliance-dashboard',
  '/entries',
  '/entries/new',
  '/shipments/assembly',
  '/tools/duty-calculator',
  '/clients',
  '/clients/new',
  '/agents',
  '/admin/queue',
  '/admin/audit',
  '/admin/queue-metrics',
  '/admin/dlq',
  '/admin/batch-schedules',
  '/admin/routing-dashboard',
  '/admin/extraction-status',
  '/admin/dashboard',
  '/admin/monitoring',
  '/admin/alerts',
  '/admin/dlq-management',
  '/admin/metrics',
] as const;

/** Admin-only routes (require admin role). */
export const ADMIN_ONLY_ROUTES = [
  '/admin/storage-config',
  '/admin/queue-config',
  '/admin/vector-store-config',
  '/admin/organizations',
  '/admin/roles',
  '/admin/retry-policy',
  '/settings/ace',
  '/settings/platform',
  '/admin/leads',
  '/admin/embeddings',
] as const;

export const DEMO_ADMIN = {
  email: 'admin@example.com',
  password: 'adminpassword',
} as const;

export const DEMO_USER = {
  email: 'demo@example.com',
  password: 'demopassword',
} as const;
