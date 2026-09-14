"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import { safeRedirect, stageForError } from "./contract";
import type { LoginStage } from "./contract";

/**
 * R19 typefaces — declared in app/portal/r19-fonts.css, selected by the
 * [data-product="kita"] theme blocks in globals.css.
 *
 * That file's own comment says only [data-product="my"] points --font-serif
 * and --font-sans at these faces. Since SAETTA-R19K K1a the kita blocks do
 * too, so it serves both products; the correction lives here because the
 * portal file belongs to another window and stays byte-identical.
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
 * What arrived. Five states —
 *
 *   idle · authenticating · success · denied · unreachable
 *
 * — and four plates, because `success` has none. It was drafted with one
 * ("Welcome back, <name>. One moment.") and measured in Chromium: the
 * destination document takes the window before React commits, so the plate
 * never painted. A plate nobody sees is the theatre this PR is deleting, so it
 * went; the stage stays, because it is what keeps the form locked while the
 * browser navigates.
 *
 * `unreachable` is the state that was MISSING. A timeout, a 429 or a 5xx is
 * not a wrong PIN, and telling someone their credentials are wrong when the
 * service is down sends them to reset a password that was never the problem.
 *
 * And the redirect is now closed, to a written spec
 * (windows/K1d-REDIRECT-SPEC.md). `?redirect=` used to reach
 * `location.replace()` unvalidated — and three attempts of mine to close it by
 * inspecting the STRING left `/%09/evil.test` open, because a browser strips
 * the TAB before it parses. `safeRedirect` judges the RESOLVED URL instead.
 *
 * Both decisions live in ./contract, where they can be tested directly — and
 * because a page module may export nothing but the framework's own symbols.
 *
 * Unchanged on purpose: the `api.login` call, the `/api/health` warm-up, the
 * `?redirect=` contract itself, and the role-based fallback.
 */

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

      setLoginStage("success");

      // Honour ?redirect= only where it RESOLVES to this origin.
      const urlParams = new URLSearchParams(globalThis.location.search);
      const requested = urlParams.get("redirect");
      const roleFallback =
        loginResponse.user?.role === "client" ? "/portal" : "/dashboard";
      // The empty fallback is how a refusal is detected without a second
      // judgement: safeRedirect returns "" only when it refused.
      const allowed = safeRedirect(requested, globalThis.location.origin, "");
      if (requested && !allowed) {
        logger.warn("Refused a redirect target that leaves this origin", {
          component: "LoginPage",
          action: "handleLogin",
        });
      }
      const redirectTo = allowed || roleFallback;

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
      ? "That email and PIN were not accepted. Check both and try again."
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
            Welcome back.
          </h1>

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
                // so a phone should offer the number pad. `pattern` is what
                // iOS Safari reads for the numeric keypad; inputMode alone is
                // not enough there.
                inputMode="numeric"
                pattern="[0-9]*"
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
        </div>
      </main>
    </div>
  );
}
