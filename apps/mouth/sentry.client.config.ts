import * as Sentry from "@sentry/nextjs";

import { IGNORE_ERRORS, isKnownNoise } from "@/lib/sentry-noise";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,
  integrations: [
    Sentry.replayIntegration({
      maskAllText: true,
      blockAllMedia: true,
    }),
  ],
  ignoreErrors: [...IGNORE_ERRORS],
  beforeSend(event) {
    // Non inviare errori in development
    if (process.env.NODE_ENV === "development") {
      return null;
    }
    // 28% of this org's production errors were dropped for quota over 7 days
    // (measured 2026-08-28), and which ones get dropped is decided by arrival
    // order rather than importance. src/lib/sentry-noise.ts says what is
    // filtered and — the load-bearing half — what deliberately is not: 401/403
    // stays, because muting it is how #5096 would come back invisibly.
    return isKnownNoise(event) ? null : event;
  },
});
