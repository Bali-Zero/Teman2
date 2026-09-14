"use client";

import { useEffect } from "react";
import { RefreshCw } from "lucide-react";
import { logger } from "@/lib/logger";

/**
 * R19 typefaces — same import the page makes, because an error boundary
 * replaces the page and would otherwise render in the fallback stack.
 */
import "../portal/r19-fonts.css";

/**
 * The boundary for /login, on concept-K "SIAP".
 *
 * What went, and why. It used to draw a shadcn `destructive` disc — the red —
 * with `text-destructive` and `text-muted-foreground` copy. kita has no red:
 * the four meanings are done/ours/needs-you/waiting, and a failure to LOAD the
 * page is "needs you". Copper carries it, and the WORDS carry what is wrong,
 * because a colour alone has never told anyone what to do next.
 *
 * Unchanged on purpose: the `reset()` handler, the `logger.error` call and the
 * `error`/`reset` prop contract Next.js passes in.
 */
export default function LoginError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    logger.error("Login Error", {}, error);
  }, [error]);

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-[var(--bz-base)] px-6 py-12 text-[var(--tx-pure)]">
      <div className="w-full max-w-[380px]">
        {/* The copper rule: the R19 masthead idiom, not a filled alarm. */}
        <div
          aria-hidden="true"
          className="mb-5 h-[3px] w-14 rounded-sm bg-[var(--bz-copper)]"
        />
        <h1
          className="text-[28px] leading-[1.06] tracking-[-0.03em]"
          style={{
            fontFamily: "var(--font-serif)",
            fontWeight: 450,
            fontVariationSettings: '"opsz" 144',
          }}
        >
          The sign-in page did not load.
        </h1>
        <p className="mt-3 text-[13px] text-[var(--tx-secondary)]">
          Nothing is wrong with your account. Try again, and if it keeps
          happening tell us — the page, not the password.
        </p>

        <button
          type="button"
          onClick={() => reset()}
          className="mt-7 inline-flex h-12 items-center gap-2 px-6 text-[13px] font-[650] tracking-[0.02em] transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]"
          style={{
            background: "var(--bz-panel)",
            color: "var(--bz-on-panel)",
          }}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Try again
        </button>

        {error.digest && (
          // The digest is what support can actually look up. It is not PII.
          <p className="mt-6 text-[11px] tracking-[0.04em] text-[var(--tx-secondary)]">
            Reference {error.digest}
          </p>
        )}
      </div>
    </div>
  );
}
