import * as Sentry from "@sentry/nextjs";

import { UNIVERSAL_NOISE, isKnownNoise } from "@/lib/sentry-noise";

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
  // UNIVERSAL only. "The operation was aborted" in a browser is a cancelled
  // navigation; on the server it is an application deadline killing real I/O —
  // an actionable timeout. The same words, opposite meanings, and a shared list
  // would delete the second (cross-family gate).
  ignoreErrors: [...UNIVERSAL_NOISE],
  beforeSend(event) {
    return isKnownNoise(event, { browser: false }) ? null : event;
  },
});
