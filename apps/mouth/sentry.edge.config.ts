import * as Sentry from "@sentry/nextjs";

import { IGNORE_ERRORS, isKnownNoise } from "@/lib/sentry-noise";

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
  ignoreErrors: [...IGNORE_ERRORS],
  beforeSend(event) {
    return isKnownNoise(event) ? null : event;
  },
});
