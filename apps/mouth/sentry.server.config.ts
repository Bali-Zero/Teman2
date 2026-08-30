import * as Sentry from "@sentry/nextjs";

import { IGNORE_ERRORS, isKnownNoise } from "@/lib/sentry-noise";

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
  // 28% of this org's production errors were dropped for quota over 7 days
  // (measured 2026-08-28). A dropped event is indistinguishable from one that
  // never happened, and which ones get dropped is decided by arrival order.
  // See src/lib/sentry-noise.ts for what is filtered and, more importantly,
  // what is deliberately not.
  ignoreErrors: [...IGNORE_ERRORS],
  beforeSend(event) {
    return isKnownNoise(event) ? null : event;
  },
});
