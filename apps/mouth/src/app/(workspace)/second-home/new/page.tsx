"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check, Home, Info, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import { toError } from "@/lib/types/common";
import { ApiError } from "@/lib/api/error-handler";
import type { Client } from "@/lib/api/crm/crm.types";
import {
  createCaseSchema,
  flattenErrors,
} from "@/lib/api/secondhome/secondhome.schemas";
import type {
  DependentCode,
  GuaranteeBasis,
} from "@/lib/api/secondhome/secondhome.types";
import { useCreateSecondHomeCase } from "@/hooks/useSecondHome";
import { ClientPicker } from "../components/ClientPicker";

const DEPENDENT_CODE_OPTIONS: { value: DependentCode; label: string }[] = [
  { value: "E31B", label: "E31B — Spouse" },
  { value: "E31E", label: "E31E — Child" },
  { value: "E31H", label: "E31H — Parent" },
  { value: "E31J", label: "E31J — Sibling" },
];

const inputClass =
  "w-full px-3 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 transition-all";
const labelClass = "text-sm font-medium text-[var(--foreground)] mb-1.5 block";

export default function NewSecondHomeCasePage() {
  const router = useRouter();
  const toast = useToast();
  const createCase = useCreateSecondHomeCase();

  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [basis, setBasis] = useState<GuaranteeBasis>("deposit");
  const [practiceId, setPracticeId] = useState<string>("");
  const [clientPractices, setClientPractices] = useState<
    { id: number; label: string }[]
  >([]);
  const [ownerEmail, setOwnerEmail] = useState("");
  const [isDependent, setIsDependent] = useState(false);
  const [dependentCode, setDependentCode] = useState<DependentCode | "">("");
  const [principalCaseId, setPrincipalCaseId] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  // Prefill owner_email with the current team member, same default as
  // process/new/page.tsx's assigned_to.
  useEffect(() => {
    api
      .getProfile()
      .then((profile) => {
        if (profile?.email) setOwnerEmail(profile.email);
      })
      .catch(() => {
        // Non-fatal — owner_email stays empty and can be filled manually.
      });
  }, []);

  // Once a client is selected, offer their existing processes as an optional
  // practice link (fixed contract has no client-scoped search endpoint for
  // second-home cases, so this reuses the CRM practices list).
  useEffect(() => {
    if (!selectedClient) {
      setClientPractices([]);
      setPracticeId("");
      return;
    }
    let cancelled = false;
    api.crm
      .getClientPractices(selectedClient.id)
      .then((practices) => {
        if (cancelled) return;
        setClientPractices(
          practices.map((p) => ({
            id: p.id,
            label: `#${p.id} — ${p.practice_type_name || p.practice_type_code} (${p.status})`,
          })),
        );
      })
      .catch((err) => {
        if (!cancelled) {
          setClientPractices([]);
          logger.warn("Failed to load client practices for linking", {
            component: "NewSecondHomeCase",
            action: "loadPractices",
          });
        }
        void err;
      });
    return () => {
      cancelled = true;
    };
  }, [selectedClient]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFieldErrors({});

    const result = createCaseSchema.safeParse({
      client_id: selectedClient?.id,
      basis,
      practice_id: practiceId ? Number(practiceId) : undefined,
      owner_email: ownerEmail,
      dependent_code: isDependent && dependentCode ? dependentCode : undefined,
      principal_case_id: isDependent ? principalCaseId : undefined,
    });

    if (!result.success) {
      setFieldErrors(flattenErrors(result.error));
      return;
    }

    try {
      const created = await createCase.mutateAsync(result.data);
      toast.success("Case Created", `${created.case_id} created at Fit Memo.`);
      router.push(`/second-home/${encodeURIComponent(created.case_id)}`);
    } catch (error) {
      logger.error(
        "Failed to create second-home case",
        { component: "NewSecondHomeCase", action: "createCase" },
        toError(error),
      );
      const message =
        error instanceof ApiError
          ? error.detail || error.message
          : "Failed to create case";
      toast.error("Error", message);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-4">
        <Link href="/second-home">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Go back to Second Home"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)] flex items-center gap-2">
            <Home className="w-5 h-5" />
            New Second Home Case
          </h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Opens the case at Fit Memo — the free assessment stage
          </p>
        </div>
      </div>

      {/* Confirmed-facts info panel — no forbidden claims, no dependent
          pricing, no price decomposition. */}
      <div className="rounded-lg border border-[var(--accent)]/20 bg-[var(--accent)]/5 p-4 flex gap-3">
        <Info className="w-4 h-4 text-[var(--accent)] shrink-0 mt-0.5" />
        <div className="text-xs text-[var(--foreground-muted)] space-y-1.5">
          <p>
            <strong className="text-[var(--foreground)]">Base E33</strong> — USD
            130,000 own-name deposit at a state-owned (BUMN) bank, or a
            completed strata-title property worth USD 1,000,000 (BERSYARAT —
            completed titles only). No sponsor. First grant up to 5 years;
            renewal follows Permenkumham 22/2023 Pasal 113 cumulative caps.
          </p>
          <p>
            <strong className="text-[var(--foreground)]">E33E</strong> — senior
            55+ (ages 55–59 handled as a signed-disclosure band).{" "}
            <strong className="text-[var(--foreground)]">E33F</strong> — senior
            55+, USD 3,000/month passive income only, no deposit.
          </p>
          <p>
            <strong className="text-[var(--foreground)]">Price</strong> — IDR
            35,000,000 all-inclusive (base E33). Dependent pricing is not live
            yet.
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-8 shadow-sm">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Client */}
          <div className="space-y-2">
            <label className={labelClass}>
              Client <span className="text-[var(--state-danger)]">*</span>
            </label>
            <ClientPicker
              selectedClient={selectedClient}
              onSelect={setSelectedClient}
              onClear={() => setSelectedClient(null)}
            />
            {fieldErrors.client_id && (
              <p className="text-xs text-[var(--state-danger)]">
                {fieldErrors.client_id}
              </p>
            )}
          </div>

          {/* Basis */}
          <div className="space-y-2">
            <label className={labelClass}>
              Qualifying Guarantee Route{" "}
              <span className="text-[var(--state-danger)]">*</span>
            </label>
            <div className="grid grid-cols-2 gap-3">
              {[
                {
                  value: "deposit" as const,
                  label: "Deposit — USD 130,000",
                  disabled: false,
                },
                {
                  value: "property" as const,
                  label: "Property — USD 1,000,000",
                  disabled: true,
                },
              ].map((option) => (
                <button
                  key={option.value}
                  type="button"
                  disabled={option.disabled}
                  onClick={() => setBasis(option.value)}
                  className={`py-2.5 rounded-lg border text-sm font-medium transition-colors ${
                    option.disabled
                      ? "border-[var(--border)] bg-[var(--background-elevated)]/50 text-[var(--foreground-muted)] opacity-50 cursor-not-allowed"
                      : basis === option.value
                        ? "border-[var(--accent)] bg-[var(--accent)]/10 text-[var(--accent)]"
                        : "border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-[var(--foreground-muted)]">
              Property route — pending official confirmation (addendum 007).
            </p>
          </div>

          {/* Practice link (optional) */}
          {clientPractices.length > 0 && (
            <div className="space-y-2">
              <label className={labelClass}>
                Link to Existing Process{" "}
                <span className="text-[var(--foreground-muted)] font-normal">
                  (optional)
                </span>
              </label>
              <select
                value={practiceId}
                onChange={(e) => setPracticeId(e.target.value)}
                className={`${inputClass} appearance-none cursor-pointer`}
              >
                <option value="">No linked process</option>
                {clientPractices.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Owner email */}
          <div className="space-y-2">
            <label className={labelClass}>
              Owner{" "}
              <span className="text-[var(--foreground-muted)] font-normal">
                (optional)
              </span>
            </label>
            <input
              type="email"
              value={ownerEmail}
              onChange={(e) => setOwnerEmail(e.target.value)}
              className={inputClass}
              placeholder="team-member@balizero.com"
            />
            {fieldErrors.owner_email && (
              <p className="text-xs text-[var(--state-danger)]">
                {fieldErrors.owner_email}
              </p>
            )}
          </div>

          {/* Dependent toggle */}
          <div className="space-y-3 rounded-lg border border-[var(--border)] p-4">
            <label className="flex items-center gap-2 text-sm font-medium text-[var(--foreground)] cursor-pointer">
              <input
                type="checkbox"
                checked={isDependent}
                onChange={(e) => {
                  setIsDependent(e.target.checked);
                  if (!e.target.checked) {
                    setDependentCode("");
                    setPrincipalCaseId("");
                  }
                }}
                className="rounded border-[var(--border)]"
              />
              This case is for a dependent (spouse / child / parent / sibling)
            </label>

            {isDependent && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                <div className="space-y-2">
                  <label className={labelClass}>Dependent Code</label>
                  <select
                    value={dependentCode}
                    onChange={(e) =>
                      setDependentCode(e.target.value as DependentCode | "")
                    }
                    className={`${inputClass} appearance-none cursor-pointer`}
                  >
                    <option value="">-- Select code --</option>
                    {DEPENDENT_CODE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                  {fieldErrors.dependent_code && (
                    <p className="text-xs text-[var(--state-danger)]">
                      {fieldErrors.dependent_code}
                    </p>
                  )}
                </div>
                <div className="space-y-2">
                  <label className={labelClass}>Principal Case ID</label>
                  <input
                    type="text"
                    value={principalCaseId}
                    onChange={(e) => setPrincipalCaseId(e.target.value)}
                    className={inputClass}
                    placeholder="E33-2026-abc123"
                  />
                  <p className="text-xs text-[var(--foreground-muted)]">
                    Copy from the principal&apos;s case detail page URL.
                  </p>
                  {fieldErrors.principal_case_id && (
                    <p className="text-xs text-[var(--state-danger)]">
                      {fieldErrors.principal_case_id}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="pt-4 flex justify-end gap-3 border-t border-[var(--border)]">
            <Link href="/second-home">
              <Button
                variant="outline"
                type="button"
                disabled={createCase.isPending}
              >
                Cancel
              </Button>
            </Link>
            <Button
              className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white min-w-[140px]"
              type="submit"
              disabled={createCase.isPending || !selectedClient}
            >
              {createCase.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <Check className="w-4 h-4 mr-2" />
                  Create Case
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
