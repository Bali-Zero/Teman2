"use client";

import {
  AlertTriangle,
  Building2,
  ExternalLink,
  FileText,
  FolderOpen,
  GitBranch,
  Loader2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
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
};

function normalize(value: string | null | undefined): string {
  return (value ?? "").toLowerCase().replace(/\s+/g, " ").trim();
}

function textContains(
  haystack: string | null | undefined,
  needle: string,
): boolean {
  const normalizedHaystack = normalize(haystack);
  const normalizedNeedle = normalize(needle);
  return (
    normalizedHaystack.length > 0 &&
    normalizedNeedle.length > 0 &&
    (normalizedHaystack.includes(normalizedNeedle) ||
      normalizedNeedle.includes(normalizedHaystack))
  );
}

function mapMatchesClient(
  map: TaxCompanyPilotMap,
  clientName: string,
  companyNames: string[],
): boolean {
  const personMatch =
    map.persons.some((person) => textContains(person.name, clientName)) ||
    map.person_dossiers.some((dossier) =>
      textContains(dossier.person_name, clientName),
    ) ||
    (map.evidence_stories ?? []).some((story) =>
      textContains(story.person_name, clientName),
    );

  const companyMatch = companyNames.some(
    (companyName) =>
      textContains(map.company.name, companyName) ||
      map.company.aliases.some((alias) => textContains(alias, companyName)),
  );

  return personMatch || companyMatch;
}

function storyMatchesClient(
  story: TaxCompanyPilotEvidenceStory,
  clientName: string,
): boolean {
  return textContains(story.person_name, clientName);
}

function dossierMatchesClient(
  dossier: TaxCompanyPilotPersonDossier,
  clientName: string,
): boolean {
  return textContains(dossier.person_name, clientName);
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

function humanReadinessLabel(readiness: TaxCompanyPilotReadiness): string {
  if (readiness.status === "ready") return "Ready";
  if (readiness.status === "blocked") return "Missing documents";
  return "Needs a check";
}

function humanConfidenceLabel(confidence: TaxCompanyPilotMap["confidence"]): string {
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

function getReadiness(map: TaxCompanyPilotMap): TaxCompanyPilotReadiness {
  if (map.readiness) return map.readiness;
  const hasHighGap = map.gaps.some((gap) => gap.severity === "high");
  if (!map.gaps.length) {
    return {
      status: "ready",
      score: 100,
      label: "Ready to operate",
      reasons: ["No blocking evidence gaps."],
    };
  }
  return {
    status: hasHighGap ? "blocked" : "needs_review",
    score: hasHighGap ? 35 : 70,
    label: hasHighGap ? "Blocked" : "Needs review",
    reasons: map.gaps.slice(0, 3).map((gap) => gap.label),
  };
}

function EmptyBusinessStory({ companyNames }: { companyNames: string[] }) {
  const hasCompanyLinks = companyNames.length > 0;
  return (
    <section
      className="rounded-xl border p-4"
      style={{
        borderColor: "rgba(255,255,255,0.08)",
        background: "rgba(32,32,36,0.65)",
      }}
    >
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 text-amber-300">
          <AlertTriangle className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-[var(--bz-text-1)]">
            {hasCompanyLinks
              ? "Story not built yet"
              : "No company linked yet"}
          </h3>
          <p className="mt-1 text-sm leading-6 text-[var(--bz-text-2)]">
            {hasCompanyLinks
              ? "This person has a company, but the CRM has not read the documents yet."
              : "Connect this person to a company, then the CRM can build the tax story."}
          </p>
        </div>
      </div>
    </section>
  );
}

export function BusinessStoryPanel({
  clientName,
  companyNames,
  maps,
  isLoading,
  error,
}: BusinessStoryPanelProps) {
  if (isLoading) {
    return (
      <section
        className="rounded-xl border p-4"
        style={{
          borderColor: "rgba(255,255,255,0.08)",
          background: "rgba(32,32,36,0.65)",
        }}
      >
        <div className="flex items-center gap-3 text-sm text-[var(--bz-text-2)]">
          <Loader2 className="h-4 w-4 animate-spin text-[var(--bz-accent)]" />
          Loading business story
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section
        className="rounded-xl border p-4"
        style={{
          borderColor: "rgba(239,68,68,0.25)",
          background: "rgba(32,32,36,0.65)",
        }}
      >
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
          <div>
            <h3 className="text-sm font-semibold text-[var(--bz-text-1)]">
              Business story unavailable
            </h3>
            <p className="mt-1 text-sm text-[var(--bz-text-2)]">
              The client profile is available, but the evidence layer did not
              load.
            </p>
          </div>
        </div>
      </section>
    );
  }

  const relevantMaps = maps.filter((map) =>
    mapMatchesClient(map, clientName, companyNames),
  );

  if (relevantMaps.length === 0) {
    return <EmptyBusinessStory companyNames={companyNames} />;
  }

  return (
    <section
      className="overflow-hidden rounded-xl border shadow-xl backdrop-blur-xl"
      style={{
        borderColor: "rgba(255,255,255,0.08)",
        background: "rgba(32,32,36,0.65)",
      }}
    >
      <header
        className="flex flex-col gap-2 border-b px-4 py-3 md:flex-row md:items-center md:justify-between"
        style={{ borderColor: "rgba(255,255,255,0.06)" }}
      >
        <div>
          <h3 className="flex items-center gap-2 text-sm font-semibold text-[var(--bz-text-1)]">
            <Sparkles className="h-4 w-4 text-[var(--bz-accent)]" />
            Client Story
          </h3>
          <p className="mt-1 text-xs text-[var(--bz-text-2)]">
            Person -&gt; company -&gt; tax -&gt; documents -&gt; next step
          </p>
        </div>
        <div className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-200">
          <ShieldCheck className="h-3.5 w-3.5" />
          Team can open Drive here. Clients only see approved downloads in the
          portal.
        </div>
      </header>

      <div className="divide-y divide-white/[0.06]">
        {relevantMaps.map((map) => {
          const story = getPrimaryStory(map, clientName);
          const dossier = getPrimaryDossier(map, clientName);
          const evidenceItems = getEvidenceItems(map, story);
          const nextAction = getNextAction(map, story, dossier);
          const relationshipPath = story?.relationship_path ?? [
            clientName,
            map.company.name,
            `Tax: ${map.tax_member.name}`,
          ];
          const readiness = getReadiness(map);
          const personName =
            story?.person_name ?? dossier?.person_name ?? clientName;
          const recap =
            story?.recap ??
            dossier?.headline ??
            map.business_story[0] ??
            map.ai_recap[0] ??
            `${clientName} is connected to ${map.company.name}.`;

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
                    {humanizeOperationalText(recap)}
                  </p>
                  {map.business_story.length > 0 && (
                    <ul className="mt-3 space-y-1 text-sm leading-6 text-[var(--bz-text-2)]">
                      {map.business_story.slice(0, 2).map((item) => (
                        <li key={item}>{humanizeOperationalText(item)}</li>
                      ))}
                    </ul>
                  )}
                </div>

                <aside className="space-y-2 rounded-lg border border-white/[0.06] bg-black/10 p-3">
                  <div className="rounded-md border border-white/[0.06] bg-white/[0.03] p-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-[var(--bz-text-1)]">
                        {humanReadinessLabel(readiness)}
                      </span>
                      <span className="rounded bg-white/[0.08] px-1.5 py-0.5 text-[10px] font-medium text-[var(--bz-text-2)]">
                        {readiness.score}%
                      </span>
                    </div>
                    {readiness.reasons.length > 0 && (
                      <p className="mt-1 text-[11px] leading-4 text-[var(--bz-text-2)]">
                        {humanizeOperationalText(readiness.reasons[0])}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-sm font-medium text-[var(--bz-text-1)]">
                    <Building2 className="h-4 w-4 text-[var(--bz-accent)]" />
                    {personName}
                  </div>
                  <p className="text-xs text-[var(--bz-text-2)]">
                    Tax owner: {map.tax_member.name}
                  </p>
                  <p className="text-xs leading-5 text-emerald-200">
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
                        className="inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-white/[0.04] px-2.5 py-1.5 text-xs font-medium text-[var(--bz-text-1)] hover:bg-white/[0.08]"
                      >
                        <FolderOpen className="h-3.5 w-3.5 text-[var(--bz-accent)]" />
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
    </section>
  );
}
