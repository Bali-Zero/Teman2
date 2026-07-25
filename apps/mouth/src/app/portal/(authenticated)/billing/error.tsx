"use client";

import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function BillingError({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Day masthead (WS3): copper rule + Cormorant serif, mirrors page.tsx */}
      <section>
        <div
          aria-hidden="true"
          className="w-14 h-[3px] rounded-sm mb-4 bg-[var(--bz-copper)]"
        />
        <h1
          className="text-2xl font-semibold tracking-tight text-[var(--tx-pure)]"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Billing
        </h1>
        <p className="text-sm text-[var(--tx-secondary)] mt-1">
          Your invoices and payments
        </p>
      </section>
      <section
        className="rounded-xl border p-8 text-center"
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
        }}
      >
        <AlertTriangle
          className="w-12 h-12 mx-auto mb-3"
          style={{ color: "var(--state-warning)" }}
        />
        <p className="font-medium">Failed to load billing data</p>
        <p className="text-sm mt-1" style={{ color: "var(--bz-text-2)" }}>
          {error.message}
        </p>
        <Button onClick={reset} variant="outline" className="mt-4">
          Retry
        </Button>
      </section>
    </div>
  );
}
