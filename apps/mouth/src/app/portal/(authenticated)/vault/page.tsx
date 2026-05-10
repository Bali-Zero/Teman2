"use client";

import React from "react";
import { VaultLayout } from "@/components/portal/vault/VaultLayout";

export default function VaultPage() {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Document Vault</h1>
        <p style={{ color: "var(--bz-text-2)" }}>
          Manage your important documents
        </p>
      </section>

      <VaultLayout />
    </div>
  );
}
