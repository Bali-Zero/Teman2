"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  User,
  FileText,
  DollarSign,
  Globe,
  Users,
  FolderOpen,
  Building2,
  AlertCircle,
  Bell,
  MessageCircle,
  Send,
  Loader2,
  AlertTriangle,
  Activity,
  Mail,
  PenLine,
  Phone,
  Calendar,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { AvatarWithFallback } from "@/components/ui/avatar-with-fallback";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import type {
  FamilyMember,
  ClientDocument,
  Interaction,
} from "@/lib/api/crm/crm.types";
import { getCountryFlag } from "@/lib/utils/nationality-flags";
import {
  useClientDetail,
  useClientBusinessStory,
  useClientTimeline,
  useDocumentCategories,
  useInvalidateClient,
  useSetClientCache,
} from "@/hooks/useClientDetail";
import { useClickOutside } from "@/hooks/useClickOutside";
import {
  Masthead,
  StatePill,
  Stamp,
  PILL_TONE,
  PILL_SQUARE,
  LedgerSection,
  EmptyState,
  EYEBROW,
  FIELD,
} from "@/components/workspace/r19";
import { clientStatusTone, viewerIsNext } from "../client-row-model";
import styles from "./client-detail-desk.module.css";

// Local component imports
import { isTabType } from "./components/types";
import type { TabType, ModalType } from "./components/types";
import type { TaxConsultantOption } from "@/lib/workspace/roster-directory";
import { useTeamMemberOptions } from "@/hooks/useTeamMembers";
import { formatCurrency } from "./components/utils";
import { OverviewTab } from "./components/OverviewTab";
import { DocumentsTab } from "./components/DocumentsTab";
import { ProcessTab } from "./components/ProcessTab";
import { FamilyTab } from "./components/FamilyTab";
import { ImmigrationTab } from "./components/ImmigrationTab";
import { CompanyTab } from "./components/CompanyTab";
import { TaxTab } from "./components/TaxTab";
import { ActivityTab } from "./components/ActivityTab";
import { PortalAccess } from "./components/PortalAccess";
import { PortalMessages } from "./components/PortalMessages";
import { BusinessStoryPanel } from "./components/BusinessStoryPanel";
import { EditClientModal } from "./components/modals/EditClientModal";
import { AddFamilyMemberModal } from "./components/modals/AddFamilyMemberModal";
import { EditFamilyMemberModal } from "./components/modals/EditFamilyMemberModal";
import { AddDocumentModal } from "./components/modals/AddDocumentModal";
import { EditDocumentModal } from "./components/modals/EditDocumentModal";
import { AddCompanyModal } from "./components/modals/AddCompanyModal";

/**
 * The client-status trigger (below) is a menu TRIGGER, not a report — it
 * needs an `aria-label` and a click handler `StatePill` has no slot for
 * (K3a's own `StatePill` is either an inert `<span>` or an
 * `aria-pressed` filter button, neither of which carries a caller
 * `aria-label`). Rather than fork the primitive or copy its class strings,
 * this reuses its own exported tone table (`PILL_TONE` + `PILL_SQUARE`) on a
 * native button, so the trigger's colour still goes through
 * `clientStatusTone` — the r19 tone vocabulary, just not the literal
 * component. Every OTHER status word on this page (the menu's own options,
 * below) IS the real `StatePill`.
 */
const STATUS_TRIGGER_BASE =
  "inline-flex h-6 items-center gap-1.5 whitespace-nowrap border px-2.5 " +
  PILL_SQUARE +
  " text-[10px] font-[650] uppercase tracking-[0.12em] bg-transparent cursor-pointer hover:opacity-80 transition-opacity disabled:cursor-wait";

export interface ClientDetailClientProps {
  /**
   * The assignable tax team, resolved on the SERVER and handed down.
   *
   * It exists as a prop for one reason: the five addresses used to be a literal
   * inside `components/TaxTab.tsx`, and a literal in a "use client" module is
   * compiled into this route's static chunk, which is served with no session.
   * Passing it means the names live in the server payload for this route instead
   * of in a file any anonymous caller can GET by path.
   */
  taxConsultants: readonly TaxConsultantOption[];
}

export function ClientDetailClient({
  taxConsultants,
}: ClientDetailClientProps) {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const clientId = params?.id ? Number(params.id) : 0;
  const { options: teamMemberOptions } = useTeamMemberOptions();

  const {
    data: profile,
    isLoading,
    error: queryError,
  } = useClientDetail(clientId);
  const { data: timelineData } = useClientTimeline(clientId);
  const { data: docCategoriesData } = useDocumentCategories();
  const invalidateClient = useInvalidateClient(clientId);
  const setClientCache = useSetClientCache(clientId);
  const businessStoryQuery = useClientBusinessStory(
    clientId,
    profile?.client.full_name ?? "",
    profile?.company_links,
  );

  // Local interactions state: seeded from query, extended optimistically on log
  const [interactions, setInteractions] = useState<Interaction[]>([]);

  // Sync local interactions state when the timeline query data arrives/updates
  useEffect(() => {
    if (timelineData) {
      setInteractions(timelineData);
    }
  }, [timelineData]);

  const docCategories = docCategoriesData ?? [];
  const error = queryError ? "Failed to load client data" : null;

  // Mirror query error to toast (matches original Promise.all error behavior)
  useEffect(() => {
    if (queryError) {
      logger.error("Failed to load client data:", {}, queryError as Error);
      toast.error("Failed to load client data");
    }
  }, [queryError]);

  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const [activeModal, setActiveModal] = useState<ModalType>("none");
  const [editingDocument, setEditingDocument] = useState<ClientDocument | null>(
    null,
  );
  const [editingFamilyMember, setEditingFamilyMember] =
    useState<FamilyMember | null>(null);
  const [isMounted, setIsMounted] = useState(false);
  // The signed-in viewer, for the ownership predicate only (copper stamp,
  // masthead subtitle) — read once, same as `api.getUserProfile()` in K3a's
  // /clients desk. `null`/no-email means "viewer unknown": no copper, no
  // subtitle, per concept.md §6.
  const [currentUserEmail, setCurrentUserEmail] = useState<string>("");
  useEffect(() => {
    let mounted = true;
    const viewerProfile = api.getUserProfile?.();
    if (viewerProfile?.email) {
      setCurrentUserEmail(viewerProfile.email);
      return;
    }
    // Cache miss — fall back to one network read. Silent failure means the
    // viewer stays unknown (no copper, no subtitle), never a thrown error;
    // the unmount guard stops a late resolve from touching an unmounted
    // desk (round-3 R5).
    api
      .getProfile()
      .then((user) => {
        if (mounted && user?.email) setCurrentUserEmail(user.email);
      })
      .catch(() => {
        // stays unknown — see docstring above
      });
    return () => {
      mounted = false;
    };
  }, []);
  const [showStatusMenu, setShowStatusMenu] = useState(false);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [showLogPanel, setShowLogPanel] = useState(false);
  const [logType, setLogType] = useState<
    "note" | "call" | "whatsapp" | "email" | "meeting" | "chat"
  >("note");
  const [logSummary, setLogSummary] = useState("");
  const [isLogging, setIsLogging] = useState(false);
  const [logSaved, setLogSaved] = useState(false);
  // R7a: the two controls the hidden Company/Tax tabs used to own for a
  // company-less client — linking the first company and assigning the tax
  // consultant. Kept on Overview so hiding the tabs orphans no action.
  const [isAddingCompany, setIsAddingCompany] = useState(false);
  const [taxConsultantValue, setTaxConsultantValue] = useState("");
  const [isSavingTaxConsultant, setIsSavingTaxConsultant] = useState(false);
  useEffect(() => {
    setTaxConsultantValue(profile?.client.tax_consultant ?? "");
  }, [profile?.client.tax_consultant]);

  const saveTaxConsultant = async (newValue: string) => {
    const previous = taxConsultantValue;
    setTaxConsultantValue(newValue);
    setIsSavingTaxConsultant(true);
    try {
      const user = await api.getProfile();
      await api.crm.updateClient(
        clientId,
        { tax_consultant: newValue || null },
        user.email,
      );
      toast.success(
        newValue
          ? `Tax consultant: ${taxConsultants.find((c) => c.value === newValue)?.label ?? newValue}`
          : "Tax consultant cleared",
      );
      void invalidateClient();
    } catch (err) {
      setTaxConsultantValue(previous); // revert on error, same as TaxTab
      toast.error("Failed to update tax consultant", {
        description: (err as Error).message,
      });
    } finally {
      setIsSavingTaxConsultant(false);
    }
  };
  const logTextareaRef = useRef<HTMLTextAreaElement>(null);
  const tabsRef = useRef<HTMLElement>(null);
  const statusMenuRef = useRef<HTMLDivElement>(null);
  useClickOutside(
    statusMenuRef,
    () => setShowStatusMenu(false),
    showStatusMenu,
  );

  const submitLog = async () => {
    if (!logSummary.trim()) return;
    setIsLogging(true);
    try {
      const user = await api.getProfile();
      const newInteraction = await api.crm.createInteraction({
        client_id: clientId,
        interaction_type: logType,
        summary: logSummary.trim(),
        team_member: user.email,
        direction: "outbound",
      });
      setInteractions((prev) => [newInteraction, ...prev]);
      toast.success("Interaction logged");
      setLogSaved(true);
      setTimeout(() => setLogSaved(false), 1500);
      setLogSummary("");
      setShowLogPanel(false);
      // Refresh to update last_interaction_date in header
      invalidateClient();
    } catch (err) {
      toast.error("Failed to log interaction", {
        description: (err as Error).message,
      });
    } finally {
      setIsLogging(false);
    }
  };

  const updateStatus = async (newStatus: string) => {
    if (newStatus === profile?.client.status) {
      setShowStatusMenu(false);
      return;
    }
    setIsUpdatingStatus(true);
    setShowStatusMenu(false);
    try {
      const user = await api.getProfile();
      const updatedClient = await api.crm.updateClient(
        clientId,
        { status: newStatus },
        user.email,
      );
      setClientCache(updatedClient);
      void invalidateClient();
      toast.success(`Status updated to ${newStatus}`);
    } catch (err) {
      toast.error("Failed to update status", {
        description: (err as Error).message,
      });
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  // Fix hydration mismatch: only render dates on client
  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Read tab from URL params and set active tab
  useEffect(() => {
    const tabParam = searchParams?.get("tab");
    if (isTabType(tabParam)) {
      setActiveTab(tabParam);
    }
  }, [searchParams]);

  const handleTabChange = (tab: TabType, alreadyActive?: boolean) => {
    // R8 gate C6: a tab entry whose `activeKeys` already cover `visibleTab`
    // (only "Activity" today, `activeKeys: ["timeline", "whatsapp"]`) is a
    // no-op when clicked from either of its own keys — clicking "Activity"
    // while `?tab=whatsapp` used to force `visibleTab` back to "timeline",
    // remounting `<ActivityTab key={...}>` and discarding a typed draft, a
    // pending Undo Slip/timer and an error Notice. An ordinary tab whose own
    // key is already `visibleTab` was already a harmless no-op before this
    // guard (same state, same URL); it stays a no-op now, just without the
    // redundant `router.replace` call.
    if (alreadyActive) return;
    const scrollY = window.scrollY;
    setActiveTab(tab);
    router.replace(`/clients/${params.id}?tab=${tab}`, { scroll: false });
    // Restore scroll position after React re-render settles
    requestAnimationFrame(() => {
      window.scrollTo(0, scrollY);
    });
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "";
    // Return placeholder during SSR to avoid hydration mismatch
    if (!isMounted) return "...";
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  };

  const formatTime = (dateStr: string) => {
    if (!dateStr) return "";
    // Return placeholder during SSR to avoid hydration mismatch
    if (!isMounted) return "...";
    return new Date(dateStr).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-[var(--tx-secondary)]" />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <AlertTriangle className="w-12 h-12 text-[var(--state-warning)]" />
        <p className="text-[var(--bz-text-2)]">{error || "Client not found"}</p>
        <Button variant="outline" onClick={() => router.push("/clients")}>
          Back to Clients
        </Button>
      </div>
    );
  }

  const {
    client,
    family_members,
    documents,
    expiry_alerts,
    practices,
    company_links,
    stats,
  } = profile;

  // General docs only — excludes passports (Overview), immigration (Immigration tab), company docs (Company tab)
  const isPassportDoc = (d: ClientDocument) =>
    d.document_type?.toLowerCase().includes("passport");
  const isImmigrationDoc = (d: ClientDocument) =>
    d.document_category === "immigration" ||
    d.document_type?.toLowerCase().includes("kitas") ||
    d.document_type?.toLowerCase().includes("kitap") ||
    d.document_type?.toLowerCase().includes("visa") ||
    d.document_type?.toLowerCase().includes("permit") ||
    d.document_type?.toLowerCase().includes("imta") ||
    d.document_type?.toLowerCase().includes("rptka") ||
    d.document_type?.toLowerCase().includes("evisa") ||
    d.document_type?.toLowerCase().includes("voa");
  const isCompanyDoc = (d: ClientDocument) => d.document_category === "pma";
  const generalDocuments = documents.filter(
    (d) => !isPassportDoc(d) && !isImmigrationDoc(d) && !isCompanyDoc(d),
  );

  // Group documents by category
  const documentsByCategory = generalDocuments.reduce(
    (acc, doc) => {
      const cat = doc.document_category || "other";
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(doc);
      return acc;
    },
    {} as Record<string, ClientDocument[]>,
  );

  // Calculate stats
  const activePractices = practices.filter(
    (p) => !["completed", "cancelled", "approved"].includes(p.status),
  );
  const completedPractices = practices.filter((p) =>
    ["completed", "approved"].includes(p.status),
  );
  const businessStoryCompanyNames = (company_links ?? [])
    .map((link) => link.company_name)
    .filter((companyName) => companyName.trim().length > 0);
  const businessStoryError =
    businessStoryQuery.error instanceof Error
      ? businessStoryQuery.error
      : businessStoryQuery.error
        ? new Error("Business story request failed")
        : null;

  // R7a: hide the Company and Tax tabs for a client with no company links.
  // The decision is made only on the LOADED profile — while `useClientDetail`
  // is unresolved the page returns the spinner before the tab bar exists,
  // so there is no window in which an `undefined`/empty `company_links` could
  // flicker the tabs out. A client whose record still names a company keeps
  // the tabs even with an empty link list: CompanyTab's name-search fallback
  // then surfaces real company data (and its Sync Drive / edit / vault
  // actions) that hiding would orphan.
  const hasCompanyLinks = (company_links?.length ?? 0) > 0;
  const showCompanyTab = hasCompanyLinks || Boolean(client.company_name);
  // R7a rework: the Tax tab also stays when the CLIENT'S OWN tax identifiers
  // are on record (TaxTab renders them — `client.npwp ?? client.tax_id` and
  // `client.nib` — and nothing else on the page does), so hiding the tab for
  // a company-less client with a personal NPWP would make a stored fact
  // invisible.
  const showTaxTab =
    showCompanyTab || Boolean(client.npwp || client.tax_id || client.nib);
  // Render-time fallback, NOT a URL-effect reset: the effect runs while the
  // profile is still loading, so bouncing there would discard a deep link
  // before the data can prove whether the tab exists.
  const visibleTab: TabType =
    (activeTab === "company" && !showCompanyTab) ||
    (activeTab === "tax" && !showTaxTab)
      ? "overview"
      : activeTab;

  // Get country flag for fallback
  const countryFlag = getCountryFlag(client.nationality);

  // Masthead subtitle — DISAPPEARS when its data cannot prove it
  // (concept.md §6): no sentence with zero active practices, none while the
  // viewer is unknown either (the ownership half would silently read false).
  const needsViewerAction = Boolean(
    currentUserEmail && viewerIsNext(client, currentUserEmail),
  );
  const clientMastheadSubtitle =
    activePractices.length > 0
      ? `${activePractices.length} ${activePractices.length === 1 ? "process is" : "processes are"} moving${
          needsViewerAction ? "; this record needs your action." : "."
        }`
      : undefined;

  const clientRefEyebrow =
    `CLIENT · #${String(client.id).padStart(4, "0")}` +
    (client.company_name ? ` · ${client.company_name}` : "");

  const clientTone = clientStatusTone(client.status);

  return (
    <div className="space-y-6">
      {/* Back */}
      <Button
        variant="ghost"
        size="icon"
        onClick={() => router.back()}
        aria-label="Go back"
      >
        <ArrowLeft className="w-5 h-5" />
      </Button>

      {/* Masthead — reference eyebrow, name, a computed sentence that
          disappears when its data cannot prove it (concept.md §6). The
          avatar has no r19 slot, so it wraps the primitive page-locally
          rather than forking it (per spec §"Hard rules"). */}
      <div className="flex items-start gap-4">
        <div className="w-16 h-16 shrink-0 rounded-full bg-[var(--bz-card)] flex items-center justify-center overflow-hidden">
          {client.avatar_url ? (
            <img
              src={client.avatar_url}
              alt={client.full_name}
              className="w-full h-full object-cover"
            />
          ) : countryFlag ? (
            <div className="w-full h-full rounded-full bg-[var(--bz-base)] flex items-center justify-center text-4xl">
              {countryFlag}
            </div>
          ) : (
            <div
              className="w-full h-full rounded-full"
              style={{ background: "var(--bz-card)" }}
            />
          )}
        </div>
        <Masthead
          className="flex-1 min-w-0"
          eyebrow={clientRefEyebrow}
          title={client.full_name}
          subtitle={clientMastheadSubtitle}
          right={
            <>
              {/* Copper "NEEDS YOU" stamp — derived ownership only, detail-only. */}
              <Stamp tone="copper" owned={needsViewerAction} />
              {client.phone && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-2 text-[var(--accent-whatsapp)] border-[color-mix(in_srgb,var(--accent-whatsapp)_30%,transparent)] hover:bg-[color-mix(in_srgb,var(--accent-whatsapp)_10%,transparent)]"
                    onClick={() => {
                      const phone = client.phone?.replace(/\D/g, "");
                      if (phone)
                        window.open(
                          `https://wa.me/${phone.startsWith("0") ? "62" + phone.slice(1) : phone}`,
                          "_blank",
                        );
                    }}
                  >
                    <MessageCircle className="w-4 h-4" />
                    WhatsApp
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-2 text-sky-500 border-sky-500/30 hover:bg-sky-500/10"
                    onClick={() => {
                      const phone = client.phone?.replace(/\D/g, "");
                      if (phone)
                        window.open(
                          `https://t.me/+${phone.startsWith("0") ? "62" + phone.slice(1) : phone}`,
                          "_blank",
                        );
                    }}
                  >
                    <Send className="w-4 h-4" />
                    Telegram
                  </Button>
                </>
              )}
              {client.email && (
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2 text-indigo-400 border-indigo-400/30 hover:bg-indigo-400/10"
                  onClick={() =>
                    window.open(`mailto:${client.email}`, "_blank")
                  }
                >
                  <Mail className="w-4 h-4" />
                  Email
                </Button>
              )}
              {/* Open/closed toggle, not ownership — ink-selected idiom
                  (same law as the tab bar's .tabActive, K3b C1/round-3 R1),
                  never the shadcn default's copper fill. */}
              <Button
                variant="outline"
                size="sm"
                className={
                  showLogPanel
                    ? "gap-2 border-[var(--tx-pure)] text-[var(--tx-pure)]"
                    : "gap-2"
                }
                onClick={() => {
                  setShowLogPanel((v) => !v);
                  if (!showLogPanel)
                    setTimeout(() => logTextareaRef.current?.focus(), 80);
                }}
              >
                <PenLine className="w-4 h-4" />
                Log
              </Button>
              {client.google_drive_folder_id && (
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2 text-[var(--tx-secondary)] border-[var(--bz-border)] hover:bg-[var(--bz-surface)] hover:text-[var(--tx-pure)]"
                  onClick={() =>
                    window.open(
                      `https://drive.google.com/drive/folders/${client.google_drive_folder_id}`,
                      "_blank",
                    )
                  }
                  title="Open client's Google Drive folder"
                  aria-label="Open client's Google Drive folder"
                >
                  <FolderOpen className="w-4 h-4" />
                  Drive
                </Button>
              )}
            </>
          }
        />
      </div>

      {/*
       * "Where it stands" — status pill, assignment, key dates, the alert
       * strip — FIRST in the DOM at every width (concept.md C14b / K3b spec
       * §3.2), moved to the right column above 1100px by
       * `styles.statusColumn`'s own `order`, never by giving the main
       * column `order: -1` (see the CSS module's own note).
       */}
      <div className={styles.detailLayout}>
        <div className={styles.statusColumn} data-testid="status-column">
          {/* Status pill — a menu TRIGGER; see the STATUS_TRIGGER_BASE note
              above for why it stays a native button styled from PILL_TONE
              instead of the StatePill component. Its options ARE StatePill. */}
          <div ref={statusMenuRef} className="relative inline-block">
            <button
              type="button"
              onClick={() => setShowStatusMenu((v) => !v)}
              disabled={isUpdatingStatus}
              className={`${STATUS_TRIGGER_BASE} ${PILL_TONE[clientTone]}`}
              title="Click to change status"
              aria-label="Change client status"
              aria-haspopup="menu"
              aria-expanded={showStatusMenu}
            >
              {isUpdatingStatus ? "..." : client.status}
            </button>
            {showStatusMenu && (
              <div className="absolute top-full left-0 mt-1 z-50 flex flex-col gap-1 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] shadow-xl p-1 min-w-[140px]">
                {(
                  ["lead", "active", "completed", "lost", "inactive"] as const
                ).map((s) => (
                  <StatePill
                    key={s}
                    tone={clientStatusTone(s)}
                    label={s}
                    pressed={s === client.status}
                    onClick={() => updateStatus(s)}
                  />
                ))}
              </div>
            )}
          </div>

          <p className="text-sm text-[var(--bz-text-2)]">
            {client.client_type || "Individual"}
            {isMounted &&
              client.last_interaction_date &&
              (() => {
                const days = Math.floor(
                  (Date.now() -
                    new Date(client.last_interaction_date).getTime()) /
                    86400000,
                );
                if (days > 30)
                  return (
                    <span className="text-[var(--state-warning)]">
                      {" "}
                      • Silent {days}d
                    </span>
                  );
                if (days > 14)
                  return (
                    <span className="text-[var(--state-warning)]">
                      {" "}
                      • {days}d ago
                    </span>
                  );
                return null;
              })()}
          </p>

          {/* Assignment */}
          {client.assigned_to && (
            <div
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--bz-surface)] border border-[var(--bz-border)]"
              title={`Assigned to: ${client.assigned_to.split("@")[0]}`}
            >
              <AvatarWithFallback
                src={
                  teamMemberOptions.find((m) => m.value === client.assigned_to)
                    ?.avatar
                }
                alt={client.assigned_to.split("@")[0]}
                className="w-8 h-8 rounded-full object-cover ring-2 ring-[color-mix(in_srgb,var(--state-success)_30%,transparent)]"
                fallback={
                  <div className="w-8 h-8 rounded-full bg-[color-mix(in_srgb,var(--state-success)_20%,transparent)] flex items-center justify-center">
                    <User className="w-4 h-4 text-[var(--state-success)]" />
                  </div>
                }
              />
              <div className="flex flex-col">
                <span className="text-xs text-[var(--bz-text-2)]">
                  Assigned to
                </span>
                <span className="text-sm font-medium text-[var(--bz-text-1)] capitalize">
                  {client.assigned_to.split("@")[0]}
                </span>
              </div>
            </div>
          )}

          {/* Alert badges — urgency (a date), never ownership: warning, never danger */}
          {(stats.expired_count > 0 ||
            stats.red_alerts > 0 ||
            stats.yellow_alerts > 0) && (
            <div className="flex flex-wrap gap-2">
              {stats.expired_count > 0 && (
                <span className="px-2 py-1 text-xs rounded-full bg-[color-mix(in_srgb,var(--state-warning)_30%,transparent)] text-[var(--state-warning)] flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  {stats.expired_count} expired
                </span>
              )}
              {stats.red_alerts > 0 && (
                <span className="px-2 py-1 text-xs rounded-full bg-[color-mix(in_srgb,var(--state-warning)_20%,transparent)] text-[var(--state-warning)] flex items-center gap-1">
                  <Bell className="w-3 h-3" />
                  {stats.red_alerts} urgent
                </span>
              )}
              {stats.yellow_alerts > 0 && (
                <span className="px-2 py-1 text-xs rounded-full bg-[color-mix(in_srgb,var(--state-warning)_20%,transparent)] text-[var(--state-warning)] flex items-center gap-1">
                  <Bell className="w-3 h-3" />
                  {stats.yellow_alerts} soon
                </span>
              )}
            </div>
          )}

          {/* Expiry Alert strip — shown when there are urgent docs. A date
              is urgency, never ownership, never danger: warning throughout. */}
          {expiry_alerts.filter(
            (a) => a.alert_color === "expired" || a.alert_color === "red",
          ).length > 0 && (
            <div
              className="flex items-start gap-3 rounded-xl px-4 py-3 border"
              style={{
                background:
                  "color-mix(in srgb, var(--state-warning) 8%, transparent)",
                borderColor:
                  "color-mix(in srgb, var(--state-warning) 30%, transparent)",
              }}
            >
              <AlertTriangle className="w-4 h-4 text-[var(--state-warning)] shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[var(--state-warning)]">
                  {expiry_alerts.filter((a) => a.alert_color === "expired")
                    .length > 0 && (
                    <span>
                      {
                        expiry_alerts.filter((a) => a.alert_color === "expired")
                          .length
                      }{" "}
                      expired
                      {expiry_alerts.filter((a) => a.alert_color === "red")
                        .length > 0
                        ? " · "
                        : ""}
                    </span>
                  )}
                  {expiry_alerts.filter((a) => a.alert_color === "red").length >
                    0 && (
                    <span>
                      {
                        expiry_alerts.filter((a) => a.alert_color === "red")
                          .length
                      }{" "}
                      expiring soon
                    </span>
                  )}
                </p>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {expiry_alerts
                    .filter(
                      (a) =>
                        a.alert_color === "expired" || a.alert_color === "red",
                    )
                    .slice(0, 4)
                    .map((alert, i) => (
                      <span
                        key={i}
                        className="text-xs px-2 py-0.5 rounded-full bg-[color-mix(in_srgb,var(--state-warning)_20%,transparent)] text-[var(--state-warning)]"
                      >
                        {alert.document_type?.replace(/_/g, " ")}
                        {alert.entity_type === "family_member"
                          ? ` (${alert.entity_name})`
                          : ""}
                        {alert.alert_color === "expired"
                          ? " — expired"
                          : ` — ${alert.days_until_expiry}d`}
                      </span>
                    ))}
                  {expiry_alerts.filter(
                    (a) =>
                      a.alert_color === "expired" || a.alert_color === "red",
                  ).length > 4 && (
                    <span className="text-xs text-[var(--state-warning)] opacity-70">
                      +
                      {expiry_alerts.filter(
                        (a) =>
                          a.alert_color === "expired" ||
                          a.alert_color === "red",
                      ).length - 4}{" "}
                      more
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className={styles.mainColumn}>
          {/* Inline Log Interaction Panel */}
          {showLogPanel && (
            <div className="rounded-xl border border-[var(--bz-border)] bg-[var(--bz-surface)] p-4 space-y-3 animate-in slide-in-from-top-2 duration-150">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-[var(--bz-text-1)]">
                  Log interaction
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setShowLogPanel(false);
                    setLogSummary("");
                  }}
                  className="p-1 rounded hover:bg-[var(--bz-card)] text-[var(--bz-text-2)]"
                  aria-label="Close log panel"
                  title="Close log panel"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              {/* Quick presets — one click to prefill + submit */}
              <div className="flex flex-wrap gap-1.5">
                <span className="text-[10px] text-[var(--bz-text-2)] self-center mr-1 uppercase tracking-wide font-medium">
                  Quick:
                </span>
                {[
                  {
                    type: "call" as const,
                    label: "📞 Called",
                    summary: "Called client",
                  },
                  {
                    type: "call" as const,
                    label: "📵 No answer",
                    summary: "Called — no answer",
                  },
                  {
                    type: "whatsapp" as const,
                    label: "💬 WA sent",
                    summary: "WhatsApp message sent",
                  },
                  {
                    type: "note" as const,
                    label: "✅ Updated",
                    summary: "Process updated",
                  },
                ].map(({ type, label, summary }) => (
                  <button
                    key={label}
                    onClick={async () => {
                      setLogType(type);
                      setLogSummary(summary);
                      setIsLogging(true);
                      try {
                        const user = await api.getProfile();
                        const newInteraction = await api.crm.createInteraction({
                          client_id: clientId,
                          interaction_type: type,
                          summary,
                          team_member: user.email,
                          direction: "outbound",
                        });
                        setInteractions((prev) => [newInteraction, ...prev]);
                        toast.success("Logged: " + summary);
                        setLogSaved(true);
                        setTimeout(() => setLogSaved(false), 1500);
                        setLogSummary("");
                        setShowLogPanel(false);
                        invalidateClient();
                      } catch (err) {
                        toast.error("Failed to log", {
                          description: (err as Error).message,
                        });
                      } finally {
                        setIsLogging(false);
                      }
                    }}
                    disabled={isLogging}
                    className="text-xs px-2.5 py-1 rounded-full border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-2)] hover:border-[var(--line-control)] hover:text-[var(--bz-text-1)] transition-colors disabled:opacity-50"
                  >
                    {label}
                  </button>
                ))}
              </div>
              {/* Type chips */}
              <div className="flex flex-wrap gap-2">
                {(
                  [
                    { key: "note", label: "Note", Icon: FileText },
                    { key: "call", label: "Call", Icon: Phone },
                    { key: "whatsapp", label: "WhatsApp", Icon: MessageCircle },
                    { key: "email", label: "Email", Icon: Mail },
                    { key: "meeting", label: "Meeting", Icon: Calendar },
                    { key: "chat", label: "Chat", Icon: MessageCircle },
                  ] as const
                ).map(({ key, label, Icon }) => (
                  <button
                    key={key}
                    onClick={() => setLogType(key)}
                    className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border transition-colors ${
                      logType === key
                        ? "bg-[var(--bz-sidebar-active-fill)] text-white border-[var(--bz-sidebar-active-fill)]"
                        : "bg-[var(--bz-base)] text-[var(--bz-text-2)] border-[var(--bz-border)] hover:border-[var(--line-control)]"
                    }`}
                  >
                    <Icon className="w-3 h-3" />
                    {label}
                  </button>
                ))}
              </div>
              {/* Summary textarea */}
              <textarea
                ref={logTextareaRef}
                value={logSummary}
                onChange={(e) => setLogSummary(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey))
                    submitLog();
                }}
                placeholder={`Add a ${logType} note… (⌘↵ to save)`}
                rows={3}
                className="w-full rounded-lg bg-[var(--bz-base)] border border-[var(--bz-border)] text-sm text-[var(--bz-text-1)] placeholder:text-[var(--bz-text-2)] px-3 py-2 resize-none focus:outline-none focus:border-[var(--line-control)] transition-colors"
              />
              <div className="flex items-center justify-between">
                <span
                  className={`text-[10px] tabular-nums transition-colors ${
                    logSummary.length > 400
                      ? "text-[var(--state-warning)]"
                      : logSummary.length > 200
                        ? "text-[var(--state-warning)]"
                        : "text-[var(--bz-text-2)]"
                  }`}
                >
                  {logSummary.length > 0 ? `${logSummary.length} chars` : ""}
                </span>
                {/* Primary submit of this panel — forest idiom (same law
                    as PortalAccess's "Invite to portal", round-3 R2). */}
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!logSummary.trim() || isLogging}
                  onClick={submitLog}
                  className="gap-2 transition-colors border-[var(--state-success)] bg-[var(--state-success)] text-white hover:bg-[var(--state-success)] hover:opacity-90"
                >
                  {isLogging ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <PenLine className="w-4 h-4" />
                  )}
                  {logSaved ? "Saved!" : "Save"}
                </Button>
              </div>
            </div>
          )}

          {/* Tabs — hairline idiom: 44px row, --line-control underline, an ink
          underline on the active tab. No role="tab"/aria-selected here: K3a
          dropped role="menu" for the same reason (decision D6) — this bar
          does not implement the arrow-key pattern a tab role promises, so it
          keeps native buttons with the browser's own Tab/Enter/Space. R5
          (kita client-profile redesign) wraps the row in a `<nav>` with its
          own accessible name — matching v3 mock's `aria-label="Client
          sections"` — and gives the active button `aria-current="page"`,
          same attribute the mock's own `.tab[aria-current="page"]` rule
          reads; TAB_KEYS itself is untouched, so every existing `?tab=`
          deep link still opens the same panel. Only the "process" label
          moves to the mock's "Practices". R8 folds Timeline + WhatsApp into
          the mock's single "Activity" button: TAB_KEYS keeps both
          "timeline" and "whatsapp" as valid deep-link keys (`?tab=whatsapp`
          bookmarks still work), so this one button matches on EITHER key —
          `activeKeys` below, not a straight `visibleTab === key` — and its
          onClick always writes the canonical "timeline" key. */}
          <nav
            ref={tabsRef}
            className={styles.tabBar}
            data-testid="tab-bar"
            aria-label="Client sections"
          >
            {[
              { key: "overview", label: "Overview", icon: User },
              {
                key: "documents",
                label: `Documents (${generalDocuments.length})`,
                icon: FileText,
              },
              {
                key: "process",
                label: `Practices (${activePractices.length + completedPractices.length})`,
                icon: FolderOpen,
              },
              {
                key: "family",
                label: `Family (${stats.family_count})`,
                icon: Users,
              },
              { key: "visas", label: "Immigration", icon: Globe },
              { key: "company", label: "Company", icon: Building2 },
              { key: "tax", label: "Tax", icon: DollarSign },
              {
                key: "timeline",
                label: `Activity (${interactions.length})`,
                icon: Activity,
                activeKeys: ["timeline", "whatsapp"] as TabType[],
              },
            ]
              .filter(({ key }) => {
                if (key === "company") return showCompanyTab;
                if (key === "tax") return showTaxTab;
                return true;
              })
              .map(({ key, label, icon: Icon, activeKeys }) => {
                const isActive = activeKeys
                  ? activeKeys.includes(visibleTab)
                  : visibleTab === key;
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => handleTabChange(key as TabType, isActive)}
                    aria-current={isActive ? "page" : undefined}
                    className={`${styles.tab} ${isActive ? styles.tabActive : ""}`}
                  >
                    <Icon className="w-4 h-4" />
                    {label}
                  </button>
                );
              })}
          </nav>

          {/* Tab Content */}
          {visibleTab === "overview" && (
            <>
              <OverviewTab
                client={client}
                stats={stats}
                documents={documents}
                activePractices={activePractices}
                completedPractices={completedPractices}
                expiryAlerts={expiry_alerts}
                needsViewerAction={needsViewerAction}
                formatDate={formatDate}
                formatCurrency={formatCurrency}
                onEditClick={() => setActiveModal("edit_client")}
                onRefresh={invalidateClient}
                clientId={clientId}
              />
              <BusinessStoryPanel
                clientName={client.full_name}
                companyNames={businessStoryCompanyNames}
                maps={businessStoryQuery.data ?? []}
                isLoading={businessStoryQuery.isLoading}
                error={businessStoryError}
              />
              <PortalAccess
                clientId={clientId}
                clientName={client.full_name}
                clientEmail={client.email}
              />
              <PortalMessages
                clientId={clientId}
                clientName={client.full_name}
              />
              {/* R7a: for a client with no company links (and no company name
                  on record) the Company/Tax tabs are hidden — so the actions
                  they carried move here, to the Overview the deep links fall
                  back to: linking the first company, and — only when the Tax
                  tab is hidden too — the tax-consultant assignment TaxTab
                  renders (two live copies of one control on one page would be
                  a defect). An r19 LedgerSection, not a boxed card: the Add
                  company control sits in the always-visible actions slot,
                  never in a hover-only row action. */}
              {!showCompanyTab && (
                <LedgerSection
                  n={2}
                  tone="wait"
                  title="Company & tax"
                  actions={
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setIsAddingCompany(true)}
                    >
                      Add company
                    </Button>
                  }
                >
                  <EmptyState>No company linked yet.</EmptyState>
                  {!showTaxTab && (
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 py-3">
                      <label
                        htmlFor="tax-consultant-inline"
                        className={EYEBROW}
                      >
                        Tax consultant
                      </label>
                      <select
                        id="tax-consultant-inline"
                        value={taxConsultantValue}
                        onChange={(e) => void saveTaxConsultant(e.target.value)}
                        disabled={isSavingTaxConsultant}
                        className={
                          FIELD +
                          " max-w-[260px] cursor-pointer appearance-auto"
                        }
                      >
                        <option value="">— not assigned —</option>
                        {taxConsultants.map((c) => (
                          <option key={c.value} value={c.value}>
                            {c.label}
                          </option>
                        ))}
                      </select>
                      {isSavingTaxConsultant && (
                        <span className="text-xs text-[var(--tx-secondary)]">
                          Saving…
                        </span>
                      )}
                    </div>
                  )}
                </LedgerSection>
              )}
            </>
          )}

          {activeTab === "documents" && (
            <DocumentsTab
              clientId={clientId}
              documents={generalDocuments}
              documentsByCategory={documentsByCategory}
              formatDate={formatDate}
              onAddClick={() => setActiveModal("add_document")}
              onEditClick={(doc) => {
                setEditingDocument(doc);
                setActiveModal("edit_document");
              }}
            />
          )}

          {activeTab === "process" && (
            <ProcessTab
              clientId={clientId}
              practices={[...activePractices, ...completedPractices]}
              formatDate={formatDate}
              onRefresh={invalidateClient}
            />
          )}

          {activeTab === "family" && (
            <FamilyTab
              clientId={clientId}
              familyMembers={family_members}
              documents={documents}
              formatDate={formatDate}
              onAddClick={() => setActiveModal("add_family")}
              onEditClick={(member) => {
                setEditingFamilyMember(member);
                setActiveModal("edit_family");
              }}
              onRefresh={invalidateClient}
            />
          )}

          {activeTab === "visas" && (
            <ImmigrationTab
              clientId={clientId}
              documents={documents}
              formatDate={formatDate}
              onAddClick={() => setActiveModal("add_document")}
              onEditClick={(doc) => {
                setEditingDocument(doc);
                setActiveModal("edit_document");
              }}
              onRefresh={invalidateClient}
            />
          )}

          {visibleTab === "company" && (
            <CompanyTab
              clientId={clientId}
              client={client}
              documents={documents}
              formatDate={formatDate}
              onRefresh={invalidateClient}
            />
          )}

          {visibleTab === "tax" && (
            <TaxTab
              clientId={clientId}
              formatDate={formatDate}
              client={profile?.client ?? null}
              companyLinks={company_links}
              onRefresh={invalidateClient}
              taxConsultants={taxConsultants}
            />
          )}

          {(visibleTab === "timeline" || visibleTab === "whatsapp") && (
            <ActivityTab
              // R8 audit item 5: ActivityTab only reads `initialSection` on
              // mount (no corrective effect) — a `key` forces the remount a
              // live `?tab=timeline` <-> `?tab=whatsapp` switch needs while
              // this guard keeps both under the same branch.
              key={visibleTab === "whatsapp" ? "whatsapp" : "timeline"}
              clientId={clientId}
              interactions={interactions}
              formatDate={formatDate}
              formatTime={formatTime}
              clientCreatedAt={client.created_at}
              clientFirstContact={client.first_contact_date}
              initialSection={
                visibleTab === "whatsapp" ? "whatsapp" : "timeline"
              }
              onInteractionCreated={(interaction) =>
                setInteractions((prev) => [interaction, ...prev])
              }
              onInteractionRemoved={(id) =>
                setInteractions((prev) => prev.filter((i) => i.id !== id))
              }
              onSaved={invalidateClient}
            />
          )}
        </div>
      </div>

      {/* Modals */}
      {activeModal === "edit_client" && profile && (
        <EditClientModal
          client={profile.client}
          onClose={() => setActiveModal("none")}
          onSave={invalidateClient}
        />
      )}

      {activeModal === "add_family" && (
        <AddFamilyMemberModal
          clientId={clientId}
          onClose={() => setActiveModal("none")}
          onSave={invalidateClient}
        />
      )}

      {activeModal === "edit_family" && editingFamilyMember && (
        <EditFamilyMemberModal
          clientId={clientId}
          member={editingFamilyMember}
          onClose={() => {
            setActiveModal("none");
            setEditingFamilyMember(null);
          }}
          onSave={invalidateClient}
        />
      )}

      {activeModal === "add_document" && (
        <AddDocumentModal
          clientId={clientId}
          categories={docCategories}
          familyMembers={family_members}
          clientHasDriveFolder={!!client.google_drive_folder_id}
          onClose={() => setActiveModal("none")}
          onSave={invalidateClient}
        />
      )}

      {activeModal === "edit_document" && editingDocument && (
        <EditDocumentModal
          clientId={clientId}
          document={editingDocument}
          categories={docCategories}
          familyMembers={family_members}
          onClose={() => {
            setActiveModal("none");
            setEditingDocument(null);
          }}
          onSave={invalidateClient}
        />
      )}

      {isAddingCompany && (
        <AddCompanyModal
          clientId={clientId}
          onClose={() => setIsAddingCompany(false)}
          onSuccess={() => {
            setIsAddingCompany(false);
            void invalidateClient();
          }}
        />
      )}
    </div>
  );
}
