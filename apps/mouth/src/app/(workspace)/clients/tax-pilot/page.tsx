"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { TaxCompanyPilotWorkspace } from "@/components/crm/TaxCompanyPilotWorkspace";
import { api } from "@/lib/api";
import type { TaxCompanyPilotMap } from "@/lib/api/crm/crm.types";

export default function TaxCompanyPilotPage() {
  const { data, isLoading, error } = useQuery<TaxCompanyPilotMap[]>({
    queryKey: ["crm-evidence-dossiers", "ocean", "bimala"],
    queryFn: async () =>
      api.crm.getEvidenceDossiers({
        companies: ["ocean", "bimala"],
        limit: 2,
      }),
    staleTime: 5 * 60_000,
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

  return <TaxCompanyPilotWorkspace maps={data} />;
}
