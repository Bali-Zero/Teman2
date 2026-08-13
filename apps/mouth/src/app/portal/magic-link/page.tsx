"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { cormorant } from "@balizero/core/fonts/cormorant";

// Day tokens (WS3 final slice, 2026-07-26): paper shell + warm card +
// concept .panel shadow; CTA = darker copper step --bz-copper-text with
// theme-aware --bz-on-warm fg (white on #9d5230 = 5.70:1 light; ink
// #0c0c0e on #d4845a = 6.74:1 dark — #b5633a with white would be 4.37:1,
// below AA). Form = warm paper input + token border + copper focus ring.
// Was a forced-dark bg-black page with gold hexes.
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
 * FASE 6 — Passwordless sign-in request page.
 *
 * Asks for the client's email and calls `POST /api/auth/request-magic-link`.
 * The backend is enumeration-safe (always 200 with a generic message), so the
 * UI shows the same confirmation regardless of whether the email is registered.
 */
export default function MagicLinkRequestPage() {
  const [isHydrated, setIsHydrated] = useState(false);
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">(
    "idle",
  );

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || status === "sending") return;
    setStatus("sending");
    try {
      const res = await fetch("/api/auth/request-magic-link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
        credentials: "include",
      });
      // Enumeration-safe backend → treat any non-5xx as "sent".
      setStatus(res.status >= 500 ? "error" : "sent");
    } catch {
      setStatus("error");
    }
  };

  return (
    <main className="min-h-screen bg-[var(--bz-base)] text-[var(--tx-primary)] flex items-center justify-center px-6">
      <div
        className="max-w-md w-full rounded-2xl border p-8"
        style={CARD_STYLE}
      >
        <h1
          className={`${cormorant.className} text-3xl md:text-4xl font-light tracking-[0.06em] mb-4 text-[var(--tx-pure)]`}
        >
          Sign in with a link
        </h1>

        {status === "sent" ? (
          <div role="status">
            <p className="text-sm text-[var(--tx-secondary)] mb-8">
              If an account exists for <strong>{email.trim()}</strong>, a secure
              sign-in link is on its way. It works once and expires in 15
              minutes. Check your inbox (and spam).
            </p>
            <Link
              href="/portal/login-upgraded"
              className="block text-center text-xs text-[var(--bz-copper-text)] hover:text-[var(--bz-copper)] uppercase tracking-[2px] transition-colors"
            >
              ← Back to login
            </Link>
          </div>
        ) : (
          <form onSubmit={submit}>
            <p className="text-sm text-[var(--tx-secondary)] mb-8">
              Enter your registered email and we&apos;ll send you a one-time
              link — no PIN needed.
            </p>
            <label htmlFor="magic-email" className="sr-only">
              Email address
            </label>
            <input
              id="magic-email"
              type="email"
              required
              autoComplete="email"
              inputMode="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded-xl border border-[var(--bz-border)] bg-[var(--bz-base)] px-4 py-4 text-base text-[var(--tx-primary)] placeholder:text-[var(--tx-tertiary)] focus:border-[var(--bz-copper)] focus:outline-none focus:ring-2 focus:ring-[color-mix(in_srgb,var(--bz-copper)_25%,transparent)] mb-4"
            />
            {status === "error" && (
              <p
                role="alert"
                className="text-xs mb-4"
                style={{ color: "var(--state-danger)" }}
              >
                Something went wrong. Please try again in a moment.
              </p>
            )}
            <button
              type="submit"
              disabled={!isHydrated || status === "sending"}
              className="block w-full text-center py-4 rounded-xl font-bold uppercase tracking-[0.08em] disabled:opacity-60"
              style={CTA_STYLE}
            >
              {status === "sending" ? "Sending…" : "Email me a link"}
            </button>
            <Link
              href="/portal/login-upgraded"
              className="block mt-6 text-center text-xs text-[var(--bz-copper-text)] hover:text-[var(--bz-copper)] uppercase tracking-[2px] transition-colors"
            >
              ← Sign in with PIN instead
            </Link>
          </form>
        )}
      </div>
    </main>
  );
}
