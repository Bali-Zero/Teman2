"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const CONSENT_KEY = "visa_oracle_consent";

export function ConsentBanner() {
  const [visible, setVisible] = useState(false);

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
          We use session data to provide visa guidance. By continuing, you agree
          to our{" "}
          <Link
            href="/privacy"
            className="underline hover:opacity-80 transition-opacity"
            style={{ color: "var(--bz-accent)" }}
          >
            Privacy Policy
          </Link>{" "}
          and{" "}
          <Link
            href="/terms"
            className="underline hover:opacity-80 transition-opacity"
            style={{ color: "var(--bz-accent)" }}
          >
            Terms of Service
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
          Got it
        </button>
      </div>
    </div>
  );
}
