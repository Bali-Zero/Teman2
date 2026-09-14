"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api/error-handler";
import { logger } from "@/lib/logger";

/**
 * R19 typefaces — declared in app/portal/r19-fonts.css, selected by the
 * [data-product="kita"] theme blocks in globals.css.
 */
import "../portal/r19-fonts.css";

/**
 * The staff gate, on concept-K "SIAP".
 *
 * What went, and why. The page used to play theatre: a system sound on focus,
 * on submit, on grant and on deny; two full-screen black overlays reading
 * ACCESS GRANTED and ACCESS DENIED in monospace; a framer-motion entrance, a
 * logo zoom and a brightness pulse on the photograph; and two artificial
 * delays — 1500ms before the redirect and 2000ms before the form came back.
 * None of it told a staff member anything the words do not, and 3500ms of it
 * was spent making them wait to be told.
 *
 * What arrived. Five honest plates instead of four:
 *
 *   idle · authenticating · success · denied · unreachable
 *
 * The fifth is the one that was missing. A timeout, a 429 or a 5xx is NOT a
 * wrong PIN, and telling someone their credentials are wrong when the service
 * is down sends them to reset a password that was never the problem. The
 * branch reads `ApiError.statusCode`, not a substring of the message.
 *
 * And the redirect is now closed. `?redirect=` used to reach
 * `location.replace()` unvalidated, so `/login?redirect=https://evil.test`
 * sent a freshly authenticated staff member off-origin. `sameOriginPath()`
 * below is the allowlist; it is exported and tested with guilt and innocence.
 *
 * Unchanged on purpose: the `api.login` call, the `/api/health` warm-up, the
 * `?redirect=` contract itself, and the role-based fallback.
 */

/** The five states this page can honestly be in. */
export type LoginStage =
  "idle" | "authenticating" | "success" | "denied" | "unreachable";

/**
 * Accept a redirect target only when it is a path on THIS origin.
 *
 * Rejected, each for a reason a reviewer can check: an absolute URL (any
 * scheme, including `javascript:`), a protocol-relative `//evil.test` (which a
 * browser resolves as an absolute URL), a backslash form `/\evil.test` (which
 * some browsers normalise to the protocol-relative one), and anything that
 * does not start with a single `/`. Everything accepted is a same-origin path,
 * so the caller can hand it straight to `location.replace`.
 */
export function sameOriginPath(raw: string | null): string | null {
  if (!raw) return null;
  if (!raw.startsWith("/")) return null;
  if (raw.startsWith("//")) return null;
  if (raw.startsWith("/\\")) return null;
  return raw;
}

/** 401 and 403 mean the credentials; everything else means the service. */
export function stageForError(error: unknown): "denied" | "unreachable" {
  if (error instanceof ApiError) {
    return error.statusCode === 401 || error.statusCode === 403
      ? "denied"
      : "unreachable";
  }
  // A thrown TypeError from fetch is a network failure, not a bad PIN.
  return "unreachable";
}

const FIELD =
  "w-full h-[52px] bg-transparent border-0 border-b border-[var(--line-control)] " +
  "px-0.5 text-[14px] text-[var(--tx-pure)] placeholder:text-[var(--tx-secondary)] " +
  "focus:outline-none focus:border-[var(--bz-copper)] " +
  "focus:shadow-[0_1px_0_0_var(--bz-copper)] disabled:opacity-50";

const LABEL =
  "block text-[10px] font-[650] uppercase tracking-[0.14em] text-[var(--tx-secondary)]";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [pin, setPin] = useState("");
  const [loginStage, setLoginStage] = useState<LoginStage>("idle");
  const [greeting, setGreeting] = useState<string | null>(null);

  // Warmup: ping backend on mount so Fly.io is awake before user submits.
  useEffect(() => {
    fetch("/api/health", { method: "GET" }).catch(() => {});
  }, []);

  const busy = loginStage === "authenticating" || loginStage === "success";

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;

    setLoginStage("authenticating");

    try {
      const loginResponse = await api.login(email, pin);

      setGreeting(loginResponse.user?.name ?? null);
      setLoginStage("success");

      // Honour ?redirect= ONLY when it is a path on this origin.
      const urlParams = new URLSearchParams(globalThis.location.search);
      const requested = urlParams.get("redirect");
      const allowed = sameOriginPath(requested);
      if (requested && !allowed) {
        logger.warn("Rejected an off-origin redirect target", {
          component: "LoginPage",
          action: "handleLogin",
        });
      }
      const redirectTo =
        allowed ??
        (loginResponse.user?.role === "client" ? "/portal" : "/dashboard");

      // A full page load, so the layout reads the fresh session.
      globalThis.location.replace(redirectTo);
    } catch (error) {
      const stage = stageForError(error);
      logger.error(
        "Login failed",
        { component: "LoginPage", action: "handleLogin", metadata: { stage } },
        error instanceof Error ? error : new Error(String(error)),
      );
      setLoginStage(stage);
    }
  };

  const notice =
    loginStage === "denied"
      ? "That email and PIN do not match. Check both and try again."
      : loginStage === "unreachable"
        ? "We could not reach the service. Nothing is wrong with your details — try again in a moment."
        : null;

  return (
    <div className="flex min-h-screen w-full flex-col bg-[var(--bz-base)] text-[var(--tx-pure)] lg:flex-row">
      {/* The one forest surface in kita. A 120px band on a phone. */}
      <section
        className="flex h-[120px] w-full shrink-0 flex-col justify-between px-6 py-5 lg:h-auto lg:min-h-screen lg:w-[40%] lg:px-14 lg:py-12"
        style={{
          background: "var(--bz-panel)",
          color: "var(--bz-on-panel)",
        }}
      >
        <div className="flex items-center gap-3 lg:flex-col lg:items-start lg:gap-8">
          <img
            src="/assets/logo/balizero-logo-clean.png"
            alt="Bali Zero"
            width={40}
            height={40}
            className="h-10 w-10 rounded-full"
            loading="eager"
          />
          <div className="min-w-0">
            <p
              className="text-[26px] leading-none tracking-[-0.03em] lg:text-[34px]"
              style={{
                fontFamily: "var(--font-serif)",
                fontWeight: 450,
                fontVariationSettings: '"opsz" 144',
              }}
            >
              kita.
            </p>
            <p className="mt-1.5 text-[13px] opacity-80 lg:mt-3 lg:text-[15px]">
              Ready when you are.
            </p>
          </div>
        </div>
        <p className="hidden text-[10px] font-[650] uppercase tracking-[0.16em] opacity-60 lg:block">
          Bali Zero · Staff
        </p>
      </section>

      {/* Paper. The form, centred. */}
      <main className="flex w-full flex-1 items-center justify-center px-6 py-12 lg:w-[60%] lg:px-16">
        <div className="w-full max-w-[380px]">
          <div
            aria-hidden="true"
            className="mb-5 h-[3px] w-14 rounded-sm bg-[var(--bz-copper)]"
          />
          <h1
            className="text-[28px] leading-[1.06] tracking-[-0.03em] lg:text-[30px]"
            style={{
              fontFamily: "var(--font-serif)",
              fontWeight: 450,
              fontVariationSettings: '"opsz" 144',
            }}
          >
            {loginStage === "success"
              ? greeting
                ? `Welcome back, ${greeting}.`
                : "Welcome back."
              : "Welcome back."}
          </h1>

          {loginStage === "success" ? (
            // Claims no destination: the redirect decides, not this sentence.
            <p
              role="status"
              className="mt-3 text-[13px] text-[var(--tx-secondary)]"
            >
              One moment.
            </p>
          ) : (
            <>
              <p className="mt-3 text-[13px] text-[var(--tx-secondary)]">
                Sign in with your Bali Zero email and PIN.
              </p>

              {notice && (
                <p
                  role="alert"
                  className="mt-5 border border-[var(--bz-copper)] px-3 py-2.5 text-[13px] text-[var(--bz-copper-text)]"
                >
                  {notice}
                </p>
              )}

              <form onSubmit={handleLogin} className="mt-7 flex flex-col gap-6">
                <div className="flex flex-col gap-1">
                  <label htmlFor="email" className={LABEL}>
                    Email
                  </label>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="username"
                    placeholder="you@balizero.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={busy}
                    className={FIELD}
                  />
                </div>

                <div className="flex flex-col gap-1">
                  <label htmlFor="pin" className={LABEL}>
                    PIN
                  </label>
                  <input
                    id="pin"
                    name="pin"
                    type="password"
                    // The backend's PIN is digits (identity/router.py:39,78),
                    // so a phone should offer the number pad.
                    inputMode="numeric"
                    autoComplete="current-password"
                    placeholder="••••••"
                    value={pin}
                    onChange={(e) => setPin(e.target.value)}
                    disabled={busy}
                    className={FIELD}
                  />
                </div>

                <button
                  type="submit"
                  disabled={busy}
                  className="mt-1 h-12 w-full text-[13px] font-[650] tracking-[0.02em] transition-opacity disabled:opacity-55"
                  style={{
                    background: "var(--bz-panel)",
                    color: "var(--bz-on-panel)",
                  }}
                >
                  {loginStage === "authenticating" ? "Signing in…" : "Enter"}
                </button>
              </form>

              <p className="mt-9 text-[12px] text-[var(--tx-secondary)]">
                Looking for the client portal?{" "}
                <a
                  href="https://my.balizero.com"
                  className="font-[650] text-[var(--bz-copper-text)] underline underline-offset-[3px]"
                >
                  my.balizero.com
                </a>
              </p>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
