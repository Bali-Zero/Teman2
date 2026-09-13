"use client";

/**
 * GARUDA VOA — staff practice detail and transitions.
 *
 * SAETTA-VOA W-VOA-V3 (2026-09-13): concept-F "RAPI" presentation pass.
 * PRESENTATION ONLY. The command builder, the Idempotency-Key lifecycle, the
 * read-only `resolved_block_id` prefill, the admin-only assignment picker and
 * every 401/422 path are unchanged — the diff on this file is class names,
 * hairlines, pills and copy placement.
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { logger } from "@/lib/logger";
import { toError } from "@/lib/types/common";
import {
  assignPractice,
  getStaffPractice,
  transitionPractice,
  GarudaStaffError,
} from "../api-client";
import { useGarudaAssignmentTargets } from "../assignment-targets";
import { getAllowedTransitions } from "../state-machine";
import {
  CARD,
  EYEBROW,
  FIELD,
  FOCUS,
  PracticeStatePill,
  SECTION_H2,
  SERIF,
} from "../r19";
import type {
  PracticeTransitionRequest,
  StaffPracticeView,
  TransitionId,
} from "../types";

function newIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `garuda-voa-staff-${Date.now()}`;
}

interface TransitionFormState {
  transitionId: TransitionId | null;
  customerReasonKey: string;
  requiredActionKey: string;
  privateStaffNote: string;
  evidenceId: string;
  artifactId: string;
  artifactDigest: string;
}

const EMPTY_FORM: TransitionFormState = {
  transitionId: null,
  customerReasonKey: "",
  requiredActionKey: "",
  privateStaffNote: "",
  evidenceId: "",
  artifactId: "",
  artifactDigest: "",
};

/** `activeBlockId` is the practice's server-reported `active_block_id` — the
 * ONLY source for `resolved_block_id` on PR-09/PR-10 (cross-family review
 * binding: this is prefilled read-only, never a field a staffer types). If
 * it is missing, the resume command cannot be built at all. */
function buildTransitionRequest(
  form: TransitionFormState,
  activeBlockId: string | null,
): PracticeTransitionRequest | null {
  switch (form.transitionId) {
    case "PR-02":
      return { transition_id: "PR-02" };
    case "PR-03":
    case "PR-05":
    case "PR-08":
      if (!form.customerReasonKey || !form.requiredActionKey) return null;
      return {
        transition_id: form.transitionId,
        customer_reason_key: form.customerReasonKey,
        required_action_key: form.requiredActionKey,
        private_staff_note: form.privateStaffNote || undefined,
      };
    case "PR-04":
    case "PR-06":
      if (!form.evidenceId) return null;
      return { transition_id: form.transitionId, evidence_id: form.evidenceId };
    case "PR-07":
      if (!form.evidenceId || !form.customerReasonKey) return null;
      return {
        transition_id: "PR-07",
        evidence_id: form.evidenceId,
        customer_reason_key: form.customerReasonKey,
        private_staff_note: form.privateStaffNote || undefined,
      };
    case "PR-09":
    case "PR-10":
      if (!activeBlockId) return null;
      return {
        transition_id: form.transitionId,
        resolved_block_id: activeBlockId,
      };
    case "PR-11":
      if (!form.artifactId || !form.artifactDigest) return null;
      return {
        transition_id: "PR-11",
        artifact_id: form.artifactId,
        artifact_digest: form.artifactDigest,
      };
    default:
      return null;
  }
}

/** Hairline definition pair — eyebrow label above the value, no boxes. */
function Field({
  label,
  children,
  className,
  mono,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
  mono?: boolean;
}) {
  return (
    <div className={className}>
      <p className={EYEBROW}>{label}</p>
      <p
        className={cn(
          "mt-1.5 text-[var(--tx-pure)]",
          mono ? "break-all font-mono text-xs" : "text-sm",
        )}
      >
        {children}
      </p>
    </div>
  );
}

export default function GarudaVoaStaffDetailPage() {
  const router = useRouter();
  const params = useParams();
  const toast = useToast();
  const practiceId = params?.practiceId as string | undefined;

  const [isAdmin, setIsAdmin] = useState(false);
  // The picker's source is the assignment gate's own enumeration, never the
  // shared CRM roster: the roster also lists rows `assignPractice` refuses (a
  // read-only accounting full-view row, any partner row), which rendered as
  // options whose only possible outcome was a 422. Admin-only, matching both
  // the picker below and the endpoint's own 403 — see ../assignment-targets.ts.
  const {
    data: assignmentTargets = [],
    isError: assignmentTargetsUnavailable,
  } = useGarudaAssignmentTargets(isAdmin);
  const [practice, setPractice] = useState<StaffPracticeView | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [form, setForm] = useState<TransitionFormState>(EMPTY_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Idempotency-Key is generated once per COMMAND and reused across retries
  // of that exact command (spec step8). A new command (transition picked, or
  // form fields changed after a failed attempt) gets a fresh key.
  const idempotencyKeyRef = useRef<string>(newIdempotencyKey());

  const [isAssigning, setIsAssigning] = useState(false);
  const assignmentIdempotencyKeyRef = useRef<string>(newIdempotencyKey());

  const loadPractice = useCallback(async () => {
    if (!practiceId) return;
    setIsLoading(true);
    setLoadError(null);
    try {
      const data = await getStaffPractice(practiceId);
      setPractice(data);
    } catch (error) {
      logger.error(
        "[GarudaVoaStaffDetail] Failed to load practice",
        { component: "GarudaVoaStaffDetail", action: "loadPractice" },
        toError(error),
      );
      setLoadError("Failed to load this practice.");
    } finally {
      setIsLoading(false);
    }
  }, [practiceId]);

  useEffect(() => {
    api
      .getProfile()
      .then(() => setIsAdmin(api.isAdmin()))
      .catch((err: unknown) => {
        logger.error(
          "[GarudaVoaStaffDetail] Failed to load user profile",
          {},
          err instanceof Error ? err : new Error(String(err)),
        );
      });
  }, []);

  useEffect(() => {
    loadPractice();
  }, [loadPractice]);

  const selectTransition = (transitionId: TransitionId) => {
    setForm({ ...EMPTY_FORM, transitionId });
    idempotencyKeyRef.current = newIdempotencyKey();
  };

  const handleFieldChange = (
    field: keyof TransitionFormState,
    value: string,
  ) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const submitTransition = async () => {
    if (!practiceId) return;
    const request = buildTransitionRequest(
      form,
      practice?.active_block_id ?? null,
    );
    if (!request) {
      toast.error("Missing fields", "Fill in every required field first.");
      return;
    }
    setIsSubmitting(true);
    try {
      const result = await transitionPractice({
        practiceId,
        request,
        idempotencyKey: idempotencyKeyRef.current,
      });
      toast.success(
        result.replayed ? "Already applied" : "Transition applied",
        `Practice is now ${result.practice.state}`,
      );
      setForm(EMPTY_FORM);
      idempotencyKeyRef.current = newIdempotencyKey();
      await loadPractice();
    } catch (error) {
      const message =
        error instanceof GarudaStaffError
          ? `${error.code}: this transition could not be applied.`
          : "Failed to apply transition.";
      logger.error(
        "[GarudaVoaStaffDetail] Transition failed",
        { component: "GarudaVoaStaffDetail", action: "transition" },
        toError(error),
      );
      toast.error("Transition failed", message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAssign = async (assignedTo: string) => {
    if (!practiceId) return;
    setIsAssigning(true);
    try {
      // assignPractice returns the thin StaffPracticeListItem shape (no
      // private_staff_note/resume_target/active_block_id) — merge into the
      // existing detail view, never replace it wholesale.
      const updated = await assignPractice({
        practiceId,
        request: { assigned_to: assignedTo || null },
        idempotencyKey: assignmentIdempotencyKeyRef.current,
      });
      setPractice((prev) => (prev ? { ...prev, ...updated } : prev));
      assignmentIdempotencyKeyRef.current = newIdempotencyKey();
      toast.success(
        "Assignment updated",
        assignedTo ? `Assigned to ${assignedTo.split("@")[0]}` : "Unassigned",
      );
    } catch (error) {
      logger.error(
        "[GarudaVoaStaffDetail] Assignment failed",
        { component: "GarudaVoaStaffDetail", action: "assign" },
        toError(error),
      );
      toast.error("Failed to update assignment");
    } finally {
      setIsAssigning(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--bz-copper)]" />
      </div>
    );
  }

  if (loadError || !practice) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4">
        <AlertCircle
          className="h-10 w-10 text-[var(--bz-copper)]"
          aria-hidden="true"
        />
        <p
          className="text-[24px] leading-[1.14] text-[var(--tx-pure)]"
          style={SERIF}
        >
          {loadError || "Practice not found"}
        </p>
        <Button
          onClick={() => router.push("/garuda-voa")}
          className="h-11 rounded bg-[var(--state-success)] px-5 text-[13px] font-semibold tracking-[0.02em] text-white hover:bg-[var(--state-success)]/90"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to practices
        </Button>
      </div>
    );
  }

  const allowedTransitions = getAllowedTransitions(
    practice.state,
    practice.resume_target,
  );

  return (
    <div className="mx-auto max-w-4xl space-y-8 p-6">
      <button
        type="button"
        onClick={() => router.push("/garuda-voa")}
        className={cn(
          "inline-flex items-center gap-2 text-xs font-semibold text-[var(--bz-copper-text)] transition-colors hover:text-[var(--tx-pure)]",
          FOCUS,
        )}
      >
        <ArrowLeft className="h-4 w-4" />
        Back to practices
      </button>

      <section>
        <div
          aria-hidden="true"
          className="mb-4 h-[3px] w-14 rounded-sm bg-[var(--bz-copper)]"
        />
        <p className={EYEBROW}>GARUDA VOA · practice</p>
        {/* Never render or link a customer document/artifact identifier here —
            the staff surface shows practice metadata only (spec step8: "Never
            link artifact ids"). */}
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2.5">
          <h1
            className="text-[26px] leading-[1.08] tracking-[-0.02em] text-[var(--tx-pure)] md:text-[30px]"
            style={SERIF}
          >
            {practice.practice_id}
          </h1>
          <PracticeStatePill state={practice.state} />
        </div>
      </section>

      <section className={cn(CARD, "space-y-6 p-6")}>
        <h2 className={cn(SECTION_H2, "text-[var(--tx-pure)]")} style={SERIF}>
          Practice details
        </h2>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          <Field label="Order" mono>
            {practice.order_id}
          </Field>
          <Field label="Updated">
            <span className="tabular-nums">
              {new Date(practice.updated_at).toLocaleString("en-GB")}
            </span>
          </Field>
          {practice.customer_reason_key && (
            <Field label="Customer reason key" mono>
              {practice.customer_reason_key}
            </Field>
          )}
          {practice.required_action_key && (
            <Field label="Required action key" mono>
              {practice.required_action_key}
            </Field>
          )}
          {practice.private_staff_note && (
            <div className="md:col-span-2">
              <p className={EYEBROW}>Private staff note</p>
              <p className="mt-1.5 whitespace-pre-wrap border-l-2 border-[var(--bz-copper)] pl-3.5 text-[15px] leading-[1.7] text-[var(--tx-pure)]">
                {practice.private_staff_note}
              </p>
            </div>
          )}
        </div>

        {isAdmin && (
          <div className="border-t border-[var(--bz-border)] pt-5">
            <label htmlFor="garuda-voa-assign" className={cn(EYEBROW, "block")}>
              Assigned to
            </label>
            <select
              id="garuda-voa-assign"
              value={practice.assigned_to || ""}
              disabled={isAssigning}
              onChange={(e) => handleAssign(e.target.value)}
              className={cn(FIELD, "mt-1.5 max-w-xs")}
            >
              <option value="">Unassigned</option>
              {/* A practice assigned BEFORE this picker was narrowed (or to a
                  row the gate refuses, e.g. the read-only accounting viewer)
                  still has to SHOW its current assignee — without this option
                  the select's value matches nothing and renders as
                  "Unassigned", which is a lie about a real assignment. Disabled
                  so it cannot be picked again into a guaranteed 422. */}
              {practice.assigned_to &&
                !assignmentTargets.some(
                  (target) => target.email === practice.assigned_to,
                ) && (
                  <option value={practice.assigned_to} disabled>
                    {practice.assigned_to} (not assignable)
                  </option>
                )}
              {assignmentTargets.map((target) => (
                <option key={target.email} value={target.email}>
                  {target.label}
                </option>
              ))}
            </select>
            {assignmentTargetsUnavailable && (
              <p className="mt-2 text-xs text-[var(--bz-copper-text)]">
                Assignee list unavailable — reload before assigning.
              </p>
            )}
          </div>
        )}
      </section>

      <section className={cn(CARD, "space-y-5 p-6")}>
        <h2 className={cn(SECTION_H2, "text-[var(--tx-pure)]")} style={SERIF}>
          Transitions
        </h2>
        {allowedTransitions.length === 0 ? (
          <p className="text-sm text-[var(--tx-secondary)]">
            No transitions are available from this state.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2.5">
            {allowedTransitions.map((option) => {
              const isPicked = form.transitionId === option.transitionId;
              return (
                <button
                  key={option.transitionId}
                  type="button"
                  onClick={() => selectTransition(option.transitionId)}
                  data-testid={`transition-${option.transitionId}`}
                  aria-pressed={isPicked}
                  className={cn(
                    "h-11 rounded-full border px-4 text-[13px] font-semibold transition-colors",
                    isPicked
                      ? "border-[var(--bz-copper)] bg-[color-mix(in_srgb,var(--bz-copper)_8%,transparent)] text-[var(--bz-copper-text)]"
                      : "border-[var(--bz-border-hover)] text-[var(--tx-pure)] hover:border-[var(--bz-copper)]",
                    FOCUS,
                  )}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        )}

        {form.transitionId && (
          <div className="space-y-4 border-t border-[var(--bz-border)] pt-5">
            {(form.transitionId === "PR-03" ||
              form.transitionId === "PR-05" ||
              form.transitionId === "PR-07" ||
              form.transitionId === "PR-08") && (
              <div>
                <label
                  htmlFor="garuda-voa-customer-reason-key"
                  className={cn(EYEBROW, "block")}
                >
                  Customer reason key
                </label>
                <input
                  id="garuda-voa-customer-reason-key"
                  type="text"
                  value={form.customerReasonKey}
                  onChange={(e) =>
                    handleFieldChange("customerReasonKey", e.target.value)
                  }
                  placeholder="garuda_voa.practice.…"
                  className={cn(FIELD, "mt-1.5 font-mono")}
                />
              </div>
            )}
            {(form.transitionId === "PR-03" ||
              form.transitionId === "PR-05" ||
              form.transitionId === "PR-08") && (
              <div>
                <label
                  htmlFor="garuda-voa-required-action-key"
                  className={cn(EYEBROW, "block")}
                >
                  Required action key
                </label>
                <input
                  id="garuda-voa-required-action-key"
                  type="text"
                  value={form.requiredActionKey}
                  onChange={(e) =>
                    handleFieldChange("requiredActionKey", e.target.value)
                  }
                  placeholder="garuda_voa.action.…"
                  className={cn(FIELD, "mt-1.5 font-mono")}
                />
              </div>
            )}
            {(form.transitionId === "PR-03" ||
              form.transitionId === "PR-05" ||
              form.transitionId === "PR-07" ||
              form.transitionId === "PR-08") && (
              <div>
                <label
                  htmlFor="garuda-voa-private-staff-note"
                  className={cn(EYEBROW, "block")}
                >
                  Private staff note (never shown to the customer)
                </label>
                <textarea
                  id="garuda-voa-private-staff-note"
                  value={form.privateStaffNote}
                  onChange={(e) =>
                    handleFieldChange("privateStaffNote", e.target.value)
                  }
                  rows={3}
                  maxLength={4000}
                  className={cn(FIELD, "mt-1.5")}
                />
              </div>
            )}
            {(form.transitionId === "PR-04" ||
              form.transitionId === "PR-06" ||
              form.transitionId === "PR-07") && (
              <div>
                <label
                  htmlFor="garuda-voa-evidence-id"
                  className={cn(EYEBROW, "block")}
                >
                  Evidence id
                </label>
                <input
                  id="garuda-voa-evidence-id"
                  type="text"
                  value={form.evidenceId}
                  onChange={(e) =>
                    handleFieldChange("evidenceId", e.target.value)
                  }
                  className={cn(FIELD, "mt-1.5 font-mono")}
                />
              </div>
            )}
            {(form.transitionId === "PR-09" ||
              form.transitionId === "PR-10") && (
              <div>
                <label
                  htmlFor="garuda-voa-resolved-block-id"
                  className={cn(EYEBROW, "block")}
                >
                  Resolved block id
                </label>
                {/* Prefilled read-only from the practice's own
                    `active_block_id` — never a free-text field a staffer
                    types (cross-family review binding). */}
                <input
                  id="garuda-voa-resolved-block-id"
                  type="text"
                  value={practice.active_block_id ?? ""}
                  readOnly
                  disabled
                  className={cn(
                    FIELD,
                    "mt-1.5 cursor-not-allowed font-mono text-[var(--tx-secondary)]",
                  )}
                />
                {!practice.active_block_id && (
                  <p className="mt-2 text-xs text-[var(--bz-copper-text)]">
                    Blocked — no active block id on record, so this transition
                    cannot be applied yet.
                  </p>
                )}
              </div>
            )}
            {form.transitionId === "PR-11" && (
              <>
                <div>
                  <label
                    htmlFor="garuda-voa-artifact-id"
                    className={cn(EYEBROW, "block")}
                  >
                    Artifact id
                  </label>
                  <input
                    id="garuda-voa-artifact-id"
                    type="text"
                    value={form.artifactId}
                    onChange={(e) =>
                      handleFieldChange("artifactId", e.target.value)
                    }
                    className={cn(FIELD, "mt-1.5 font-mono")}
                  />
                </div>
                <div>
                  <label
                    htmlFor="garuda-voa-artifact-digest"
                    className={cn(EYEBROW, "block")}
                  >
                    Artifact digest (sha256)
                  </label>
                  <input
                    id="garuda-voa-artifact-digest"
                    type="text"
                    value={form.artifactDigest}
                    onChange={(e) =>
                      handleFieldChange("artifactDigest", e.target.value)
                    }
                    placeholder="64 hex characters"
                    className={cn(FIELD, "mt-1.5 font-mono")}
                  />
                </div>
              </>
            )}

            <div className="flex items-center gap-2.5 pt-1">
              <Button
                onClick={submitTransition}
                disabled={isSubmitting}
                className="h-11 rounded bg-[var(--state-success)] px-6 text-[13px] font-semibold tracking-[0.02em] text-white hover:bg-[var(--state-success)]/90"
              >
                {isSubmitting && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Apply
              </Button>
              <button
                type="button"
                onClick={() => setForm(EMPTY_FORM)}
                disabled={isSubmitting}
                className={cn(
                  "h-11 rounded-full border border-[var(--bz-border-hover)] px-5 text-[13px] font-semibold text-[var(--tx-pure)] transition-colors hover:border-[var(--bz-copper)] disabled:opacity-50",
                  FOCUS,
                )}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
