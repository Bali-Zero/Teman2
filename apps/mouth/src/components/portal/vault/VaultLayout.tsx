"use client";
import { useMemo, useState } from "react";
import { VaultSidebar } from "./VaultSidebar";
import { VaultFileGrid } from "./VaultFileGrid";
import { VaultSearchBar } from "./VaultSearchBar";
import { VaultUploadZone } from "./VaultUploadZone";
import { VaultErrorBoundary } from "./VaultErrorBoundary";
import { useVaultFiles } from "@/hooks/useVaultFiles";
import type { VaultFile } from "@/lib/schemas/vault";

export function VaultLayout() {
  const { data, error, isLoading, mutate } = useVaultFiles();
  const [practiceFilter, setPracticeFilter] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [q, setQ] = useState("");

  const files = data ?? [];
  const filtered = useMemo(() => {
    const ql = q.toLowerCase();
    return files.filter((f) => {
      if (practiceFilter && String(f.practice_id) !== practiceFilter)
        return false;
      if (typeFilter && f.type !== typeFilter) return false;
      if (ql) {
        const hay = [f.name, f.type, f.practice_name ?? ""]
          .join(" ")
          .toLowerCase();
        if (!hay.includes(ql)) return false;
      }
      return true;
    });
  }, [files, practiceFilter, typeFilter, q]);

  const handleDownload = (file: VaultFile) => {
    // BE exposes `downloadable` but no specific download URL. Best-effort:
    // open the presumed endpoint in a new tab. If it 404s, user gets browser error.
    // TODO: replace once BE exposes /api/portal/documents/{id}/download.
    window.open(
      `/api/portal/documents/${file.id}/download`,
      "_blank",
      "noopener",
    );
  };

  return (
    <VaultErrorBoundary>
      <div className="space-y-4">
        <div className="flex flex-col md:flex-row gap-3 md:items-center">
          <div className="flex-1">
            <VaultSearchBar value={q} onChange={setQ} />
          </div>
        </div>
        <VaultUploadZone practiceId={practiceFilter} onDone={() => mutate()} />
        <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-4">
          <VaultSidebar
            files={files}
            practiceFilter={practiceFilter}
            typeFilter={typeFilter}
            onPracticeChange={setPracticeFilter}
            onTypeChange={setTypeFilter}
          />
          <div>
            {isLoading && (
              <p className="text-sm text-[#c9a96e]/60 py-8 text-center">
                Loading your files…
              </p>
            )}
            {error && !isLoading && (
              <div
                role="alert"
                className="rounded-lg p-4 border border-white/10 text-sm"
              >
                <p className="mb-2 text-[#f0ece4]">Unable to load vault.</p>
                <button
                  onClick={() => mutate()}
                  className="text-xs uppercase tracking-[2px] text-[#d4845a] hover:underline"
                >
                  Retry
                </button>
              </div>
            )}
            {data && (
              <VaultFileGrid files={filtered} onDownload={handleDownload} />
            )}
          </div>
        </div>
      </div>
    </VaultErrorBoundary>
  );
}
