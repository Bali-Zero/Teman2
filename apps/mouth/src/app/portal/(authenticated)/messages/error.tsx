"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { RefreshCw, MessageSquare } from "lucide-react";
import { logger } from "@/lib/logger";
import { ApiError } from "@/lib/api/error-handler";

export default function MessagesError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    logger.error("Messages Error", {}, error);
  }, [error]);

  // Branch on the real HTTP status, never on message text. This also read
  // `error.message.includes("403")`, which is true of "Practice 4034 not
  // found" — a 404 would have rendered "Access Denied". `error.status` was
  // never set by anything, so only the substring arm could ever fire.
  const is403 = error instanceof ApiError && error.statusCode === 403;

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
      {/*
        No "Chat with your team" action on THIS boundary: it is the error
        boundary for /portal/messages, so that link would send the reader back
        into the page that just failed. The other boundaries keep it because
        their remedy is a different route. What the escape hatch should be when
        the 403 is account-level (and /portal/messages would 403 too) is a
        product decision — see the PR discussion.
      */}
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Button onClick={() => reset()} variant="default">
          <RefreshCw className="mr-2 h-4 w-4" />
          Try Again
        </Button>
      </div>
    </div>
  );
}
