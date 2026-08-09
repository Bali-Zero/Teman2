"use client";

import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface PartnerLoadErrorProps {
  readonly onRetry: () => void;
  readonly title?: string;
}

export function PartnerLoadError({
  onRetry,
  title = "Partner information is temporarily unavailable",
}: PartnerLoadErrorProps) {
  return (
    <div
      role="alert"
      className="m-6 rounded-xl border p-6"
      style={{
        background: "var(--bz-card)",
        borderColor: "var(--bz-border)",
      }}
    >
      <h2 className="font-medium text-[var(--tx-pure)]">{title}</h2>
      <p className="mt-2 text-sm text-[var(--tx-secondary)]">
        We couldn&apos;t load this information. Please try again.
      </p>
      <Button type="button" className="mt-4" onClick={onRetry}>
        <RefreshCw className="mr-2 h-4 w-4" />
        Try Again
      </Button>
    </div>
  );
}

interface PartnerPartialWarningProps {
  readonly onRetry: () => void;
}

export function PartnerPartialWarning({ onRetry }: PartnerPartialWarningProps) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-xl border p-4 sm:flex-row sm:items-center sm:justify-between"
      style={{
        background: "var(--bz-card)",
        borderColor: "var(--state-warning)",
      }}
    >
      <p className="text-sm text-[var(--tx-primary)]">
        Some partner information is temporarily unavailable.
      </p>
      <Button type="button" variant="outline" onClick={onRetry}>
        <RefreshCw className="mr-2 h-4 w-4" />
        Try Again
      </Button>
    </div>
  );
}
