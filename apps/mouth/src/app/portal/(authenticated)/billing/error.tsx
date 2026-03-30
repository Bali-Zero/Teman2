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
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Billing</h1>
        <p style={{ color: "var(--bz-text-2)" }}>Your invoices and payments</p>
      </section>
      <section
        className="rounded-xl border p-8 text-center"
        style={{
          background: "rgba(30,30,35,0.7)",
          borderColor: "rgba(255,255,255,0.05)",
        }}
      >
        <AlertTriangle className="w-12 h-12 mx-auto mb-3 text-amber-400" />
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
