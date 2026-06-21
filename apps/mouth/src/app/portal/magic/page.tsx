"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Cormorant_Garamond } from "next/font/google";
import { api } from "@/lib/api";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["300", "400", "700"],
  display: "swap",
});

const REDIRECT_DELAY_MS = 600;

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
    <main className="min-h-screen bg-black text-[#f0ece4] flex items-center justify-center px-6">
      <div className="max-w-md w-full text-center">
        <h1
          className={`${cormorant.className} text-3xl md:text-4xl font-light tracking-[0.06em] mb-4 text-white`}
        >
          {state === "error" ? "Link not valid" : "Signing you in…"}
        </h1>

        {state === "verifying" && (
          <p role="status" className="text-sm text-[#c9a96e]/70">
            One moment while we verify your link.
          </p>
        )}

        {state === "ok" && (
          <p role="status" className="text-sm text-[#c9a96e]/80">
            You&apos;re in. Taking you to your portal…
          </p>
        )}

        {state === "error" && (
          <div>
            <p className="text-sm text-[#c9a96e]/70 mb-8">
              This sign-in link is invalid or has expired. Links work once and
              last 15 minutes — request a fresh one.
            </p>
            <Link
              href="/portal/magic-link"
              className="block w-full text-center py-4 rounded-xl bg-gradient-to-br from-[#d9bd7a] to-[#a07838] text-black font-bold uppercase tracking-[0.08em] shadow-[0_4px_24px_rgba(201,169,110,0.3)]"
            >
              Send me a new link
            </Link>
            <Link
              href="/portal/login-upgraded"
              className="block mt-6 text-center text-xs text-[#c9a96e]/60 hover:text-[#c9a96e] uppercase tracking-[2px]"
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
        <main className="min-h-screen bg-black text-[#f0ece4] flex items-center justify-center">
          <p className="text-sm text-[#c9a96e]/70">Loading…</p>
        </main>
      }
    >
      <MagicVerifyInner />
    </Suspense>
  );
}
