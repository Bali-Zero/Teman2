"use client";

/**
 * Partner role-gate layout.
 *
 * Wraps all /portal/(authenticated)/partner/* pages.
 * On mount it calls /api/partners/me — the backend returns 403 for non-partner
 * roles and 200 for role=partner. This is the role-gate mechanism: if the call
 * fails with a 403-class error we redirect away immediately.
 *
 * NOTE: The middleware (middleware.ts) handles only domain routing — it has no
 * JWT decode capability. The role-gate lives here instead (escalation
 * fallback as per Task 10 spec). This is safe: the API itself enforces the
 * role boundary; the layout redirect is a UX guard only.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMe } from "@/lib/api/partners/partners";

export default function PartnerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    getMe()
      .then(() => {
        // Confirmed partner role — allow rendering
        setChecked(true);
      })
      .catch(() => {
        // Non-partner or unauthenticated → redirect to main portal dashboard
        router.replace("/portal/dashboard");
      });
  }, [router]);

  if (!checked) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div
            className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin"
            style={{
              borderColor: "var(--bz-accent-warm, #d4845a)",
              borderTopColor: "transparent",
            }}
          />
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
