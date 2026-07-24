"use client";

/**
 * Forgot Password — recovery is a mailto to the team (no self-serve reset).
 *
 * WS3 final slice (GARUDA Day Edition, 2026-07-26): aligned to the day
 * tokens (was a forced-dark bg-black page with gold hexes). Paper shell
 * (--bz-base), warm card (--bz-card + --bz-border + concept .panel
 * shadow), serif headline in --tx-pure (Cormorant stays), CTA = darker
 * copper step --bz-copper-text with theme-aware --bz-on-warm fg (5.70:1
 * light; 6.74:1 dark — the base copper step with white would be 4.37:1,
 * below the 4.5:1 AA floor). Links read --bz-copper-text (5.05:1 on
 * paper). Layout unchanged.
 */

import Link from "next/link";
import { Cormorant_Garamond } from "next/font/google";
import { I18nProvider, useTranslation } from "@/i18n";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["300", "400", "700"],
  display: "swap",
});

// CTA: darker copper step + theme-aware on-warm fg (AA both themes, see
// header comment). Was a #d9bd7a→#a07838 gradient with black text.
const CTA_STYLE = {
  background: "var(--bz-copper-text)",
  color: "var(--bz-on-warm)",
  boxShadow: "0 4px 24px color-mix(in srgb, var(--bz-copper) 30%, transparent)",
} as const;

function ForgotPasswordInner() {
  const { t } = useTranslation();
  const subject = encodeURIComponent("Portal Access Recovery");
  const body = encodeURIComponent(
    "Hi team,\n\nI need help recovering access to my Bali Zero client portal.\n\nRegistered email: ",
  );
  const mailto = `mailto:zantara@balizero.com?subject=${subject}&body=${body}`;
  return (
    <main className="min-h-screen bg-[var(--bz-base)] text-[var(--tx-primary)] flex items-center justify-center px-6">
      <div
        className="max-w-md w-full rounded-2xl border p-8"
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
          boxShadow: "0 14px 34px rgba(22, 33, 58, 0.07)",
        }}
      >
        <h1
          className={`${cormorant.className} text-3xl md:text-4xl font-light tracking-[0.06em] mb-4 text-[var(--tx-pure)]`}
        >
          {t("portal.forgot_password.title")}
        </h1>
        <p className="text-sm text-[var(--tx-secondary)] mb-8">
          {t("portal.forgot_password.sent")}
        </p>
        <a
          href={mailto}
          className="block w-full text-center py-4 rounded-xl font-bold uppercase tracking-[0.08em]"
          style={CTA_STYLE}
        >
          Write to the team
        </a>
        <Link
          href="/portal/login-upgraded"
          className="block mt-6 text-center text-xs text-[var(--bz-copper-text)] hover:text-[var(--bz-copper)] uppercase tracking-[2px] transition-colors"
        >
          ← Back to login
        </Link>
      </div>
    </main>
  );
}

export default function ForgotPasswordPage() {
  return (
    <I18nProvider>
      <ForgotPasswordInner />
    </I18nProvider>
  );
}
