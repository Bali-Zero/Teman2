// apps/mouth/src/app/portal/login-upgraded/page.tsx
"use client";

import React, { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { BZLogo } from "@balizero/core/components/BZLogo";
import { useSystemSound } from "@/hooks/useSystemSound";
import { publicAuth } from "@/lib/api/public-auth";
import { sanitizeRedirect } from "@/lib/auth/sanitizeRedirect";
import { logger } from "@/lib/logger";
import { I18nProvider, useTranslation } from "@/i18n";

// Configuration
const REDIRECT_DELAY_MS = 1500;
const ERROR_RESET_DELAY_MS = 2000;

// R19 concept F ("RAPI"): forest is the ONLY primary-button fill. Copper
// carries "needs you" as text, numerals and outline — never as a filled
// surface — and red does not exist on this surface at all.
const LOGIN_CTA_STYLE = {
  background: "var(--r19-forest)",
  color: "var(--r19-paper)",
} as const;

// Page-local presentation layer. Scoped under .r19-gate so nothing here can
// reach kita/prime; the palette lives as page-local custom properties until
// the my-product token seam carries the R19 values.
const R19_STYLES = `
.r19-gate{
  --r19-paper:#f7f4ee;--r19-surface:#fffcf7;--r19-ink:#1d2c3b;--r19-muted:#58626b; /* token-lint-ok: concept-F paper/ink scale, page-local until the my-product token seam lands */
  --r19-line:#dad8d1;--r19-line-strong:#a8aca9; /* token-lint-ok: concept-F hairlines */
  --r19-copper:#a44b36;--r19-forest:#253e33; /* token-lint-ok: concept-F copper (needs-you) and forest (done) meanings */
  position:relative;display:grid;grid-template-columns:minmax(0,5fr) minmax(0,6fr);
  min-height:100vh;background:var(--r19-paper);color:var(--r19-ink);
  font-size:15px;line-height:1.75;
}
.r19-serif{font-family:var(--font-serif),Georgia,serif;font-weight:450;letter-spacing:-0.03em}
.r19-eyebrow{font-size:10px;line-height:1.4;font-weight:650;letter-spacing:0.14em;text-transform:uppercase;color:var(--r19-muted)}
.r19-gate button{cursor:pointer;border:0;background:none;color:inherit;font:inherit}
.r19-gate a{color:inherit;text-decoration:none}

.r19-hero{background:var(--r19-forest);color:var(--r19-paper);display:flex;flex-direction:column;justify-content:space-between;gap:32px;padding:40px 48px}
.r19-brand{display:flex;align-items:center;gap:10px}
.r19-brand-text{display:flex;flex-direction:column}
.r19-brand-name{font-size:17px;line-height:1;font-weight:500;letter-spacing:-0.01em}
.r19-brand-role{margin-top:5px;color:rgba(247,244,238,0.6)}
.r19-hero-rule{width:56px;height:3px;border-radius:2px;background:var(--r19-copper);margin-bottom:22px}
.r19-hero h2{margin:0;font-size:clamp(40px,4vw,56px);line-height:1.04}
.r19-hero-lede{margin:20px 0 0;max-width:34ch;font-size:15px;color:rgba(247,244,238,0.78)}
.r19-hero-foot{display:flex;justify-content:space-between;gap:16px;color:rgba(247,244,238,0.55)}

.r19-form{display:flex;flex-direction:column;justify-content:center;align-items:center;padding:48px 32px}
.r19-box{width:100%;max-width:400px}
.r19-steps{display:flex;align-items:center;gap:6px;margin-bottom:18px}
.r19-steps i{display:block;width:28px;height:3px;border-radius:2px;background:var(--r19-line)}
.r19-steps i.on{background:var(--r19-forest)}
.r19-form h1{margin:10px 0 8px;font-size:40px;line-height:1.06}
.r19-hint{margin:0 0 26px;color:var(--r19-muted)}
.r19-field{margin-bottom:16px}
.r19-field-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px}
.r19-input{display:block;width:100%;height:52px;padding:0 16px;font-size:15px;color:var(--r19-ink);background:var(--r19-surface);border:1px solid var(--r19-line-strong);border-radius:0.25rem;outline:none}
.r19-input::placeholder{color:var(--r19-muted)}
.r19-input:focus{border-color:var(--r19-copper);box-shadow:0 0 0 3px rgba(164,75,54,0.18)}
.r19-input:disabled{opacity:0.55;cursor:not-allowed}
.r19-pin{font-size:22px;text-align:center;letter-spacing:14px;font-variant-numeric:tabular-nums}
.r19-gate .r19-btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;width:100%;height:48px;margin-top:6px;padding:0 22px;border-radius:0.25rem;font-size:13px;font-weight:650;letter-spacing:0.02em}
.r19-gate .r19-btn:disabled{opacity:0.5;cursor:not-allowed}
.r19-gate .r19-back{font-size:12px;font-weight:650;color:var(--r19-copper)}
.r19-alt{margin-top:22px;display:flex;flex-direction:column;gap:10px;font-size:13px}
.r19-gate .r19-link{color:var(--r19-copper);font-weight:650}
.r19-gate .r19-link:hover{text-decoration:underline}
.r19-alt-sep{border-top:1px solid var(--r19-line);margin:6px 0}
.r19-quiet{color:var(--r19-muted)}
.r19-formfoot{margin-top:40px;display:flex;gap:16px;font-size:12px;color:var(--r19-muted);font-variant-numeric:tabular-nums}
.r19-formfoot a:hover{text-decoration:underline}

.r19-overlay{position:absolute;inset:0;z-index:50;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:24px;text-align:center;background:color-mix(in srgb, var(--r19-paper) 92%, transparent);backdrop-filter:blur(8px)}
.r19-overlay h1{margin:0;font-size:clamp(34px,5vw,56px);line-height:1.05}
.r19-overlay-ok h1{color:var(--r19-forest)}
.r19-overlay-denied h1{color:var(--r19-copper)}
.r19-overlay p{margin:0;max-width:34rem;font-size:15px;color:var(--r19-ink)}

.r19-input:-webkit-autofill,
.r19-input:-webkit-autofill:hover,
.r19-input:-webkit-autofill:focus,
.r19-input:-webkit-autofill:active{
  -webkit-box-shadow:0 0 0 30px var(--r19-surface) inset !important;
  -webkit-text-fill-color:var(--r19-ink) !important;
  caret-color:var(--r19-copper) !important;
}

@media (max-width:767px){
  .r19-gate{grid-template-columns:1fr}
  .r19-hero{padding:28px 22px 30px;gap:28px}
  .r19-hero h2{font-size:34px}
  .r19-hero-lede{margin-top:12px;font-size:14px}
  .r19-hero-foot{display:none}
  .r19-form{padding:32px 22px 40px;align-items:stretch}
  .r19-form h1{font-size:34px}
}
`;

// Map HTTP status code → i18n error key. Unknown → server_error (5xx) or
// network_error (anything else, including status=0 from opaque fetch failures).
function errorKeyFor(status: number): string {
  switch (status) {
    case 401:
      return "portal.login.errors.invalid_credentials";
    case 403:
      return "portal.login.errors.portal_unavailable";
    case 404:
      return "portal.login.errors.email_not_found";
    case 422:
      return "portal.login.errors.invalid_2fa";
    case 429:
      return "portal.login.errors.rate_limited";
    case 503:
      return "portal.login.errors.maintenance";
    default:
      return status >= 500
        ? "portal.login.errors.server_error"
        : "portal.login.errors.network_error";
  }
}

export default function UpgradedLoginPage() {
  // `useTranslation` requires an I18nProvider ancestor; the root layout does
  // not wrap one (only (blog) does). Wrap locally so /portal/login-upgraded
  // can consume the shared locale JSON without touching global providers.
  return (
    <I18nProvider>
      <UpgradedLoginPageInner />
    </I18nProvider>
  );
}

function UpgradedLoginPageInner() {
  const router = useRouter();
  const { t } = useTranslation();
  const [isHydrated, setIsHydrated] = useState(false);
  const [email, setEmail] = useState("");
  const [pin, setPin] = useState("");
  const [step, setStep] = useState<"email" | "pin">("email");
  const [loginStage, setLoginStage] = useState<
    "idle" | "authenticating" | "success" | "denied"
  >("idle");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const { play } = useSystemSound();
  const loginInFlightRef = useRef(false);

  // Keep the controlled fields inert until React owns them. Without this
  // guard, a fast user (or WebKit restoring form state) can update the native
  // input before hydration while React still holds an empty email, leaving the
  // visible value and the disabled CTA out of sync.
  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // Same persona declaration the authenticated portal layout makes at mount
  // (portal/(authenticated)/layout.tsx): the sign-in page is part of My, so
  // the product token seam has to apply here too. No cleanup — the layout
  // does not remove the attribute either, and a removal on unmount would
  // strip the persona during the redirect into the portal itself.
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.product = "my";
    if (root.dataset.theme === "light") root.dataset.theme = "operative-light";
    if (root.dataset.theme === "dark") root.dataset.theme = "operative-dark";
    if (
      root.dataset.theme !== "operative-light" &&
      root.dataset.theme !== "operative-dark"
    ) {
      root.dataset.theme = "operative-light";
    }
  }, []);

  const playClickSound = () => {
    play("focus");
    if (typeof window !== "undefined" && "vibrate" in navigator) {
      navigator.vibrate(10);
    }
  };

  const handleSubmitEmail = (e: React.FormEvent) => {
    e.preventDefault();
    const normalizedEmail = email.trim();
    if (normalizedEmail) {
      playClickSound();
      setEmail(normalizedEmail);
      setStep("pin");
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    const normalizedEmail = email.trim();
    if (
      loginStage !== "idle" ||
      loginInFlightRef.current ||
      !normalizedEmail ||
      pin.length < 4 ||
      pin.length > 8
    ) {
      return;
    }
    loginInFlightRef.current = true;

    logger.info("Login process started", {
      component: "UpgradedLoginPage",
      action: "handleLogin",
    });

    play("auth_start");
    setLoginStage("authenticating");

    try {
      const loginResult = await publicAuth.login(normalizedEmail, pin);
      setLoginStage("success");
      play("access_granted");

      const urlParams = new URLSearchParams(globalThis.location.search);
      const requestedRedirect = sanitizeRedirect(urlParams.get("redirect"));
      const backendRedirect = sanitizeRedirect(loginResult.redirectTo ?? null);
      const role = loginResult.user.role;
      const redirectTo =
        role === "partner"
          ? requestedRedirect?.startsWith("/portal/partner/")
            ? requestedRedirect
            : "/portal/partner/dashboard"
          : role === "client"
            ? requestedRedirect?.startsWith("/portal/partner/")
              ? "/portal"
              : (requestedRedirect ?? "/portal")
            : (backendRedirect ?? "/dashboard");

      setTimeout(() => {
        router.replace(redirectTo);
      }, REDIRECT_DELAY_MS);
    } catch (error) {
      // Extract HTTP status from error shape (best-effort — covers both
      // fetch Response-shaped errors and axios-style { response: { status } }).
      const status =
        (error as { response?: { status?: number } })?.response?.status ??
        (error as { status?: number })?.status ??
        0;

      // Auth telemetry is deliberately limited to non-sensitive diagnostics.
      // Never pass credentials, addresses, the current URL, or the raw HTTP
      // error (which may embed a request body) to the logger/Sentry pipeline.
      const telemetryContext = {
        component: "UpgradedLoginPage",
        action: "handleLogin",
        code: status,
        reason: errorKeyFor(status),
      } as const;
      if (status >= 400 && status < 500) {
        logger.info("Login denied", telemetryContext);
      } else {
        logger.error("Login failed", telemetryContext);
      }

      let msg = t(errorKeyFor(status));
      if (status === 429) {
        const retryAfter = (
          error as {
            response?: { headers?: { get?: (k: string) => string | null } };
          }
        )?.response?.headers?.get?.("retry-after");
        const seconds = retryAfter ? parseInt(retryAfter, 10) : 60;
        msg = t("portal.login.errors.rate_limited", {
          seconds: String(Number.isFinite(seconds) ? seconds : 60),
        });
      }
      setErrorMessage(msg);
      setLoginStage("denied");
      play("access_denied");

      setTimeout(() => {
        loginInFlightRef.current = false;
        setLoginStage("idle");
      }, ERROR_RESET_DELAY_MS);
    }
  };

  // The two existing alternative paths, equal and visible on both steps.
  const alternatives = (
    <div className="r19-alt">
      <Link href="/portal/magic-link" className="r19-link">
        Sign in with an email link instead
      </Link>
      <Link href="/portal/forgot-password" className="r19-link">
        {t("portal.login.forgot_password")}
      </Link>
      <div className="r19-alt-sep" aria-hidden="true" />
      <span className="r19-quiet">
        New here? Your Bali Zero contact sends the invitation — there is nothing
        to register.
      </span>
    </div>
  );

  const formFooter = (
    <div className="r19-formfoot">
      <span>© 2026 Bali Zero</span>
      <Link href="/privacy">Privacy</Link>
      <Link href="/terms">Terms</Link>
    </div>
  );

  return (
    <div className="r19-gate">
      {/* Safe: static presentation CSS, no external input. */}
      <style dangerouslySetInnerHTML={{ __html: R19_STYLES }} />

      {/* ACCESS GRANTED OVERLAY */}
      {loginStage === "success" && (
        <div
          className="r19-overlay r19-overlay-ok"
          role="status"
          aria-live="polite"
        >
          <h1 className="r19-serif">Portal Unlocked</h1>
        </div>
      )}

      {/* ACCESS DENIED OVERLAY — copper, never red: the state carries a word. */}
      {loginStage === "denied" && (
        <div
          className="r19-overlay r19-overlay-denied"
          role="alert"
          aria-live="assertive"
        >
          <h1 className="r19-serif">Access Denied</h1>
          {errorMessage && <p id="portal-login-error">{errorMessage}</p>}
        </div>
      )}

      {/* The one forest surface of the portal. No personal data before auth. */}
      <aside className="r19-hero" aria-label="Bali Zero">
        <span className="r19-brand">
          <BZLogo variant="mark" size={28} priority />
          <span className="r19-brand-text">
            <span className="r19-brand-name r19-serif">Bali Zero</span>
            <span className="r19-brand-role r19-eyebrow">Client portal</span>
          </span>
        </span>
        <div>
          <div className="r19-hero-rule" aria-hidden="true" />
          <h2 className="r19-serif">
            Your Bali file,
            <br />
            kept in order.
          </h2>
          <p className="r19-hero-lede">
            Visas, company, taxes and documents — one place, one team, and
            always a clear next step.
          </p>
        </div>
        <div className="r19-hero-foot r19-eyebrow">
          <span>my.balizero.com</span>
          <span>Denpasar · Bali</span>
        </div>
      </aside>

      {/* The existing two-step flow: email, then the PIN. */}
      <section className="r19-form" aria-label="Sign in">
        {step === "email" ? (
          <form className="r19-box" onSubmit={handleSubmitEmail}>
            <div className="r19-steps" aria-hidden="true">
              <i className="on" />
              <i />
            </div>
            <p className="r19-eyebrow">Sign in · step 1 of 2</p>
            <h1 className="r19-serif">Welcome back.</h1>
            <p className="r19-hint">
              Enter the email registered with Bali Zero. We will ask for your
              PIN next.
            </p>
            <div className="r19-field">
              <div className="r19-field-head">
                <label className="r19-eyebrow" htmlFor="portal-email">
                  Corporate Email
                </label>
              </div>
              <input
                id="portal-email"
                type="email"
                name="email"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onFocus={() => play("focus")}
                disabled={!isHydrated || loginStage !== "idle"}
                placeholder="client@company.com"
                required
                autoFocus
                className="r19-input"
              />
            </div>
            <button
              type="submit"
              disabled={!isHydrated || loginStage !== "idle" || !email.trim()}
              className="r19-btn"
              style={LOGIN_CTA_STYLE}
            >
              Continue
            </button>
            {alternatives}
            {formFooter}
          </form>
        ) : (
          <form className="r19-box" onSubmit={handleLogin}>
            <div className="r19-steps" aria-hidden="true">
              <i className="on" />
              <i className="on" />
            </div>
            <p className="r19-eyebrow">Sign in · step 2 of 2</p>
            <h1 className="r19-serif">Welcome back.</h1>
            <p className="r19-hint">
              Enter the PIN from your invitation email.
            </p>
            <div className="r19-field">
              <div className="r19-field-head">
                <label className="r19-eyebrow" htmlFor="portal-pin">
                  Access PIN
                </label>
                <button
                  type="button"
                  onClick={() => {
                    playClickSound();
                    setStep("email");
                  }}
                  className="r19-back"
                >
                  ← {email.split("@")[0]}
                </button>
              </div>
              <input
                id="portal-pin"
                type="password"
                name="password"
                autoComplete="current-password"
                inputMode="numeric"
                aria-describedby={
                  errorMessage ? "portal-login-error" : undefined
                }
                aria-invalid={loginStage === "denied"}
                value={pin}
                onChange={(e) => {
                  setPin(e.target.value);
                  if (
                    e.target.value.length === 6 &&
                    typeof window !== "undefined" &&
                    "vibrate" in navigator
                  )
                    navigator.vibrate(20);
                }}
                onFocus={() => play("focus")}
                disabled={loginStage !== "idle"}
                placeholder="••••••"
                required
                autoFocus
                minLength={4}
                maxLength={8}
                className="r19-input r19-pin"
              />
            </div>
            <button
              type="submit"
              disabled={
                loginStage !== "idle" || pin.length < 4 || pin.length > 8
              }
              aria-label={
                loginStage === "authenticating"
                  ? "Verifying identity"
                  : "Verify Identity"
              }
              className="r19-btn"
              style={LOGIN_CTA_STYLE}
            >
              {loginStage === "authenticating" ? (
                <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
              ) : (
                "Verify Identity"
              )}
            </button>
            {alternatives}
            {formFooter}
          </form>
        )}
      </section>
    </div>
  );
}
