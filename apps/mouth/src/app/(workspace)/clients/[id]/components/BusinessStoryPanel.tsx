"use client";

import { useId, useState } from "react";
import {
  AlertTriangle,
  Building2,
  ExternalLink,
  FileText,
  FolderOpen,
  GitBranch,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import {
  EmptyState,
  FOCUS,
  LedgerSection,
  Notice,
  StatePill,
  type PillTone,
} from "@/components/workspace/r19";
import { cn } from "@/lib/utils";
import type {
  TaxCompanyPilotEvidenceStory,
  TaxCompanyPilotMap,
  TaxCompanyPilotPersonDossier,
  TaxCompanyPilotReadiness,
  TaxCompanyPilotStoryEvidence,
} from "@/lib/api/crm/crm.types";

type BusinessStoryPanelProps = {
  clientName: string;
  companyNames: string[];
  maps: TaxCompanyPilotMap[];
  isLoading: boolean;
  error: Error | null;
  /** Section ordinal in the Overview "ledger" stack. Defaults to 2 to sit
   * under the not-yet-built "Needs attention" ledger (ordinal 1); pass an
   * explicit value once that section lands. */
  n?: number;
};

function normalize(value: string | null | undefined): string {
  return (value ?? "").toLowerCase().replace(/\s+/g, " ").trim();
}

/**
 * Exact match only, after case-fold and whitespace-collapse normalization.
 * The previous bidirectional SUBSTRING check matched "PT Alpha" against
 * "PT Alpha Beta Indonesia" (and vice versa), attaching one company's
 * evidence dossier to an unrelated client's profile. `company.aliases` is
 * the mechanism the data already provides for "the same company, spelled
 * differently" (e.g. the person-first key "BIMALA / Bimala Investments Bali
 * PT" next to the CRM's own "Bimala Investments Bali PT") — matching against
 * aliases in addition to the company name covers that case without any
 * fuzzy matching.
 */
function namesMatch(value: string | null | undefined, other: string): boolean {
  const a = normalize(value);
  const b = normalize(other);
  return a.length > 0 && b.length > 0 && a === b;
}

function mapMatchesClient(
  map: TaxCompanyPilotMap,
  clientName: string,
  companyNames: string[],
): boolean {
  const personMatch =
    map.persons.some((person) => namesMatch(person.name, clientName)) ||
    map.person_dossiers.some((dossier) =>
      namesMatch(dossier.person_name, clientName),
    ) ||
    (map.evidence_stories ?? []).some((story) =>
      namesMatch(story.person_name, clientName),
    );

  const companyMatch = companyNames.some(
    (companyName) =>
      namesMatch(map.company.name, companyName) ||
      map.company.aliases.some((alias) => namesMatch(alias, companyName)),
  );

  return personMatch || companyMatch;
}

function storyMatchesClient(
  story: TaxCompanyPilotEvidenceStory,
  clientName: string,
): boolean {
  return namesMatch(story.person_name, clientName);
}

function dossierMatchesClient(
  dossier: TaxCompanyPilotPersonDossier,
  clientName: string,
): boolean {
  return namesMatch(dossier.person_name, clientName);
}

function getPrimaryDossier(
  map: TaxCompanyPilotMap,
  clientName: string,
): TaxCompanyPilotPersonDossier | null {
  return (
    map.person_dossiers.find((dossier) =>
      dossierMatchesClient(dossier, clientName),
    ) ??
    map.person_dossiers[0] ??
    null
  );
}

function getPrimaryStory(
  map: TaxCompanyPilotMap,
  clientName: string,
): TaxCompanyPilotEvidenceStory | null {
  const stories = map.evidence_stories ?? [];
  return (
    stories.find((story) => storyMatchesClient(story, clientName)) ??
    stories[0] ??
    null
  );
}

function getEvidenceItems(
  map: TaxCompanyPilotMap,
  story: TaxCompanyPilotEvidenceStory | null,
): TaxCompanyPilotStoryEvidence[] {
  if (story?.evidence_items.length) {
    return story.evidence_items.slice(0, 4);
  }

  return map.evidence_links.slice(0, 4).map((link) => ({
    label: "Evidence",
    detail: link.label,
    source_label: link.label,
    source_url: link.url,
    source_kind: link.kind,
    audience: "team",
    confidence: map.confidence,
  }));
}

function getReviewedWorkspaceAiFacts(map: TaxCompanyPilotMap) {
  return map.workspace_ai?.facts.slice(0, 3) ?? [];
}

function humanizeOperationalText(value: string): string {
  const normalized = value.trim();
  const direct: Record<string, string> = {
    "Attach source documents.": "Add the missing documents.",
    "Attach source documents before using this company story operationally.":
      "Add the missing documents before using this story for work.",
    "Run OCR/KG linking for stronger relationships.":
      "Let the CRM read the documents and connect them.",
    "Run OCR/KG linking to strengthen the person-company evidence chain.":
      "Let the CRM read the documents and connect this person to the company.",
    "Attach tax or LKPM evidence.": "Add the tax or LKPM files.",
    "No blocking evidence gaps.": "Nothing important is missing.",
  };
  if (direct[normalized]) return direct[normalized];

  return normalized
    .replace(/\bOCR\/KG linking\b/g, "document reading")
    .replace(/\bKG\b/g, "CRM map")
    .replace(/\bOCR\b/g, "document reading")
    .replace(/\bevidence layer\b/gi, "document map")
    .replace(/\bevidence\b/gi, "documents")
    .replace(/\bsource documents\b/gi, "missing documents")
    .replace(/\bperson-first workspace\b/gi, "client story")
    .replace(/\boperationally\b/gi, "for work");
}

/**
 * The categorical readiness state, WITHOUT the numeric score. When
 * `map.readiness` is absent, the backend has not computed one; the previous
 * fallback invented a score (35/70/100) to go with a heuristic derived from
 * real `gaps` data. The status/label pairing below is still derived from
 * real fields (`map.gaps`), so it stays; the fabricated number does not.
 */
type ReadinessDisplay = Pick<
  TaxCompanyPilotReadiness,
  "status" | "label" | "reasons"
>;

function getReadiness(map: TaxCompanyPilotMap): ReadinessDisplay {
  if (map.readiness) return map.readiness;
  const hasHighGap = map.gaps.some((gap) => gap.severity === "high");
  if (!map.gaps.length) {
    return {
      status: "ready",
      label: "Ready to operate",
      reasons: ["No blocking evidence gaps."],
    };
  }
  return {
    status: hasHighGap ? "blocked" : "needs_review",
    label: hasHighGap ? "Blocked" : "Needs review",
    reasons: map.gaps.slice(0, 3).map((gap) => gap.label),
  };
}

function humanReadinessLabel(readiness: ReadinessDisplay): string {
  if (readiness.status === "ready") return "Ready";
  if (readiness.status === "blocked") return "Missing documents";
  return "Needs a check";
}

/** Ownership is not derivable here (no viewer/record comparison available),
 * so this never returns copper — README law #1: "where ownership is not
 * derivable, use wait." */
function readinessTone(status: ReadinessDisplay["status"]): PillTone {
  return status === "ready" ? "ok" : "wait";
}

function humanConfidenceLabel(
  confidence: TaxCompanyPilotMap["confidence"],
): string {
  const labels: Record<TaxCompanyPilotMap["confidence"], string> = {
    unconfirmed: "not confirmed",
    low: "early draft",
    medium: "some documents",
    high: "strong documents",
    confirmed: "confirmed",
  };
  return labels[confidence] ?? confidence;
}

function getNextAction(
  map: TaxCompanyPilotMap,
  story: TaxCompanyPilotEvidenceStory | null,
  dossier: TaxCompanyPilotPersonDossier | null,
): string {
  return humanizeOperationalText(
    story?.next_action ??
      dossier?.next_action ??
      map.next_best_actions[0]?.label ??
      "Review the company documents and decide the next step.",
  );
}

function getSummary(
  map: TaxCompanyPilotMap,
  clientName: string,
  story: TaxCompanyPilotEvidenceStory | null,
  dossier: TaxCompanyPilotPersonDossier | null,
): string {
  return humanizeOperationalText(
    story?.recap ??
      dossier?.headline ??
      map.business_story[0] ??
      map.ai_recap[0] ??
      `${clientName} is connected to ${map.company.name}.`,
  );
}

export function BusinessStoryPanel({
  clientName,
  companyNames,
  maps,
  isLoading,
  error,
  n = 2,
}: BusinessStoryPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const detailId = useId();

  let toggle: React.ReactNode = null;
  let body: React.ReactNode;

  if (isLoading) {
    body = (
      <div className="flex items-center gap-3 px-4 py-4 text-sm text-[var(--tx-secondary)]">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading business story
      </div>
    );
  } else if (error) {
    body = (
      <div className="flex items-start gap-3 px-4 py-4">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--state-warning)]" />
        <p className="text-sm text-[var(--tx-secondary)]">
          The client profile is available, but the evidence layer did not load.
        </p>
      </div>
    );
  } else {
    const relevantMaps = maps.filter((map) =>
      mapMatchesClient(map, clientName, companyNames),
    );

    if (relevantMaps.length === 0) {
      const hasCompanyLinks = companyNames.length > 0;
      body = (
        <EmptyState className="px-4">
          {hasCompanyLinks
            ? "This person has a company, but the CRM has not read the documents yet."
            : "Connect this person to a company, then the CRM can build the tax story."}
        </EmptyState>
      );
    } else {
      const primaryMap = relevantMaps[0];
      const primaryStory = getPrimaryStory(primaryMap, clientName);
      const primaryDossier = getPrimaryDossier(primaryMap, clientName);
      const summary = getSummary(
        primaryMap,
        clientName,
        primaryStory,
        primaryDossier,
      );

      toggle = (
        <button
          type="button"
          aria-expanded={isOpen}
          aria-controls={detailId}
          onClick={() => setIsOpen((open) => !open)}
          className={cn(
            "text-xs font-medium text-[var(--tx-secondary)] hover:text-[var(--tx-pure)]",
            FOCUS,
          )}
        >
          {isOpen ? "Close" : "Open"}
        </button>
      );

      // Closed: one paragraph, real recap/headline text only. The mock also
      // shows a "Last WhatsApp signal … 2 days ago" line, but no field on
      // `TaxCompanyPilotMap` carries a last-contact timestamp today — left
      // out rather than invented (see PLAN-redesign.md "Deferred").
      // Open: the full per-company breakdown, in place of the summary.
      body = !isOpen ? (
        <p className="px-4 py-3 text-sm leading-6 text-[var(--tx-pure)]">
          {summary}
        </p>
      ) : (
        <div id={detailId} className="divide-y divide-[var(--bz-border)]">
          <div className="p-4 pb-0">
            <Notice tone="ok" role="status" className="flex items-center gap-2">
              <ShieldCheck className="h-3.5 w-3.5 shrink-0" />
              Team can open Drive here. Clients only see approved downloads in
              the portal.
            </Notice>
          </div>
          {relevantMaps.map((map) => {
            const story = getPrimaryStory(map, clientName);
            const dossier = getPrimaryDossier(map, clientName);
            const evidenceItems = getEvidenceItems(map, story);
            const workspaceAiFacts = getReviewedWorkspaceAiFacts(map);
            const nextAction = getNextAction(map, story, dossier);
            const relationshipPath = story?.relationship_path ?? [
              clientName,
              map.company.name,
              `Tax: ${map.tax_member.name}`,
            ];
            const readiness = getReadiness(map);
            const personName =
              story?.person_name ?? dossier?.person_name ?? clientName;
            const recap = getSummary(map, clientName, story, dossier);

            return (
              <article key={`${map.key}-${map.company.name}`} className="p-4">
                <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="text-base font-semibold text-[var(--bz-text-1)]">
                        {map.company.name}
                      </h4>
                      <span className="rounded bg-white/[0.06] px-2 py-1 text-[11px] font-medium text-[var(--bz-text-2)]">
                        {humanConfidenceLabel(map.confidence)}
                      </span>
                    </div>
                    <p className="mt-1 flex items-center gap-2 text-xs font-medium text-[var(--bz-text-2)]">
                      <GitBranch className="h-3.5 w-3.5" />
                      {relationshipPath.join(" -> ")}
                    </p>
                    <p className="mt-3 text-sm leading-6 text-[var(--bz-text-1)]">
                      {recap}
                    </p>
                    {map.business_story.length > 0 && (
                      <ul className="mt-3 space-y-1 text-sm leading-6 text-[var(--bz-text-2)]">
                        {map.business_story.slice(0, 2).map((item) => (
                          <li key={item}>{humanizeOperationalText(item)}</li>
                        ))}
                      </ul>
                    )}
                    {workspaceAiFacts.length > 0 && (
                      <div className="mt-4 rounded-lg border border-[var(--state-success)]/15 bg-[var(--state-success)]/[0.06] p-3">
                        <p className="text-xs font-semibold uppercase text-[var(--state-success)]">
                          Reviewed Workspace AI
                        </p>
                        <ul className="mt-2 space-y-1 text-sm leading-6 text-[var(--bz-text-1)]">
                          {workspaceAiFacts.map((fact) => (
                            <li key={`${fact.category}-${fact.label}`}>
                              {humanizeOperationalText(fact.detail)}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>

                  <aside className="space-y-2 rounded-lg border border-white/[0.06] bg-black/10 p-3">
                    <div className="rounded-md border border-white/[0.06] bg-white/[0.03] p-2">
                      <StatePill
                        tone={readinessTone(readiness.status)}
                        label={humanReadinessLabel(readiness)}
                      />
                      {readiness.reasons.length > 0 && (
                        <p className="mt-1 text-[11px] leading-4 text-[var(--bz-text-2)]">
                          {humanizeOperationalText(readiness.reasons[0])}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-sm font-medium text-[var(--bz-text-1)]">
                      <Building2 className="h-4 w-4 text-[var(--tx-secondary)]" />
                      {personName}
                    </div>
                    <p className="text-xs text-[var(--bz-text-2)]">
                      Tax owner: {map.tax_member.name}
                    </p>
                    <p className="text-xs leading-5 text-[var(--state-success)]">
                      {nextAction}
                    </p>
                    {map.next_best_actions.length > 0 && (
                      <div className="pt-2">
                        <p className="text-[11px] font-semibold uppercase text-[var(--bz-text-2)]">
                          What to do next
                        </p>
                        <ul className="mt-2 space-y-2">
                          {map.next_best_actions.slice(0, 3).map((action) => (
                            <li
                              key={`${map.key}-${action.owner}-${action.label}`}
                              className="rounded-md border border-white/[0.06] bg-white/[0.03] p-2"
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-xs font-medium text-[var(--bz-text-1)]">
                                  {humanizeOperationalText(action.label)}
                                </span>
                                <span className="shrink-0 rounded bg-white/[0.08] px-1.5 py-0.5 text-[10px] font-medium text-[var(--bz-text-2)]">
                                  {action.owner}
                                </span>
                              </div>
                              <p className="mt-1 text-[11px] leading-4 text-[var(--bz-text-2)]">
                                {humanizeOperationalText(action.reason)}
                              </p>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </aside>
                </div>

                {evidenceItems.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {evidenceItems.map((item) =>
                      item.source_url ? (
                        <a
                          key={`${map.key}-${item.label}-${item.source_label}`}
                          href={item.source_url}
                          target="_blank"
                          rel="noreferrer"
                          aria-label={`Open ${item.source_label} evidence`}
                          className="inline-flex items-center gap-1.5 rounded-md border border-[var(--bz-border)] bg-[var(--bz-surface)] px-2.5 py-1.5 text-xs font-medium text-[var(--bz-text-1)] hover:bg-[var(--bz-card-hover)]"
                        >
                          <FolderOpen className="h-3.5 w-3.5 text-[var(--tx-secondary)]" />
                          {item.source_label}
                          <ExternalLink className="h-3.5 w-3.5 text-[var(--bz-text-2)]" />
                        </a>
                      ) : (
                        <span
                          key={`${map.key}-${item.label}-${item.source_label}`}
                          className="inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-white/[0.04] px-2.5 py-1.5 text-xs text-[var(--bz-text-2)]"
                        >
                          <FileText className="h-3.5 w-3.5" />
                          {item.source_label}
                        </span>
                      ),
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      );
    }
  }

  return (
    <LedgerSection n={n} tone="wait" title="Case notes" actions={toggle}>
      {body}
    </LedgerSection>
  );
}
