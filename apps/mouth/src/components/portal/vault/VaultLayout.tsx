"use client";
import { useMemo, useState } from "react";
import { VaultSidebar } from "./VaultSidebar";
import { VaultFileGrid } from "./VaultFileGrid";
import { VaultSearchBar } from "./VaultSearchBar";
import { VaultUploadZone } from "./VaultUploadZone";
import { VaultErrorBoundary } from "./VaultErrorBoundary";
import { VaultPracticePicker } from "./VaultPracticePicker";
import { useVaultFiles } from "@/hooks/useVaultFiles";
import { useVaultDocumentActions } from "@/hooks/useVaultDocumentActions";
import { usePortalMatters } from "@/hooks/usePortal";
import {
  activeMatters,
  resolveUploadPractice,
  uploadNeedsPractice,
  type UploadPracticeChoice,
} from "@/lib/vault/uploadPractice";
import type { VaultFile } from "@/lib/schemas/vault";

export function VaultLayout() {
  const { data, error, isLoading, mutate } = useVaultFiles();
  const {
    remove,
    restore,
    pendingId,
    error: actionError,
  } = useVaultDocumentActions(() => mutate());
  const [practiceFilter, setPracticeFilter] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const matters = usePortalMatters();
  const [uploadChoice, setUploadChoice] =
    useState<UploadPracticeChoice>(undefined);

  const active = useMemo(
    () => activeMatters(matters.data?.matters ?? []),
    [matters.data],
  );
  const uploadPracticeId = resolveUploadPractice(active, uploadChoice);
  const uploadBlockedReason = matters.isLoading
    ? "Loading your practices…"
    : uploadNeedsPractice(active, uploadPracticeId)
      ? "Choose a practice above before uploading."
      : undefined;

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
    // Keep the storage provider opaque: the same-origin endpoint proxies the
    // authenticated document and returns a browser download response.
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
        {matters.isLoading && (
          <p role="status" className="text-xs text-[var(--bz-text-2)]">
            Loading your practices…
          </p>
        )}
        {matters.isError && !matters.isLoading && (
          <div role="alert" className="text-xs text-[var(--bz-text-2)]">
            We couldn&apos;t load your practices, so this file will be uploaded
            without one.{" "}
            <button
              type="button"
              onClick={() => matters.refetch()}
              className="font-medium text-[var(--bz-copper-text)] underline underline-offset-2"
            >
              Retry
            </button>
          </div>
        )}
        {active.length > 0 && (
          <VaultPracticePicker
            matters={active}
            value={uploadPracticeId}
            onChange={setUploadChoice}
          />
        )}
        <VaultUploadZone
          practiceId={uploadPracticeId}
          disabled={uploadBlockedReason !== undefined}
          disabledReason={uploadBlockedReason}
          onDone={() => mutate()}
        />
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
              <p className="text-sm text-[var(--bz-text-2)] py-8 text-center">
                Loading your files…
              </p>
            )}
            {error && !isLoading && (
              <div
                role="alert"
                className="bz-product-panel rounded-lg p-4 text-sm"
              >
                <p className="mb-2 text-[var(--bz-text-1)]">
                  Unable to load vault.
                </p>
                <button
                  onClick={() => mutate()}
                  className="text-xs uppercase tracking-[2px] text-[var(--bz-copper-text)] hover:underline"
                >
                  Retry
                </button>
              </div>
            )}
            {actionError && (
              <p
                role="alert"
                className="text-xs text-[var(--state-danger)] mb-2"
              >
                {actionError}
              </p>
            )}
            {data && (
              <VaultFileGrid
                files={filtered}
                onDownload={handleDownload}
                onDelete={(f) => remove(f.id)}
                onRestore={(f) => restore(f.id)}
                pendingId={pendingId}
              />
            )}
          </div>
        </div>
      </div>
    </VaultErrorBoundary>
  );
}
