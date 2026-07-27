"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import {
  ArrowLeft,
  User,
  Mail,
  Phone,
  Calendar,
  DollarSign,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  FileText,
  MessageCircle,
  MoreVertical,
  Edit,
  Trash2,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { toast as sonnerToast } from "sonner";
import { api } from "@/lib/api";
import type { Practice } from "@/lib/api/crm/crm.types";
import {
  STATUS_LABELS as STATUS_DROPDOWN_LABELS,
  getAllowedNextStatuses,
  type PracticeStatus,
} from "@/lib/api/crm/state-machine";
import { casesMetrics } from "@/lib/metrics/cases-metrics";
import { logger } from "@/lib/logger";
import { toError } from "@/lib/types/common";
import { Money } from "@balizero/core";
import {
  COLUMN_COLORS,
  getStatusColumn,
} from "@/components/process/kanban-colors";
import { RequiredDocumentsCard } from "./RequiredDocumentsCard";
import { useTeamMemberOptions } from "@/hooks/useTeamMembers";
import { initialsOf } from "@/data/team-roster";
import { AvatarWithFallback } from "@/components/ui/avatar-with-fallback";

// Status badge styling — WS2 (GARUDA OS): reuses the canonical kanban column
// palette (kanban-colors.ts) so the detail page can never drift from the
// board. "cancelled" is outside the 5-step workflow and reads --state-danger.
const statusBadgeStyle = (status: string): React.CSSProperties => {
  if (status === "cancelled") {
    return {
      background: "color-mix(in srgb, var(--state-danger) 10%, transparent)",
      color: "var(--state-danger)",
    };
  }
  const colors = COLUMN_COLORS[getStatusColumn(status)];
  return { background: colors.badgeBg, color: colors.textColor };
};

// Status mapping for display — icons per status; colors come from
// statusBadgeStyle (kanban palette) instead of per-page Tailwind steps.
const STATUS_INFO: Record<string, { label: string; icon: React.ReactNode }> = {
  inquiry: {
    label: "Inquiry",
    icon: <AlertCircle className="w-4 h-4" />,
  },
  waiting_documents: {
    label: "Waiting Documents",
    icon: <FileText className="w-4 h-4" />,
  },
  sending_invoice: {
    label: "Sending Invoice",
    icon: <DollarSign className="w-4 h-4" />,
  },
  on_process: {
    label: "On Process",
    icon: <Clock className="w-4 h-4" />,
  },
  completed: {
    label: "Completed",
    icon: <CheckCircle2 className="w-4 h-4" />,
  },
  cancelled: {
    label: "Cancelled",
    icon: <XCircle className="w-4 h-4" />,
  },
};

export default function CaseDetailPage() {
  const router = useRouter();
  const params = useParams();
  const toast = useToast();
  const caseId = params?.id ? parseInt(params.id as string) : null;

  const { options: teamMemberOptions } = useTeamMemberOptions();
  const [practice, setPractice] = useState<Practice | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit modal state
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editForm, setEditForm] = useState({
    status: "",
    priority: "",
    payment_status: "",
    quoted_price: "",
    actual_price: "",
    assigned_to: "",
    start_date: "",
  });
  // Whether the current user is allowed to perform admin-only state
  // transitions (e.g. completed → cancelled, cancelled → inquiry).
  // Hydrated from `api.isAdmin()` after the profile loads.
  const [isAdmin, setIsAdmin] = useState(false);

  // Inline notes edit
  const [isEditingNotes, setIsEditingNotes] = useState(false);
  const [notesValue, setNotesValue] = useState("");
  const [isSavingNotes, setIsSavingNotes] = useState(false);

  // Inline payment status update
  const [isUpdatingPayment, setIsUpdatingPayment] = useState(false);

  // Inline priority cycle
  const [isUpdatingPriority, setIsUpdatingPriority] = useState(false);

  // More options dropdown
  const [showMoreMenu, setShowMoreMenu] = useState(false);
  const moreMenuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!showMoreMenu) return;
    const handler = (e: MouseEvent) => {
      if (
        moreMenuRef.current &&
        !moreMenuRef.current.contains(e.target as Node)
      ) {
        setShowMoreMenu(false);
      }
    };
    const escapeHandler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowMoreMenu(false);
    };
    document.addEventListener("mousedown", handler);
    document.addEventListener("keydown", escapeHandler);
    return () => {
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("keydown", escapeHandler);
    };
  }, [showMoreMenu]);

  // Inline price edit
  const [editingPrice, setEditingPrice] = useState<"quoted" | "actual" | null>(
    null,
  );
  const [priceValue, setPriceValue] = useState("");
  const [isSavingPrice, setIsSavingPrice] = useState(false);

  // Performance tracking
  const startTime = useRef(performance.now());
  const userEmail = useRef<string | null>(null);

  // Track page view and performance on mount
  useEffect(() => {
    const initMetrics = async () => {
      try {
        const user = await api.getProfile();
        userEmail.current = user.email;
        setIsAdmin(api.isAdmin());

        if (caseId) {
          casesMetrics.trackPageView("detail", caseId, user.email);
        }
      } catch (err) {
        logger.error(
          "Failed to init metrics",
          { component: "CaseDetail", action: "initMetrics" },
          toError(err),
        );
      }
    };

    initMetrics();
  }, [caseId]);

  useEffect(() => {
    const loadPractice = async () => {
      if (!caseId) {
        setError("Invalid process ID");
        setIsLoading(false);
        casesMetrics.trackError(
          "Invalid Case ID",
          "No case ID provided",
          "CasesDetailPage",
          undefined,
          userEmail.current || undefined,
        );
        return;
      }

      setIsLoading(true);
      setError(null);
      casesMetrics.startPerformanceMark("case_detail_load");
      const apiStart = performance.now();

      try {
        // ✅ Using dedicated GET endpoint for single practice (efficient: 1 query instead of loading 200 practices)
        const foundPractice = await api.crm.getPractice(caseId);
        const apiDuration = performance.now() - apiStart;
        casesMetrics.trackApiCall(
          `/api/crm/practices/${caseId}`,
          "GET",
          true,
          apiDuration,
          caseId,
          userEmail.current || undefined,
        );

        setPractice(foundPractice);
        setNotesValue(foundPractice.notes || "");
        casesMetrics.endPerformanceMark(
          "case_detail_load",
          caseId,
          userEmail.current || undefined,
        );
      } catch (err) {
        const apiDuration = performance.now() - apiStart;
        casesMetrics.trackApiCall(
          `/api/crm/practices/${caseId}`,
          "GET",
          false,
          apiDuration,
          caseId,
          userEmail.current || undefined,
        );

        logger.error(
          "Failed to load process",
          { component: "CaseDetail", action: "loadProcess" },
          toError(err),
        );
        setError("Failed to load process details");
        toast.error("Error", "Failed to load process details");
        casesMetrics.trackError(
          "API Error",
          (err as Error).message,
          "CasesDetailPage",
          caseId,
          userEmail.current || undefined,
        );
      } finally {
        setIsLoading(false);
      }
    };

    loadPractice();
  }, [caseId]);

  const formatDate = (dateString?: string) => {
    if (!dateString) return "Not set";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  };

  const saveNotes = async () => {
    if (!practice || !caseId) return;
    setIsSavingNotes(true);
    try {
      const user = await api.getProfile();
      await api.crm.updatePractice(caseId, { notes: notesValue });
      setPractice((prev) => (prev ? { ...prev, notes: notesValue } : prev));
      toast.success("Notes saved");
      setIsEditingNotes(false);
    } catch (err) {
      toast.error("Failed to save notes", (err as Error).message);
    } finally {
      setIsSavingNotes(false);
    }
  };

  const cyclePaymentStatus = async () => {
    if (!practice || !caseId || isUpdatingPayment) return;
    const cycle: string[] = ["unpaid", "partial", "paid"];
    const current = practice.payment_status || "unpaid";
    const nextIndex = (cycle.indexOf(current) + 1) % cycle.length;
    const nextStatus = cycle[nextIndex];
    setIsUpdatingPayment(true);
    try {
      const user = await api.getProfile();
      await api.crm.updatePractice(caseId, { payment_status: nextStatus });
      setPractice((prev) =>
        prev ? { ...prev, payment_status: nextStatus } : prev,
      );
      toast.success("Payment status updated", `→ ${nextStatus}`);
    } catch (err) {
      toast.error("Failed to update payment status", (err as Error).message);
    } finally {
      setIsUpdatingPayment(false);
    }
  };

  const cyclePriority = async () => {
    if (!practice || !caseId || isUpdatingPriority) return;
    const cycle: string[] = ["normal", "high", "urgent"];
    const current = practice.priority || "normal";
    const nextIndex = (cycle.indexOf(current) + 1) % cycle.length;
    const nextPriority = cycle[nextIndex];
    setIsUpdatingPriority(true);
    try {
      const user = await api.getProfile();
      await api.crm.updatePractice(caseId, { priority: nextPriority });
      setPractice((prev) =>
        prev ? { ...prev, priority: nextPriority } : prev,
      );
      toast.success("Priority updated", `→ ${nextPriority}`);
    } catch (err) {
      toast.error("Failed to update priority", (err as Error).message);
    } finally {
      setIsUpdatingPriority(false);
    }
  };

  const savePrice = async (field: "quoted_price" | "actual_price") => {
    if (!practice || !caseId) return;
    const num = Number(priceValue);
    if (isNaN(num) || num < 0) {
      setEditingPrice(null);
      return;
    }
    setIsSavingPrice(true);
    try {
      const user = await api.getProfile();
      await api.crm.updatePractice(caseId, { [field]: num });
      setPractice((prev) => (prev ? { ...prev, [field]: num } : prev));
      toast.success("Price updated");
    } catch (err) {
      toast.error("Failed to update price", (err as Error).message);
    } finally {
      setIsSavingPrice(false);
      setEditingPrice(null);
    }
  };

  const [isJumpingStatus, setIsJumpingStatus] = useState<string | null>(null);

  const jumpToStatus = async (newStatus: string) => {
    if (
      !practice ||
      !caseId ||
      practice.status === newStatus ||
      isJumpingStatus
    )
      return;
    setIsJumpingStatus(newStatus);
    try {
      const user = await api.getProfile();
      await api.crm.updatePractice(caseId, { status: newStatus });
      setPractice((prev) => (prev ? { ...prev, status: newStatus } : prev));
      toast.success("Status updated", `→ ${newStatus.replace(/_/g, " ")}`);
    } catch (err) {
      toast.error("Failed to update status", (err as Error).message);
    } finally {
      setIsJumpingStatus(null);
    }
  };

  const handleEditClick = () => {
    if (!practice) return;

    casesMetrics.trackButtonClick(
      "Edit",
      "CasesDetailPage",
      caseId || undefined,
      undefined,
      userEmail.current || undefined,
    );
    casesMetrics.trackModal(
      "edit",
      "open",
      caseId || undefined,
      userEmail.current || undefined,
    );

    setEditForm({
      status: practice.status || "",
      priority: practice.priority || "normal",
      payment_status: practice.payment_status || "unpaid",
      quoted_price: practice.quoted_price?.toString() || "",
      actual_price: practice.actual_price?.toString() || "",
      assigned_to: practice.assigned_to || "",
      start_date: practice.start_date ? practice.start_date.split("T")[0] : "",
    });
    setIsEditModalOpen(true);
  };

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isSaving) setIsEditModalOpen(false);
    };
    if (isEditModalOpen) document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isEditModalOpen, isSaving]);

  const handleSaveChanges = async () => {
    if (!practice || !caseId) return;
    setIsSaving(true);

    const apiStart = performance.now();

    try {
      const user = await api.getProfile();
      const updates: Partial<
        Pick<
          Practice,
          | "status"
          | "priority"
          | "payment_status"
          | "quoted_price"
          | "actual_price"
          | "assigned_to"
          | "start_date"
        >
      > = {};

      if (editForm.status && editForm.status !== practice.status)
        updates.status = editForm.status;
      if (editForm.priority && editForm.priority !== practice.priority)
        updates.priority = editForm.priority;
      if (
        editForm.payment_status &&
        editForm.payment_status !== practice.payment_status
      )
        updates.payment_status = editForm.payment_status;
      if (
        editForm.quoted_price &&
        Number(editForm.quoted_price) !== practice.quoted_price
      )
        updates.quoted_price = Number(editForm.quoted_price);
      if (
        editForm.actual_price &&
        Number(editForm.actual_price) !== practice.actual_price
      )
        updates.actual_price = Number(editForm.actual_price);
      if (editForm.assigned_to !== (practice.assigned_to || ""))
        updates.assigned_to = editForm.assigned_to || undefined;
      const currentStartDate = practice.start_date
        ? practice.start_date.split("T")[0]
        : "";
      if (editForm.start_date !== currentStartDate)
        updates.start_date = editForm.start_date || undefined;

      if (Object.keys(updates).length === 0) {
        toast.error("No Changes", "No fields were modified.");
        casesMetrics.trackModal("edit", "close", caseId, user.email);
        setIsEditModalOpen(false);
        setIsSaving(false);
        return;
      }

      const fieldsUpdated = Object.keys(updates);
      const updateType = updates.status
        ? "status"
        : updates.payment_status
          ? "payment"
          : "details";

      // Log pre-request details
      logger.info(`Attempting to update case ${caseId}`, {
        component: "CaseDetail",
        action: "updateCase",
        user: user.email,
      });

      await api.crm.updatePractice(caseId, updates);
      const apiDuration = performance.now() - apiStart;
      casesMetrics.trackApiCall(
        "/api/crm/practices/update",
        "PATCH",
        true,
        apiDuration,
        caseId,
        user.email,
      );

      // Reload practice data with dedicated endpoint
      const updatedPractice = await api.crm.getPractice(caseId);
      setPractice(updatedPractice);

      // Track case update
      casesMetrics.trackCaseUpdate(
        caseId,
        fieldsUpdated,
        updateType,
        user.email,
      );
      casesMetrics.trackModal("edit", "submit", caseId, user.email);

      toast.success("Process Updated", "Successfully updated process details.");
      setIsEditModalOpen(false);
    } catch (err) {
      const apiDuration = performance.now() - apiStart;
      casesMetrics.trackApiCall(
        "/api/crm/practices/update",
        "PATCH",
        false,
        apiDuration,
        caseId,
        userEmail.current || undefined,
      );
      casesMetrics.trackError(
        "Update Failed",
        (err as Error).message,
        "CasesDetailPage",
        caseId,
        userEmail.current || undefined,
      );

      // Detailed error logging
      const errorDetails = {
        caseId,
        updates: editForm,
        userEmail: userEmail.current,
        error:
          err instanceof Error
            ? {
                message: err.message,
                name: err.name,
                stack: err.stack,
              }
            : err,
        apiDuration,
        timestamp: new Date().toISOString(),
        endpoint: `/api/crm/practices/${caseId}`,
      };

      logger.error(
        "Failed to update case details",
        { component: "CaseDetail", action: "updateCase" },
        toError(err),
      );

      // Check for specific error types and provide user-friendly messages
      let errorMessage = "Failed to update process details.";
      if (err instanceof Error) {
        if (
          err.message.includes("401") ||
          err.message.includes("Unauthorized")
        ) {
          errorMessage = "Authentication failed. Please login again.";
          logger.error(
            "Authentication error - user may need to re-authenticate",
            {
              component: "CaseDetail",
              action: "updateCase",
            },
          );
        } else if (
          err.message.includes("403") ||
          err.message.includes("Forbidden")
        ) {
          errorMessage = "You do not have permission to update this process.";
          logger.error("Authorization error - user may not have permission", {
            component: "CaseDetail",
            action: "updateCase",
          });
        } else if (
          err.message.includes("404") ||
          err.message.includes("Not Found")
        ) {
          errorMessage = "Process not found. It may have been deleted.";
          logger.error("Case not found - may have been deleted", {
            component: "CaseDetail",
            action: "updateCase",
          });
        } else if (
          err.message.includes("Network") ||
          err.message.includes("fetch")
        ) {
          errorMessage =
            "Network error. Please check your connection and try again.";
          logger.error("Network error - backend may be unreachable", {
            component: "CaseDetail",
            action: "updateCase",
          });
        } else if (err.message.includes("CORS")) {
          errorMessage = "CORS error. Please contact support.";
          logger.error(
            "CORS error - backend CORS configuration may be incorrect",
            {
              component: "CaseDetail",
              action: "updateCase",
            },
          );
        }
      }

      toast.error("Error", errorMessage);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2
            className="w-12 h-12 animate-spin mx-auto mb-4"
            style={{ color: "var(--bz-accent)" }}
          />
          <p style={{ color: "var(--bz-text-2)" }}>
            Loading process details...
          </p>
        </div>
      </div>
    );
  }

  if (error || !practice) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-16 h-16 text-[var(--state-danger)] mx-auto mb-4" />
          <h2
            className="text-2xl font-bold mb-2"
            style={{ color: "var(--bz-text-1)" }}
          >
            {error || "Process Not Found"}
          </h2>
          <p className="mb-6" style={{ color: "var(--bz-text-2)" }}>
            The process you're looking for doesn't exist or you don't have
            permission to view it.
          </p>
          <Button onClick={() => router.push("/process")} variant="default">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Process
          </Button>
        </div>
      </div>
    );
  }

  const statusInfo = STATUS_INFO[practice.status] || {
    label: practice.status,
    icon: <FileText className="w-4 h-4" />,
  };
  const statusStyle = statusBadgeStyle(practice.status);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={() => {
              casesMetrics.trackButtonClick(
                "Back to Process",
                "CasesDetailPage",
                caseId || undefined,
                "/process",
                userEmail.current || undefined,
              );
              router.back();
            }}
            className="flex items-center gap-2 transition-colors"
            style={{ color: "var(--bz-text-2)" }}
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back</span>
          </button>
          {practice.client_id && (
            <>
              <span
                style={{ color: "var(--bz-text-2)" }}
                className="opacity-30"
              >
                /
              </span>
              <button
                onClick={() =>
                  router.push(`/clients/${practice.client_id}?tab=process`)
                }
                className="flex items-center gap-1.5 transition-colors text-sm"
                style={{ color: "var(--bz-text-2)" }}
              >
                <User className="w-3.5 h-3.5" />
                <span>
                  {practice.client_name || `Client #${practice.client_id}`}
                </span>
              </button>
            </>
          )}
        </div>

        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2 flex-wrap">
              <h1
                className="text-3xl font-bold"
                style={{ color: "var(--bz-text-1)" }}
              >
                {practice.practice_type_code
                  ?.toUpperCase()
                  .replace(/_/g, " ") || "Process"}{" "}
                #{practice.id}
              </h1>
              <div
                className="flex items-center gap-2 px-3 py-1 rounded-full"
                style={statusStyle}
              >
                {statusInfo.icon}
                <span className="text-sm font-medium">{statusInfo.label}</span>
              </div>
              {(() => {
                // Age in current status: use last status transition date or updated_at
                const lastTransition = practice.status_transitions?.length
                  ? practice.status_transitions[
                      practice.status_transitions.length - 1
                    ]
                  : null;
                const sinceDate = lastTransition?.at || practice.updated_at;
                if (!sinceDate) return null;
                const ageDays = Math.floor(
                  (Date.now() - new Date(sinceDate).getTime()) / 86400000,
                );
                if (ageDays === 0) return null;
                const label =
                  ageDays >= 30
                    ? `${Math.floor(ageDays / 30)}mo`
                    : ageDays >= 7
                      ? `${Math.floor(ageDays / 7)}w`
                      : `${ageDays}d`;
                const isStale = ageDays > 14;
                const isVeryStale = ageDays > 30;
                return (
                  <span
                    className="text-[10px] px-2 py-1 rounded-full font-medium"
                    style={{
                      background: isVeryStale
                        ? "color-mix(in srgb, var(--state-danger) 15%, transparent)"
                        : isStale
                          ? "color-mix(in srgb, var(--state-warning) 15%, transparent)"
                          : "var(--surface-raised)",
                      color: isVeryStale
                        ? "var(--state-danger)"
                        : isStale
                          ? "var(--state-warning)"
                          : "var(--bz-text-2)",
                    }}
                    title={`In current status for ${ageDays} days`}
                  >
                    {label} in status
                  </span>
                );
              })()}
            </div>
            <p style={{ color: "var(--bz-text-2)" }}>
              {practice.practice_type_name || "Process Details"}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {practice.payment_status !== undefined && (
              <button
                onClick={cyclePaymentStatus}
                disabled={isUpdatingPayment}
                title="Click to cycle payment status: unpaid → partial → paid"
                aria-label="Cycle payment status"
                className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-all disabled:opacity-50"
                style={{
                  background:
                    practice.payment_status === "paid"
                      ? "color-mix(in srgb, var(--state-success) 12%, transparent)"
                      : practice.payment_status === "partial"
                        ? "color-mix(in srgb, var(--state-warning) 12%, transparent)"
                        : "color-mix(in srgb, var(--state-danger) 12%, transparent)",
                  color:
                    practice.payment_status === "paid"
                      ? "var(--state-success)"
                      : practice.payment_status === "partial"
                        ? "var(--state-warning)"
                        : "var(--state-danger)",
                  border:
                    practice.payment_status === "paid"
                      ? "1px solid color-mix(in srgb, var(--state-success) 25%, transparent)"
                      : practice.payment_status === "partial"
                        ? "1px solid color-mix(in srgb, var(--state-warning) 25%, transparent)"
                        : "1px solid color-mix(in srgb, var(--state-danger) 25%, transparent)",
                }}
              >
                {isUpdatingPayment ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <span
                    className="w-1.5 h-1.5 rounded-full"
                    style={{
                      background:
                        practice.payment_status === "paid"
                          ? "var(--state-success)"
                          : practice.payment_status === "partial"
                            ? "var(--state-warning)"
                            : "var(--state-danger)",
                    }}
                  />
                )}
                <span className="capitalize">
                  {practice.payment_status || "unpaid"}
                </span>
              </button>
            )}
            {(practice.actual_price || practice.quoted_price) && (
              <div
                className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1.5 rounded-lg tabular-nums"
                style={{
                  background: "var(--bz-accent-subtle)",
                  color: "var(--bz-accent)",
                  border:
                    "1px solid color-mix(in srgb, var(--bz-accent) 20%, transparent)",
                }}
                title={
                  practice.actual_price
                    ? "Actual price"
                    : "Quoted price (not yet invoiced)"
                }
              >
                <DollarSign className="w-3.5 h-3.5" />
                <Money
                  value={practice.actual_price ?? practice.quoted_price ?? 0}
                />
                {!practice.actual_price && (
                  <span className="opacity-60 font-normal ml-0.5">est</span>
                )}
              </div>
            )}
            <Button variant="outline" size="sm" onClick={handleEditClick}>
              <Edit className="w-4 h-4 mr-2" />
              Edit
            </Button>
            <div className="relative" ref={moreMenuRef}>
              <Button
                variant="outline"
                size="sm"
                aria-label="More options"
                onClick={() => setShowMoreMenu((v) => !v)}
              >
                <MoreVertical className="w-4 h-4" />
              </Button>
              {showMoreMenu && (
                <div className="absolute right-0 top-full mt-1 z-50 min-w-[180px] rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] shadow-xl py-1 animate-in fade-in zoom-in-95 duration-100">
                  <button
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[var(--bz-text-1)] hover:bg-[var(--bz-card)] transition-colors"
                    onClick={() => {
                      navigator.clipboard.writeText(window.location.href);
                      toast.success(
                        "Copied",
                        "Process link copied to clipboard",
                      );
                      setShowMoreMenu(false);
                    }}
                  >
                    <FileText className="w-3.5 h-3.5 opacity-60" />
                    Copy link
                  </button>
                  {practice?.client_phone && (
                    <button
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[var(--bz-text-1)] hover:bg-[var(--bz-card)] transition-colors"
                      onClick={() => {
                        const phone = practice.client_phone?.replace(/\D/g, "");
                        window.open(
                          `https://wa.me/${phone}?text=Hi ${practice.client_name}, regarding your process...`,
                          "_blank",
                        );
                        setShowMoreMenu(false);
                      }}
                    >
                      <MessageCircle className="w-3.5 h-3.5 text-[var(--accent-whatsapp)]" />
                      WhatsApp client
                    </button>
                  )}
                  {practice?.client_email && (
                    <button
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[var(--bz-text-1)] hover:bg-[var(--bz-card)] transition-colors"
                      onClick={() => {
                        window.open(
                          `mailto:${practice.client_email}`,
                          "_blank",
                        );
                        setShowMoreMenu(false);
                      }}
                    >
                      <Mail className="w-3.5 h-3.5 text-[var(--state-info)]" />
                      Email client
                    </button>
                  )}
                  {practice?.client_id && (
                    <button
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[var(--bz-text-1)] hover:bg-[var(--bz-card)] transition-colors"
                      onClick={() => {
                        router.push(`/clients/${practice.client_id}`);
                        setShowMoreMenu(false);
                      }}
                    >
                      <User className="w-3.5 h-3.5 opacity-60" />
                      View client profile
                    </button>
                  )}
                  <div className="my-1 border-t border-[var(--bz-border)]" />
                  <button
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[var(--state-danger)] hover:bg-[color-mix(in_srgb,var(--state-danger)_10%,transparent)] transition-colors"
                    onClick={async () => {
                      setShowMoreMenu(false);
                      if (!caseId) return;
                      const confirmed = window.confirm(
                        "Delete this process? This action will cancel the process and cannot be undone.",
                      );
                      if (!confirmed) return;
                      try {
                        const user = await api.getProfile();
                        await api.crm.deletePractice(caseId, user.email);
                        sonnerToast.success("Process deleted");
                        router.push("/process");
                      } catch (err) {
                        logger.error(
                          "Failed to delete process",
                          { component: "CaseDetail", action: "deleteProcess" },
                          toError(err),
                        );
                        sonnerToast.error("Failed to delete process");
                      }
                    }}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Delete process
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Workflow Progress Stepper — colors read the canonical kanban column
          palette (kanban-colors.ts); filled steps carry dark ink on the pastel
          fills (white on pastel would fail AA). */}
      {(() => {
        const STEPS = [
          {
            key: "inquiry",
            label: "Inquiry",
            color: COLUMN_COLORS.inquiry.textColor,
          },
          {
            key: "waiting_documents",
            label: "Documents",
            color: COLUMN_COLORS.waiting_documents.textColor,
          },
          {
            key: "sending_invoice",
            label: "Invoice",
            color: COLUMN_COLORS.sending_invoice.textColor,
          },
          {
            key: "on_process",
            label: "Processing",
            color: COLUMN_COLORS.on_process.textColor,
          },
          {
            key: "completed",
            label: "Done",
            color: COLUMN_COLORS.completed.textColor,
          },
        ];
        const currentIdx = STEPS.findIndex((s) => {
          if (practice.status === s.key) return true;
          // map legacy statuses
          if (
            s.key === "sending_invoice" &&
            (practice.status === "waiting_payment" ||
              practice.status === "quotation_sent")
          )
            return true;
          if (
            s.key === "on_process" &&
            (practice.status === "in_progress" ||
              practice.status === "submitted_to_gov" ||
              practice.status === "approved")
          )
            return true;
          return false;
        });
        return (
          <div className="mb-6 flex items-center gap-0">
            {STEPS.map((step, idx) => {
              const isDone = idx < currentIdx;
              const isCurrent = idx === currentIdx;
              const isJumping = isJumpingStatus === step.key;
              return (
                <React.Fragment key={step.key}>
                  <button
                    className="flex flex-col items-center gap-1 flex-shrink-0 group/step"
                    onClick={() => jumpToStatus(step.key)}
                    disabled={isCurrent || !!isJumpingStatus}
                    title={
                      isCurrent
                        ? `Current: ${step.label}`
                        : `Jump to: ${step.label}`
                    }
                  >
                    <div
                      className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold transition-all ${
                        isDone
                          ? "group-hover/step:opacity-80"
                          : isCurrent
                            ? ""
                            : "text-[var(--bz-text-2)] group-hover/step:opacity-70"
                      }`}
                      style={{
                        background:
                          isDone || isCurrent
                            ? step.color
                            : "rgba(255,255,255,0.06)",
                        ...(isDone || isCurrent
                          ? { color: "var(--bz-base)" }
                          : {}),
                        ...(isCurrent
                          ? {
                              outline: `2px solid ${step.color}`,
                              outlineOffset: "2px",
                            }
                          : {}),
                      }}
                    >
                      {isJumping ? (
                        <svg
                          className="w-3 h-3 animate-spin"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                        >
                          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
                        </svg>
                      ) : isDone ? (
                        "✓"
                      ) : (
                        idx + 1
                      )}
                    </div>
                    <span
                      className="text-[9px] font-medium whitespace-nowrap hidden sm:block transition-colors"
                      style={{
                        color: isCurrent
                          ? step.color
                          : isDone
                            ? "var(--bz-text-2)"
                            : "var(--bz-text-2)",
                        opacity: isDone ? 0.6 : 1,
                      }}
                    >
                      {step.label}
                    </span>
                  </button>
                  {idx < STEPS.length - 1 && (
                    <div
                      className="flex-1 h-[2px] mx-1 mb-3"
                      style={{
                        background:
                          idx < currentIdx
                            ? step.color
                            : "rgba(255,255,255,0.08)",
                      }}
                    />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        );
      })()}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Client Information */}
          <div
            className="rounded-xl p-6"
            style={{
              border: "1px solid var(--bz-border)",
              background: "rgba(35,35,40,0.65)",
            }}
          >
            <h2
              className="text-xl font-semibold mb-4 flex items-center gap-2"
              style={{ color: "var(--bz-text-1)" }}
            >
              <User className="w-5 h-5" />
              Client Information
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label
                  className="text-sm mb-1 block"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  Client Name
                </label>
                <button
                  onClick={() => {
                    casesMetrics.trackButtonClick(
                      "Client Name Link",
                      "CasesDetailPage",
                      caseId || undefined,
                      `/clients/${practice.client_id}`,
                      userEmail.current || undefined,
                    );
                    router.push(`/clients/${practice.client_id}`);
                  }}
                  className="hover:underline font-medium text-left transition-colors"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  {practice.client_name || "Not specified"}
                </button>
              </div>

              <div>
                <label
                  className="text-sm mb-1 block"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  Client ID
                </label>
                <button
                  onClick={() => {
                    casesMetrics.trackButtonClick(
                      "Client ID Link",
                      "CasesDetailPage",
                      caseId || undefined,
                      `/clients/${practice.client_id}`,
                      userEmail.current || undefined,
                    );
                    router.push(`/clients/${practice.client_id}`);
                  }}
                  className="hover:underline font-medium"
                  style={{ color: "var(--bz-accent)" }}
                >
                  #{practice.client_id}
                </button>
              </div>

              {practice.client_email && (
                <div>
                  <label
                    className="text-sm mb-1 block"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    Email
                  </label>
                  <a
                    href={`mailto:${practice.client_email}`}
                    onClick={() =>
                      casesMetrics.trackQuickAction(
                        "email",
                        caseId || 0,
                        "CasesDetailPage",
                        userEmail.current || undefined,
                      )
                    }
                    className="min-w-0 transition-colors flex items-start gap-2"
                    style={{ color: "var(--bz-text-1)" }}
                  >
                    <Mail className="w-4 h-4 shrink-0 mt-0.5" />
                    <span className="min-w-0 break-all">
                      {practice.client_email}
                    </span>
                  </a>
                </div>
              )}

              {practice.client_phone && (
                <div>
                  <label
                    className="text-sm mb-1 block"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    Phone
                  </label>
                  <a
                    href={`https://wa.me/${practice.client_phone.replace(/\D/g, "")}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={() =>
                      casesMetrics.trackQuickAction(
                        "whatsapp",
                        caseId || 0,
                        "CasesDetailPage",
                        userEmail.current || undefined,
                      )
                    }
                    className="transition-colors flex items-center gap-2"
                    style={{ color: "var(--bz-text-1)" }}
                  >
                    <Phone className="w-4 h-4" />
                    {practice.client_phone}
                  </a>
                </div>
              )}

              {practice.client_lead && (
                <div>
                  <label
                    className="text-sm mb-1 block"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    Lead Team Member
                  </label>
                  <p
                    className="font-medium"
                    style={{ color: "var(--bz-text-1)" }}
                  >
                    {practice.client_lead}
                  </p>
                </div>
              )}

              {practice.assigned_to &&
                (() => {
                  const assignedMember = teamMemberOptions.find(
                    (m) => m.value === practice.assigned_to,
                  );
                  const assignedName =
                    assignedMember?.label ||
                    practice.assigned_to?.split("@")[0] ||
                    "";
                  const assignedAvatar = assignedMember?.avatar ?? null;
                  return (
                    <div>
                      <label
                        className="text-sm mb-1 block"
                        style={{ color: "var(--bz-text-2)" }}
                      >
                        Assigned To
                      </label>
                      <div className="flex items-center gap-2">
                        <AvatarWithFallback
                          src={assignedAvatar}
                          alt={assignedName}
                          className="w-7 h-7 rounded-full object-cover ring-1 ring-[var(--glass-highlight)]"
                          fallback={
                            <div className="w-7 h-7 rounded-full bg-[rgba(255,255,255,0.08)] ring-1 ring-[var(--glass-highlight)] flex items-center justify-center">
                              <span className="text-[9px] font-bold uppercase text-[var(--bz-text-2)]">
                                {initialsOf(assignedName)}
                              </span>
                            </div>
                          }
                        />
                        <p
                          className="font-medium"
                          style={{ color: "var(--bz-text-1)" }}
                        >
                          {assignedName}
                        </p>
                      </div>
                    </div>
                  );
                })()}
            </div>
          </div>

          {/* Process Details */}
          <div
            className="rounded-xl p-6"
            style={{
              border: "1px solid var(--bz-border)",
              background: "rgba(35,35,40,0.65)",
            }}
          >
            <h2
              className="text-xl font-semibold mb-4 flex items-center gap-2"
              style={{ color: "var(--bz-text-1)" }}
            >
              <FileText className="w-5 h-5" />
              Process Details
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label
                  className="text-sm mb-1 block"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  Status
                </label>
                <div
                  className="inline-flex items-center gap-2 px-3 py-1 rounded-full"
                  style={statusStyle}
                >
                  {statusInfo.icon}
                  <span className="font-medium">{statusInfo.label}</span>
                </div>
              </div>

              <div>
                <label
                  className="text-sm mb-1 block"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  Priority
                </label>
                <button
                  onClick={cyclePriority}
                  disabled={isUpdatingPriority}
                  title="Click to cycle: normal → high → urgent"
                  aria-label="Cycle priority"
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium transition-colors cursor-pointer ${
                    practice.priority === "urgent"
                      ? "bg-[color-mix(in_srgb,var(--state-danger)_15%,transparent)] text-[var(--state-danger)] hover:bg-[color-mix(in_srgb,var(--state-danger)_25%,transparent)]"
                      : practice.priority === "high"
                        ? "bg-[color-mix(in_srgb,var(--state-warning)_15%,transparent)] text-[var(--state-warning)] hover:bg-[color-mix(in_srgb,var(--state-warning)_25%,transparent)]"
                        : "bg-[color-mix(in_srgb,var(--bz-text-2)_15%,transparent)] text-[var(--bz-text-2)] hover:bg-[color-mix(in_srgb,var(--bz-text-2)_25%,transparent)]"
                  }`}
                >
                  {isUpdatingPriority ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <span className="w-1.5 h-1.5 rounded-full bg-current" />
                  )}
                  <span className="capitalize">
                    {practice.priority || "normal"}
                  </span>
                </button>
              </div>

              <div>
                <label
                  className="text-sm mb-1 block"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  Payment Status
                </label>
                <button
                  onClick={cyclePaymentStatus}
                  disabled={isUpdatingPayment}
                  title="Click to cycle: unpaid → partial → paid"
                  aria-label="Cycle payment status"
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium transition-colors cursor-pointer ${
                    practice.payment_status === "paid"
                      ? "bg-[color-mix(in_srgb,var(--state-success)_15%,transparent)] text-[var(--state-success)] hover:bg-[color-mix(in_srgb,var(--state-success)_25%,transparent)]"
                      : practice.payment_status === "partial"
                        ? "bg-[color-mix(in_srgb,var(--state-warning)_15%,transparent)] text-[var(--state-warning)] hover:bg-[color-mix(in_srgb,var(--state-warning)_25%,transparent)]"
                        : "bg-[color-mix(in_srgb,var(--state-danger)_15%,transparent)] text-[var(--state-danger)] hover:bg-[color-mix(in_srgb,var(--state-danger)_25%,transparent)]"
                  }`}
                >
                  {isUpdatingPayment ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <span className="w-1.5 h-1.5 rounded-full bg-current" />
                  )}
                  <span className="capitalize">
                    {practice.payment_status || "unpaid"}
                  </span>
                </button>
              </div>

              <div>
                <label
                  className="text-sm mb-1 block"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  Quoted Price
                </label>
                {editingPrice === "quoted" ? (
                  <div className="flex items-center gap-2">
                    <input
                      autoFocus
                      type="number"
                      min="0"
                      step="1"
                      value={priceValue}
                      onChange={(e) => setPriceValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") savePrice("quoted_price");
                        if (e.key === "Escape") setEditingPrice(null);
                      }}
                      className="w-32 px-2 py-1 rounded text-sm focus:outline-none"
                      style={{
                        background: "var(--bz-base)",
                        border: "1px solid var(--bz-accent)",
                        color: "var(--bz-text-1)",
                      }}
                    />
                    {isSavingPrice ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <button
                        onClick={() => savePrice("quoted_price")}
                        className="text-xs text-[var(--state-success)]"
                      >
                        ✓
                      </button>
                    )}
                  </div>
                ) : (
                  <button
                    onClick={() => {
                      setEditingPrice("quoted");
                      setPriceValue(practice.quoted_price?.toString() || "");
                    }}
                    className="font-medium hover:underline text-left transition-colors"
                    style={{ color: "var(--bz-text-1)" }}
                    title="Click to edit"
                    aria-label="Edit quoted price"
                  >
                    {practice.quoted_price != null ? (
                      <Money value={practice.quoted_price} />
                    ) : (
                      "Not set"
                    )}
                  </button>
                )}
              </div>

              <div>
                <label
                  className="text-sm mb-1 block"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  Actual Price
                </label>
                {editingPrice === "actual" ? (
                  <div className="flex items-center gap-2">
                    <input
                      autoFocus
                      type="number"
                      min="0"
                      step="1"
                      value={priceValue}
                      onChange={(e) => setPriceValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") savePrice("actual_price");
                        if (e.key === "Escape") setEditingPrice(null);
                      }}
                      className="w-32 px-2 py-1 rounded text-sm focus:outline-none"
                      style={{
                        background: "var(--bz-base)",
                        border: "1px solid var(--bz-accent)",
                        color: "var(--bz-text-1)",
                      }}
                    />
                    {isSavingPrice ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <button
                        onClick={() => savePrice("actual_price")}
                        className="text-xs text-[var(--state-success)]"
                      >
                        ✓
                      </button>
                    )}
                  </div>
                ) : (
                  <button
                    onClick={() => {
                      setEditingPrice("actual");
                      setPriceValue(practice.actual_price?.toString() || "");
                    }}
                    className="font-medium hover:underline text-left transition-colors"
                    style={{ color: "var(--bz-text-1)" }}
                    title="Click to edit"
                    aria-label="Edit actual price"
                  >
                    {practice.actual_price != null ? (
                      <Money value={practice.actual_price} />
                    ) : (
                      "Not set"
                    )}
                  </button>
                )}
              </div>

              <div>
                <label
                  className="text-sm mb-1 block"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  Created
                </label>
                <div className="flex items-baseline gap-2 flex-wrap">
                  <p style={{ color: "var(--bz-text-1)" }}>
                    {formatDate(practice.created_at)}
                  </p>
                  {(() => {
                    const ageDays = Math.floor(
                      (Date.now() - new Date(practice.created_at).getTime()) /
                        86400000,
                    );
                    if (ageDays < 1) return null;
                    const label =
                      ageDays >= 365
                        ? `${Math.floor(ageDays / 365)}y ago`
                        : ageDays >= 30
                          ? `${Math.floor(ageDays / 30)}mo ago`
                          : ageDays >= 7
                            ? `${Math.floor(ageDays / 7)}w ago`
                            : `${ageDays}d ago`;
                    return (
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded tabular-nums"
                        style={{
                          background:
                            ageDays > 180
                              ? "color-mix(in srgb, var(--state-danger) 8%, transparent)"
                              : "var(--surface-raised)",
                          color:
                            ageDays > 180
                              ? "var(--state-danger)"
                              : "var(--bz-text-2)",
                        }}
                        title={`${ageDays} days since created`}
                      >
                        {label}
                      </span>
                    );
                  })()}
                </div>
              </div>

              {practice.start_date && (
                <div>
                  <label
                    className="text-sm mb-1 block"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    Start Date
                  </label>
                  <div className="flex items-baseline gap-2 flex-wrap">
                    <p style={{ color: "var(--bz-text-1)" }}>
                      {formatDate(practice.start_date)}
                    </p>
                    {(() => {
                      const ageDays = Math.floor(
                        (Date.now() -
                          new Date(practice.start_date!).getTime()) /
                          86400000,
                      );
                      if (ageDays < 1) return null;
                      const label =
                        ageDays >= 365
                          ? `${Math.floor(ageDays / 365)}y ago`
                          : ageDays >= 30
                            ? `${Math.floor(ageDays / 30)}mo ago`
                            : ageDays >= 7
                              ? `${Math.floor(ageDays / 7)}w ago`
                              : `${ageDays}d ago`;
                      return (
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded tabular-nums"
                          style={{
                            background: "var(--surface-raised)",
                            color: "var(--bz-text-2)",
                          }}
                        >
                          {label}
                        </span>
                      );
                    })()}
                  </div>
                </div>
              )}

              {practice.completion_date && (
                <div>
                  <label
                    className="text-sm mb-1 block"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    Completion Date
                  </label>
                  <div className="flex items-baseline gap-2 flex-wrap">
                    <p style={{ color: "var(--bz-text-1)" }}>
                      {formatDate(practice.completion_date)}
                    </p>
                    {(() => {
                      const ageDays = Math.floor(
                        (Date.now() -
                          new Date(practice.completion_date!).getTime()) /
                          86400000,
                      );
                      if (ageDays < 1) return null;
                      const label =
                        ageDays >= 365
                          ? `${Math.floor(ageDays / 365)}y ago`
                          : ageDays >= 30
                            ? `${Math.floor(ageDays / 30)}mo ago`
                            : ageDays >= 7
                              ? `${Math.floor(ageDays / 7)}w ago`
                              : `${ageDays}d ago`;
                      return (
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded tabular-nums"
                          style={{
                            background:
                              "color-mix(in srgb, var(--state-success) 8%, transparent)",
                            color: "var(--state-success)",
                          }}
                          title="Time since completion"
                          aria-label="Time since completion"
                        >
                          {label}
                        </span>
                      );
                    })()}
                  </div>
                </div>
              )}

              {practice.expiry_date && (
                <div>
                  <label
                    className="text-sm mb-1 block"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    Expiry Date
                  </label>
                  {(() => {
                    const daysLeft = Math.ceil(
                      (new Date(practice.expiry_date!).getTime() - Date.now()) /
                        86400000,
                    );
                    const color =
                      daysLeft < 0
                        ? "var(--state-danger)"
                        : daysLeft <= 30
                          ? "var(--state-warning)"
                          : "var(--bz-text-1)";
                    const label =
                      daysLeft < 0
                        ? `Expired ${Math.abs(daysLeft)}d ago`
                        : daysLeft === 0
                          ? "Expires today"
                          : daysLeft <= 365
                            ? `⏰ ${daysLeft}d left`
                            : `${Math.floor(daysLeft / 30)}mo left`;
                    return (
                      <p
                        style={{ color }}
                        title={formatDate(practice.expiry_date!)}
                      >
                        {label}
                      </p>
                    );
                  })()}
                </div>
              )}
            </div>
          </div>

          {/* Notes Section */}
          <div
            className="rounded-xl p-6"
            style={{
              border: "1px solid var(--bz-border)",
              background: "rgba(35,35,40,0.65)",
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <h2
                className="text-xl font-semibold flex items-center gap-2"
                style={{ color: "var(--bz-text-1)" }}
              >
                <FileText className="w-5 h-5" />
                Notes
              </h2>
              {!isEditingNotes && (
                <button
                  onClick={() => setIsEditingNotes(true)}
                  className="p-1.5 rounded-lg transition-colors"
                  style={{ color: "var(--bz-text-2)" }}
                  title="Edit notes"
                  aria-label="Edit notes"
                >
                  <Edit className="w-4 h-4" />
                </button>
              )}
            </div>
            {isEditingNotes ? (
              <div className="space-y-3">
                <textarea
                  autoFocus
                  value={notesValue}
                  onChange={(e) => setNotesValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey))
                      saveNotes();
                    if (e.key === "Escape") {
                      setIsEditingNotes(false);
                      setNotesValue(practice?.notes || "");
                    }
                  }}
                  rows={5}
                  className="w-full rounded-lg px-3 py-2 text-sm resize-none focus:outline-none transition-colors"
                  style={{
                    background: "var(--bz-base)",
                    border: "1px solid var(--bz-border)",
                    color: "var(--bz-text-1)",
                  }}
                  placeholder="Add internal notes about this process… (⌘↵ to save)"
                />
                <div className="flex items-center justify-end gap-2">
                  <button
                    onClick={() => {
                      setIsEditingNotes(false);
                      setNotesValue(practice?.notes || "");
                    }}
                    className="text-sm px-3 py-1.5 rounded-lg transition-colors"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    Cancel
                  </button>
                  <Button
                    size="sm"
                    onClick={saveNotes}
                    disabled={isSavingNotes}
                    className="gap-2"
                  >
                    {isSavingNotes && (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    )}
                    Save
                  </Button>
                </div>
              </div>
            ) : (
              <div
                className="cursor-pointer rounded-lg p-3 min-h-[80px] transition-colors"
                style={{ background: "var(--bz-base)" }}
                onClick={() => setIsEditingNotes(true)}
              >
                {practice.notes ? (
                  <p
                    className="text-sm whitespace-pre-wrap"
                    style={{ color: "var(--bz-text-1)" }}
                  >
                    {practice.notes}
                  </p>
                ) : (
                  <p
                    className="text-sm italic"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    Click to add notes…
                  </p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Quick Actions */}
          <div
            className="rounded-xl p-6"
            style={{
              border: "1px solid var(--bz-border)",
              background: "rgba(35,35,40,0.65)",
            }}
          >
            <h3
              className="text-lg font-semibold mb-4"
              style={{ color: "var(--bz-text-1)" }}
            >
              Quick Actions
            </h3>
            <div className="space-y-2">
              {practice.client_phone && (
                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={() => {
                    casesMetrics.trackQuickAction(
                      "whatsapp",
                      caseId || 0,
                      "CasesDetailPage",
                      userEmail.current || undefined,
                    );
                    const phone = practice.client_phone?.replace(/\D/g, "");
                    window.open(
                      `https://wa.me/${phone}?text=Hi ${practice.client_name}, regarding your process...`,
                      "_blank",
                    );
                  }}
                >
                  <MessageCircle className="w-4 h-4 mr-2" />
                  WhatsApp Client
                </Button>
              )}

              {practice.client_email && (
                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={() => {
                    casesMetrics.trackQuickAction(
                      "email",
                      caseId || 0,
                      "CasesDetailPage",
                      userEmail.current || undefined,
                    );
                    window.open(`mailto:${practice.client_email}`, "_blank");
                  }}
                >
                  <Mail className="w-4 h-4 mr-2" />
                  Email Client
                </Button>
              )}

              <Button
                variant="outline"
                className="w-full justify-start"
                onClick={() => {
                  casesMetrics.trackButtonClick(
                    "View Client Profile",
                    "CasesDetailPage",
                    caseId || undefined,
                    `/clients/${practice.client_id}`,
                    userEmail.current || undefined,
                  );
                  router.push(`/clients/${practice.client_id}`);
                }}
              >
                <User className="w-4 h-4 mr-2" />
                View Client Profile
              </Button>
            </div>
          </div>

          {/* Required Documents */}
          {caseId && <RequiredDocumentsCard practiceId={caseId} />}

          {/* Status History */}
          {practice.status_transitions &&
            practice.status_transitions.length > 0 && (
              <div
                className="rounded-xl p-6"
                style={{
                  border: "1px solid var(--bz-border)",
                  background: "rgba(35,35,40,0.65)",
                }}
              >
                <h3
                  className="text-lg font-semibold mb-4 flex items-center gap-2"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  <Clock className="w-5 h-5" />
                  Status History
                </h3>
                <div className="space-y-2">
                  {(() => {
                    const sorted = [...practice.status_transitions].sort(
                      (a, b) =>
                        new Date(a.at).getTime() - new Date(b.at).getTime(),
                    );
                    return sorted.map((t, idx) => {
                      const nextAt =
                        idx < sorted.length - 1 ? sorted[idx + 1].at : null;
                      const isCurrent = idx === sorted.length - 1;
                      const endMs = nextAt
                        ? new Date(nextAt).getTime()
                        : Date.now();
                      const durationDays = Math.round(
                        (endMs - new Date(t.at).getTime()) / 86400000,
                      );
                      const durationLabel =
                        durationDays >= 30
                          ? `${Math.floor(durationDays / 30)}mo ${durationDays % 30}d`
                          : durationDays >= 7
                            ? `${Math.floor(durationDays / 7)}w ${durationDays % 7}d`
                            : `${durationDays}d`;
                      return (
                        <div
                          key={idx}
                          className="flex items-center gap-3 text-sm py-1"
                        >
                          <div
                            className="w-1.5 h-1.5 rounded-full shrink-0"
                            style={{
                              background: isCurrent
                                ? "var(--bz-accent)"
                                : "var(--bz-text-3)",
                            }}
                          />
                          <span
                            className="capitalize font-medium flex-1"
                            style={{
                              color: isCurrent
                                ? "var(--bz-text-1)"
                                : "var(--bz-text-2)",
                            }}
                          >
                            {t.status.replace(/_/g, " ")}
                          </span>
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded"
                            style={{
                              background:
                                durationDays > 14
                                  ? "color-mix(in srgb, var(--state-warning) 12%, transparent)"
                                  : "var(--surface-raised)",
                              color:
                                durationDays > 14
                                  ? "var(--state-warning)"
                                  : "var(--bz-text-2)",
                            }}
                            title={`Time in this status: ${durationLabel}\nEntered: ${formatDate(t.at)}`}
                          >
                            {durationLabel}
                          </span>
                          <span
                            className="text-[10px]"
                            style={{
                              color: "var(--bz-text-2)",
                              minWidth: "60px",
                              textAlign: "right",
                            }}
                          >
                            {formatDate(t.at)}
                          </span>
                        </div>
                      );
                    });
                  })()}
                </div>
              </div>
            )}
        </div>
      </div>

      {/* Edit Modal */}
      {isEditModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div
            className="rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto"
            style={{
              background: "var(--bz-surface)",
              border: "1px solid var(--bz-border)",
            }}
          >
            <div
              className="p-6 flex items-center justify-between sticky top-0 z-10"
              style={{
                borderBottom: "1px solid var(--bz-border)",
                background: "var(--bz-surface)",
              }}
            >
              <h2
                className="text-xl font-bold"
                style={{ color: "var(--bz-text-1)" }}
              >
                Edit Process #{practice.id}
              </h2>
              <button
                onClick={() => setIsEditModalOpen(false)}
                className="transition-colors"
                style={{ color: "var(--bz-text-2)" }}
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Status */}
              <div className="space-y-2">
                <label
                  className="text-sm font-medium"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  Status
                </label>
                <select
                  value={editForm.status}
                  onChange={(e) =>
                    setEditForm((prev) => ({ ...prev, status: e.target.value }))
                  }
                  className="w-full px-3 py-2 rounded-lg focus:outline-none"
                  style={{
                    border: "1px solid var(--bz-border)",
                    background: "var(--bz-card)",
                    color: "var(--bz-text-1)",
                  }}
                >
                  {getAllowedNextStatuses(
                    editForm.status as PracticeStatus,
                    isAdmin,
                  ).map((status) => (
                    <option key={status} value={status}>
                      {STATUS_DROPDOWN_LABELS[status] ?? status}
                    </option>
                  ))}
                </select>
              </div>

              {/* Priority */}
              <div className="space-y-2">
                <label
                  className="text-sm font-medium"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  Priority
                </label>
                <div className="flex gap-2">
                  {(
                    [
                      {
                        value: "normal",
                        label: "Normal",
                        color: "var(--bz-text-2)",
                        activeBg:
                          "color-mix(in srgb, var(--bz-text-2) 20%, transparent)",
                        activeBorder:
                          "color-mix(in srgb, var(--bz-text-2) 40%, transparent)",
                      },
                      {
                        value: "high",
                        label: "↑ High",
                        color: "var(--state-warning)",
                        activeBg:
                          "color-mix(in srgb, var(--state-warning) 20%, transparent)",
                        activeBorder:
                          "color-mix(in srgb, var(--state-warning) 40%, transparent)",
                      },
                      {
                        value: "urgent",
                        label: "🔥 Urgent",
                        color: "var(--state-danger)",
                        activeBg:
                          "color-mix(in srgb, var(--state-danger) 20%, transparent)",
                        activeBorder:
                          "color-mix(in srgb, var(--state-danger) 40%, transparent)",
                      },
                    ] as const
                  ).map((p) => (
                    <button
                      key={p.value}
                      type="button"
                      onClick={() =>
                        setEditForm((prev) => ({ ...prev, priority: p.value }))
                      }
                      className="flex-1 py-2 rounded-lg text-sm font-medium transition-colors"
                      style={
                        editForm.priority === p.value
                          ? {
                              background: p.activeBg,
                              border: `1px solid ${p.activeBorder}`,
                              color: p.color,
                            }
                          : {
                              background: "var(--bz-card)",
                              border: "1px solid var(--bz-border)",
                              color: "var(--bz-text-2)",
                            }
                      }
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Payment Status */}
              <div className="space-y-2">
                <label
                  className="text-sm font-medium"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  Payment Status
                </label>
                <select
                  value={editForm.payment_status}
                  onChange={(e) =>
                    setEditForm((prev) => ({
                      ...prev,
                      payment_status: e.target.value,
                    }))
                  }
                  className="w-full px-3 py-2 rounded-lg focus:outline-none"
                  style={{
                    border: "1px solid var(--bz-border)",
                    background: "var(--bz-card)",
                    color: "var(--bz-text-1)",
                  }}
                >
                  <option value="unpaid">Unpaid</option>
                  <option value="partial">Partial</option>
                  <option value="paid">Paid</option>
                </select>
              </div>

              {/* Quoted Price */}
              <div className="space-y-2">
                <label
                  className="text-sm font-medium"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  Quoted Price (IDR)
                </label>
                <input
                  type="number"
                  value={editForm.quoted_price}
                  onChange={(e) =>
                    setEditForm((prev) => ({
                      ...prev,
                      quoted_price: e.target.value,
                    }))
                  }
                  className="w-full px-3 py-2 rounded-lg focus:outline-none"
                  style={{
                    border: "1px solid var(--bz-border)",
                    background: "var(--bz-card)",
                    color: "var(--bz-text-1)",
                  }}
                  placeholder="0.00"
                  step="0.01"
                />
              </div>

              {/* Actual Price */}
              <div className="space-y-2">
                <label
                  className="text-sm font-medium"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  Actual Price (IDR)
                </label>
                <input
                  type="number"
                  value={editForm.actual_price}
                  onChange={(e) =>
                    setEditForm((prev) => ({
                      ...prev,
                      actual_price: e.target.value,
                    }))
                  }
                  className="w-full px-3 py-2 rounded-lg focus:outline-none"
                  style={{
                    border: "1px solid var(--bz-border)",
                    background: "var(--bz-card)",
                    color: "var(--bz-text-1)",
                  }}
                  placeholder="0.00"
                  step="0.01"
                />
              </div>

              {/* Assigned To */}
              <div className="space-y-2">
                <label
                  className="text-sm font-medium"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  Assigned To
                </label>
                <select
                  value={editForm.assigned_to}
                  onChange={(e) =>
                    setEditForm((prev) => ({
                      ...prev,
                      assigned_to: e.target.value,
                    }))
                  }
                  className="w-full px-3 py-2 rounded-lg focus:outline-none"
                  style={{
                    border: "1px solid var(--bz-border)",
                    background: "var(--bz-card)",
                    color: "var(--bz-text-1)",
                  }}
                >
                  <option value="">— unassigned —</option>
                  <option value="zero@balizero.com">Zero</option>
                  <option value="asya@balizero.com">Asya</option>
                  <option value="antonellosiano@gmail.com">Antonello</option>
                </select>
              </div>

              {/* Start Date */}
              <div className="space-y-2">
                <label
                  className="text-sm font-medium"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  Start Date
                </label>
                <input
                  type="date"
                  value={editForm.start_date}
                  onChange={(e) =>
                    setEditForm((prev) => ({
                      ...prev,
                      start_date: e.target.value,
                    }))
                  }
                  className="w-full px-3 py-2 rounded-lg focus:outline-none"
                  style={{
                    border: "1px solid var(--bz-border)",
                    background: "var(--bz-card)",
                    color: "var(--bz-text-1)",
                  }}
                />
              </div>
            </div>

            <div
              className="p-6 flex justify-end gap-3 sticky bottom-0"
              style={{
                borderTop: "1px solid var(--bz-border)",
                background: "var(--bz-surface)",
              }}
            >
              <Button
                variant="outline"
                onClick={() => setIsEditModalOpen(false)}
                disabled={isSaving}
              >
                Cancel
              </Button>
              <Button
                className="text-white"
                style={{ background: "var(--bz-accent)" }}
                onClick={handleSaveChanges}
                disabled={isSaving}
              >
                {isSaving ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                    Save Changes
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
