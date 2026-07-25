"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Building2, RefreshCw, ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { logger } from "@/lib/logger";

export default function CompanyDetailError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const router = useRouter();

  useEffect(() => {
    logger.error("Portal company detail page error", {}, error);
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
        <Building2
          className="h-8 w-8"
          style={{ color: "var(--state-danger)" }}
        />
      </div>
      <div className="space-y-2 max-w-sm">
        <h2 className="text-xl font-semibold">Company details unavailable</h2>
        <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
          We couldn&apos;t load this company&apos;s details. Please try again.
        </p>
      </div>
      <div className="flex gap-3">
        <Button variant="outline" onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Go Back
        </Button>
        <Button onClick={() => reset()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Try Again
        </Button>
      </div>
    </div>
  );
}
