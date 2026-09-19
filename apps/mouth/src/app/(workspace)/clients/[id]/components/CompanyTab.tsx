"use client";

import React, { useState, useEffect } from "react";
import { Copy, Edit2, Loader2, Plus, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import type {
  ClientProfile,
  ClientDocument,
  CompanyDocument,
} from "@/lib/api/crm/crm.types";
import {
  CellStack,
  EmptyState,
  EYEBROW,
  FOCUS,
  HairlineBody,
  HairlineGrid,
  HairlineHead,
  HairlineRow,
  LedgerSection,
  Numeral,
  StatePill,
  TABULAR,
  type PillTone,
} from "@/components/workspace/r19";
import {
  companyTypeSubtitles,
  computeAge,
  formatCapital,
  formatCapitalFull,
  getInitials,
} from "@/components/portal/company/editorial-tokens";
import {
  COMPANY_TYPE_OPTIONS,
  normalizeCompanyType,
} from "./company/companyType";
import { CompanyDocUpload } from "./company/CompanyDocUpload";
import { EditCompanyModal } from "./company/EditCompanyModal";
import { AddCompanyModal } from "./modals/AddCompanyModal";

/** 7 common KBLI codes' English titles — real static reference data, kept
 * verbatim from the old `KBLIEditorial.tsx`, not a per-record fabrication. */
const KBLI_ENGLISH: Record<string, string> = {
  "68110": "Real Estate Activities — Own or Leased",
  "70209": "Other Management Consulting Activities",
  "56101": "Restaurant",
  "47111": "Retail Trade in Mini Markets",
  "46100": "Wholesale Trade on a Fee or Contract Basis",
  "62011": "Computer Programming Activities",
  "73100": "Advertising",
};

const DOC_VAULT_SLOTS = [
  { docType: "akta_pendirian", label: "Akta Pendirian", hint: "PDF/JPG" },
  { docType: "sk_decree", label: "SK Kemenkumham", hint: "PDF/JPG" },
  { docType: "npwp", label: "NPWP Perusahaan", hint: "PDF/JPG" },
  { docType: "nib", label: "NIB", hint: "PDF/JPG" },
  { docType: "company_profile", label: "Company Profile", hint: "PDF" },
  { docType: "wlkp", label: "WLKP", hint: "PDF" },
  { docType: "bpjs", label: "BPJS Ketenagakerjaan", hint: "PDF" },
  { docType: "organogram", label: "Bagan Organisasi", hint: "PDF/JPG" },
  { docType: "rekening_koran", label: "Rekening Koran", hint: "PDF" },
];

/** Real `company_status` word for every value the field can carry — the old
 * chip only covered active/in_setup/dormant and rendered NOTHING for
 * "dissolved" (a gap, not a design choice); this closes it with the same
 * field, never a guess. */
function companyStatusPill(status: string): { tone: PillTone; label: string } {
  if (status === "active") return { tone: "ok", label: "Active" };
  if (status === "in_setup") return { tone: "wait", label: "In Setup" };
  if (status === "dormant") return { tone: "wait", label: "Dormant" };
  if (status === "dissolved") return { tone: "wait", label: "Dissolved" };
  return { tone: "wait", label: status };
}

/** Same `custom_fields` shape three old sub-components each parsed on their
 * own (authorized capital, shareholder count, OCR shareholder list) —
 * consolidated into one parse, same try/catch-swallow behaviour. */
function parseCustomFields(
  raw: Record<string, unknown> | string | undefined,
): Record<string, unknown> {
  try {
    const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
    return parsed && typeof parsed === "object"
      ? (parsed as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

/** Ownership % is a share of the COMPANY: the record's `shares_count` is the
 * denominator whenever it exists, and the sum of the OCR'd rows only stands
 * in when it does not — same priority the old `PeopleColumn` applied. */
function parseOcrShareholders(
  cf: Record<string, unknown>,
  totalShares?: number,
): Array<{ name?: string; role: string; shares?: number; pct?: number }> {
  try {
    const sh = cf.shareholders;
    if (!sh) return [];
    const parsed = typeof sh === "string" ? JSON.parse(sh) : sh;
    if (!Array.isArray(parsed) || parsed.length === 0) return [];
    const total =
      totalShares ||
      parsed.reduce(
        (sum: number, s: { shares?: number }) => sum + (s.shares || 0),
        0,
      );
    return parsed.map(
      (s: { name?: string; role?: string; shares?: number }) => ({
        name: s.name,
        role: s.role?.toLowerCase() || "shareholder",
        shares: s.shares,
        pct:
          total > 0 && s.shares
            ? Math.round((s.shares / total) * 100 * 10) / 10
            : undefined,
      }),
    );
  } catch {
    return [];
  }
}

function KvItem({
  label,
  value,
  sub,
  action,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className={EYEBROW}>{label}</span>
      <span className="flex items-center gap-1.5 text-[15px] font-semibold text-[var(--tx-pure)]">
        <span style={TABULAR}>{value}</span>
        {action}
      </span>
      {sub ? (
        <span className="text-[12px] text-[var(--tx-secondary)]">{sub}</span>
      ) : null}
    </div>
  );
}

function CopyButton({ value, field }: { value: string; field: string }) {
  return (
    <button
      type="button"
      aria-label={`Copy ${field}`}
      onClick={() => {
        void navigator.clipboard.writeText(value);
        toast.success("Copied");
      }}
      className={cn(
        "inline-flex h-6 w-6 items-center justify-center text-[var(--tx-secondary)] hover:text-[var(--tx-pure)]",
        FOCUS,
      )}
    >
      <Copy className="h-3 w-3" aria-hidden="true" />
    </button>
  );
}

const KV_GRID =
  "grid grid-cols-1 gap-x-8 gap-y-5 py-5 sm:grid-cols-2 lg:grid-cols-3";

// ============================================
// COMPANY TAB (main export)
// ============================================
export function CompanyTab({
  clientId,
  client,
  documents,
  formatDate,
  onRefresh,
}: {
  clientId: number;
  client: ClientProfile["client"];
  documents: ClientDocument[];
  formatDate: (d: string) => string;
  onRefresh: () => Promise<void>;
}) {
  const pmaDocs = documents.filter((d) => d.document_category === "pma");

  const [companyData, setCompanyData] = useState<{
    company_name: string;
    company_type: string;
    kbli_code?: string;
    kbli_description?: string;
    nib?: string;
    npwp_company?: string;
    akta_pendirian_no?: string;
    akta_pendirian_date?: string;
    akta_perubahan_no?: string;
    akta_perubahan_date?: string;
    sk_menhumkam_no?: string;
    sk_menhumkam_date?: string;
    registered_address?: string;
    office_address?: string;
    city?: string;
    province?: string;
    company_status?: string;
    shares_count?: number;
    share_nominal_value?: number;
    setup_progress?: number;
    company_id?: number;
    custom_fields?: Record<string, unknown>;
  } | null>(null);

  const [associates, setAssociates] = useState<
    Array<{
      client_name?: string;
      role: string;
      ownership_percentage?: number;
      shares_count?: number;
    }>
  >([]);

  const [companyDocs, setCompanyDocs] = useState<CompanyDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isEditingCompany, setIsEditingCompany] = useState(false);
  const [isAddingCompany, setIsAddingCompany] = useState(false);
  const [isSyncingDrive, setIsSyncingDrive] = useState(false);
  const [reloadTrigger, setReloadTrigger] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function loadCompanyData() {
      try {
        // Step 1: Try linked companies
        const linked = await api.crm.getClientCompanies(clientId);
        if (!cancelled && linked.length > 0) {
          const co = linked[0];
          setCompanyData({
            company_name: co.company_name,
            company_type: co.company_type,
            kbli_code: co.kbli_code,
            kbli_description: co.kbli_description,
            nib: co.nib,
            npwp_company: co.npwp_company,
            akta_pendirian_no: co.akta_pendirian_no,
            akta_pendirian_date: co.akta_pendirian_date,
            akta_perubahan_no: co.akta_perubahan_no,
            akta_perubahan_date: co.akta_perubahan_date,
            sk_menhumkam_no: co.sk_menhumkam_no,
            sk_menhumkam_date: co.sk_menhumkam_date,
            registered_address: co.registered_address,
            office_address: co.office_address,
            city: co.city,
            province: co.province,
            company_status: co.company_status,
            shares_count: co.shares_count,
            share_nominal_value: co.share_nominal_value,
            setup_progress: co.setup_progress,
            company_id: co.company_id,
            custom_fields: co.custom_fields,
          });

          if (co.company_id) {
            api.crm
              .getCompany(co.company_id)
              .then((full) => {
                if (cancelled) return;
                if (full.associates?.length) {
                  const grouped = new Map<
                    string,
                    {
                      client_name?: string;
                      roles: string[];
                      ownership_percentage?: number;
                      shares_count?: number;
                    }
                  >();
                  for (const a of full.associates) {
                    const key = a.client_name || "unknown";
                    if (!grouped.has(key)) {
                      grouped.set(key, {
                        client_name: a.client_name,
                        roles: [],
                        ownership_percentage: a.ownership_percentage,
                        shares_count: a.shares_count,
                      });
                    }
                    const entry = grouped.get(key)!;
                    if (a.role && !entry.roles.includes(a.role))
                      entry.roles.push(a.role);
                    if (
                      a.shares_count &&
                      (!entry.shares_count ||
                        a.shares_count > entry.shares_count)
                    )
                      entry.shares_count = a.shares_count;
                    if (
                      a.ownership_percentage &&
                      (!entry.ownership_percentage ||
                        a.ownership_percentage > entry.ownership_percentage)
                    )
                      entry.ownership_percentage = a.ownership_percentage;
                  }
                  const groupedAssociates = Array.from(grouped.values()).map(
                    (g) => ({
                      client_name: g.client_name,
                      role: g.roles.join(" / "),
                      ownership_percentage: g.ownership_percentage,
                      shares_count: g.shares_count,
                    }),
                  );
                  setAssociates(groupedAssociates);
                  const totalShares = groupedAssociates.reduce(
                    (sum, a) => sum + (a.shares_count || 0),
                    0,
                  );
                  if (totalShares > 0) {
                    setCompanyData((prev) =>
                      prev ? { ...prev, shares_count: totalShares } : prev,
                    );
                  }
                } else {
                  setAssociates([
                    {
                      client_name: client.full_name,
                      role: co.role,
                      ownership_percentage: co.ownership_percentage,
                      shares_count: co.shares_count,
                    },
                  ]);
                }
                if (full.documents?.length) setCompanyDocs(full.documents);
              })
              .catch((err) => {
                logger.error(
                  "[CompanyTab] Failed to load company details",
                  {},
                  err instanceof Error ? err : new Error(String(err)),
                );
                setAssociates([
                  {
                    client_name: client.full_name,
                    role: co.role,
                    ownership_percentage: co.ownership_percentage,
                    shares_count: co.shares_count,
                  },
                ]);
              });
          } else {
            setAssociates([
              {
                client_name: client.full_name,
                role: co.role,
                ownership_percentage: co.ownership_percentage,
                shares_count: co.shares_count,
              },
            ]);
          }
          return;
        }

        // Step 2: Fallback — search by client.company_name
        if (client.company_name) {
          const found = await api.crm.searchCompanyByName(client.company_name);
          if (!cancelled && found) {
            setCompanyData({
              company_name: found.company_name,
              company_type: found.company_type,
              kbli_code: found.kbli_code,
              kbli_description: found.kbli_description,
              nib: found.nib,
              npwp_company: found.npwp_company,
              akta_pendirian_no: found.akta_pendirian_no,
              akta_pendirian_date: found.akta_pendirian_date,
              akta_perubahan_no: found.akta_perubahan_no,
              akta_perubahan_date: found.akta_perubahan_date,
              sk_menhumkam_no: found.sk_menhumkam_no,
              sk_menhumkam_date: found.sk_menhumkam_date,
              registered_address: found.registered_address,
              office_address: found.office_address,
              city: found.city,
              province: found.province,
              company_status: found.status,
              company_id: found.id,
              custom_fields: found.custom_fields,
            });
            if (found.associates?.length) {
              const grouped2 = new Map<
                string,
                {
                  client_name?: string;
                  roles: string[];
                  ownership_percentage?: number;
                  shares_count?: number;
                }
              >();
              for (const a of found.associates) {
                const key = a.client_name || "unknown";
                if (!grouped2.has(key)) {
                  grouped2.set(key, {
                    client_name: a.client_name,
                    roles: [],
                    ownership_percentage: a.ownership_percentage,
                    shares_count: a.shares_count,
                  });
                }
                const entry = grouped2.get(key)!;
                if (a.role && !entry.roles.includes(a.role))
                  entry.roles.push(a.role);
                if (
                  a.shares_count &&
                  (!entry.shares_count || a.shares_count > entry.shares_count)
                )
                  entry.shares_count = a.shares_count;
                if (
                  a.ownership_percentage &&
                  (!entry.ownership_percentage ||
                    a.ownership_percentage > entry.ownership_percentage)
                )
                  entry.ownership_percentage = a.ownership_percentage;
              }
              const groupedAssociates2 = Array.from(grouped2.values()).map(
                (g) => ({
                  client_name: g.client_name,
                  role: g.roles.join(" / "),
                  ownership_percentage: g.ownership_percentage,
                  shares_count: g.shares_count,
                }),
              );
              setAssociates(groupedAssociates2);
              const totalShares2 = groupedAssociates2.reduce(
                (sum, a) => sum + (a.shares_count || 0),
                0,
              );
              if (totalShares2 > 0) {
                setCompanyData((prev) =>
                  prev ? { ...prev, shares_count: totalShares2 } : prev,
                );
              }
            }
            api.crm
              .getCompanyDocuments(found.id)
              .then((docs) => !cancelled && setCompanyDocs(docs))
              .catch((err) => {
                logger.error(
                  "[CompanyTab] Failed to load company documents",
                  {},
                  err instanceof Error ? err : new Error(String(err)),
                );
              });
            return;
          }
        }
      } catch (err) {
        if (!cancelled) {
          toast.error("Failed to load company data", {
            description: (err as Error).message,
          });
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    loadCompanyData();
    return () => {
      cancelled = true;
    };
  }, [clientId, client.company_name, client.full_name, reloadTrigger]);

  // ── LOADING ────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-[var(--tx-secondary)]" />
      </div>
    );
  }

  // ── EMPTY STATE ────────────────────────────────────────────────────────
  const hasCompanyName = !!client.company_name;
  const hasAnyDoc = pmaDocs.length > 0;

  if (!companyData && !hasCompanyName && !hasAnyDoc) {
    return (
      <>
        <EmptyState
          action={
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => setIsAddingCompany(true)}
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              Add company
            </Button>
          }
        >
          No company linked yet.
        </EmptyState>
        {isAddingCompany && (
          <AddCompanyModal
            clientId={clientId}
            onClose={() => setIsAddingCompany(false)}
            onSuccess={() => {
              setIsAddingCompany(false);
              setReloadTrigger((t) => t + 1);
              void onRefresh();
            }}
          />
        )}
      </>
    );
  }

  // ── DERIVED DATA ───────────────────────────────────────────────────────
  const co = companyData;
  const companyName = co?.company_name || client.company_name || "Company";
  const companyTypeRaw = co?.company_type || "";
  const normalizedType = normalizeCompanyType(companyTypeRaw);
  const companyTypeOption = COMPANY_TYPE_OPTIONS.find(
    (o) => o.value === normalizedType,
  );
  const companyTypeLabel = companyTypeRaw
    ? companyTypeOption?.label || companyTypeRaw
    : "—";
  // Indonesian expansion of the entity type, keyed on the stored value first
  // and on its canonical form second, so a legacy `PT_PMA` row keeps its gloss.
  const companyTypeSubtitle = companyTypeRaw
    ? companyTypeSubtitles[companyTypeRaw] ||
      companyTypeSubtitles[normalizedType]
    : undefined;
  const isPMA = companyTypeRaw === "PT PMA" || companyTypeRaw === "PMA";
  const capital = formatCapital(co?.shares_count, co?.share_nominal_value);

  const customFields = parseCustomFields(co?.custom_fields);
  const capitalFull =
    formatCapitalFull(co?.shares_count, co?.share_nominal_value) ||
    (() => {
      const authCap = customFields.authorized_capital;
      if (authCap) {
        const num = Number(authCap);
        if (!isNaN(num) && num > 0) return `Rp ${num.toLocaleString("id-ID")}`;
      }
      return null;
    })();

  const ocrShareholders = parseOcrShareholders(customFields, co?.shares_count);
  const people =
    ocrShareholders.length > associates.length
      ? ocrShareholders.map((s) => ({
          name: s.name,
          role: s.role,
          shares: s.shares,
          pct: s.pct,
        }))
      : associates.map((a) => ({
          name: a.client_name,
          role: a.role,
          shares: a.shares_count,
          pct: a.ownership_percentage,
        }));
  const shareholderCount = people.length;

  // If pendirian fields are identical to perubahan, treat pendirian as absent
  const pendirianIsDuplicate =
    co?.akta_pendirian_no &&
    co?.akta_pendirian_no === co?.akta_perubahan_no &&
    co?.akta_pendirian_date === co?.akta_perubahan_date;
  const effectivePendirianNo = pendirianIsDuplicate
    ? undefined
    : co?.akta_pendirian_no;
  const effectivePendirianDate = pendirianIsDuplicate
    ? undefined
    : co?.akta_pendirian_date;

  const foundingDate = effectivePendirianDate || co?.sk_menhumkam_date;
  const age = computeAge(foundingDate);

  const streetAddress = co?.registered_address || co?.office_address;
  const cityProvince = [co?.city, co?.province].filter(Boolean).join(", ");

  // Merge docs for count
  const allDocs = [
    ...pmaDocs.map((d) => ({
      key: `client-${d.id}`,
      name: d.file_name || d.document_type,
    })),
    ...companyDocs
      .filter((cd) => cd.google_drive_file_url || cd.google_drive_file_id)
      .map((cd) => ({
        key: `company-${cd.id}`,
        name: cd.file_name || cd.document_type,
      })),
  ];

  const hasLegalData =
    effectivePendirianNo || co?.akta_perubahan_no || co?.sk_menhumkam_no;

  const hasCapitalFacts =
    capitalFull || co?.shares_count || foundingDate || co?.akta_perubahan_no;

  const kbliCodes = co?.kbli_code
    ? co.kbli_code.split(",").map((c) => c.trim())
    : [];
  const kbliDescriptions = (co?.kbli_description || "")
    .split(";")
    .map((d) => d.trim());

  // Legal timeline entries — same push order as the old component (amendment,
  // NIB/OSS, incorporation), never re-sorted by date.
  const legalEntries: Array<{
    key: string;
    kind: string;
    title: string;
    body: string;
    refText?: string;
    date?: string;
  }> = [];
  if (co?.akta_perubahan_no && co?.akta_perubahan_date) {
    legalEntries.push({
      key: "amendment",
      kind: "Akta Perubahan · Corporate Amendment",
      title: `Revision #${co.akta_perubahan_no}`,
      body: `Amendment filed with Kemenkumham.${capital ? ` Authorized capital updated to ${capital}.` : ""}`,
      refText: `Akta Perubahan #${co.akta_perubahan_no}`,
      date: co.akta_perubahan_date,
    });
  }
  if (co?.nib) {
    legalEntries.push({
      key: "nib",
      kind: "Regulatory · OSS Compliance",
      title: "NIB Issued & OSS Platform Verified",
      body: `Registered on the Online Single Submission (OSS) platform.${co.npwp_company ? ` NPWP ${co.npwp_company} completed.` : ""}`,
      refText: `NIB ${co.nib}${co.npwp_company ? ` · NPWP ${co.npwp_company}` : ""}`,
    });
  }
  if (effectivePendirianNo && effectivePendirianDate) {
    legalEntries.push({
      key: "incorporation",
      kind: "Incorporation · Company Formation",
      title: `${companyName} Established`,
      body: `Incorporated as a Perseroan Terbatas${isPMA ? " under the PMA regime (foreign direct investment)" : ""}.${co?.sk_menhumkam_no ? " Approved by the Ministry of Law and Human Rights." : ""}`,
      refText: co?.sk_menhumkam_no,
      date: effectivePendirianDate,
    });
  } else if (co?.sk_menhumkam_no && co?.sk_menhumkam_date) {
    legalEntries.push({
      key: "incorporation-sk",
      kind: "Incorporation · Company Formation",
      title: `${companyName} Established`,
      body: "Incorporated and approved by Kemenkumham.",
      refText: co.sk_menhumkam_no,
      date: co.sk_menhumkam_date,
    });
  }

  const editAction = co?.company_id ? (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="h-8 w-8 text-[var(--tx-secondary)] hover:text-[var(--tx-pure)]"
      aria-label="Edit company"
      title="Edit company"
      onClick={() => setIsEditingCompany(true)}
    >
      <Edit2 className="h-4 w-4" />
    </Button>
  ) : null;

  const syncDriveAction = co?.company_id ? (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="gap-1.5"
      disabled={isSyncingDrive}
      onClick={async () => {
        setIsSyncingDrive(true);
        try {
          const res = (await api.post(
            `/api/crm/companies/${co.company_id}/sync-drive`,
            {},
          )) as { added: number; skipped: number; total_in_folder: number };
          toast.success(
            `Drive sync: ${res.added} added, ${res.skipped} skipped`,
            {
              description: `${res.total_in_folder} files in folder`,
            },
          );
          if (res.added > 0) {
            setReloadTrigger((t) => t + 1);
            void onRefresh();
          }
        } catch (err) {
          toast.error("Drive sync failed", {
            description: (err as Error).message,
          });
        } finally {
          setIsSyncingDrive(false);
        }
      }}
    >
      {isSyncingDrive ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
      )}
      Sync Drive
    </Button>
  ) : null;

  const addCompanyAction = (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="gap-1.5"
      onClick={() => setIsAddingCompany(true)}
    >
      <Plus className="h-3.5 w-3.5" aria-hidden="true" />
      Add company
    </Button>
  );

  // ── RENDER ─────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-8">
      <LedgerSection
        n={1}
        tone={co ? "done" : "wait"}
        title="Company identity"
        actions={
          <>
            {editAction}
            {syncDriveAction}
            {addCompanyAction}
          </>
        }
      >
        <div className={KV_GRID}>
          <KvItem label="Legal name" value={companyName} />
          <KvItem
            label="Company type"
            value={companyTypeLabel}
            sub={companyTypeSubtitle}
          />
          <KvItem
            label="NIB"
            value={co?.nib || "—"}
            sub={
              co?.nib
                ? "Nomor Induk Berusaha · OSS registered"
                : "Nomor Induk Berusaha"
            }
            action={co?.nib ? <CopyButton value={co.nib} field="NIB" /> : null}
          />
          <KvItem
            label="NPWP"
            value={co?.npwp_company || "—"}
            sub="Tax Identification Number"
            action={
              co?.npwp_company ? (
                <CopyButton value={co.npwp_company} field="NPWP" />
              ) : null
            }
          />
          <KvItem
            label="KBLI"
            value={kbliCodes[0] || "—"}
            sub={kbliDescriptions[0] || undefined}
          />
          <KvItem
            label="Registered address"
            value={streetAddress || cityProvince || "—"}
            sub={streetAddress && cityProvince ? cityProvince : undefined}
          />
        </div>
        {co ? (
          <div className="pb-4">
            <StatePill {...companyStatusPill(co.company_status || "active")} />
          </div>
        ) : null}
      </LedgerSection>

      {hasCapitalFacts && (
        <LedgerSection n={2} title="Capital & shares">
          <div className={KV_GRID}>
            {capitalFull && (
              <KvItem
                label="Authorized capital"
                value={capitalFull}
                sub={
                  co?.akta_perubahan_no
                    ? `IDR · Increased via Akta #${co.akta_perubahan_no}${co.akta_perubahan_date ? ` · ${formatDate(co.akta_perubahan_date)}` : ""}`
                    : "IDR"
                }
              />
            )}
            {co?.shares_count ? (
              <KvItem
                label="Share structure"
                value={`${co.shares_count.toLocaleString()} shares`}
                sub={
                  co.share_nominal_value
                    ? `Rp ${(co.share_nominal_value / 1e6).toFixed(0)},000,000 par value per share`
                    : undefined
                }
              />
            ) : null}
            {foundingDate ? (
              <KvItem
                label="Incorporation date"
                value={formatDate(foundingDate)}
                sub={[co?.sk_menhumkam_no, age ? `${age.label} old` : undefined]
                  .filter(Boolean)
                  .join(" · ")}
              />
            ) : null}
            {co?.akta_perubahan_no ? (
              <KvItem
                label="Last amendment"
                value={`Akta #${co.akta_perubahan_no}`}
                sub={
                  co.akta_perubahan_date
                    ? `${formatDate(co.akta_perubahan_date)} · Capital restructuring`
                    : undefined
                }
              />
            ) : null}
          </div>
        </LedgerSection>
      )}

      {shareholderCount > 0 && (
        <LedgerSection
          n={3}
          title={
            <span className="flex items-baseline gap-2">
              Shareholders &amp; officers{" "}
              <Numeral n={shareholderCount} size="count" />
            </span>
          }
        >
          <HairlineGrid cols="minmax(12rem,1.8fr) minmax(8rem,1fr) minmax(6rem,0.7fr) minmax(6rem,0.7fr)">
            <HairlineHead>
              <span>Person</span>
              <span>Role</span>
              <span>Shares</span>
              <span>Ownership</span>
            </HairlineHead>
            <HairlineBody>
              {people.map((person, i) => {
                const name = person.name || client.full_name || "?";
                return (
                  <HairlineRow key={`${name}-${i}`}>
                    <div className="min-w-0 px-2.5">
                      <CellStack
                        primary={
                          <span className="flex min-w-0 items-center gap-3">
                            <span
                              aria-hidden="true"
                              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[6px] bg-[var(--bz-card)] text-xs text-[var(--tx-pure)]"
                            >
                              {getInitials(name)}
                            </span>
                            <span className="truncate">{name}</span>
                          </span>
                        }
                      />
                    </div>
                    <span className="truncate px-2.5 capitalize text-[var(--tx-pure)]">
                      {person.role || "Shareholder"}
                    </span>
                    <span className="px-2.5" style={TABULAR}>
                      {person.shares != null
                        ? person.shares.toLocaleString()
                        : "—"}
                    </span>
                    <span className="px-2.5" style={TABULAR}>
                      {person.pct != null ? `${person.pct}%` : "—"}
                    </span>
                  </HairlineRow>
                );
              })}
            </HairlineBody>
          </HairlineGrid>
        </LedgerSection>
      )}

      {kbliCodes.length > 0 && (
        <LedgerSection n={4} title="Business activities">
          <HairlineGrid cols="96px minmax(0,1fr) 110px">
            <HairlineHead>
              <span>Code</span>
              <span>Activity</span>
              <span>Tag</span>
            </HairlineHead>
            <HairlineBody>
              {kbliCodes.map((code, i) => {
                const desc = kbliDescriptions[i] || kbliDescriptions[0] || "";
                const english = KBLI_ENGLISH[code];
                return (
                  <HairlineRow key={code}>
                    <span className="px-2.5 font-semibold" style={TABULAR}>
                      {code}
                    </span>
                    <div className="min-w-0 px-2.5">
                      <CellStack
                        primary={english || desc || `KBLI ${code}`}
                        secondary={english ? desc : undefined}
                      />
                    </div>
                    <span className="px-2.5">
                      <StatePill
                        tone={i === 0 ? "ink" : "wait"}
                        label={i === 0 ? "Primary" : "Secondary"}
                      />
                    </span>
                  </HairlineRow>
                );
              })}
            </HairlineBody>
          </HairlineGrid>
        </LedgerSection>
      )}

      {hasLegalData && (
        <LedgerSection n={5} title="Legal timeline">
          <HairlineGrid cols="minmax(10rem,1.2fr) minmax(14rem,2fr) 110px">
            <HairlineHead>
              <span>Event</span>
              <span>Detail</span>
              <span>Date</span>
            </HairlineHead>
            <HairlineBody>
              {legalEntries.map((entry) => (
                <HairlineRow key={entry.key}>
                  <div className="min-w-0 px-2.5">
                    <CellStack primary={entry.title} secondary={entry.kind} />
                  </div>
                  <div className="min-w-0 px-2.5 py-2">
                    <p className="text-[12px] text-[var(--tx-secondary)]">
                      {entry.body}
                    </p>
                    {entry.refText ? (
                      <p
                        className="mt-1 text-[11px] text-[var(--tx-secondary)]"
                        style={TABULAR}
                      >
                        {entry.refText}
                      </p>
                    ) : null}
                  </div>
                  <span className="px-2.5" style={TABULAR}>
                    {entry.date ? formatDate(entry.date) : "—"}
                  </span>
                </HairlineRow>
              ))}
            </HairlineBody>
          </HairlineGrid>
        </LedgerSection>
      )}

      {co?.company_id && (
        <LedgerSection
          n={6}
          title={
            <span className="flex items-baseline gap-2">
              Document vault <Numeral n={allDocs.length} size="count" />
            </span>
          }
        >
          <div className="grid grid-cols-1 gap-3 py-5 sm:grid-cols-2 lg:grid-cols-3">
            {DOC_VAULT_SLOTS.map((item) => {
              // Search company docs first, then client docs with pma category
              const typeNorm = item.docType.toLowerCase().replace(/_/g, "");
              const matchType = (dt: string) => {
                const norm = (dt || "").toLowerCase().replace(/_/g, "");
                return norm === typeNorm || dt === item.docType;
              };
              const fromCompany = companyDocs.find((d) =>
                matchType(d.document_type),
              );
              const fromClient = !fromCompany
                ? (documents || [])
                    .filter((d) => d.document_category === "pma")
                    .find((d) => matchType(d.document_type))
                : null;
              // Map ClientDocument to CompanyDocument-compatible shape for the vault slot
              const existing: CompanyDocument | null =
                fromCompany ??
                (fromClient
                  ? {
                      id: fromClient.id,
                      uuid: "",
                      document_type: fromClient.document_type,
                      status:
                        (fromClient.status as CompanyDocument["status"]) ??
                        "active",
                      google_drive_file_id: fromClient.file_id,
                      google_drive_file_url:
                        fromClient.google_drive_file_url ?? fromClient.file_url,
                      file_name: fromClient.file_name,
                      is_verified: fromClient.status === "verified",
                      created_at: fromClient.created_at ?? "",
                    }
                  : null);
              return (
                <CompanyDocUpload
                  key={item.docType}
                  clientId={clientId}
                  companyId={co.company_id!}
                  companyName={companyName}
                  docType={item.docType}
                  label={item.label}
                  hint={item.hint}
                  existingDoc={existing}
                  onUploaded={() => {
                    setReloadTrigger((t) => t + 1);
                    void onRefresh();
                  }}
                />
              );
            })}
          </div>
        </LedgerSection>
      )}

      {/* ── EDIT MODAL ─────────────────────────────────────────────────── */}
      {isEditingCompany && co?.company_id && (
        <EditCompanyModal
          companyId={co.company_id}
          initialData={co}
          onClose={() => setIsEditingCompany(false)}
          onSave={() => {
            setIsEditingCompany(false);
            setReloadTrigger((t) => t + 1);
          }}
        />
      )}

      {/* ── ADD COMPANY MODAL ──────────────────────────────────────────── */}
      {isAddingCompany && (
        <AddCompanyModal
          clientId={clientId}
          onClose={() => setIsAddingCompany(false)}
          onSuccess={() => {
            setIsAddingCompany(false);
            setReloadTrigger((t) => t + 1);
            void onRefresh();
          }}
        />
      )}
    </div>
  );
}
