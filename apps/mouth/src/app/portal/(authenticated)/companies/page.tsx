"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Loader2,
  Building2,
  ChevronRight,
  CheckCircle,
  Clock,
  Shield,
  AlertTriangle,
} from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import type { PortalCompany } from "@/lib/api/portal/portal.types";

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
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Your Companies</h1>
        <p className="text-muted-foreground">
          Manage your business entities in Indonesia
        </p>
      </section>

      {/* Companies List */}
      {companies.length === 0 ? (
        <section className="rounded-xl border border-dashed bg-card p-12 text-center">
          <Building2 className="w-16 h-16 mx-auto mb-4 text-muted-foreground/30" />
          <h2 className="text-lg font-semibold text-muted-foreground">
            No companies yet
          </h2>
          <p className="text-sm text-muted-foreground/70 mt-1">
            Contact us to set up your Indonesian business entity.
          </p>
        </section>
      ) : (
        <section className="space-y-3">
          {companies.map((company) => (
            <CompanyCard
              key={company.id}
              company={company}
              onClick={() => router.push(`/portal/company/${company.id}`)}
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
      return { label: "Overdue", className: "text-red-600 dark:text-red-400" };
    }
    if (hasUpcoming) {
      return {
        label: "Upcoming",
        className: "text-amber-600 dark:text-amber-400",
      };
    }
    return {
      label: "Compliant",
      className: "text-emerald-600 dark:text-emerald-400",
    };
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
    <div
      onClick={onClick}
      className={cn(
        "rounded-xl border bg-card p-4 cursor-pointer transition-all",
        "hover:bg-muted/50 hover:border-primary/30 active:scale-[0.99]",
      )}
    >
      <div className="flex items-start gap-4">
        <div className="p-3 rounded-xl bg-primary/10 flex-shrink-0">
          <Building2 className="w-6 h-6 text-primary" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-base truncate">
                  {company.name}
                </h3>
                {company.isPrimary && (
                  <Shield className="w-4 h-4 text-primary flex-shrink-0" />
                )}
              </div>
              <p className="text-sm text-muted-foreground mt-0.5">
                {company.type}
              </p>
            </div>

            <div className="flex items-center gap-1 flex-shrink-0">
              <StatusBadge status={company.status} />
              <ChevronRight className="w-5 h-5 text-muted-foreground" />
            </div>
          </div>

          {/* Quick Stats */}
          <div className="flex items-center gap-4 mt-3 text-xs">
            {company.licenses &&
              company.licenses.length > 0 &&
              licenseStatus && (
                <div className="flex items-center gap-1.5">
                  <licenseStatus.icon
                    className={cn("w-3.5 h-3.5", licenseStatus.className)}
                  />
                  <span className="text-muted-foreground">
                    {company.licenses.length} license
                    {company.licenses.length !== 1 ? "s" : ""}
                  </span>
                </div>
              )}

            {company.directors && company.directors.length > 0 && (
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <span>
                  {company.directors.length} director
                  {company.directors.length !== 1 ? "s" : ""}
                </span>
              </div>
            )}

            {compliance && (
              <div className={cn("font-medium", compliance.className)}>
                {compliance.label}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: "active" | "pending" }) {
  const config = {
    active: {
      icon: CheckCircle,
      label: "Active",
      className:
        "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
    },
    pending: {
      icon: Clock,
      label: "Pending",
      className:
        "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    },
  };

  const { icon: Icon, label, className } = config[status];

  return (
    <div
      className={cn(
        "px-2 py-1 rounded-full flex items-center gap-1 text-xs font-medium",
        className,
      )}
    >
      <Icon className="w-3 h-3" />
      {label}
    </div>
  );
}
