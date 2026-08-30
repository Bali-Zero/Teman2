import * as Sentry from "@sentry/nextjs";

import { UNIVERSAL_NOISE, isKnownNoise } from "@/lib/sentry-noise";

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
  // 28% of this org's production errors were dropped for quota over 7 days
  // (measured 2026-08-28). A dropped event is indistinguishable from one that
  // never happened, and which ones get dropped is decided by arrival order.
  // See src/lib/sentry-noise.ts for what is filtered and, more importantly,
  // what is deliberately not.
  // UNIVERSAL only. "The operation was aborted" in a browser is a cancelled
  // navigation; on the server it is an application deadline killing real I/O —
  // an actionable timeout. The same words, opposite meanings, and a shared list
  // would delete the second (cross-family gate).
  ignoreErrors: [...UNIVERSAL_NOISE],
  beforeSend(event) {
    return isKnownNoise(event, { browser: false }) ? null : event;
  },
});
