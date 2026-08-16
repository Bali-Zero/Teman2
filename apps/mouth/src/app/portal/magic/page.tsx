"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { cormorant } from "@balizero/core/fonts/cormorant";
import { api } from "@/lib/api";

const REDIRECT_DELAY_MS = 600;

// Day surface + CTA tokens (WS3 final slice, 2026-07-26): card = --bz-card
// + --bz-border + concept .panel shadow; CTA = darker copper step
// --bz-copper-text with theme-aware --bz-on-warm fg (white on #9d5230 =
// 5.70:1 light; ink #0c0c0e on #d4845a = 6.74:1 dark — #b5633a with white
// would be 4.37:1, below AA). Was a forced-dark bg-black page with gold
// hexes (#c9a96e text, #d9bd7a→#a07838 CTA gradient).
const CARD_STYLE = {
  background: "var(--bz-card)",
  borderColor: "var(--bz-border)",
  boxShadow: "0 14px 34px rgba(22, 33, 58, 0.07)",
} as const;

const CTA_STYLE = {
  background: "var(--bz-copper-text)",
  color: "var(--bz-on-warm)",
  boxShadow: "0 4px 24px color-mix(in srgb, var(--bz-copper) 30%, transparent)",
} as const;

/**
 * FASE 6 — Magic-link verify landing.
 *
 * The emailed link points here with `?token=...`. We exchange the single-use
 * token for a session (`GET /api/auth/verify-magic/{token}` sets the httpOnly
 * cookie) and redirect into the portal. Invalid/expired tokens show a recovery
 * path back to the request page.
 */
function MagicVerifyInner() {
  const params = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<"verifying" | "ok" | "error">("verifying");
  // Guard against React 18 StrictMode double-invoke consuming a single-use token twice.
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    if (!token) {
      setState("error");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        await api.verifyMagicLink(token);
        if (cancelled) return;
        setState("ok");
        setTimeout(() => {
          globalThis.location.replace("/portal");
        }, REDIRECT_DELAY_MS);
      } catch {
        if (!cancelled) setState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <main className="min-h-screen bg-[var(--bz-base)] text-[var(--tx-primary)] flex items-center justify-center px-6">
      <div
        className="max-w-md w-full text-center rounded-2xl border p-8"
        style={CARD_STYLE}
      >
        <h1
          className={`${cormorant.className} text-3xl md:text-4xl font-light tracking-[0.06em] mb-4 text-[var(--tx-pure)]`}
        >
          {state === "error" ? "Link not valid" : "Signing you in…"}
        </h1>

        {state === "verifying" && (
          <p role="status" className="text-sm text-[var(--tx-secondary)]">
            One moment while we verify your link.
          </p>
        )}

        {state === "ok" && (
          <p role="status" className="text-sm text-[var(--state-success)]">
            You&apos;re in. Taking you to your portal…
          </p>
        )}

        {state === "error" && (
          <div>
            <p className="text-sm text-[var(--tx-secondary)] mb-8">
              This sign-in link is invalid or has expired. Links work once and
              last 15 minutes — request a fresh one.
            </p>
            <Link
              href="/portal/magic-link"
              className="block w-full text-center py-4 rounded-xl font-bold uppercase tracking-[0.08em]"
              style={CTA_STYLE}
            >
              Send me a new link
            </Link>
            <Link
              href="/portal/login-upgraded"
              className="block mt-6 text-center text-xs text-[var(--bz-copper-text)] hover:text-[var(--bz-copper)] uppercase tracking-[2px] transition-colors"
            >
              ← Sign in with PIN instead
            </Link>
          </div>
        )}
      </div>
    </main>
  );
}

export default function MagicVerifyPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-[var(--bz-base)] text-[var(--tx-primary)] flex items-center justify-center">
          <p className="text-sm text-[var(--tx-secondary)]">Loading…</p>
        </main>
      }
    >
      <MagicVerifyInner />
    </Suspense>
  );
}
