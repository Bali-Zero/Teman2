"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { TaxCompanyPilotWorkspace } from "@/components/crm/TaxCompanyPilotWorkspace";
import { api } from "@/lib/api";
import type { TaxCompanyPilotMap } from "@/lib/api/crm/crm.types";

export default function TaxCompanyPilotPage() {
  const { data, isLoading, error } = useQuery<TaxCompanyPilotMap[]>({
    queryKey: ["crm-tax-company-pilot"],
    queryFn: async () =>
      Promise.all([
        api.crm.getTaxCompanyPilotMap("ocean"),
        api.crm.getTaxCompanyPilotMap("bimala"),
      ]),
    staleTime: 5 * 60_000,
  });

  if (isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#0b1020] text-white">
        <Loader2 className="mr-2 animate-spin" size={18} />
        Loading tax company map
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#0b1020] px-4 text-white">
        <div className="rounded-lg border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-100">
          Tax company map is unavailable.
        </div>
      </main>
    );
  }

  return <TaxCompanyPilotWorkspace maps={data} />;
}
