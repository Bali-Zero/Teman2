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

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getMe } from "@/lib/api/partners/partners";
import { ApiError } from "@/lib/api/error-handler";
import { PartnerLoadError } from "./PartnerLoadError";

type PartnerGateState = "checking" | "allowed" | "unavailable" | "unlinked";

export default function PartnerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [state, setState] = useState<PartnerGateState>("checking");

  const checkAccess = useCallback(async () => {
    setState("checking");
    try {
      await getMe();
      setState("allowed");
    } catch (error) {
      if (error instanceof ApiError && error.statusCode === 401) {
        const search =
          typeof window === "undefined" ? "" : window.location.search;
        const destination = `${pathname}${search}`;
        router.replace(
          `/portal/login-upgraded?redirect=${encodeURIComponent(destination)}`,
        );
        return;
      }
      if (
        error instanceof ApiError &&
        (error.statusCode === 403 || error.statusCode === 404)
      ) {
        setState("unlinked");
        return;
      }
      setState("unavailable");
    }
  }, [pathname, router]);

  useEffect(() => {
    void checkAccess();
  }, [checkAccess]);

  if (state === "checking") {
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

  if (state === "unavailable") {
    return <PartnerLoadError onRetry={checkAccess} />;
  }

  if (state === "unlinked") {
    return (
      <div
        role="alert"
        className="m-6 rounded-xl border p-6"
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
        }}
      >
        <h2 className="font-medium text-[var(--tx-pure)]">
          Partner access is unavailable
        </h2>
        <p className="mt-2 text-sm text-[var(--tx-secondary)]">
          This account is not linked to an active partner profile. Contact Bali
          Zero support for help.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
