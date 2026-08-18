"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Plus, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSecondHomeCase } from "@/hooks/useSecondHome";
import { STAGE_LABELS } from "@/lib/api/secondhome/state-machine";
import { StageTimeline } from "../components/StageTimeline";
import { TransitionControl } from "../components/TransitionControl";
import { GuaranteePanel } from "../components/GuaranteePanel";
import { EvidenceList } from "../components/EvidenceList";
import { AddEvidenceModal } from "../components/AddEvidenceModal";
import { DependentsSection } from "../components/DependentsSection";

export default function SecondHomeCaseDetailPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = params?.id ? decodeURIComponent(String(params.id)) : null;
  const { data: caseDetail, isLoading, isError } = useSecondHomeCase(caseId);
  const [isEvidenceModalOpen, setIsEvidenceModalOpen] = useState(false);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-sm text-[var(--bz-text-2)]">Loading case…</p>
      </div>
    );
  }

  if (isError || !caseDetail) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <p className="text-sm text-[var(--state-danger)]">
          Could not load this case. It may not exist, or you may not have
          access.
        </p>
        <Button variant="outline" onClick={() => router.push("/second-home")}>
          Back to Second Home
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/second-home">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Go back to Second Home"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Link
              href={`/clients/${caseDetail.client_id}`}
              className="text-xl font-bold text-[var(--bz-text-1)] hover:text-[var(--bz-accent)] transition-colors"
            >
              {caseDetail.client_name}
            </Link>
            <span className="text-xs font-mono text-[var(--bz-text-2)]">
              {caseDetail.case_id}
            </span>
            {caseDetail.stayguard_eligible && (
              <span
                className="text-[9px] px-1.5 py-0.5 rounded-full font-medium uppercase flex items-center gap-0.5"
                style={{
                  background:
                    "color-mix(in srgb, var(--state-success) 15%, transparent)",
                  color: "var(--state-success)",
                }}
              >
                <ShieldCheck className="w-2.5 h-2.5" />
                StayGuard-eligible
              </span>
            )}
          </div>
          <p className="text-sm text-[var(--bz-text-2)]">
            {caseDetail.basis === "deposit"
              ? "Deposit route"
              : "Property route"}{" "}
            · {STAGE_LABELS[caseDetail.stage]}
            {caseDetail.owner_email ? ` · Owner ${caseDetail.owner_email}` : ""}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <StageTimeline
            history={caseDetail.stage_history}
            currentStage={caseDetail.stage}
          />

          <div className="rounded-xl border border-[var(--bz-border)] bg-[var(--bz-card)] p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-[var(--bz-text-1)]">
                Evidence
              </h3>
              <Button
                size="sm"
                variant="outline"
                className="gap-1.5"
                onClick={() => setIsEvidenceModalOpen(true)}
              >
                <Plus className="w-3.5 h-3.5" />
                Add Evidence
              </Button>
            </div>
            <EvidenceList evidence={caseDetail.evidence} />
          </div>

          <DependentsSection
            dependents={caseDetail.dependents}
            principalCaseId={caseDetail.principal_case_id}
            dependentCode={caseDetail.dependent_code}
          />
        </div>

        <div className="space-y-4">
          <TransitionControl
            caseId={caseDetail.case_id}
            currentStage={caseDetail.stage}
            allowedNextStages={caseDetail.allowed_next_stages}
            basis={caseDetail.basis}
            evidence={caseDetail.evidence}
          />
          <GuaranteePanel
            guarantee={caseDetail.guarantee}
            hasEntryOrItasDate={Boolean(
              caseDetail.entry_date || caseDetail.itas_date,
            )}
          />
        </div>
      </div>

      {isEvidenceModalOpen && (
        <AddEvidenceModal
          caseId={caseDetail.case_id}
          onClose={() => setIsEvidenceModalOpen(false)}
        />
      )}
    </div>
  );
}
