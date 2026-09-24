"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import { trackPortalPage } from "@/lib/portal-analytics";

/** Mounted only after the portal layout has resolved authentication. */
export function PortalUsageTracker() {
  const pathname = usePathname();
  const previous = useRef<string | null>(null);
  useEffect(() => {
    if (previous.current === pathname) return;
    previous.current = pathname;
    trackPortalPage(pathname, () => ({
      role: api.getUserProfile?.()?.role,
      impersonating: api.getPortalImpersonation?.() !== null,
    }));
  }, [pathname]);
  return null;
}
