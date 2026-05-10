import {
  AlertTriangle,
  Building2,
  ExternalLink,
  FileText,
  Link2,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import type {
  TaxCompanyPilotDocument,
  TaxCompanyPilotGap,
  TaxCompanyPilotMap,
} from "@/lib/api/crm/crm.types";

const severityClass: Record<TaxCompanyPilotGap["severity"], string> = {
  high: "border-red-400/35 bg-red-500/10 text-red-100",
  medium: "border-amber-400/35 bg-amber-500/10 text-amber-100",
  low: "border-sky-400/35 bg-sky-500/10 text-sky-100",
};

const documentGroupLabel: Record<TaxCompanyPilotDocument["group"], string> = {
  company: "Company",
  tax: "Tax",
  lkpm: "LKPM",
  finance: "Finance",
  person: "Person",
  coretax: "Coretax",
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

function CompanyPilotPanel({ map }: { map: TaxCompanyPilotMap }) {
  const documentsByGroup = groupDocuments(map.documents);

  return (
    <article className="rounded-lg border border-white/10 bg-[#111827] p-4 shadow-sm">
      <header className="flex flex-col gap-3 border-b border-white/10 pb-4 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-1 text-[11px] font-semibold text-emerald-200">
              <ShieldCheck size={13} />
              Read-only
            </span>
            <span className="rounded-md bg-white/5 px-2 py-1 text-[11px] text-white/60">
              Confidence: {map.confidence}
            </span>
          </div>
          <h2 className="text-xl font-semibold text-white">
            {map.company.name}
          </h2>
          <p className="mt-1 text-sm text-white/50">
            {map.company.aliases.join(" · ")}
          </p>
        </div>
        <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm">
          <p className="text-[11px] font-semibold uppercase text-white/40">
            Tax member
          </p>
          <p className="font-semibold text-white">{map.tax_member.name}</p>
          <p className="mt-1 text-xs text-white/45">
            {map.tax_member.workspace_branch}
          </p>
        </div>
      </header>

      <div className="grid gap-4 py-4 lg:grid-cols-[1fr_1.15fr]">
        <section>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
            <UserRound size={16} />
            People
          </div>
          <div className="divide-y divide-white/10 rounded-lg border border-white/10">
            {map.persons.map((person) => (
              <div key={person.name} className="p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-white">{person.name}</p>
                    <p className="mt-1 text-xs text-white/45">
                      relationship {person.relationship_confidence}
                      {person.role ? ` · ${person.role}` : ""}
                    </p>
                  </div>
                  {person.folder_url && (
                    <a
                      aria-label={`Open person folder for ${person.name}`}
                      href={person.folder_url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-md p-1.5 text-white/50 hover:bg-white/10 hover:text-white"
                    >
                      <ExternalLink size={15} />
                    </a>
                  )}
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {person.evidence.map((item) => (
                    <span
                      key={item}
                      className="rounded bg-white/5 px-2 py-1 text-[11px] text-white/60"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
            <FileText size={16} />
            Evidence
          </div>
          <div className="space-y-3">
            {Object.entries(documentsByGroup).map(([group, documents]) => (
              <div
                key={group}
                className="rounded-lg border border-white/10 p-3"
              >
                <p className="mb-2 text-xs font-semibold uppercase text-white/45">
                  {group}
                </p>
                <div className="flex flex-wrap gap-2">
                  {documents.map((document) => (
                    <a
                      key={`${group}-${document.name}`}
                      href={document.evidence_url ?? "#"}
                      target={document.evidence_url ? "_blank" : undefined}
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 rounded-md bg-white/5 px-2 py-1 text-xs text-white/70 hover:bg-white/10 hover:text-white"
                    >
                      {document.name}
                      {document.sensitivity === "financial" ||
                      document.sensitivity === "credential" ? (
                        <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] text-amber-100">
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
      </div>

      <section className="grid gap-4 border-t border-white/10 pt-4 lg:grid-cols-2">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
            <AlertTriangle size={16} />
            Gaps
          </div>
          <div className="space-y-2">
            {map.gaps.map((gap) => (
              <p
                key={gap.code}
                className={`rounded-md border px-3 py-2 text-sm ${severityClass[gap.severity]}`}
              >
                {gap.label}
              </p>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
            <Link2 size={16} />
            Duplicate Candidates
          </div>
          <div className="space-y-2">
            {map.duplicate_candidates.map((candidate) => (
              <div
                key={candidate.label}
                className="rounded-md border border-white/10 px-3 py-2"
              >
                <p className="text-sm text-white">{candidate.label}</p>
                <p className="mt-1 text-xs text-white/45">
                  confidence {candidate.confidence}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-4 grid gap-4 border-t border-white/10 pt-4 lg:grid-cols-[1fr_auto]">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
            <Building2 size={16} />
            Recap
          </div>
          <ul className="space-y-2 text-sm text-white/65">
            {map.ai_recap.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div className="flex flex-wrap content-start gap-2 lg:max-w-[260px]">
          {map.evidence_links.map((link) => (
            <a
              key={link.url}
              href={link.url}
              target="_blank"
              rel="noreferrer"
              aria-label={`Open Drive ${link.label}`}
              className="inline-flex items-center gap-1.5 rounded-md border border-white/10 px-2.5 py-1.5 text-xs font-medium text-white/70 hover:bg-white/10 hover:text-white"
            >
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

  return (
    <main className="min-h-screen bg-[#0b1020] px-4 py-5 text-white md:px-6">
      <header className="mb-5 flex flex-col gap-4 border-b border-white/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-300/80">
            CRM tax pilot
          </p>
          <h1 className="mt-1 text-2xl font-semibold md:text-3xl">
            Tax company map
          </h1>
        </div>
        <div className="grid grid-cols-3 gap-2 text-right">
          <div className="rounded-lg border border-white/10 px-3 py-2">
            <p className="text-xl font-semibold">{maps.length}</p>
            <p className="text-[11px] uppercase text-white/40">Companies</p>
          </div>
          <div className="rounded-lg border border-white/10 px-3 py-2">
            <p className="text-xl font-semibold">{totalPeople}</p>
            <p className="text-[11px] uppercase text-white/40">People</p>
          </div>
          <div className="rounded-lg border border-white/10 px-3 py-2">
            <p className="text-xl font-semibold">{totalDocuments}</p>
            <p className="text-[11px] uppercase text-white/40">
              {highGaps} high gaps
            </p>
          </div>
        </div>
      </header>
      <div className="grid gap-4 xl:grid-cols-2">
        {maps.map((map) => (
          <CompanyPilotPanel key={map.key} map={map} />
        ))}
      </div>
    </main>
  );
}
