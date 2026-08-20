"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useOptionalTranslation } from "@/i18n";

const CONSENT_KEY = "visa_oracle_consent";

// Fallback for routes that mount this banner OUTSIDE any <I18nProvider>
// ancestor — /visa itself has none anywhere in its layout chain (verified
// 2026-08-20), while /visa/second-home/* (landing + Studio) does via that
// route's layout.tsx. useOptionalTranslation() returns null there instead
// of throwing (the useTranslation() white-screen class), so this banner
// carries its own EN default rather than assume a provider is present.
const CONSENT_EN_FALLBACK = {
  text: "We use session data to provide visa guidance. By continuing, you agree to our",
  privacyPolicy: "Privacy Policy",
  and: "and",
  termsOfService: "Terms of Service",
  dismiss: "Got it",
} as const;

function useConsentCopy() {
  const i18n = useOptionalTranslation();
  return (key: keyof typeof CONSENT_EN_FALLBACK): string =>
    i18n ? i18n.t(`common.consent.${key}`) : CONSENT_EN_FALLBACK[key];
}

export function ConsentBanner() {
  const [visible, setVisible] = useState(false);
  const tc = useConsentCopy();

  useEffect(() => {
    // SSR guard: only run in the browser
    if (typeof window === "undefined") return;

    const acknowledged = localStorage.getItem(CONSENT_KEY);
    if (!acknowledged) {
      setVisible(true);
    }
  }, []);

  function handleDismiss() {
    if (typeof window !== "undefined") {
      localStorage.setItem(CONSENT_KEY, "true");
    }
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 px-6 py-4"
      style={{
        backgroundColor: "var(--bz-elevated)",
        borderTop: "1px solid rgba(255,255,255,0.12)",
      }}
    >
      <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <p
          className="text-sm text-center sm:text-left"
          style={{ color: "var(--tx-secondary)" }}
        >
          {tc("text")}{" "}
          <Link
            href="/visa/privacy"
            className="underline hover:opacity-80 transition-opacity"
            style={{ color: "var(--bz-accent)" }}
          >
            {tc("privacyPolicy")}
          </Link>{" "}
          {tc("and")}{" "}
          <Link
            href="/visa/terms"
            className="underline hover:opacity-80 transition-opacity"
            style={{ color: "var(--bz-accent)" }}
          >
            {tc("termsOfService")}
          </Link>
          .
        </p>
        <button
          onClick={handleDismiss}
          className="shrink-0 px-4 py-2 rounded text-sm font-medium transition-opacity hover:opacity-80"
          style={{
            backgroundColor: "var(--bz-accent)",
            color: "#ffffff",
          }}
        >
          {tc("dismiss")}
        </button>
      </div>
    </div>
  );
}
