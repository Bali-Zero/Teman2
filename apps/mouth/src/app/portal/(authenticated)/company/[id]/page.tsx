"use client";

/**
 * Company Detail — Portal (Read-only)
 *
 * Mirrors the workspace CompanyTab layout using the same editorial components
 * (imported from components/portal/company/*). Staff-only edit affordances
 * (EditCompanyModal, DocUpload) are intentionally omitted: shareholders see
 * the same rich view but cannot mutate.
 */

import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { Building2 } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import type { PortalCompany } from "@/lib/api/portal/portal.types";
import {
  PortalBackButton,
  PortalEmptyState,
  PortalPageLoader,
} from "@/components/portal";

// Above-fold components: eager (first paint)
import { EditorialHero } from "@/components/portal/company/EditorialHero";
import { IdentityRow } from "@/components/portal/company/IdentityRow";

// Below-fold components: lazy (loaded after first paint)
// Reduces initial chunk count on /portal/company/[id] — ERR_INSUFFICIENT_RESOURCES mitigation.
const FactBoxes = dynamic(
  () =>
    import("@/components/portal/company/FactBoxes").then((m) => ({
      default: m.FactBoxes,
    })),
  { ssr: false },
);
const DividerLabel = dynamic(
  () =>
    import("@/components/portal/company/DividerLabel").then((m) => ({
      default: m.DividerLabel,
    })),
  { ssr: false },
);
const KeyNumbersColumn = dynamic(
  () =>
    import("@/components/portal/company/KeyNumbersColumn").then((m) => ({
      default: m.KeyNumbersColumn,
    })),
  { ssr: false },
);
const PeopleColumn = dynamic(
  () =>
    import("@/components/portal/company/PeopleColumn").then((m) => ({
      default: m.PeopleColumn,
    })),
  { ssr: false },
);
const LegalTimeline = dynamic(
  () =>
    import("@/components/portal/company/LegalTimeline").then((m) => ({
      default: m.LegalTimeline,
    })),
  { ssr: false },
);

function formatDate(d: string): string {
  if (!d) return "—";
  try {
    return new Date(d).toLocaleDateString("en-GB", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return d;
  }
}

function deriveFoundingYear(aktaDate?: string | null): number | null {
  if (!aktaDate) return null;
  const d = new Date(aktaDate);
  if (Number.isNaN(d.getTime())) return null;
  return d.getFullYear();
}

function extractCity(address?: string): string | undefined {
  if (!address) return undefined;
  // OSS address format: "JALAN ..., KELURAHAN, KECAMATAN, KABUPATEN/KOTA X, PROVINSI Y"
  // Take the kabupaten/kota token (before the province) as best-effort city.
  const parts = address.split(",").map((p) => p.trim());
  const kabIdx = parts.findIndex((p) => /^kabupaten|^kota /i.test(p));
  if (kabIdx >= 0) return parts[kabIdx].replace(/^kabupaten |^kota /i, "");
  return parts[parts.length - 2];
}

function extractProvince(address?: string): string | undefined {
  if (!address) return undefined;
  const parts = address.split(",").map((p) => p.trim());
  return parts[parts.length - 1];
}

export default function CompanyDetailPage() {
  const params = useParams();
  const { error } = useToast();
  const [company, setCompany] = useState<PortalCompany | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const companyId = params?.id ? parseInt(params.id as string) : null;

  useEffect(() => {
    if (!companyId) return;
    let cancelled = false;
    (async () => {
      try {
        setIsLoading(true);
        const data = await api.portal.getCompanyDetail(companyId);
        if (!cancelled) setCompany(data);
      } catch (err) {
        if (!cancelled) {
          error("Failed to load company details", "Please try again later");
          logger.error(
            "Failed to load portal company detail",
            {},
            err as Error,
          );
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [companyId, error]);

  if (isLoading) {
    return <PortalPageLoader />;
  }

  if (!company) {
    return (
      <div>
        <PortalBackButton href="/portal/companies" label="Back to Companies" />
        <PortalEmptyState
          icon={Building2}
          title="Company not found"
          description="The company you're looking for doesn't exist or you don't have access to it."
        />
      </div>
    );
  }

  // Editorial props derived from portal shape
  const foundingYear = deriveFoundingYear(
    company.aktaDate || company.akta_pendirian_date,
  );
  const city = extractCity(company.address);
  const province = extractProvince(company.address);

  // PortalCompany uses simple `shareholders: {name, pct}[]` and `directors: string[]`.
  // Editorial components (PeopleColumn) want `associates: {client_name, role, ownership_percentage}[]`.
  // Adapt in-line.
  const directorsArr = Array.isArray(company.directors)
    ? company.directors
    : [];
  const shareholdersArr = Array.isArray(company.shareholders)
    ? company.shareholders
    : [];
  const associates: Array<{
    client_name?: string;
    role: string;
    ownership_percentage?: number;
  }> = [
    ...directorsArr.map((name) => ({
      client_name: typeof name === "string" ? name : undefined,
      role: "Director",
    })),
    ...shareholdersArr.map((s) => ({
      client_name: s.name,
      role: "Shareholder",
      ownership_percentage: s.pct ?? undefined,
    })),
  ];

  return (
    <div className="animate-in fade-in duration-500">
      <PortalBackButton href="/portal/companies" label="Back to Companies" />

      {/* Editorial Hero */}
      <EditorialHero
        companyName={company.name}
        companyType={company.type}
        companyStatus={company.status}
        nib={company.nib}
        kbliDescription={undefined} // portal endpoint doesn't send KBLI descriptions yet
        city={city}
        province={province}
        addressStr={company.address}
        capital={company.authorizedCapital ?? null}
        shareholderCount={shareholdersArr.length}
        foundingYear={foundingYear}
        // No companyId passed + no onEdit → edit pencil hidden
      />

      {/* Identity row (NIB / NPWP / Entity Type) */}
      <div className="mb-8">
        <IdentityRow
          nib={company.nib}
          npwp={company.npwp}
          companyType={company.type}
        />
      </div>

      {/* Fact Boxes (capital + amendments + documents count) */}
      <div className="mb-10">
        <FactBoxes
          capital={company.authorizedCapital ?? null}
          aktaPerubahanNo={undefined}
          aktaPerubahanDate={undefined}
          foundingDate={company.aktaDate}
          documentCount={(company.documents || []).length}
        />
      </div>

      <DividerLabel text="Structure" />

      {/* Two-column: legal/numeric facts + people */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10">
        <KeyNumbersColumn
          sharesCount={undefined}
          shareNominalValue={undefined}
          capital={company.authorizedCapital ?? null}
          aktaPerubahanNo={undefined}
          aktaPerubahanDate={undefined}
          foundingDate={company.aktaDate}
          skNo={company.skNumber}
          addressStr={company.address}
          city={city}
          fullAddress={company.address}
          formatDate={formatDate}
        />
        <PeopleColumn
          associates={associates}
          fallbackName={undefined}
          totalShares={undefined}
        />
      </div>

      {/* Legal Timeline */}
      {(company.aktaNo || company.skNumber) && (
        <>
          <DividerLabel text="Legal Journey" />
          <div className="mb-10">
            <LegalTimeline
              aktaPendirianNo={company.aktaNo}
              aktaPendirianDate={company.aktaDate}
              aktaPerubahanNo={undefined}
              aktaPerubahanDate={undefined}
              skNo={company.skNumber}
              skDate={company.aktaDate}
              nib={company.nib}
              npwp={company.npwp}
              companyName={company.name}
              companyType={company.type}
              capital={company.authorizedCapital ?? null}
              formatDate={formatDate}
            />
          </div>
        </>
      )}

      {/* Licenses (if present) */}
      {Array.isArray(company.licenses) && company.licenses.length > 0 && (
        <>
          <DividerLabel text="Licenses" />
          <section className="space-y-3 mb-10">
            {company.licenses.map((lic) => (
              <div
                key={lic.id}
                className="rounded-xl border p-4"
                style={{
                  background: "rgba(30,30,35,0.7)",
                  borderColor: "rgba(255,255,255,0.05)",
                  backdropFilter: "blur(24px)",
                }}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{lic.name}</p>
                    <p
                      className="text-xs mt-0.5"
                      style={{ color: "var(--bz-text-2)" }}
                    >
                      Expires {formatDate(lic.expiryDate)}
                      {typeof lic.daysRemaining === "number" &&
                        ` · ${lic.daysRemaining}d left`}
                    </p>
                  </div>
                  <span
                    className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full"
                    style={{
                      background:
                        lic.status === "active"
                          ? "rgba(52,211,153,0.1)"
                          : lic.status === "expiring"
                            ? "rgba(251,191,36,0.1)"
                            : "rgba(248,113,113,0.1)",
                      color:
                        lic.status === "active"
                          ? "#34d399"
                          : lic.status === "expiring"
                            ? "#fbbf24"
                            : "#f87171",
                    }}
                  >
                    {lic.status}
                  </span>
                </div>
              </div>
            ))}
          </section>
        </>
      )}
    </div>
  );
}
