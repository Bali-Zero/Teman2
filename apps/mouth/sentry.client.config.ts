import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,

  // Performance Monitoring
  tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 1.0,

  // Session Replay (optional)
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,

  // Set environment
  environment: process.env.NODE_ENV,

  // Only enable in production or when DSN is set
  enabled: !!process.env.NEXT_PUBLIC_SENTRY_DSN,

  // Ignore common non-actionable errors
  ignoreErrors: [
    // Network errors
    'Network request failed',
    'Failed to fetch',
    'Load failed',
    // User aborted
    'AbortError',
    // Browser extensions
    /^chrome-extension:\/\//,
    /^moz-extension:\/\//,
  ],

  beforeSend(event) {
    // Don't send events in development without DSN
    if (!process.env.NEXT_PUBLIC_SENTRY_DSN) {
      return null;
    }
    return event;
  },
});
