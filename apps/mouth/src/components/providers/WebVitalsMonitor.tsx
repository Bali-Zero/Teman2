"use client";

import { useEffect } from "react";
import { initWebVitals } from "@/lib/web-vitals";

const ENDPOINT = "/api/analytics/web-vitals";

// Feature flag — only ship beacons to our backend when explicitly enabled.
// Default is "false" so new environments don't start posting until the endpoint
// (or a downstream pipeline) is ready to receive.
const BEACON_ENABLED =
  process.env.NEXT_PUBLIC_WEB_VITALS_ENABLED === "true" ||
  process.env.NEXT_PUBLIC_WEB_VITALS_ENABLED === "1";

function sendBeacon(metric: {
  name: string;
  value: number;
  rating: string;
  id: string;
  navigationType: string;
}) {
  if (typeof window === "undefined") return;
  const payload = JSON.stringify({
    ...metric,
    url: window.location.pathname,
  });
  try {
    if (typeof navigator !== "undefined" && navigator.sendBeacon) {
      const blob = new Blob([payload], { type: "application/json" });
      navigator.sendBeacon(ENDPOINT, blob);
      return;
    }
    void fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
      keepalive: true,
    });
  } catch {
    // Silent — web vitals must never break the page.
  }
}

export function WebVitalsMonitor() {
  useEffect(() => {
    initWebVitals({
      enabled: true,
      debug: process.env.NODE_ENV === "development",
      sendToAnalytics: BEACON_ENABLED ? sendBeacon : undefined,
    });
  }, []);

  return null;
}
