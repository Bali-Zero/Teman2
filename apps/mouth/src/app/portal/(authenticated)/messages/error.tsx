"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { RefreshCw, MessageSquare } from "lucide-react";
import { logger } from "@/lib/logger";

export default function MessagesError({
  error,
  reset,
}: {
  error: Error & { digest?: string; status?: number };
  reset: () => void;
}) {
  useEffect(() => {
    logger.error("Messages Error", {}, error);
  }, [error]);

  const is403 =
    (error as { status?: number })?.status === 403 ||
    error?.message === "Forbidden" ||
    error?.message?.includes("HTTP 403");

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-6">
      <div
        className="flex h-20 w-20 items-center justify-center rounded-full"
        style={{
          background:
            "color-mix(in srgb, var(--state-danger) 10%, transparent)",
        }}
      >
        <MessageSquare
          className="h-10 w-10"
          style={{ color: "var(--state-danger)" }}
        />
      </div>
      <div className="mt-6 text-center space-y-2 max-w-md">
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--tx-pure)" }}
        >
          {is403 ? "Access Denied" : "Couldn't Load Messages"}
        </h2>
        <p style={{ color: "var(--tx-secondary)" }}>
          {is403
            ? "Your account needs verification."
            : "There was an error loading this page. Please try again or contact support if the problem persists."}
        </p>
      </div>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Button onClick={() => reset()} variant="default">
          <RefreshCw className="mr-2 h-4 w-4" />
          Try Again
        </Button>
        {is403 && (
          <Button asChild variant="outline">
            <a
              href="https://wa.me/628213454721"
              target="_blank"
              rel="noreferrer"
            >
              <MessageSquare className="mr-2 h-4 w-4" />
              Contact your team
            </a>
          </Button>
        )}
      </div>
    </div>
  );
}
