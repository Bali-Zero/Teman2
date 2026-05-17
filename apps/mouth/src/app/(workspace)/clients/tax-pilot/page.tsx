"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { TaxCompanyPilotWorkspace } from "@/components/crm/TaxCompanyPilotWorkspace";
import { api } from "@/lib/api";
import type {
  TaxCompanyPilotMap,
  WorkspaceAiSnapshotReviewItem,
} from "@/lib/api/crm/crm.types";

export default function TaxCompanyPilotPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery<TaxCompanyPilotMap[]>({
    queryKey: ["crm-evidence-dossiers", "ocean", "bimala"],
    queryFn: async () =>
      api.crm.getEvidenceDossiers({
        companies: ["ocean", "bimala"],
        limit: 2,
    }),
    staleTime: 5 * 60_000,
  });
  const reviewQueue = useQuery<WorkspaceAiSnapshotReviewItem[]>({
    queryKey: ["crm-workspace-ai-review", "draft"],
    queryFn: async () =>
      api.crm.getWorkspaceAiReviewQueue({ status: "draft", limit: 25 }),
    staleTime: 60_000,
  });
  const approveSnapshot = useMutation({
    mutationFn: (snapshotId: string) =>
      api.crm.approveWorkspaceAiSnapshot(snapshotId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["crm-workspace-ai-review"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["crm-evidence-dossiers"],
        }),
      ]);
    },
  });

  if (isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#0b1020] text-white">
        <Loader2 className="mr-2 animate-spin" size={18} />
        Loading evidence dossiers
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#0b1020] px-4 text-white">
        <div className="rounded-lg border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-100">
          Evidence dossiers are unavailable.
        </div>
      </main>
    );
  }

  return (
    <TaxCompanyPilotWorkspace
      maps={data}
      reviewSnapshots={reviewQueue.data ?? []}
      reviewLoading={reviewQueue.isLoading}
      approvingSnapshotId={approveSnapshot.variables ?? null}
      onApproveSnapshot={(snapshotId) => approveSnapshot.mutate(snapshotId)}
    />
  );
}
