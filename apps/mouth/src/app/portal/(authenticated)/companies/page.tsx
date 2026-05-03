"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Building2,
  ChevronRight,
  CheckCircle,
  Shield,
  AlertTriangle,
} from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { logger } from "@/lib/logger";
import type { PortalCompany } from "@/lib/api/portal/portal.types";
import {
  StatusBadge,
  PortalEmptyState,
  PortalListSkeleton,
} from "@/components/portal";

export default function CompaniesPage() {
  const router = useRouter();
  const { error } = useToast();
  const [companies, setCompanies] = useState<PortalCompany[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadCompanies();
  }, []);

  const loadCompanies = async () => {
    try {
      setIsLoading(true);
      const data = await api.portal.getCompanies();
      setCompanies(data);
    } catch (err) {
      error("Failed to load companies", "Please try again later");
      logger.error("Failed to load portal companies", {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <section>
          <div
            className="h-7 w-48 rounded animate-pulse"
            style={{ background: "var(--bz-border)" }}
          />
          <div
            className="h-4 w-72 rounded mt-2 animate-pulse"
            style={{ background: "var(--bz-border)", opacity: 0.5 }}
          />
        </section>
        <PortalListSkeleton count={3} />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Your Companies</h1>
        <p style={{ color: "var(--bz-text-2)" }}>
          Manage your business entities in Indonesia
        </p>
      </section>

      {/* Companies List */}
      {companies.length === 0 ? (
        <PortalEmptyState
          icon={Building2}
          title="No companies yet"
          description="Contact us to set up your Indonesian business entity."
          cta={{ label: "Message our team", href: "/portal/chat" }}
        />
      ) : (
        <section className="space-y-3">
          {companies.map((company) => (
            <CompanyCard
              key={company.id}
              company={company}
              // The backend returns company.id = client_company_links.id (the
              // relationship row id) and company.company_id = the real
              // companies.id. The detail endpoint expects companies.id, so use
              // company_id with a fallback to id for shapes that already flatten
              // the two (workspace consumers).
              onClick={() => {
                const targetId =
                  (company as PortalCompany & { company_id?: number })
                    .company_id ?? company.id;
                router.push(`/portal/company/${targetId}`);
              }}
            />
          ))}
        </section>
      )}
    </div>
  );
}

function CompanyCard({
  company,
  onClick,
}: {
  company: PortalCompany;
  onClick: () => void;
}) {
  const getComplianceStatus = () => {
    if (!company.compliance || company.compliance.length === 0) return null;

    const hasOverdue = company.compliance.some((c) => c.status === "overdue");
    const hasUpcoming = company.compliance.some((c) => c.status === "upcoming");

    if (hasOverdue) {
      return { label: "Overdue", color: "#f87171" };
    }
    if (hasUpcoming) {
      return { label: "Upcoming", color: "#fbbf24" };
    }
    return { label: "Compliant", color: "#34d399" };
  };

  const getLicenseStatus = () => {
    if (!company.licenses || company.licenses.length === 0) return null;

    const hasExpired = company.licenses.some((l) => l.status === "expired");
    const hasExpiring = company.licenses.some((l) => l.status === "expiring");

    if (hasExpired) {
      return { icon: AlertTriangle, className: "text-red-500" };
    }
    if (hasExpiring) {
      return { icon: AlertTriangle, className: "text-amber-500" };
    }
    return { icon: CheckCircle, className: "text-emerald-500" };
  };

  const compliance = getComplianceStatus();
  const licenseStatus = getLicenseStatus();

  return (
    <article
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      tabIndex={0}
      role="button"
      aria-label={`View ${company.name} details`}
      className="rounded-xl border p-4 cursor-pointer transition-all duration-200 active:scale-[0.99] hover:-translate-y-0.5 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-accent-warm)]"
      style={{
        background: "rgba(30,30,35,0.7)",
        borderColor: "rgba(255,255,255,0.05)",
        backdropFilter: "blur(24px)",
      }}
    >
      <div className="flex items-start gap-4">
        <div
          className="p-3 rounded-xl flex-shrink-0"
          style={{ background: "rgba(201,169,110,0.1)" }}
        >
          <Building2
            className="w-6 h-6"
            style={{ color: "var(--bz-accent-warm)" }}
          />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-base truncate">
                  {company.name}
                </h3>
                {company.isPrimary && (
                  <Shield
                    className="w-4 h-4 flex-shrink-0"
                    style={{ color: "var(--bz-accent-warm)" }}
                  />
                )}
              </div>
              <p
                className="text-sm mt-0.5"
                style={{ color: "var(--bz-text-2)" }}
              >
                {company.type}
              </p>
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              {/* "Set primary" is portal-inappropriate: shareholders sit on
                  5-10 PTs via client_company_links, a single primary pick
                  doesn't match their mental model. Staff still manage it
                  from the workspace CompanyTab. Shield icon stays as a
                  read-only marker. */}
              <StatusBadge status={company.status} />
              <ChevronRight
                className="w-5 h-5"
                style={{ color: "var(--bz-text-2)" }}
              />
            </div>
          </div>

          {/* Quick Stats — monospace chips for identifiers, plain text for counts. */}
          <div className="flex flex-wrap items-center gap-2 mt-3 text-xs">
            {company.nib && (
              <span
                className="px-2 py-0.5 rounded-full font-mono tabular-nums"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  color: "var(--bz-text-1)",
                  border: "1px solid rgba(255,255,255,0.06)",
                }}
                title="Nomor Induk Berusaha"
              >
                NIB {company.nib}
              </span>
            )}
            {company.kbli && (
              <span
                className="px-2 py-0.5 rounded-full font-mono tabular-nums"
                style={{
                  background: "rgba(201,169,110,0.08)",
                  color: "var(--bz-accent-warm)",
                  border: "1px solid rgba(201,169,110,0.2)",
                }}
                title="KBLI activity codes"
              >
                KBLI {company.kbli.split(",")[0]}
                {company.kbli.includes(",")
                  ? ` +${company.kbli.split(",").length - 1}`
                  : ""}
              </span>
            )}
            {company.licenses &&
              company.licenses.length > 0 &&
              licenseStatus && (
                <span
                  className="flex items-center gap-1"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  <licenseStatus.icon
                    className={cn("w-3.5 h-3.5", licenseStatus.className)}
                  />
                  {company.licenses.length} license
                  {company.licenses.length !== 1 ? "s" : ""}
                </span>
              )}
            {company.directors && company.directors.length > 0 && (
              <span style={{ color: "var(--bz-text-2)" }}>
                {company.directors.length} director
                {company.directors.length !== 1 ? "s" : ""}
              </span>
            )}
            {compliance && (
              <span
                className="font-medium px-2 py-0.5 rounded-full"
                style={{
                  color: compliance.color,
                  background: `${compliance.color}15`,
                }}
              >
                {compliance.label}
              </span>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}
