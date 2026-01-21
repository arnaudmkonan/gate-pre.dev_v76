/**
 * Sentry error tracking initialization for React frontend.
 * Captures uncaught exceptions, performance monitoring, and user interactions.
 */

import * as Sentry from "@sentry/react";
import { BrowserTracing } from "@sentry/tracing";

/**
 * Initialize Sentry for the React application.
 * Sets up error tracking, performance monitoring, and PII redaction.
 */
export function initSentry(): void {
  // @ts-ignore - Vite env typing
  const sentryDSN = import.meta.env?.VITE_SENTRY_DSN;
  // @ts-ignore - Vite env typing
  const environment = (import.meta.env?.VITE_ENV || "development") as string;
  // @ts-ignore - Vite env typing
  const traceSampleRateStr = import.meta.env?.VITE_SENTRY_TRACES_SAMPLE_RATE || "0.1";
  const traceSampleRate = parseFloat(traceSampleRateStr as string);

  // Skip initialization if DSN is not configured
  if (!sentryDSN) {
    console.info("Sentry DSN not configured, skipping frontend initialization");
    return;
  }

  Sentry.init({
    dsn: sentryDSN,
    environment,
    tracesSampleRate: traceSampleRate,
    integrations: [
      new BrowserTracing({
        // Set sampling rate for transactions
        tracingOrigins: ["localhost", /^\//],
      }),
    ],
    // Redact PII before sending to Sentry
    beforeSend(event) {
      return redactPII(event);
    },
    // Filter what data we capture
    denyUrls: [
      // Browser extensions
      /extensions\//i,
      /^chrome:\/\//i,
    ],
    allowUrls: [
      // Allow same origin
      /^\/(?!\/)/,
    ],
  });

  console.info(`Sentry initialized for environment: ${environment}`);
}

/**
 * Redact PII (Personally Identifiable Information) from Sentry events.
 * Filters out: emails, phone numbers, credit cards, API keys, passwords, SSN
 */
function redactPII(
  event: Sentry.Event
): Sentry.Event | null {
  const piiPatterns: Array<[RegExp, string]> = [
    // Email addresses
    [/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/gi, "[EMAIL]"],
    // Phone numbers (US format)
    [/\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b/g, "[PHONE]"],
    // Credit card numbers
    [/\b(?:\d{4}[-\s]?){3}\d{4}\b/g, "[CARD]"],
    // Passwords and API keys
    [/(password|passwd|secret|api[_-]?key|token|authorization)[:\s=]+[^\s,}\"]+/gi, "$1=[REDACTED]"],
    // Social Security Numbers
    [/\b\d{3}-\d{2}-\d{4}\b/g, "[SSN]"],
  ];

  function redactString(str: string): string {
    if (typeof str !== "string") return str;

    let redacted = str;
    for (const [pattern, replacement] of piiPatterns) {
      redacted = redacted.replace(pattern, replacement);
    }
    return redacted;
  }

  function redactObject(obj: any): any {
    if (typeof obj === "string") {
      return redactString(obj);
    }
    if (Array.isArray(obj)) {
      return obj.map(redactObject);
    }
    if (obj !== null && typeof obj === "object") {
      return Object.keys(obj).reduce((acc, key) => {
        acc[key] = redactObject(obj[key]);
        return acc;
      }, {} as any);
    }
    return obj;
  }

  // Redact exception messages
  if (event.exception && event.exception.values) {
    for (const exc of event.exception.values) {
      if (exc.value) {
        exc.value = redactString(exc.value);
      }
      if (exc.stacktrace && exc.stacktrace.frames) {
        for (const frame of exc.stacktrace.frames) {
          if (frame.vars) {
            frame.vars = redactObject(frame.vars);
          }
        }
      }
    }
  }

  // Redact request data
  if (event.request) {
    if (event.request.url) {
      event.request.url = redactString(event.request.url);
    }
    // @ts-ignore - cookies is optional on request
    if (event.request.cookies) {
      // @ts-ignore - setting cookies to string
      event.request.cookies = "[REDACTED]";
    }
    if (event.request.headers && typeof event.request.headers === "object") {
      // Redact auth headers
      for (const headerKey of ["authorization", "cookie", "x-api-key"]) {
        if (event.request.headers[headerKey]) {
          event.request.headers[headerKey] = "[REDACTED]";
        }
      }
    }
  }

  // Redact user context
  if (event.user) {
    if (event.user.email) {
      event.user.email = "[EMAIL]";
    }
    if (event.user.ip_address) {
      event.user.ip_address = "[IP]";
    }
  }

  // Redact breadcrumbs
  if (event.breadcrumbs) {
    for (const breadcrumb of event.breadcrumbs) {
      if (breadcrumb.message) {
        breadcrumb.message = redactString(breadcrumb.message);
      }
      if (breadcrumb.data) {
        breadcrumb.data = redactObject(breadcrumb.data);
      }
    }
  }

  // Redact extra context
  if (event.extra) {
    event.extra = redactObject(event.extra);
  }

  // Redact tags
  if (event.tags) {
    const redactedTags: { [key: string]: string } = {};
    for (const [key, value] of Object.entries(event.tags)) {
      if (typeof value === "string") {
        redactedTags[key] = redactString(value);
      } else {
        redactedTags[key] = String(value);
      }
    }
    event.tags = redactedTags;
  }

  return event;
}

/**
 * Capture an exception with additional context.
 */
export function captureException(
  error: Error,
  context?: Record<string, any>
): string {
  return Sentry.captureException(error, {
    extra: context,
  });
}

/**
 * Capture a message with additional context.
 */
export function captureMessage(
  message: string,
  level: "fatal" | "error" | "warning" | "info" | "debug" = "info",
  context?: Record<string, any>
): string {
  return Sentry.captureMessage(message, {
    level,
    extra: context,
  });
}

/**
 * Set user context for error tracking.
 */
export function setUserContext(userId: string, email?: string): void {
  Sentry.setUser({
    id: userId,
    email: email ? "[EMAIL]" : undefined, // Redact email
  });
}

/**
 * Clear user context when logging out.
 */
export function clearUserContext(): void {
  Sentry.setUser(null);
}

/**
 * Add breadcrumb for tracking user actions.
 */
export function addBreadcrumb(
  message: string,
  category: string = "user-action",
  level: "fatal" | "error" | "warning" | "info" | "debug" = "info"
): void {
  Sentry.addBreadcrumb({
    message,
    category,
    level,
    timestamp: Date.now() / 1000,
  });
}

export default Sentry;
