"use client";

import { useEffect } from "react";
import { trackKBLICodeViewed } from "@/lib/analytics";

export function KBLIPageTracker({
  code,
  tier,
}: {
  code: string;
  tier: string;
}) {
  useEffect(() => {
    trackKBLICodeViewed(code, tier);
  }, [code, tier]);

  return null;
}
