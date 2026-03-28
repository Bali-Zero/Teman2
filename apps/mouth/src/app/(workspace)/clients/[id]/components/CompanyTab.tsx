"use client";

import React, { useState, useEffect } from "react";
import { Building2, Loader2, Upload } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type {
  ClientProfile,
  ClientDocument,
  CompanyDocument,
} from "@/lib/api/crm/crm.types";

import { formatCapital } from "./company/editorial-tokens";
import { EditorialHero } from "./company/EditorialHero";
import { IdentityRow } from "./company/IdentityRow";
import { FactBoxes } from "./company/FactBoxes";
import { DividerLabel } from "./company/DividerLabel";
import { KeyNumbersColumn } from "./company/KeyNumbersColumn";
import { PeopleColumn } from "./company/PeopleColumn";
import { KBLIEditorial } from "./company/KBLIEditorial";
import { LegalTimeline } from "./company/LegalTimeline";
import { CompanyDocUpload } from "./company/CompanyDocUpload";
import { EditCompanyModal } from "./company/EditCompanyModal";

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
              .catch(() => {
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
              .catch(() => {});
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
        <Loader2 className="w-6 h-6 animate-spin text-[var(--kbli-text-muted)]" />
      </div>
    );
  }

  // ── EMPTY STATE ────────────────────────────────────────────────────────
  const hasCompanyName = !!client.company_name;
  const hasAnyDoc = pmaDocs.length > 0;

  if (!companyData && !hasCompanyName && !hasAnyDoc) {
    return (
      <div className="rounded-xl border border-dashed border-[var(--bz-border)] bg-[var(--bz-surface)]/50 p-12 text-center space-y-2">
        <Building2 className="w-12 h-12 mx-auto text-[var(--bz-text-2)] mb-3 opacity-40" />
        <p className="text-sm font-medium text-[var(--bz-text-1)]">No company linked</p>
        <p className="text-xs text-[var(--bz-text-2)] max-w-xs mx-auto">
          This client has no associated company. Upload a PMA document or link a company from the database to get started.
        </p>
      </div>
    );
  }

  // ── DERIVED DATA ───────────────────────────────────────────────────────
  const co = companyData;
  const companyName = co?.company_name || client.company_name || "Company";
  const companyType = co?.company_type || "";
  const capital = formatCapital(co?.shares_count, co?.share_nominal_value);

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

  const foundingYear = effectivePendirianDate
    ? new Date(effectivePendirianDate).getFullYear()
    : co?.sk_menhumkam_date
      ? new Date(co.sk_menhumkam_date).getFullYear()
      : null;

  const foundingDate = effectivePendirianDate || co?.sk_menhumkam_date;

  const addressStr = [
    co?.registered_address || co?.office_address,
    co?.city,
    co?.province,
  ]
    .filter(Boolean)
    .join(", ");

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

  // ── RENDER ─────────────────────────────────────────────────────────────
  return (
    <div className="max-w-[960px] mx-auto">
      {/* ── EDITORIAL HERO ─────────────────────────────────────────────── */}
      <EditorialHero
        companyName={companyName}
        companyType={companyType}
        companyStatus={co?.company_status}
        nib={co?.nib}
        kbliDescription={co?.kbli_description}
        city={co?.city}
        province={co?.province}
        addressStr={addressStr}
        capital={capital}
        shareholderCount={associates.length}
        foundingYear={foundingYear}
        companyId={co?.company_id}
        onEdit={() => setIsEditingCompany(true)}
      />

      {/* ── IDENTITY ROW (NIB / NPWP / TYPE) ──────────────────────────── */}
      <IdentityRow
        nib={co?.nib}
        npwp={co?.npwp_company}
        companyType={companyType}
      />

      {/* ── FACT BOXES (CAPITAL / AGE / DOCS) ─────────────────────────── */}
      <FactBoxes
        capital={capital}
        aktaPerubahanNo={co?.akta_perubahan_no}
        aktaPerubahanDate={co?.akta_perubahan_date}
        foundingDate={foundingDate}
        documentCount={allDocs.length}
      />

      {/* ── KEY NUMBERS & PEOPLE ───────────────────────────────────────── */}
      {(capital || associates.length > 0) && (
        <>
          <DividerLabel text="Key Numbers & People" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-10 md:gap-16">
            <KeyNumbersColumn
              sharesCount={co?.shares_count}
              shareNominalValue={co?.share_nominal_value}
              capital={capital}
              aktaPerubahanNo={co?.akta_perubahan_no}
              aktaPerubahanDate={co?.akta_perubahan_date}
              foundingDate={foundingDate}
              skNo={co?.sk_menhumkam_no}
              addressStr={addressStr}
              city={co?.city}
              fullAddress={co?.registered_address || co?.office_address}
              formatDate={formatDate}
            />
            <PeopleColumn
              associates={associates}
              fallbackName={client.full_name}
            />
          </div>
        </>
      )}

      {/* ── KBLI BUSINESS ACTIVITIES ───────────────────────────────────── */}
      {co?.kbli_code && (
        <>
          <DividerLabel text="Business Activities" />
          <KBLIEditorial
            kbliCode={co.kbli_code}
            kbliDescription={co.kbli_description}
          />
        </>
      )}

      {/* ── LEGAL TIMELINE ─────────────────────────────────────────────── */}
      {hasLegalData && (
        <>
          <DividerLabel text="Legal Timeline" />
          <LegalTimeline
            aktaPendirianNo={effectivePendirianNo}
            aktaPendirianDate={effectivePendirianDate}
            aktaPerubahanNo={co?.akta_perubahan_no}
            aktaPerubahanDate={co?.akta_perubahan_date}
            skNo={co?.sk_menhumkam_no}
            skDate={co?.sk_menhumkam_date}
            nib={co?.nib}
            npwp={co?.npwp_company}
            companyName={companyName}
            companyType={companyType}
            capital={capital}
            formatDate={formatDate}
          />
        </>
      )}

      {/* ── UPLOAD DOCUMENTS ───────────────────────────────────────────── */}
      {co?.company_id && (
        <>
          <DividerLabel text="Document Vault" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {[
              {
                docType: "akta_pendirian",
                label: "Akta Pendirian",
                hint: "PDF/JPG",
              },
              {
                docType: "sk_decree",
                label: "SK Kemenkumham",
                hint: "PDF/JPG",
              },
              {
                docType: "npwp",
                label: "NPWP Perusahaan",
                hint: "PDF/JPG",
              },
              { docType: "nib", label: "NIB", hint: "PDF/JPG" },
              {
                docType: "company_profile",
                label: "Company Profile",
                hint: "PDF",
              },
            ].map((item) => {
              const existing =
                companyDocs.find((d) => d.document_type === item.docType) ||
                null;
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
        </>
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
    </div>
  );
}
