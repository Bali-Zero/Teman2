"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import {
  ArrowLeft,
  FolderKanban,
  Loader2,
  User,
  Search,
  Check,
  DollarSign,
  UserCheck,
  Calendar,
  ChevronDown,
  Tag,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { CreatePracticeParams, Client } from "@/lib/api/crm/crm.types";
import * as partnersApi from "@/lib/api/partners/partners";
import { createPracticeSchema, flattenErrors } from "@/lib/api/crm/crm.schemas";
import { casesMetrics } from "@/lib/metrics/cases-metrics";
import { logger } from "@/lib/logger";
import { toError } from "@/lib/types/common";
import { useTeamMemberOptions } from "@/hooks/useTeamMembers";
import { ReferrerDropdown } from "@/components/partners/ReferrerDropdown";

interface ServiceItem {
  code: string;
  name: string;
  description: string | null;
  base_price: number | null;
  typical_duration_days: number | null;
}

interface ServiceCategory {
  code: string;
  label: string;
  services: ServiceItem[];
}

function formatPrice(price: number): string {
  return new Intl.NumberFormat("id-ID").format(price);
}

export default function NewPracticePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();

  const [isLoading, setIsLoading] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const preselectedClientId = searchParams?.get("client_id")
    ? Number(searchParams.get("client_id"))
    : undefined;

  // Service catalog from backend
  const [catalog, setCatalog] = useState<ServiceCategory[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);

  // Team members for assignment dropdown (loaded from API)
  const { options: allTeamOptions } = useTeamMemberOptions();
  const [assignableMembers, setAssignableMembers] = useState<{ email: string; name: string }[]>([]);

  // Form state
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedServiceCode, setSelectedServiceCode] = useState("");
  const [formData, setFormData] = useState({
    title: "",
    client_id: preselectedClientId,
    quoted_price: "",
    assigned_to: "",
    priority: "normal" as "normal" | "high" | "urgent",
    start_date: "",
    referrer_id: null as number | null,
  });

  // Client Search State
  const [clientSearch, setClientSearch] = useState("");
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [isSearchingClients, setIsSearchingClients] = useState(false);
  const [showClientDropdown, setShowClientDropdown] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  const userEmail = useRef<string | null>(null);

  const servicesInCategory = useMemo(() => {
    if (!selectedCategory) return [];
    const cat = catalog.find((c) => c.code === selectedCategory);
    return cat?.services ?? [];
  }, [catalog, selectedCategory]);

  const selectedService = useMemo(() => {
    if (!selectedServiceCode) return null;
    for (const cat of catalog) {
      const svc = cat.services.find((s) => s.code === selectedServiceCode);
      if (svc) return svc;
    }
    return null;
  }, [catalog, selectedServiceCode]);

  // Load catalog on mount
  useEffect(() => {
    const loadCatalog = async () => {
      try {
        const data = await api.crm.getPracticeTypesCatalog();
        setCatalog(data.categories);
      } catch (err) {
        logger.error(
          "Failed to load practice types catalog",
          { component: "NewProcess", action: "loadCatalog" },
          toError(err),
        );
        toast.error("Error", "Failed to load service catalog");
      } finally {
        setCatalogLoading(false);
      }
    };
    loadCatalog();
  }, []);

  // Map API team options to the format used by the form
  const allTeamMembers = useMemo(
    () => allTeamOptions.map((o) => ({ email: o.value, name: o.label })),
    [allTeamOptions],
  );

  useEffect(() => {
    const initMetrics = async () => {
      try {
        const user = await api.getProfile();
        userEmail.current = user.email;
        casesMetrics.trackPageView("new", undefined, user.email);
        // Admin sees all team members, others see only themselves
        if (api.isAdmin()) {
          setAssignableMembers(allTeamMembers);
        } else {
          const self = allTeamMembers.find((m) => m.email === user.email);
          setAssignableMembers(self ? [self] : allTeamMembers);
          if (self) {
            setFormData((prev) => ({ ...prev, assigned_to: user.email }));
          }
        }
      } catch (err) {
        logger.error(
          "Failed to init metrics",
          { component: "NewProcess", action: "initMetrics" },
          toError(err),
        );
      }
    };
    if (allTeamMembers.length > 0) {
      initMetrics();
    }
  }, [allTeamMembers]);

  useEffect(() => {
    const preselectedId = searchParams?.get("client_id");
    if (preselectedId) {
      api.crm
        .getClient(Number(preselectedId))
        .then((client) => {
          setSelectedClient(client);
          setFormData((prev) => ({ ...prev, client_id: client.id }));
        })
        .catch((err) => logger.error("Failed to load preselected client", err));
    }
  }, [searchParams]);

  useEffect(() => {
    const searchClients = async () => {
      if (!clientSearch.trim()) {
        setClients([]);
        return;
      }
      setIsSearchingClients(true);
      const apiStart = performance.now();
      try {
        const results = await api.crm.getClients({
          search: clientSearch,
          limit: 20,
        });
        const apiDuration = performance.now() - apiStart;
        casesMetrics.trackApiCall(
          "/api/crm/clients/search",
          "GET",
          true,
          apiDuration,
          undefined,
          userEmail.current || undefined,
        );
        casesMetrics.trackClientSearch(
          clientSearch,
          results.length,
          userEmail.current || undefined,
        );
        setClients(results);
      } catch (error) {
        const apiDuration = performance.now() - apiStart;
        casesMetrics.trackApiCall(
          "/api/crm/clients/search",
          "GET",
          false,
          apiDuration,
          undefined,
          userEmail.current || undefined,
        );
        casesMetrics.trackError(
          "Client Search Failed",
          (error as Error).message,
          "CasesNewPage",
          undefined,
          userEmail.current || undefined,
        );
        logger.error(
          "Failed to search clients",
          { component: "NewProcess", action: "searchClients" },
          toError(error),
        );
      } finally {
        setIsSearchingClients(false);
      }
    };
    const debounce = setTimeout(searchClients, 300);
    return () => clearTimeout(debounce);
  }, [clientSearch]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowClientDropdown(false);
      }
    };
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowClientDropdown(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const handleCategoryChange = (catCode: string) => {
    setSelectedCategory(catCode);
    setSelectedServiceCode("");
    setFormData((prev) => ({ ...prev, quoted_price: "" }));
  };

  const handleServiceChange = (serviceCode: string) => {
    setSelectedServiceCode(serviceCode);
    const cat = catalog.find((c) => c.code === selectedCategory);
    const svc = cat?.services.find((s) => s.code === serviceCode);
    if (svc?.base_price) {
      setFormData((prev) => ({
        ...prev,
        quoted_price: String(svc.base_price),
      }));
    } else {
      setFormData((prev) => ({ ...prev, quoted_price: "" }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFieldErrors({});

    if (!selectedServiceCode) {
      setFieldErrors({ service: "Select a service" });
      return;
    }

    const result = createPracticeSchema.safeParse({
      client_id: formData.client_id,
      practice_type_code: selectedServiceCode,
      notes: formData.title,
    });

    if (!result.success) {
      const errors = flattenErrors(result.error);
      setFieldErrors(errors);
      casesMetrics.trackError(
        "Validation Error",
        Object.values(errors).join(", "),
        "CasesNewPage",
        undefined,
        userEmail.current || undefined,
      );
      return;
    }

    setIsLoading(true);
    casesMetrics.trackButtonClick(
      "Create Case",
      "CasesNewPage",
      undefined,
      undefined,
      userEmail.current || undefined,
    );
    casesMetrics.startPerformanceMark("case_creation");
    const apiStart = performance.now();

    try {
      const user = await api.getProfile();

      // Duplicate check — may fail with 403 if RBAC denies access (non-admin
      // creating process for a client assigned to someone else). Skip check
      // on failure rather than blocking creation entirely.
      try {
        const existingPractices = await api.crm.getClientPractices(
          result.data.client_id,
        );
        const duplicateCheck = existingPractices.find(
          (p) =>
            p.practice_type_code === result.data.practice_type_code &&
            !["completed", "cancelled"].includes(p.status),
        );

        if (duplicateCheck) {
          toast.error(
            "Duplicate Process",
            `Client already has an active ${selectedService?.name || result.data.practice_type_code} process (ID: #${duplicateCheck.id}, Status: ${duplicateCheck.status}). Complete or cancel it first.`,
          );
          casesMetrics.trackError(
            "Duplicate Process Blocked",
            `Prevented duplicate ${result.data.practice_type_code} for client ${result.data.client_id}`,
            "CasesNewPage",
            duplicateCheck.id,
            user.email,
          );
          return;
        }
      } catch {
        // RBAC 403 or network error — skip duplicate check, proceed with creation
        logger.warn("Duplicate check skipped — could not fetch client practices", {
          component: "NewProcess",
          action: "duplicateCheck",
          itemId: String(result.data.client_id),
        });
      }

      const backendData = {
        client_id: result.data.client_id,
        practice_type_code: result.data.practice_type_code,
        status: "inquiry",
        priority: formData.priority,
        notes: result.data.notes,
        ...(formData.quoted_price
          ? { quoted_price: Number(formData.quoted_price) }
          : {}),
        ...(formData.assigned_to ? { assigned_to: formData.assigned_to } : {}),
        ...(formData.start_date ? { start_date: formData.start_date } : {}),
      } as CreatePracticeParams;

      const createdPractice = await api.crm.createPractice(
        backendData,
      );

      if (formData.referrer_id != null && createdPractice?.id) {
        try {
          await partnersApi.createReferral(formData.referrer_id, {
            practice_id: createdPractice.id,
          });
        } catch (referralErr) {
          // Non-fatal: practice exists. Log but don't block user.
          console.warn("Referral row creation failed", referralErr);
        }
      }
      const apiDuration = performance.now() - apiStart;
      casesMetrics.trackApiCall(
        "/api/crm/practices/create",
        "POST",
        true,
        apiDuration,
        undefined,
        user.email,
      );

      const caseId = createdPractice?.id || 0;
      casesMetrics.trackCaseCreation(
        caseId,
        result.data.practice_type_code,
        result.data.client_id,
        user.email,
      );
      casesMetrics.endPerformanceMark("case_creation", caseId, user.email);

      toast.success(
        "Process Created",
        `${selectedService?.name || "Process"} created successfully.`,
      );
      if (preselectedClientId) {
        router.push(`/clients/${preselectedClientId}?tab=process`);
      } else {
        const newId = createdPractice?.id;
        router.push(newId ? `/process/${newId}` : "/process");
      }
    } catch (error) {
      const apiDuration = performance.now() - apiStart;
      casesMetrics.trackApiCall(
        "/api/crm/practices/create",
        "POST",
        false,
        apiDuration,
        undefined,
        userEmail.current || undefined,
      );
      casesMetrics.trackError(
        "Create Case Failed",
        (error as Error).message,
        "CasesNewPage",
        undefined,
        userEmail.current || undefined,
      );
      logger.error(
        "Failed to create case",
        { component: "NewProcess", action: "createCase" },
        toError(error),
      );
      toast.error("Error", (error as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  const inputClass =
    "w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 transition-all";
  const labelClass =
    "text-sm font-medium text-[var(--foreground)] mb-1.5 block";

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-4">
        <Link href="/process">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Go back to process list"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">
            New Process
          </h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Select the service and define the details
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-8 shadow-sm">
        <form onSubmit={handleSubmit} className="space-y-6">
          {fieldErrors._form && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
              {fieldErrors._form}
            </div>
          )}

          {/* Client Selection */}
          <div className="space-y-2 relative" ref={searchRef}>
            <label className={labelClass}>
              Client <span className="text-red-500">*</span>
            </label>
            {selectedClient ? (
              <div className="flex items-center justify-between p-3 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/10">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-[var(--accent)]/20 flex items-center justify-center">
                    <User className="w-4 h-4 text-[var(--accent)]" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-[var(--foreground)]">
                      {selectedClient.full_name}
                    </p>
                    <p className="text-xs text-[var(--foreground-muted)]">
                      {selectedClient.email || "No email"}
                    </p>
                  </div>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSelectedClient(null);
                    setFormData((prev) => ({ ...prev, client_id: undefined }));
                    setClientSearch("");
                  }}
                >
                  Change
                </Button>
              </div>
            ) : (
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                <input
                  type="text"
                  value={clientSearch}
                  aria-label="Search client"
                  onChange={(e) => {
                    setClientSearch(e.target.value);
                    setShowClientDropdown(true);
                  }}
                  onFocus={() => setShowClientDropdown(true)}
                  className={inputClass}
                  placeholder="Search client by name or email..."
                />
                {isSearchingClients && (
                  <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-[var(--foreground-muted)]" />
                )}
                {showClientDropdown && clientSearch && (
                  <div className="absolute z-10 w-full mt-1 bg-[var(--background-elevated)] border border-[var(--border)] rounded-lg shadow-lg max-h-60 overflow-y-auto">
                    {clients.length > 0 ? (
                      clients.map((client) => (
                        <button
                          key={client.id}
                          type="button"
                          onClick={() => {
                            setSelectedClient(client);
                            setFormData((prev) => ({
                              ...prev,
                              client_id: client.id,
                            }));
                            setShowClientDropdown(false);
                          }}
                          className="w-full text-left px-4 py-3 hover:bg-[var(--background-secondary)] transition-colors border-b border-[var(--border)] last:border-0 flex items-center justify-between group"
                        >
                          <div>
                            <p className="text-sm font-medium text-[var(--foreground)] group-hover:text-[var(--accent)] transition-colors">
                              {client.full_name}
                            </p>
                            <p className="text-xs text-[var(--foreground-muted)]">
                              {client.email ||
                                client.phone ||
                                "No contact info"}
                            </p>
                          </div>
                          {client.nationality && (
                            <span className="text-xs px-2 py-0.5 rounded bg-[var(--background)] text-[var(--foreground-muted)]">
                              {client.nationality}
                            </span>
                          )}
                        </button>
                      ))
                    ) : (
                      <div className="p-4 text-center text-sm text-[var(--foreground-muted)]">
                        {isSearchingClients
                          ? "Searching..."
                          : "No clients found"}
                      </div>
                    )}
                    {clients.length === 20 && (
                      <div className="px-4 py-2 text-xs text-[var(--foreground-muted)] border-t border-[var(--border)] bg-[var(--background-secondary)]/30">
                        Showing top 20 results. Type more to refine search.
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
            {fieldErrors.client_id && (
              <p className="text-xs text-red-400 mt-1">
                {fieldErrors.client_id}
              </p>
            )}
          </div>

          {/* Service Selection — 2 levels */}
          <div className="space-y-4">
            <label className={labelClass}>
              Service <span className="text-red-500">*</span>
            </label>
            {catalogLoading ? (
              <div className="flex items-center gap-2 text-sm text-[var(--foreground-muted)] py-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading services...
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="relative">
                  <Tag className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)] pointer-events-none" />
                  <select
                    value={selectedCategory}
                    onChange={(e) => handleCategoryChange(e.target.value)}
                    className={`${inputClass} appearance-none cursor-pointer pr-10`}
                  >
                    <option value="">-- Select category --</option>
                    {catalog.map((cat) => (
                      <option key={cat.code} value={cat.code}>
                        {cat.label} ({cat.services.length})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="relative">
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)] pointer-events-none" />
                  <select
                    value={selectedServiceCode}
                    onChange={(e) => handleServiceChange(e.target.value)}
                    disabled={!selectedCategory}
                    className={`${inputClass} appearance-none cursor-pointer pr-10 pl-4 ${!selectedCategory ? "opacity-50 cursor-not-allowed" : ""}`}
                  >
                    <option value="">
                      {selectedCategory
                        ? "-- Select service --"
                        : "Select category first"}
                    </option>
                    {servicesInCategory.map((svc) => (
                      <option key={svc.code} value={svc.code}>
                        {svc.name}
                        {svc.base_price
                          ? ` — Rp ${formatPrice(svc.base_price)}`
                          : " — Quote"}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            {selectedService && (
              <div className="flex items-center gap-3 p-3 rounded-lg border border-[var(--accent)]/20 bg-[var(--accent)]/5">
                <div className="flex-1">
                  <p className="text-sm font-medium text-[var(--foreground)]">
                    {selectedService.name}
                  </p>
                  {selectedService.description && (
                    <p className="text-xs text-[var(--foreground-muted)] mt-0.5">
                      {selectedService.description}
                    </p>
                  )}
                </div>
                <div className="text-right">
                  {selectedService.base_price ? (
                    <p className="text-sm font-semibold text-[var(--accent)]">
                      Rp {formatPrice(selectedService.base_price)}
                    </p>
                  ) : (
                    <p className="text-xs text-[var(--foreground-muted)] italic">
                      Contact for quote
                    </p>
                  )}
                  {selectedService.typical_duration_days && (
                    <p className="text-xs text-[var(--foreground-muted)]">
                      ~{selectedService.typical_duration_days} days
                    </p>
                  )}
                </div>
              </div>
            )}

            {fieldErrors.service && (
              <p className="text-xs text-red-400">{fieldErrors.service}</p>
            )}
            {fieldErrors.practice_type_code && (
              <p className="text-xs text-red-400">
                {fieldErrors.practice_type_code}
              </p>
            )}
          </div>

          {/* Quoted Price + Assigned To */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className={labelClass}>
                Quoted Price{" "}
                <span className="text-[var(--foreground-muted)] font-normal">
                  (IDR)
                </span>
              </label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                <input
                  type="number"
                  min="0"
                  step="100000"
                  value={formData.quoted_price}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      quoted_price: e.target.value,
                    }))
                  }
                  className={inputClass}
                  placeholder="Auto-filled from catalog"
                />
              </div>
              {formData.quoted_price && (
                <p className="text-xs text-[var(--foreground-muted)]">
                  Rp {formatPrice(Number(formData.quoted_price))}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <label className={labelClass}>
                Assigned To{" "}
                <span className="text-[var(--foreground-muted)] font-normal">
                  (optional)
                </span>
              </label>
              <div className="relative">
                <UserCheck className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                <select
                  value={formData.assigned_to}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      assigned_to: e.target.value,
                    }))
                  }
                  className={`${inputClass} appearance-none cursor-pointer`}
                >
                  <option value="">— unassigned —</option>
                  {assignableMembers.map((m) => (
                    <option key={m.email} value={m.email}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Priority */}
          <div className="space-y-2">
            <label className={labelClass}>Priority</label>
            <div className="flex gap-2">
              {[
                {
                  value: "normal" as const,
                  label: "Normal",
                  color: "text-zinc-400",
                  activeBg: "bg-zinc-500/20",
                  activeBorder: "border-zinc-500/40",
                },
                {
                  value: "high" as const,
                  label: "High",
                  color: "text-orange-400",
                  activeBg: "bg-orange-500/20",
                  activeBorder: "border-orange-500/40",
                },
                {
                  value: "urgent" as const,
                  label: "Urgent",
                  color: "text-red-400",
                  activeBg: "bg-red-500/20",
                  activeBorder: "border-red-500/40",
                },
              ].map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() =>
                    setFormData((prev) => ({ ...prev, priority: p.value }))
                  }
                  className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors ${
                    formData.priority === p.value
                      ? `${p.activeBg} ${p.activeBorder} ${p.color}`
                      : "border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground-muted)] hover:border-[var(--border)] hover:text-[var(--foreground)]"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Start Date */}
          <div className="space-y-2">
            <label className={labelClass}>
              Start Date{" "}
              <span className="text-[var(--foreground-muted)] font-normal">
                (optional)
              </span>
            </label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
              <input
                type="date"
                value={formData.start_date}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    start_date: e.target.value,
                  }))
                }
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 transition-all"
              />
            </div>
          </div>

          {/* Referrer (Partner) */}
          <div className="space-y-2">
            <label className={labelClass}>
              Referrer{" "}
              <span className="text-[var(--foreground-muted)] font-normal">
                (optional)
              </span>
            </label>
            <ReferrerDropdown
              value={formData.referrer_id}
              onChange={(id) => setFormData((prev) => ({ ...prev, referrer_id: id }))}
              className="w-full"
            />
          </div>

          {/* Notes */}
          <div className="space-y-2">
            <label className={labelClass}>Notes</label>
            <div className="relative">
              <FolderKanban className="absolute left-3 top-3 w-4 h-4 text-[var(--foreground-muted)]" />
              <textarea
                value={formData.title}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, title: e.target.value }))
                }
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 transition-all resize-none"
                placeholder="Special requirements, client requests, internal notes..."
                rows={3}
              />
            </div>
          </div>

          <div className="pt-4 flex justify-end gap-3 border-t border-[var(--border)]">
            <Link href="/process">
              <Button variant="outline" type="button" disabled={isLoading}>
                Cancel
              </Button>
            </Link>
            <Button
              className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white min-w-[120px]"
              type="submit"
              disabled={
                isLoading || !formData.client_id || !selectedServiceCode
              }
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <Check className="w-4 h-4 mr-2" />
                  Create Process
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
