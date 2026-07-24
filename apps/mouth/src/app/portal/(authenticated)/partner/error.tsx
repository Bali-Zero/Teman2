"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Handshake, RefreshCw } from "lucide-react";
import { logger } from "@/lib/logger";

export default function PartnerError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    logger.error("Portal partner page error", {}, error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 p-6 text-center">
      {/* WS3 final slice: --neon-rose → --state-danger (WS2 operative-light
          AA step, 5.74:1 on paper); tint is a color-mix OF the state
          token so each theme gets a tint of its own AA step. */}
      <div
        className="flex h-16 w-16 items-center justify-center rounded-full"
        style={{
          background:
            "color-mix(in srgb, var(--state-danger) 10%, transparent)",
        }}
      >
        <Handshake
          className="h-8 w-8"
          style={{ color: "var(--state-danger)" }}
        />
      </div>
      <div className="space-y-2 max-w-sm">
        <h2 className="text-xl font-semibold text-[var(--tx-pure)]">
          Partner data unavailable
        </h2>
        <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
          We couldn&apos;t load your partner information. Please try again.
        </p>
      </div>
      <Button onClick={() => reset()}>
        <RefreshCw className="mr-2 h-4 w-4" />
        Try Again
      </Button>
    </div>
  );
}
