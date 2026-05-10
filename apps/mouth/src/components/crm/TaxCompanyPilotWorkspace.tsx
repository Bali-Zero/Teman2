import {
  AlertTriangle,
  BriefcaseBusiness,
  ExternalLink,
  FileText,
  Link2,
  ListChecks,
  Sparkles,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import type {
  TaxCompanyPilotDocument,
  TaxCompanyPilotGap,
  TaxCompanyPilotMap,
  TaxCompanyPilotNextAction,
  TaxCompanyPilotPersonDossier,
} from "@/lib/api/crm/crm.types";

const severityClass: Record<TaxCompanyPilotGap["severity"], string> = {
  high: "border-red-200 bg-red-50 text-red-800",
  medium: "border-amber-200 bg-amber-50 text-amber-800",
  low: "border-sky-200 bg-sky-50 text-sky-800",
};

const severityLabel: Record<TaxCompanyPilotGap["severity"], string> = {
  high: "Decision needed",
  medium: "Check",
  low: "Watch",
};

const actionOwnerLabel: Record<TaxCompanyPilotNextAction["owner"], string> = {
  crm: "CRM",
  tax: "Tax",
  setup: "Setup",
};

const documentGroupLabel: Record<TaxCompanyPilotDocument["group"], string> = {
  company: "Company registry",
  tax: "Tax filings",
  lkpm: "Investment reports",
  finance: "Finance",
  person: "Person files",
  coretax: "Coretax access",
};

function groupDocuments(documents: TaxCompanyPilotDocument[]) {
  return documents.reduce<Record<string, TaxCompanyPilotDocument[]>>(
    (groups, document) => {
      const group = documentGroupLabel[document.group];
      groups[group] = [...(groups[group] ?? []), document];
      return groups;
    },
    {},
  );
}

function getCompanyStatus(map: TaxCompanyPilotMap) {
  const highCount = map.gaps.filter((gap) => gap.severity === "high").length;
  if (highCount > 0) return "Needs business review";
  if (map.gaps.length > 0) return "Almost ready";
  return "Ready to operate";
}

function getPersonDossiers(
  map: TaxCompanyPilotMap,
): TaxCompanyPilotPersonDossier[] {
  if (map.person_dossiers?.length) return map.person_dossiers;

  const documentGroups = Object.keys(groupDocuments(map.documents));
  return map.persons.map((person) => ({
    person_name: person.name,
    company_name: map.company.name,
    headline: person.role
      ? `${person.role} connected to ${map.company.name}`
      : `Person to verify before opening ${map.company.name}`,
    tax_owner: map.tax_member.name,
    drive_folder_url: person.folder_url,
    document_groups: documentGroups,
    risk_flags:
      person.relationship_confidence === "unconfirmed"
        ? ["Relationship needs human confirmation."]
        : [],
    next_action: person.role
      ? "Review the person profile and attach the confirmed business timeline."
      : "Confirm the company role from registry documents.",
    relationship_confidence: person.relationship_confidence,
  }));
}

function getNextBestActions(
  map: TaxCompanyPilotMap,
): TaxCompanyPilotNextAction[] {
  if (map.next_best_actions?.length) return map.next_best_actions;

  return map.gaps.map((gap) => ({
    owner:
      gap.code.includes("tax") || gap.code.includes("family") ? "tax" : "setup",
    label: gap.label,
    reason: `Needed before ${map.company.name} can become a clean person-first workspace.`,
    severity: gap.severity,
  }));
}

function CompanyPilotPanel({ map }: { map: TaxCompanyPilotMap }) {
  const documentsByGroup = groupDocuments(map.documents);
  const companyStatus = getCompanyStatus(map);
  const personDossiers = getPersonDossiers(map);
  const nextBestActions = getNextBestActions(map);
  const businessStory =
    map.business_story?.length > 0 ? map.business_story : map.ai_recap;

  return (
    <article className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <header className="grid gap-4 border-b border-slate-200 bg-slate-50 p-4 lg:grid-cols-[1fr_240px]">
        <div className="min-w-0">
          <p className="mb-2 text-xs font-semibold uppercase text-emerald-700">
            {companyStatus}
          </p>
          <h2 className="text-xl font-semibold text-slate-950">
            {map.company.name}
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            {map.company.aliases.join(" · ")}
          </p>
        </div>
        <div className="border-l border-slate-200 pl-4 text-sm">
          <p className="text-[11px] font-semibold uppercase text-slate-500">
            Tax owner
          </p>
          <p className="font-semibold text-slate-950">{map.tax_member.name}</p>
          <p className="mt-1 text-xs text-slate-500">
            {map.tax_member.workspace_branch}
          </p>
        </div>
      </header>

      <div className="grid gap-6 p-4 lg:grid-cols-[1fr_1.05fr]">
        <section>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-950">
            <UserRound size={16} />
            Person entry
          </div>
          <div className="divide-y divide-slate-100">
            {personDossiers.map((dossier) => (
              <div
                key={dossier.person_name}
                className="py-3 first:pt-0 last:pb-0"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-slate-950">
                      {dossier.person_name}
                    </p>
                    <p className="mt-1 text-sm leading-5 text-slate-600">
                      {dossier.headline}
                    </p>
                  </div>
                  {dossier.drive_folder_url && (
                    <a
                      aria-label={`Open ${dossier.person_name} in Drive`}
                      href={dossier.drive_folder_url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-900"
                    >
                      <ExternalLink size={15} />
                    </a>
                  )}
                </div>
                <p className="mt-2 text-xs font-medium text-emerald-800">
                  {dossier.next_action}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {dossier.document_groups.map((item) => (
                    <span
                      key={`${dossier.person_name}-${item}`}
                      className="rounded bg-slate-100 px-2 py-1 text-[11px] text-slate-600"
                    >
                      {item}
                    </span>
                  ))}
                </div>
                {dossier.risk_flags.length > 0 && (
                  <ul className="mt-2 space-y-1 text-xs leading-5 text-amber-800">
                    {dossier.risk_flags.map((flag) => (
                      <li key={`${dossier.person_name}-${flag}`}>{flag}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </section>

        <section>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-950">
            <Sparkles size={16} />
            Business story
          </div>
          <ul className="space-y-2 text-sm leading-6 text-slate-700">
            {businessStory.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <div className="mt-4 border-l-2 border-emerald-600 bg-emerald-50 px-3 py-2 text-sm text-emerald-950">
            <div className="mb-1 flex items-center gap-2 font-semibold">
              <ShieldCheck size={15} />
              Internal review
            </div>
            <p>
              Team members can open Drive evidence here; client portal access
              remains limited to approved document downloads.
            </p>
          </div>
        </section>
      </div>

      <section className="border-t border-slate-200 px-4 py-4">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-950">
          <ListChecks size={16} />
          Next best actions
        </div>
        <div className="grid gap-2 md:grid-cols-3">
          {nextBestActions.map((action) => (
            <div
              key={`${action.owner}-${action.label}`}
              className={`rounded-md border px-3 py-2 text-sm ${severityClass[action.severity]}`}
            >
              <p className="text-[11px] font-semibold uppercase">
                {actionOwnerLabel[action.owner]}
              </p>
              <p className="mt-1 font-medium">{action.label}</p>
              <p className="mt-1 text-xs leading-5 opacity-85">
                {action.reason}
              </p>
            </div>
          ))}
        </div>
      </section>

      <div className="grid gap-6 border-t border-slate-200 px-4 py-4 lg:grid-cols-[1.1fr_0.9fr]">
        <section>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-950">
            <FileText size={16} />
            Key company records
          </div>
          <div className="space-y-3">
            {Object.entries(documentsByGroup).map(([group, documents]) => (
              <div
                key={group}
                className="border-l-2 border-slate-200 bg-slate-50 px-3 py-2"
              >
                <p className="mb-2 text-xs font-semibold uppercase text-slate-500">
                  {group}
                </p>
                <div className="flex flex-wrap gap-2">
                  {documents.map((document) => (
                    <a
                      key={`${group}-${document.name}`}
                      href={document.evidence_url ?? "#"}
                      target={document.evidence_url ? "_blank" : undefined}
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 rounded-md bg-white px-2 py-1 text-xs text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100 hover:text-slate-950"
                    >
                      {document.name}
                      {document.sensitivity === "financial" ||
                      document.sensitivity === "credential" ? (
                        <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-800">
                          {document.sensitivity}
                        </span>
                      ) : null}
                    </a>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-950">
            <AlertTriangle size={16} />
            Open decisions
          </div>
          <div className="space-y-2">
            {map.gaps.map((gap) => (
              <div
                key={gap.code}
                className={`rounded-md border px-3 py-2 text-sm ${severityClass[gap.severity]}`}
              >
                <p className="text-[11px] font-semibold uppercase">
                  {severityLabel[gap.severity]}
                </p>
                <p className="mt-1">{gap.label}</p>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="grid gap-4 border-t border-slate-200 p-4 lg:grid-cols-[1fr_auto]">
        <div>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-950">
            <BriefcaseBusiness size={16} />
            Folder cleanup
          </div>
          <div className="space-y-2">
            {map.duplicate_candidates.map((candidate) => (
              <div
                key={candidate.label}
                className="border-l-2 border-slate-200 px-3 py-1.5"
              >
                <p className="text-sm text-slate-900">{candidate.label}</p>
                <p className="mt-1 text-xs text-slate-500">
                  Keep one client-facing source of truth before creating team
                  shortcuts.
                </p>
              </div>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap content-start gap-2 lg:max-w-[280px]">
          {map.evidence_links.map((link) => (
            <a
              key={link.url}
              href={link.url}
              target="_blank"
              rel="noreferrer"
              aria-label={`Open ${link.label} in Drive`}
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 hover:text-slate-950"
            >
              <Link2 size={13} />
              {link.label}
              <ExternalLink size={13} />
            </a>
          ))}
        </div>
      </section>
    </article>
  );
}

export function TaxCompanyPilotWorkspace({
  maps,
}: {
  maps: TaxCompanyPilotMap[];
}) {
  const totalPeople = maps.reduce((sum, map) => sum + map.persons.length, 0);
  const totalDocuments = maps.reduce(
    (sum, map) => sum + map.documents.length,
    0,
  );
  const highGaps = maps.reduce(
    (sum, map) =>
      sum + map.gaps.filter((gap) => gap.severity === "high").length,
    0,
  );
  const openDecisions = maps.reduce((sum, map) => sum + map.gaps.length, 0);

  return (
    <section className="min-h-screen bg-[#f4f6f1] px-4 py-5 text-slate-950 md:px-6">
      <header className="mb-5 flex flex-col gap-4 border-b border-slate-200 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-emerald-700">
            CRM tax workspace
          </p>
          <h1 className="mt-1 text-2xl font-semibold md:text-3xl">
            Person-first intelligence desk
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Start from each person, then review the company, tax owner, records,
            Drive evidence, and decisions behind them.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-right md:grid-cols-4">
          <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
            <p className="text-xl font-semibold">{maps.length}</p>
            <p className="text-[11px] uppercase text-slate-500">
              Companies under review
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
            <p className="text-xl font-semibold">{totalPeople}</p>
            <p className="text-[11px] uppercase text-slate-500">
              People connected
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
            <p className="text-xl font-semibold">{totalDocuments}</p>
            <p className="text-[11px] uppercase text-slate-500">
              Records mapped
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
            <p className="text-xl font-semibold">{openDecisions}</p>
            <p className="text-[11px] uppercase text-slate-500">
              Open decisions
            </p>
            {highGaps > 0 && (
              <p className="mt-1 text-[10px] text-red-700">{highGaps} urgent</p>
            )}
          </div>
        </div>
      </header>
      <div className="grid gap-4 xl:grid-cols-2">
        {maps.map((map, index) => (
          <CompanyPilotPanel
            key={`${map.key}-${map.company.name}-${index}`}
            map={map}
          />
        ))}
      </div>
    </section>
  );
}
