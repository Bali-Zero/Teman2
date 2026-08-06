/**
 * CSP-safe Zod entrypoint for client and shared application code.
 *
 * Zod's object parser can probe `Function("")` before choosing its JIT fast
 * path. Even though Zod catches the resulting exception, Firefox reports the
 * blocked evaluation as a CSP violation. Configure Zod before any schema is
 * constructed so the probe is never attempted; do not add `unsafe-eval` to
 * the application CSP.
 *
 * Application code must import `z` from this module instead of directly from
 * `zod` so the configuration always runs first.
 */
import { z } from "zod";

z.config({ jitless: true });

export { z };
