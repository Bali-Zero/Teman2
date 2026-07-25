"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Plane, RefreshCw } from "lucide-react";
import { logger } from "@/lib/logger";

export default function VisaError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    logger.error("Portal visa page error", {}, error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 p-6 text-center">
      {/* WS3 slice 9: danger tone reads the semantic state token (AA on
          operative-light paper; neon-rose was a dark-theme hue). */}
      <div
        className="flex h-16 w-16 items-center justify-center rounded-full"
        style={{
          background:
            "color-mix(in srgb, var(--state-danger) 10%, transparent)",
        }}
      >
        <Plane className="h-8 w-8" style={{ color: "var(--state-danger)" }} />
      </div>
      <div className="space-y-2 max-w-sm">
        <h2 className="text-xl font-semibold">Immigration data unavailable</h2>
        <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
          We couldn&apos;t load your visa information. Please try again.
        </p>
      </div>
      <Button onClick={() => reset()}>
        <RefreshCw className="mr-2 h-4 w-4" />
        Try Again
      </Button>
    </div>
  );
}
