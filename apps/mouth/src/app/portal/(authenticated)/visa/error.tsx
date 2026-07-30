"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Plane, RefreshCw, MessageSquare } from "lucide-react";
import { logger } from "@/lib/logger";

export default function VisaError({
  error,
  reset,
}: {
  error: Error & { digest?: string; status?: number };
  reset: () => void;
}) {
  useEffect(() => {
    logger.error("Portal visa page error", {}, error);
  }, [error]);

  const is403 =
    (error as { status?: number })?.status === 403 ||
    error?.message === "Forbidden" ||
    error?.message?.includes("HTTP 403");

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
        <h2 className="text-xl font-semibold">
          {is403 ? "Access Denied" : "Immigration data unavailable"}
        </h2>
        <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
          {is403
            ? "Your account needs verification."
            : "We couldn't load your visa information. Please try again."}
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button onClick={() => reset()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Try Again
        </Button>
        {is403 ? (
          <Button asChild variant="outline">
            <a
              href="https://wa.me/6282230102328"
              target="_blank"
              rel="noreferrer"
            >
              <MessageSquare className="mr-2 h-4 w-4" />
              Contact your team
            </a>
          </Button>
        ) : (
          <Button asChild variant="outline">
            <Link href="/portal/messages">
              <MessageSquare className="mr-2 h-4 w-4" />
              Chat with your team
            </Link>
          </Button>
        )}
      </div>
    </div>
  );
}
