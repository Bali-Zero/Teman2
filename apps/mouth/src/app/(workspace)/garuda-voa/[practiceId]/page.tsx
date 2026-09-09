"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
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
import type {
  PracticeTransitionRequest,
  StaffPracticeView,
  TransitionId,
} from "../types";

function newIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `garuda-voa-staff-${Date.now()}`;
}

// Never render or link a customer document/artifact identifier here — the
// staff surface shows practice metadata only (spec step8: "Never link
// artifact ids").
function StatusBadge({ state }: { state: string }) {
  return (
    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-[var(--surface-raised)] text-[var(--bz-text-1)]">
      {state}
    </span>
  );
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
      <div className="min-h-[50vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-[var(--bz-accent)]" />
      </div>
    );
  }

  if (loadError || !practice) {
    return (
      <div className="min-h-[50vh] flex flex-col items-center justify-center gap-4">
        <AlertCircle className="w-12 h-12 text-[var(--state-danger)]" />
        <p className="text-[var(--bz-text-1)]">
          {loadError || "Practice not found"}
        </p>
        <Button onClick={() => router.push("/garuda-voa")} variant="default">
          <ArrowLeft className="w-4 h-4 mr-2" />
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
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.push("/garuda-voa")}
          className="flex items-center gap-2 text-[var(--bz-text-2)]"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
      </div>

      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-[var(--bz-text-1)] font-mono">
            {practice.practice_id}
          </h1>
          <StatusBadge state={practice.state} />
        </div>
      </div>

      <div className="rounded-xl p-6 border border-[var(--bz-border)] bg-[var(--bz-card)] space-y-4">
        <h2 className="text-lg font-semibold text-[var(--bz-text-1)]">
          Practice details
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div>
            <label className="block text-[var(--bz-text-2)] mb-1">Order</label>
            <p className="font-mono text-[var(--bz-text-1)]">
              {practice.order_id}
            </p>
          </div>
          <div>
            <label className="block text-[var(--bz-text-2)] mb-1">
              Updated
            </label>
            <p className="text-[var(--bz-text-1)]">
              {new Date(practice.updated_at).toLocaleString("en-GB")}
            </p>
          </div>
          {practice.customer_reason_key && (
            <div>
              <label className="block text-[var(--bz-text-2)] mb-1">
                Customer reason key
              </label>
              <p className="font-mono text-xs text-[var(--bz-text-1)]">
                {practice.customer_reason_key}
              </p>
            </div>
          )}
          {practice.required_action_key && (
            <div>
              <label className="block text-[var(--bz-text-2)] mb-1">
                Required action key
              </label>
              <p className="font-mono text-xs text-[var(--bz-text-1)]">
                {practice.required_action_key}
              </p>
            </div>
          )}
          {practice.private_staff_note && (
            <div className="md:col-span-2">
              <label className="block text-[var(--bz-text-2)] mb-1">
                Private staff note
              </label>
              <p className="text-[var(--bz-text-1)] whitespace-pre-wrap">
                {practice.private_staff_note}
              </p>
            </div>
          )}
        </div>

        {isAdmin && (
          <div className="pt-4 border-t border-[var(--bz-border)]">
            <label
              htmlFor="garuda-voa-assign"
              className="block text-sm text-[var(--bz-text-2)] mb-1"
            >
              Assigned to
            </label>
            <select
              id="garuda-voa-assign"
              value={practice.assigned_to || ""}
              disabled={isAssigning}
              onChange={(e) => handleAssign(e.target.value)}
              className="w-full max-w-xs border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] rounded-lg px-3 py-2 text-sm"
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
              <p className="mt-1 text-xs text-[var(--bz-text-2)]">
                Assignee list unavailable — reload before assigning.
              </p>
            )}
          </div>
        )}
      </div>

      <div className="rounded-xl p-6 border border-[var(--bz-border)] bg-[var(--bz-card)] space-y-4">
        <h2 className="text-lg font-semibold text-[var(--bz-text-1)]">
          Transitions
        </h2>
        {allowedTransitions.length === 0 ? (
          <p className="text-sm text-[var(--bz-text-2)]">
            No transitions are available from this state.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {allowedTransitions.map((option) => (
              <Button
                key={option.transitionId}
                variant={
                  form.transitionId === option.transitionId
                    ? "default"
                    : "outline"
                }
                onClick={() => selectTransition(option.transitionId)}
                data-testid={`transition-${option.transitionId}`}
              >
                {option.label}
              </Button>
            ))}
          </div>
        )}

        {form.transitionId && (
          <div className="space-y-3 pt-4 border-t border-[var(--bz-border)]">
            {(form.transitionId === "PR-03" ||
              form.transitionId === "PR-05" ||
              form.transitionId === "PR-07" ||
              form.transitionId === "PR-08") && (
              <div>
                <label className="block text-sm text-[var(--bz-text-2)] mb-1">
                  Customer reason key
                </label>
                <input
                  type="text"
                  value={form.customerReasonKey}
                  onChange={(e) =>
                    handleFieldChange("customerReasonKey", e.target.value)
                  }
                  placeholder="garuda_voa.practice.…"
                  className="w-full border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] rounded-lg px-3 py-2 text-sm font-mono"
                />
              </div>
            )}
            {(form.transitionId === "PR-03" ||
              form.transitionId === "PR-05" ||
              form.transitionId === "PR-08") && (
              <div>
                <label className="block text-sm text-[var(--bz-text-2)] mb-1">
                  Required action key
                </label>
                <input
                  type="text"
                  value={form.requiredActionKey}
                  onChange={(e) =>
                    handleFieldChange("requiredActionKey", e.target.value)
                  }
                  placeholder="garuda_voa.action.…"
                  className="w-full border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] rounded-lg px-3 py-2 text-sm font-mono"
                />
              </div>
            )}
            {(form.transitionId === "PR-03" ||
              form.transitionId === "PR-05" ||
              form.transitionId === "PR-07" ||
              form.transitionId === "PR-08") && (
              <div>
                <label className="block text-sm text-[var(--bz-text-2)] mb-1">
                  Private staff note (never shown to the customer)
                </label>
                <textarea
                  value={form.privateStaffNote}
                  onChange={(e) =>
                    handleFieldChange("privateStaffNote", e.target.value)
                  }
                  rows={3}
                  maxLength={4000}
                  className="w-full border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] rounded-lg px-3 py-2 text-sm"
                />
              </div>
            )}
            {(form.transitionId === "PR-04" ||
              form.transitionId === "PR-06" ||
              form.transitionId === "PR-07") && (
              <div>
                <label className="block text-sm text-[var(--bz-text-2)] mb-1">
                  Evidence id
                </label>
                <input
                  type="text"
                  value={form.evidenceId}
                  onChange={(e) =>
                    handleFieldChange("evidenceId", e.target.value)
                  }
                  className="w-full border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] rounded-lg px-3 py-2 text-sm font-mono"
                />
              </div>
            )}
            {(form.transitionId === "PR-09" ||
              form.transitionId === "PR-10") && (
              <div>
                <label
                  htmlFor="garuda-voa-resolved-block-id"
                  className="block text-sm text-[var(--bz-text-2)] mb-1"
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
                  className="w-full border border-[var(--bz-border)] bg-[var(--surface-raised)] text-[var(--bz-text-2)] rounded-lg px-3 py-2 text-sm font-mono cursor-not-allowed"
                />
                {!practice.active_block_id && (
                  <p className="mt-1 text-xs text-[var(--state-danger)]">
                    No active block id on record — this transition cannot be
                    applied yet.
                  </p>
                )}
              </div>
            )}
            {form.transitionId === "PR-11" && (
              <>
                <div>
                  <label className="block text-sm text-[var(--bz-text-2)] mb-1">
                    Artifact id
                  </label>
                  <input
                    type="text"
                    value={form.artifactId}
                    onChange={(e) =>
                      handleFieldChange("artifactId", e.target.value)
                    }
                    className="w-full border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] rounded-lg px-3 py-2 text-sm font-mono"
                  />
                </div>
                <div>
                  <label className="block text-sm text-[var(--bz-text-2)] mb-1">
                    Artifact digest (sha256)
                  </label>
                  <input
                    type="text"
                    value={form.artifactDigest}
                    onChange={(e) =>
                      handleFieldChange("artifactDigest", e.target.value)
                    }
                    placeholder="64 hex characters"
                    className="w-full border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] rounded-lg px-3 py-2 text-sm font-mono"
                  />
                </div>
              </>
            )}

            <div className="flex items-center gap-2 pt-2">
              <Button onClick={submitTransition} disabled={isSubmitting}>
                {isSubmitting && (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                )}
                Apply
              </Button>
              <Button
                variant="outline"
                onClick={() => setForm(EMPTY_FORM)}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
