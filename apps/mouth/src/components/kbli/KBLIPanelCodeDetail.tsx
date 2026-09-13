"use client";

import Link from "next/link";
import { ArrowLeft, ExternalLink } from "lucide-react";
import type { KBLIPanelDetail } from "@/lib/kbli-panel-detail";
import { PMABadge } from "./PMABadge";
import { RiskBadge } from "./RiskBadge";
import { BaliStatusBadge } from "./BaliStatusBadge";
import { TransitionBadge } from "./TransitionBadge";

/**
 * Drill-down view shown inside the open panel.
 *
 * Deliberately a SUMMARY, not a mirror of `/kbli/[code]`. That page carries the
 * editorial layer, provenance panel, licensing tables, structured data and
 * hero — reproducing it here would multiply the panel's payload and give us two
 * places where the same disclosure rules have to stay true. What this view owns
 * is the decision "is this the code I want?"; the full page stays one click
 * away and remains the canonical, shareable, indexable URL.
 *
 * Every value comes pre-resolved from `toPanelDetail` on the server — this
 * component decides nothing about disclosure, it only lays out verdicts.
 */
export function KBLIPanelCodeDetail({
  detail,
  sectionId,
  onBack,
}: {
  detail: KBLIPanelDetail;
  sectionId: string;
  onBack: () => void;
}) {
  return (
    <div
      className="min-h-0 flex-1 overflow-y-auto px-5 py-5"
      data-testid="kbli-panel-code-detail"
    >
      <button
        type="button"
        onClick={onBack}
        data-testid="kbli-panel-detail-back"
        className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-zinc-400
                   transition-colors hover:text-white focus:outline-none
                   focus-visible:ring-2 focus-visible:ring-[var(--kbli-accent)]"
      >
        <ArrowLeft size={13} />
        Back to Section {sectionId}
      </button>

      <div className="mt-4">
        <span className="font-mono text-sm font-bold text-[var(--kbli-accent)]">
          {detail.code}
        </span>
        <h3 className="mt-1 text-lg font-bold leading-snug text-white">
          {detail.titleEn}
        </h3>
        <p className="mt-0.5 text-sm text-zinc-400">{detail.titleId}</p>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {/* Same order and same props as KBLICard — Bali verdict before the
            national PMA one, caps forwarded rather than defaulted. */}
        {detail.bali.status && (
          <BaliStatusBadge
            status={detail.bali.status}
            pmaStatus={
              detail.pma.verdictVerified ? detail.pma.status : "unknown"
            }
            size="sm"
          />
        )}
        <PMABadge
          status={detail.pma.status}
          maxForeign={detail.pma.maxForeign}
          verdictVerified={detail.pma.verdictVerified}
          capSpecial={detail.pma.capSpecial}
          capVerified={detail.pma.capVerified}
          baliBlocked={detail.bali.blocked}
          size="sm"
        />
        {detail.riskCategory && (
          <RiskBadge
            riskCategory={detail.riskCategory}
            size="sm"
            verificationPending={detail.riskVerificationPending}
          />
        )}
        <TransitionBadge transition={detail.transition} />
      </div>

      <p className="mt-5 border-t border-white/[0.06] pt-4 text-sm leading-relaxed text-zinc-400">
        Scope description, licensing by business scale, authority and processing
        time are on the code&apos;s own page — rendered there by the components
        that know how to state what is verified and what is derived.
      </p>

      <Link
        href={`/kbli/${detail.code}`}
        data-testid="kbli-panel-detail-full"
        className="mt-6 inline-flex items-center gap-2 rounded-xl border border-white/[0.10] bg-white/[0.06]
                   px-4 py-2.5 text-sm font-bold text-white backdrop-blur-md transition-all
                   hover:border-[var(--kbli-accent)]/60 hover:bg-[var(--kbli-accent)]/20
                   focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--kbli-accent)]"
      >
        Open full page for {detail.code}
        <ExternalLink size={14} />
      </Link>
    </div>
  );
}
