"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

import { redactSensitiveQueryParams } from "@/lib/analytics-url";

type GtagWindow = typeof window & { gtag?: (...args: unknown[]) => void };

/**
 * GA4 page_view on client-side navigation (Filo 3, 2026-06-11).
 *
 * The App Router does not emit page_view on <Link> navigations, so
 * sections browsed client-side (KBLI code → code, article → article)
 * were invisible past the first SSR load. The initial load is already
 * tracked by the gtag config bootstrap — this component skips the first
 * render and fires only on PATH changes (search-param changes are
 * intentionally ignored: useSearchParams would force a Suspense
 * boundary in the root layout for marginal value).
 */
export function RouteChangeTracker() {
  const pathname = usePathname();
  const isFirstRender = useRef(true);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    const win = window as GtagWindow;
    if (typeof win.gtag !== "function") return;
    win.gtag("event", "page_view", {
      page_path: pathname,
      // Never the raw href: a credential-bearing query string reached
      // Google verbatim through this field (portal audit L-GA, 2026-09-11).
      page_location: redactSensitiveQueryParams(window.location.href),
      page_title: document.title,
    });
  }, [pathname]);

  return null;
}
