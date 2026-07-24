"use client";

/**
 * Portal Vault — client document vault.
 *
 * WS3 slice 5 (GARUDA Day Edition, 2026-07-24): day-theme token alignment,
 * mirroring slice 3 (billing, PR #3055). Masthead = copper rule + Cormorant
 * serif (--font-serif) in --tx-pure; the vault render tree (VaultLayout,
 * VaultFileGrid, VaultSidebar, VaultSearchBar, VaultUploadZone,
 * VaultErrorBoundary) drains legacy #c9a96e/#d4845a/#f0ece4 hexes and
 * white/* dark utilities to semantic tokens (--bz-text-*, --tx-*,
 * --bz-copper / --bz-copper-text, --bz-border, --glass-rim, --state-*).
 */

import React from "react";
import { VaultLayout } from "@/components/portal/vault/VaultLayout";

export default function VaultPage() {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header — Day masthead (GARUDA Day Edition): copper rule + Cormorant
          serif headline per concept (--font-serif, wired on <html>); Inter
          everywhere else. */}
      <section>
        <div
          aria-hidden="true"
          className="w-14 h-[3px] rounded-sm mb-4 bg-[var(--bz-copper)]"
        />
        <h1
          className="text-2xl font-semibold tracking-tight text-[var(--tx-pure)]"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Document Vault
        </h1>
        <p className="text-sm text-[var(--tx-secondary)] mt-1">
          Manage your important documents
        </p>
      </section>

      <VaultLayout />
    </div>
  );
}
