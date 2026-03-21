"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Loader2,
  Building2,
  Users,
  FileCheck,
  Calendar,
  CheckCircle,
  AlertTriangle,
  Clock,
  ChevronLeft,
  Shield,
  MapPin,
  Mail,
  Phone,
  Hash,
  Briefcase,
  FileText,
} from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { logger } from "@/lib/logger";
import type {
  PortalCompany,
  CompanyLicense,
  ComplianceItem,
} from "@/lib/api/portal/portal.types";
import { Button } from "@/components/ui/button";

export default function CompanyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { error } = useToast();
  const [company, setCompany] = useState<PortalCompany | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const companyId = params?.id ? parseInt(params.id as string) : null;

  useEffect(() => {
    if (companyId) {
      loadCompany();
    }
  }, [companyId]);

  const loadCompany = async () => {
    if (!companyId) return;

    try {
      setIsLoading(true);
      const data = await api.portal.getCompanyDetail(companyId);
      setCompany(data);
    } catch (err) {
      error("Failed to load company details", "Please try again later");
      logger.error("Failed to load portal company detail", {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2
          className="w-8 h-8 animate-spin"
          style={{ color: "var(--bz-accent-warm)" }}
        />
      </div>
    );
  }

  if (!company) {
    return (
      <div className="text-center py-12">
        <Building2
          className="w-16 h-16 mx-auto mb-4 opacity-30"
          style={{ color: "var(--bz-text-2)" }}
        />
        <h2
          className="text-lg font-semibold"
          style={{ color: "var(--bz-text-2)" }}
        >
          Company not found
        </h2>
        <Button
          variant="ghost"
          className="mt-4"
          onClick={() => router.push("/portal/vault")}
        >
          <ChevronLeft className="w-4 h-4 mr-1" />
          Back to Vault
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Back Button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.back()}
        className="-ml-2"
      >
        <ChevronLeft className="w-4 h-4 mr-1" />
        Back
      </Button>

      {/* Company Header */}
      <section
        className="rounded-xl border p-6"
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
        }}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className="p-3 rounded-xl"
              style={{ background: "rgba(201,169,110,0.1)" }}
            >
              <Building2
                className="w-6 h-6"
                style={{ color: "var(--bz-accent-warm)" }}
              />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">
                {company.name}
              </h1>
              <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
                {company.type}
              </p>
            </div>
          </div>
          <StatusBadge status={company.status} />
        </div>

        {company.address && (
          <p className="mt-4 text-sm" style={{ color: "var(--bz-text-2)" }}>
            {company.address}
          </p>
        )}

        {company.isPrimary && (
          <div
            className="mt-4 px-3 py-1.5 text-xs font-medium rounded-full inline-flex items-center gap-1.5"
            style={{
              background: "rgba(201,169,110,0.1)",
              color: "var(--bz-accent-warm)",
            }}
          >
            <Shield className="w-3.5 h-3.5" />
            Primary Company
          </div>
        )}
      </section>

      {/* Business Details Section */}
      <BusinessDetailsSection company={company} />

      {/* Licenses Section */}
      <section
        className="rounded-xl border p-6 space-y-4"
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
        }}
      >
        <div className="flex items-center gap-2">
          <FileCheck
            className="w-5 h-5"
            style={{ color: "var(--bz-accent-warm)" }}
          />
          <h2 className="text-lg font-semibold">Licenses</h2>
        </div>

        {company.licenses && company.licenses.length > 0 ? (
          <div className="space-y-3">
            {company.licenses.map((license) => (
              <LicenseCard key={license.id} license={license} />
            ))}
          </div>
        ) : (
          <div
            className="text-center py-8"
            style={{ color: "var(--bz-text-2)" }}
          >
            <FileCheck className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No licenses on record</p>
          </div>
        )}
      </section>

      {/* Compliance Calendar Section */}
      <section
        className="rounded-xl border p-6 space-y-4"
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
        }}
      >
        <div className="flex items-center gap-2">
          <Calendar
            className="w-5 h-5"
            style={{ color: "var(--bz-accent-warm)" }}
          />
          <h2 className="text-lg font-semibold">Compliance Calendar</h2>
        </div>

        {company.compliance && company.compliance.length > 0 ? (
          <div className="space-y-3">
            {company.compliance
              .sort(
                (a, b) =>
                  new Date(a.dueDate).getTime() - new Date(b.dueDate).getTime(),
              )
              .map((item) => (
                <ComplianceCard key={item.id} item={item} />
              ))}
          </div>
        ) : (
          <div
            className="text-center py-8"
            style={{ color: "var(--bz-text-2)" }}
          >
            <Calendar className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No compliance deadlines</p>
          </div>
        )}
      </section>

      {/* Directors Section */}
      <section
        className="rounded-xl border p-6 space-y-4"
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
        }}
      >
        <div className="flex items-center gap-2">
          <Users
            className="w-5 h-5"
            style={{ color: "var(--bz-accent-warm)" }}
          />
          <h2 className="text-lg font-semibold">Directors</h2>
        </div>

        {company.directors && company.directors.length > 0 ? (
          <div className="grid gap-2">
            {company.directors.map((director, index) => (
              <div
                key={index}
                className="flex items-center gap-3 p-3 rounded-lg"
                style={{ background: "var(--bz-surface)" }}
              >
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center"
                  style={{ background: "rgba(201,169,110,0.1)" }}
                >
                  <span
                    className="text-sm font-semibold"
                    style={{ color: "var(--bz-accent-warm)" }}
                  >
                    {director.charAt(0).toUpperCase()}
                  </span>
                </div>
                <span className="font-medium text-sm">{director}</span>
              </div>
            ))}
          </div>
        ) : (
          <div
            className="text-center py-8"
            style={{ color: "var(--bz-text-2)" }}
          >
            <Users className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No directors on record</p>
          </div>
        )}
      </section>
    </div>
  );
}

// Sub-components

function BusinessDetailsSection({ company }: { company: PortalCompany }) {
  const fields = [
    { icon: Hash, label: "NIB", value: company.nib },
    { icon: Hash, label: "NPWP", value: company.npwp },
    { icon: Briefcase, label: "KBLI", value: company.kbli },
    { icon: MapPin, label: "Registered Address", value: company.address },
    { icon: Mail, label: "Email", value: company.email },
    { icon: Phone, label: "Phone", value: company.phone },
    {
      icon: FileText,
      label: "Akta No.",
      value: company.aktaNo
        ? `${company.aktaNo}${company.aktaDate ? ` (${new Date(company.aktaDate).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })})` : ""}`
        : undefined,
    },
    { icon: FileText, label: "SK Kemenkumham", value: company.skNumber },
    { icon: MapPin, label: "Tax Office (KPP)", value: company.taxOffice },
    {
      icon: Briefcase,
      label: "Investment Type",
      value: company.investmentType,
    },
    { icon: Briefcase, label: "Company Status", value: company.companyStatus },
  ].filter((f) => f.value);

  if (fields.length === 0) return null;

  return (
    <section
      className="rounded-xl border p-6 space-y-4"
      style={{ background: "var(--bz-card)", borderColor: "var(--bz-border)" }}
    >
      <div className="flex items-center gap-2">
        <Building2
          className="w-5 h-5"
          style={{ color: "var(--bz-accent-warm)" }}
        />
        <h2 className="text-lg font-semibold">Business Details</h2>
      </div>

      <div className="grid gap-3">
        {fields.map((field) => (
          <div
            key={field.label}
            className="flex items-start gap-3 p-3 rounded-lg"
            style={{ background: "var(--bz-surface)" }}
          >
            <field.icon
              className="w-4 h-4 mt-0.5 flex-shrink-0"
              style={{ color: "var(--bz-accent-warm)" }}
            />
            <div className="min-w-0 flex-1">
              <p
                className="text-xs font-medium"
                style={{ color: "var(--bz-text-3)" }}
              >
                {field.label}
              </p>
              <p className="text-sm mt-0.5 break-words">{field.value}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function StatusBadge({ status }: { status: "active" | "pending" }) {
  const config: Record<
    string,
    { icon: React.ElementType; label: string; style: React.CSSProperties }
  > = {
    active: {
      icon: CheckCircle,
      label: "Active",
      style: { background: "rgba(16,185,129,0.12)", color: "#34d399" },
    },
    pending: {
      icon: Clock,
      label: "Pending",
      style: { background: "rgba(245,158,11,0.12)", color: "#fbbf24" },
    },
  };

  const { icon: Icon, label, style } = config[status] ?? config.pending;

  return (
    <div
      className="px-3 py-1.5 rounded-full flex items-center gap-1.5 text-xs font-medium"
      style={style}
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
    </div>
  );
}

function LicenseCard({ license }: { license: CompanyLicense }) {
  const getStatusConfig = (
    status: string,
  ): {
    icon: React.ElementType;
    badgeStyle: React.CSSProperties;
    borderColor: string;
  } => {
    switch (status) {
      case "active":
        return {
          icon: CheckCircle,
          badgeStyle: { background: "rgba(16,185,129,0.12)", color: "#34d399" },
          borderColor: "rgba(16,185,129,0.25)",
        };
      case "expiring":
        return {
          icon: AlertTriangle,
          badgeStyle: { background: "rgba(245,158,11,0.12)", color: "#fbbf24" },
          borderColor: "rgba(245,158,11,0.3)",
        };
      case "expired":
        return {
          icon: AlertTriangle,
          badgeStyle: { background: "rgba(239,68,68,0.12)", color: "#f87171" },
          borderColor: "rgba(239,68,68,0.3)",
        };
      default:
        return {
          icon: Clock,
          badgeStyle: {
            background: "var(--bz-surface)",
            color: "var(--bz-text-2)",
          },
          borderColor: "var(--bz-border)",
        };
    }
  };

  const config = getStatusConfig(license.status);
  const Icon = config.icon;

  return (
    <div
      className="rounded-lg border p-4"
      style={{
        borderColor: config.borderColor,
        background: "var(--bz-surface)",
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-sm">{license.name}</h3>
          <p className="text-xs mt-1" style={{ color: "var(--bz-text-2)" }}>
            Expires:{" "}
            {new Date(license.expiryDate).toLocaleDateString("en-US", {
              month: "long",
              day: "numeric",
              year: "numeric",
            })}
          </p>
          {license.daysRemaining !== undefined && (
            <p
              className="text-xs font-medium mt-1"
              style={{
                color:
                  license.daysRemaining <= 30
                    ? "#f87171"
                    : license.daysRemaining <= 60
                      ? "#fbbf24"
                      : "#34d399",
              }}
            >
              {license.daysRemaining} days remaining
            </p>
          )}
        </div>
        <div
          className="px-2.5 py-1 rounded-full flex items-center gap-1 text-xs font-medium"
          style={config.badgeStyle}
        >
          <Icon className="w-3 h-3" />
          {license.status.charAt(0).toUpperCase() + license.status.slice(1)}
        </div>
      </div>
    </div>
  );
}

function ComplianceCard({ item }: { item: ComplianceItem }) {
  const getStatusConfig = (
    status: string,
  ): {
    icon: React.ElementType;
    badgeStyle: React.CSSProperties;
    bgStyle: React.CSSProperties;
  } => {
    switch (status) {
      case "completed":
        return {
          icon: CheckCircle,
          badgeStyle: { background: "rgba(16,185,129,0.12)", color: "#34d399" },
          bgStyle: {
            background: "var(--bz-surface)",
            borderColor: "var(--bz-border)",
          },
        };
      case "overdue":
        return {
          icon: AlertTriangle,
          badgeStyle: { background: "rgba(239,68,68,0.12)", color: "#f87171" },
          bgStyle: {
            background: "rgba(239,68,68,0.06)",
            borderColor: "rgba(239,68,68,0.25)",
          },
        };
      case "upcoming":
      default:
        return {
          icon: Clock,
          badgeStyle: { background: "rgba(245,158,11,0.12)", color: "#fbbf24" },
          bgStyle: {
            background: "rgba(245,158,11,0.06)",
            borderColor: "rgba(245,158,11,0.25)",
          },
        };
    }
  };

  const config = getStatusConfig(item.status);
  const Icon = config.icon;
  const dueDate = new Date(item.dueDate);
  const isPast = dueDate < new Date() && item.status !== "completed";

  return (
    <div className="rounded-lg p-4 border" style={config.bgStyle}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <h3 className="font-semibold text-sm">{item.name}</h3>
          <p
            className="text-xs mt-1"
            style={{
              color: isPast ? "#f87171" : "var(--bz-text-2)",
              fontWeight: isPast ? 500 : 400,
            }}
          >
            {isPast ? "Was due: " : "Due: "}
            {dueDate.toLocaleDateString("en-US", {
              weekday: "short",
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
          </p>
        </div>
        <div
          className="px-2.5 py-1 rounded-full flex items-center gap-1 text-xs font-medium"
          style={config.badgeStyle}
        >
          <Icon className="w-3 h-3" />
          {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
        </div>
      </div>
    </div>
  );
}
