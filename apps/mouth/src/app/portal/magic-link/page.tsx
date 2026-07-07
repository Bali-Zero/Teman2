"use client";

import { useState } from "react";
import Link from "next/link";
import { Cormorant_Garamond } from "next/font/google";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["300", "400", "700"],
  display: "swap",
});

/**
 * FASE 6 — Passwordless sign-in request page.
 *
 * Asks for the client's email and calls `POST /api/auth/request-magic-link`.
 * The backend is enumeration-safe (always 200 with a generic message), so the
 * UI shows the same confirmation regardless of whether the email is registered.
 */
export default function MagicLinkRequestPage() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">(
    "idle",
  );

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
    <main className="min-h-screen bg-black text-[#f0ece4] flex items-center justify-center px-6">
      <div className="max-w-md w-full">
        <h1
          className={`${cormorant.className} text-3xl md:text-4xl font-light tracking-[0.06em] mb-4 text-white`}
        >
          Sign in with a link
        </h1>

        {status === "sent" ? (
          <div role="status">
            <p className="text-sm text-[#c9a96e]/80 mb-8">
              If an account exists for <strong>{email.trim()}</strong>, a secure
              sign-in link is on its way. It works once and expires in 15
              minutes. Check your inbox (and spam).
            </p>
            <Link
              href="/portal/login-upgraded"
              className="block text-center text-xs text-[#c9a96e]/60 hover:text-[#c9a96e] uppercase tracking-[2px]"
            >
              ← Back to login
            </Link>
          </div>
        ) : (
          <form onSubmit={submit}>
            <p className="text-sm text-[#c9a96e]/70 mb-8">
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
              className="w-full rounded-xl border border-white/15 bg-white/5 px-4 py-4 text-base text-[#f0ece4] placeholder:text-[#c9a96e]/30 focus:border-[#c9a96e] focus:outline-none mb-4"
            />
            {status === "error" && (
              <p role="alert" className="text-xs text-[#c94a4a] mb-4">
                Something went wrong. Please try again in a moment.
              </p>
            )}
            <button
              type="submit"
              disabled={status === "sending"}
              className="block w-full text-center py-4 rounded-xl bg-gradient-to-br from-[#d9bd7a] to-[#a07838] text-black font-bold uppercase tracking-[0.08em] shadow-[0_4px_24px_rgba(201,169,110,0.3)] disabled:opacity-60"
            >
              {status === "sending" ? "Sending…" : "Email me a link"}
            </button>
            <Link
              href="/portal/login-upgraded"
              className="block mt-6 text-center text-xs text-[#c9a96e]/60 hover:text-[#c9a96e] uppercase tracking-[2px]"
            >
              ← Sign in with PIN instead
            </Link>
          </form>
        )}
      </div>
    </main>
  );
}
