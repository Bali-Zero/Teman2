"use client";

/**
 * Clients Page - CRM Workspace
 *
 * Ottimizzata con:
 * - React Query per caching e sincronizzazione
 * - Virtualized list per grandi dataset
 * - Debounced search
 * - Error Boundary per resilienza
 *
 * K3a (SAETTA-R19K window K3): the masthead/KPI-band/desk-strip/table
 * grammar of `R19-KITA-20260914/fusion/03-clients-list.html`. Colour and
 * ownership rules live in `./client-row-model.ts`; the table's own CSS
 * (sticky head, 1360 collapse, mobile card stack) lives in
 * `./clients-desk.module.css`. The card (list), kanban and map views below
 * are unchanged in behaviour.
 */

import React, {
  useState,
  useEffect,
  useMemo,
  useRef,
  useCallback,
} from "react";
import { useRouter, useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import {
  Filter,
  UserPlus,
  LayoutGrid,
  List,
  Map as MapIcon,
  Table2,
  X,
  SortAsc,
  SortDesc,
  AlertCircle,
  BarChart3,
  ExternalLink,
  Copy,
  Check,
  MoreVertical,
} from "lucide-react";

const PrimeNexusLayout = dynamic(
  () => import("@/components/maps/prime/PrimeNexusLayout"),
  {
    ssr: false,
    loading: () => (
      <div style={{ padding: 24 }}>{STRINGS.common.loadingMap}</div>
    ),
  },
);
import { useVirtualizer } from "@tanstack/react-virtual";
import { Button } from "@/components/ui/button";
import { formatIDRCompact } from "@balizero/core/utils";
import { FilterBar, FilterSelect, SearchBox } from "@balizero/core";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import type { Client } from "@/lib/api/crm/crm.types";
import { CLIENT_STATUSES, COMMON_NATIONALITIES } from "@/lib/api/crm/crm.types";
import { ClientKanban } from "@/components/crm/ClientKanban";
import { ClientCard } from "@/components/crm/ClientCard";
import { CRMErrorBoundary, CRMSkeleton } from "@/components/crm";
import { useCrmClients, useCrmStats } from "@/hooks";
import { useTeamMemberOptions } from "@/hooks/useTeamMembers";
import { useQuery } from "@tanstack/react-query";
import { logger } from "@/lib/logger";
import {
  CLIENTS_VIEW_MODE_KEY,
  loadViewMode,
  saveViewMode,
} from "@/lib/utils/view-mode-storage";
import { STRINGS } from "@/lib/strings";
import UnnamedLeadsBanner from "./UnnamedLeadsBanner";
import {
  Masthead,
  DeskStrip,
  StatePill,
  Slip,
  EmptyState,
  Numeral,
  SERIF,
  TABULAR,
  EYEBROW,
} from "@/components/workspace/r19";
import styles from "./clients-desk.module.css";
import {
  clientStatusTone,
  deskCounts,
  lastContactAgeDays,
  lastContactLabel,
  lastContactTone,
  passportDaysLeft,
  passportLabel,
  passportTone,
  viewerIsNext,
} from "./client-row-model";

type SortField =
  | "full_name"
  | "created_at"
  | "last_interaction_date"
  | "status"
  | "passport_expiry"
  | "active_practices";
type SortOrder = "asc" | "desc";
type ViewMode = "list" | "kanban" | "table" | "map";

interface Filters {
  status: string;
  nationality: string;
  assigned_to: string;
  passport_expiring_days?: number;
}

const PAGE_SIZE = 50;
const ESTIMATED_CARD_HEIGHT = 200;
const VIRTUALIZATION_THRESHOLD = 30;
const SEARCH_DEBOUNCE_MS = 300;

const FILTER_SELECT_STYLE: React.CSSProperties = {
  border: "1px solid var(--bz-border)",
  background: "var(--bz-base)",
  color: "var(--bz-text-1)",
};

const VIEW_MODES = [
  { mode: "list" as const, icon: List, aria: "Switch to list view" },
  {
    mode: "kanban" as const,
    icon: LayoutGrid,
    aria: "Switch to kanban board view",
  },
  { mode: "table" as const, icon: Table2, aria: "Switch to table view" },
  { mode: "map" as const, icon: MapIcon, aria: "Switch to map view" },
];

const KPI_TONE_COLOR: Record<string, string> = {
  ink: "var(--tx-pure)",
  copper: "var(--bz-copper-text)",
  warning: "var(--state-warning)",
  success: "var(--state-success)",
  muted: "var(--tx-secondary)",
};

/**
 * Virtualized client grid for better performance with large lists
 */
function VirtualizedClientGrid({
  clients,
  loadMoreRef,
  isLoadingMore,
  hasMore,
  totalClients,
  isMounted,
  onNearBottom,
}: {
  clients: Client[];
  loadMoreRef: React.RefObject<HTMLDivElement | null>;
  isLoadingMore: boolean;
  hasMore: boolean;
  totalClients: number;
  isMounted: boolean;
  onNearBottom?: () => void;
}) {
  const parentRef = useRef<HTMLDivElement>(null);
  const shouldVirtualize = clients.length > VIRTUALIZATION_THRESHOLD;

  const [columns, setColumns] = useState(3);
  useEffect(() => {
    const updateColumns = () => {
      const width = window.innerWidth;
      if (width >= 1024) setColumns(3);
      else if (width >= 768) setColumns(2);
      else setColumns(1);
    };
    updateColumns();
    window.addEventListener("resize", updateColumns);
    return () => window.removeEventListener("resize", updateColumns);
  }, []);

  const rows = Math.ceil(clients.length / columns);
  const rowHeight = ESTIMATED_CARD_HEIGHT + 16;

  const virtualizer = useVirtualizer({
    count: rows,
    getScrollElement: () => parentRef.current,
    estimateSize: () => rowHeight,
    overscan: 2,
  });

  const scrollTimer = useRef<NodeJS.Timeout | null>(null);
  const handleScroll = useCallback(() => {
    if (scrollTimer.current) return;
    scrollTimer.current = setTimeout(() => {
      scrollTimer.current = null;
      const el = parentRef.current;
      if (!el || !onNearBottom) return;
      if (el.scrollHeight - el.scrollTop - el.clientHeight < 500) {
        onNearBottom();
      }
    }, 300);
  }, [onNearBottom]);

  useEffect(() => {
    if (parentRef.current && shouldVirtualize) {
      virtualizer.measure();
    }
  }, [virtualizer, shouldVirtualize]);

  // Identical footer on both render paths (only one mounts per render).
  const loadMoreFooter = (
    <div ref={loadMoreRef} className="h-10 flex items-center justify-center">
      {isLoadingMore && (
        <div
          className="flex items-center gap-2 text-sm"
          style={{ color: "var(--bz-text-2)" }}
        >
          <div
            className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin"
            style={{ borderColor: "var(--bz-accent)" }}
          />
          Loading more clients...
        </div>
      )}
      {!hasMore && totalClients > PAGE_SIZE && (
        <span className="text-sm" style={{ color: "var(--bz-text-2)" }}>
          All {isMounted ? totalClients.toLocaleString("en-US") : totalClients}{" "}
          clients loaded
        </span>
      )}
    </div>
  );

  if (!shouldVirtualize) {
    return (
      <>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pb-4">
          {clients.map((client) => (
            <ClientCard key={client.id} client={client} />
          ))}
        </div>
        {loadMoreFooter}
      </>
    );
  }

  const virtualRows = virtualizer.getVirtualItems();

  return (
    <div
      ref={parentRef}
      onScroll={handleScroll}
      className="flex-1 overflow-auto pb-4 min-h-[400px]"
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: "100%",
          position: "relative",
        }}
      >
        {virtualRows.map((virtualRow) => {
          const startIndex = virtualRow.index * columns;
          const endIndex = Math.min(startIndex + columns, clients.length);
          const rowClients = clients.slice(startIndex, endIndex);

          return (
            <div
              key={virtualRow.key}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: `${virtualRow.size}px`,
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 px-1">
                {rowClients.map((client) => (
                  <ClientCard key={client.id} client={client} />
                ))}
                {rowClients.length < columns &&
                  Array.from({ length: columns - rowClients.length }).map(
                    (_, i) => <div key={`empty-${i}`} />,
                  )}
              </div>
            </div>
          );
        })}
      </div>
      {loadMoreFooter}
    </div>
  );
}

/**
 * Clients list content component
 */
function ClientsListContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // When arriving from the "contacts to name" banner (/clients?unnamed=1),
  // show ONLY phone-keyed leads still on a placeholder name.
  const unnamedOnly = searchParams.get("unnamed") === "1";
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<Filters>({
    status: "",
    nationality: "",
    assigned_to: "",
  });
  const [needsOnly, setNeedsOnly] = useState(false);
  const [sortField, setSortField] = useState<SortField>("created_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [currentUserEmail, setCurrentUserEmail] = useState<string>("");
  const [isMounted, setIsMounted] = useState(false);
  // P2.2: persist the view toggle across navigations (lazy-init + write-through)
  const [viewMode, setViewMode] = useState<ViewMode>(() =>
    loadViewMode(
      CLIENTS_VIEW_MODE_KEY,
      ["list", "kanban", "table", "map"],
      "list",
    ),
  );
  useEffect(() => {
    saveViewMode(CLIENTS_VIEW_MODE_KEY, viewMode);
  }, [viewMode]);
  const [silentFilter, setSilentFilter] = useState<number | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  // Optimistic "mark completed" overrides + the row-menu-open state and the
  // one Slip on screen. See §4.5 of the K3a spec.
  const [optimisticStatus, setOptimisticStatus] = useState<
    Record<number, string>
  >({});
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);
  const [slip, setSlip] = useState<{
    tone: "ok" | "you";
    title: string;
    detail?: string;
    onUndo?: () => void;
  } | null>(null);
  const slipTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Guards every state write that happens after an await: a completion PATCH
  // can still be in flight when the visitor navigates to a client.
  const mountedRef = useRef(true);
  const menuTriggerRefs = useRef<Map<number, HTMLButtonElement>>(new Map());
  const menuFirstItemRefs = useRef<Map<number, HTMLButtonElement>>(new Map());

  const showSlip = useCallback(
    (next: {
      tone: "ok" | "you";
      title: string;
      detail?: string;
      onUndo?: () => void;
    }) => {
      if (!mountedRef.current) return;
      if (slipTimerRef.current) clearTimeout(slipTimerRef.current);
      setSlip(next);
      slipTimerRef.current = setTimeout(() => {
        setSlip(null);
        slipTimerRef.current = null;
      }, 6000);
    },
    [],
  );

  const dismissSlip = useCallback(() => {
    if (slipTimerRef.current) clearTimeout(slipTimerRef.current);
    slipTimerRef.current = null;
    setSlip(null);
  }, []);

  useEffect(
    () => () => {
      mountedRef.current = false;
      if (slipTimerRef.current) clearTimeout(slipTimerRef.current);
    },
    [],
  );

  // Close the row menu and hand focus back to the trigger that opened it —
  // without this, activating an item drops focus on <body> and a keyboard
  // visitor loses their place in the table.
  const closeMenu = useCallback((clientId: number, restoreFocus = true) => {
    setOpenMenuId((cur) => (cur === clientId ? null : cur));
    if (restoreFocus) menuTriggerRefs.current.get(clientId)?.focus();
  }, []);

  // Escape closes and refocuses; a click outside closes. The outside test is
  // scoped to the OPEN row's cell by id: `.menuCell` is on every row, so a
  // class-only test counted a click in a different row's cell as "inside".
  useEffect(() => {
    if (openMenuId === null) return;
    const onDocClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (!target?.closest(`[data-menu-cell="${openMenuId}"]`)) {
        setOpenMenuId(null);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeMenu(openMenuId);
    };
    document.addEventListener("click", onDocClick);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("click", onDocClick);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [openMenuId, closeMenu]);

  useEffect(() => {
    if (openMenuId !== null) {
      menuFirstItemRefs.current.get(openMenuId)?.focus();
    }
  }, [openMenuId]);

  // Load current user profile
  useEffect(() => {
    const loadProfile = () => {
      const profile = api.getUserProfile();
      if (profile?.email) {
        setCurrentUserEmail(profile.email);
      }
    };
    loadProfile();
    const interval = setInterval(loadProfile, 1000);
    const timeout = setTimeout(() => clearInterval(interval), 5000);
    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, []);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Use optimized CRM hook with caching
  const {
    clients,
    total,
    isLoading,
    isError,
    error,
    loadMore,
    hasMore,
    isLoadingMore,
  } = useCrmClients({
    status: filters.status || undefined,
    assigned_to: filters.assigned_to || undefined,
    nationality: filters.nationality || undefined,
    passport_expiring_days: filters.passport_expiring_days,
    search: debouncedSearch || undefined,
    limit: PAGE_SIZE,
  });

  // Stats hook
  const { data: stats, isError: statsError } = useCrmStats();

  // Load team assignees from API (not just from loaded clients)
  const { data: assigneesData } = useQuery({
    queryKey: ["crm", "client-assignees"],
    queryFn: () => api.crm.getClientAssignees(),
    staleTime: 5 * 60 * 1000,
  });

  // Team member names for display (email → full name lookup)
  const { options: teamMemberOptions } = useTeamMemberOptions();

  // Infinite scroll — check if near bottom on scroll + interval fallback
  const hasMoreRef = useRef(hasMore);
  const isLoadingRef = useRef(isLoading || isLoadingMore);
  hasMoreRef.current = hasMore;
  isLoadingRef.current = isLoading || isLoadingMore;
  const loadMoreRef2 = useRef(loadMore);
  loadMoreRef2.current = loadMore;

  useEffect(() => {
    const check = () => {
      if (!hasMoreRef.current || isLoadingRef.current) return;
      const d = document.documentElement;
      if (d.scrollHeight - d.scrollTop - d.clientHeight < 800) {
        loadMoreRef2.current();
      }
    };
    window.addEventListener("scroll", check, { passive: true });
    // Fallback: check every 2s in case scroll event doesn't fire
    const interval = setInterval(check, 2000);
    return () => {
      window.removeEventListener("scroll", check);
      clearInterval(interval);
    };
  }, []);

  // The status write, in two shapes on purpose.
  //
  // `updateClientStatus` REJECTS on failure, because the table's optimistic
  // "mark completed" has to roll its cache back when the write does not land.
  // `handleStatusChange` swallows after logging, because that is the contract
  // ClientKanban's drop handler has always had: it does a bare
  // `await onStatusChange(...)` with no catch, so a rejection there would
  // both raise an unhandled rejection AND skip its `setDraggedClient(null)`,
  // leaving the board stuck mid-drag. One write, two callers, no regression.
  const updateClientStatus = useCallback(
    async (clientId: number, newStatus: string) => {
      try {
        const currentUser = api.getUserProfile();
        await api.crm.updateClient(
          clientId,
          { status: newStatus },
          currentUser?.email || "system",
        );
      } catch (error) {
        logger.error("Failed to update status:", {}, error as Error);
        throw error;
      }
    },
    [],
  );

  const handleStatusChange = useCallback(
    async (clientId: number, newStatus: string) => {
      try {
        await updateClientStatus(clientId, newStatus);
      } catch {
        // already logged by updateClientStatus
      }
    },
    [updateClientStatus],
  );

  const statusOf = useCallback(
    (c: Client): string => optimisticStatus[c.id] ?? c.status,
    [optimisticStatus],
  );

  const handleCopyReference = useCallback(
    (client: Client) => {
      const text = `Client ${client.id}`;
      navigator.clipboard
        ?.writeText(text)
        .then(() => {
          showSlip({ tone: "ok", title: "Reference copied", detail: text });
        })
        .catch(() => {});
    },
    [showSlip],
  );

  const handleCompleteClient = useCallback(
    async (client: Client) => {
      const previousStatus = statusOf(client);
      setOptimisticStatus((prev) => ({ ...prev, [client.id]: "completed" }));
      try {
        await updateClientStatus(client.id, "completed");
        if (!mountedRef.current) return;
        showSlip({
          tone: "ok",
          title: "Status updated",
          detail: `Client ${client.id} is completed.`,
          onUndo: () => {
            setOptimisticStatus((prev) => {
              const next = { ...prev };
              delete next[client.id];
              return next;
            });
            void handleStatusChange(client.id, previousStatus);
            dismissSlip();
          },
        });
      } catch {
        if (!mountedRef.current) return;
        setOptimisticStatus((prev) => {
          const next = { ...prev };
          delete next[client.id];
          return next;
        });
        showSlip({
          tone: "you",
          title: "Could not update — the row is unchanged.",
        });
      }
    },
    [dismissSlip, handleStatusChange, showSlip, statusOf, updateClientStatus],
  );

  // Filtering
  const visibleClients = isMounted ? clients : [];
  // Use API assignees list (all team members, not just those in the loaded page)
  const uniqueAssignees: string[] = assigneesData
    ? assigneesData
        .map((a) => a.assigned_to)
        .filter((v): v is string => typeof v === "string" && v.length > 0)
    : Array.from(
        new Set(
          visibleClients
            .map((c) => c.assigned_to)
            .filter((v): v is string => typeof v === "string" && v.length > 0),
        ),
      );

  const filteredClients = visibleClients
    .filter((client) => {
      // status, nationality, assigned_to are already applied server-side via API.
      // Client-side filter handles only cases where the server didn't filter
      // (e.g. stale cache with mismatched data) — kept as a safety net for
      // assigned_to which the API may not always honour for all roles.
      if (filters.assigned_to && client.assigned_to !== filters.assigned_to)
        return false;
      // Hide inactive/test clients by default unless user explicitly filters by inactive status
      if (!filters.status && client.status === "inactive") return false;
      // "Contacts to name" view (?unnamed=1): only placeholder-named phone leads.
      // Mirrors the backend `unnamed=true` predicate + wa-dashboard JUNK_NAME_PATTERNS.
      if (unnamedOnly) {
        const n = (client.full_name || "").trim();
        const isPlaceholder =
          n === "" ||
          /^lead\s*\+?[0-9]+$/i.test(n) ||
          /^wa:\s*\+?[0-9]+$/i.test(n) ||
          /^\+?[0-9]{8,}$/.test(n);
        if (!isPlaceholder) return false;
      }
      // Silent filter: only show clients not contacted in N days
      if (silentFilter !== null) {
        const lastContact = client.last_interaction_date
          ? (Date.now() - new Date(client.last_interaction_date).getTime()) /
            86400000
          : Infinity;
        if (lastContact < silentFilter) return false;
      }
      // Needs-me filter: only records where this viewer is the next actor.
      // It reads the OPTIMISTIC status, so a row marked completed leaves this
      // filter in the same paint that clears its copper (DISPOSITION F6).
      if (
        needsOnly &&
        !viewerIsNext(
          {
            assigned_to: client.assigned_to,
            status: statusOf(client) as Client["status"],
          },
          currentUserEmail,
        )
      )
        return false;
      return true;
    })
    .sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case "full_name":
          comparison = (a.full_name || "").localeCompare(b.full_name || "");
          break;
        case "created_at":
          comparison =
            new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          break;
        case "last_interaction_date":
          const aDate = a.last_interaction_date
            ? new Date(a.last_interaction_date).getTime()
            : 0;
          const bDate = b.last_interaction_date
            ? new Date(b.last_interaction_date).getTime()
            : 0;
          comparison = aDate - bDate;
          break;
        case "status":
          comparison = (a.status || "").localeCompare(b.status || "");
          break;
        case "passport_expiry": {
          const aExp = a.passport_expiry
            ? new Date(a.passport_expiry).getTime()
            : Infinity;
          const bExp = b.passport_expiry
            ? new Date(b.passport_expiry).getTime()
            : Infinity;
          comparison = aExp - bExp;
          break;
        }
        case "active_practices":
          comparison = (a.active_practices ?? 0) - (b.active_practices ?? 0);
          break;
      }
      return sortOrder === "asc" ? comparison : -comparison;
    });

  // Desk counts follow the optimistic status, so the copper ordinal and the
  // "Needs action" KPI clear the instant a row is marked completed, and
  // return the instant its Undo fires (DISPOSITION F6).
  const effectiveClients = useMemo(
    () =>
      filteredClients.map((c) =>
        c.id in optimisticStatus
          ? { ...c, status: optimisticStatus[c.id] as Client["status"] }
          : c,
      ),
    [filteredClients, optimisticStatus],
  );
  const counts = deskCounts(effectiveClients, currentUserEmail);
  const nowMs = Date.now();

  const handleNewClient = () => {
    router.push("/clients/new");
  };

  const clearFilters = () => {
    setFilters({
      status: "",
      nationality: "",
      assigned_to: "",
      passport_expiring_days: undefined,
    });
    setSilentFilter(null);
    setNeedsOnly(false);
  };

  const activeFiltersCount =
    Object.values(filters).filter((v) => v !== "" && v !== undefined).length +
    (silentFilter !== null ? 1 : 0) +
    (needsOnly ? 1 : 0);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
  };

  // Error state
  if (isError) {
    return (
      <div className="rounded-xl border border-[var(--state-warning)] p-8 text-center">
        <AlertCircle
          className="mx-auto mb-4 h-12 w-12 text-[var(--state-warning)]"
          aria-hidden="true"
        />
        <h2 className="mb-2 text-lg font-semibold text-[var(--tx-pure)]">
          Error loading clients
        </h2>
        <p className="mb-4 text-sm text-[var(--tx-secondary)]">
          {error instanceof Error
            ? error.message
            : "An unexpected error occurred"}
        </p>
        <Button onClick={() => window.location.reload()} variant="outline">
          Retry
        </Button>
      </div>
    );
  }

  const kpis: Array<{
    key: string;
    label: string;
    value: string;
    tone: "ink" | "copper" | "warning" | "success" | "muted";
    copy: string;
  }> = [
    {
      key: "total",
      label: "Total clients",
      value: stats
        ? stats.totalClients.toLocaleString("en-US")
        : String(counts.total),
      tone: "ink",
      copy: "all clients",
    },
    {
      key: "active",
      label: "Active practices",
      value: stats ? stats.activePractices.toLocaleString("en-US") : "—",
      tone: "ink",
      copy: "moving",
    },
    {
      key: "needs",
      label: "Needs action",
      value: String(counts.needsYou).padStart(2, "0"),
      tone: "copper",
      copy: "owned by you",
    },
    {
      key: "outstanding",
      label: "Outstanding",
      value: stats ? formatIDRCompact(stats.revenue.outstanding) : "—",
      tone: stats && stats.revenue.outstanding > 0 ? "warning" : "muted",
      copy: "unpaid",
    },
    {
      key: "paid",
      label: "Paid revenue",
      value: stats ? formatIDRCompact(stats.revenue.paid) : "—",
      tone: stats ? "success" : "muted",
      copy: "settled",
    },
  ];

  return (
    <div className="space-y-6">
      <UnnamedLeadsBanner />

      <Masthead
        eyebrow={`CRM · ${filteredClients.length} in view`}
        title="Clients"
        subtitle="The action margin marks records where you move next."
        right={
          <>
            <Button
              variant="outline"
              className="gap-2"
              onClick={() => router.push("/clients/analytics")}
            >
              <BarChart3 className="w-4 h-4" aria-hidden="true" />
              Analytics
            </Button>
            <Button className="gap-2" onClick={handleNewClient}>
              <UserPlus className="w-4 h-4" aria-hidden="true" />
              New client
            </Button>
          </>
        }
      />
      {statsError && isMounted && (
        <p className="text-xs text-[var(--tx-secondary)]">
          Stats unavailable — retry to reload counts.
        </p>
      )}

      {/* KPI band — desk counts, 22px Fraunces (not the 44px dashboard numeral) */}
      <section aria-label="Client metrics" className={styles.kpiBand}>
        {kpis.map((kpi) => (
          <div key={kpi.key}>
            <p className={EYEBROW}>{kpi.label}</p>
            <p
              className="my-1.5 text-[22px] leading-none"
              style={{ ...SERIF, ...TABULAR, color: KPI_TONE_COLOR[kpi.tone] }}
            >
              {kpi.value}
            </p>
            <p className="text-[10px] text-[var(--tx-secondary)]">{kpi.copy}</p>
          </div>
        ))}
      </section>

      {/* Passport health line — urgency (a date), never ownership: warning, never danger. */}
      {isMounted &&
        stats &&
        (stats.passportExpired > 0 || stats.passportExpiringSoon > 0) && (
          <div className="flex flex-wrap gap-2 text-xs">
            {stats.passportExpired > 0 && (
              <button
                type="button"
                onClick={() =>
                  setFilters((f) => ({ ...f, passport_expiring_days: 0 }))
                }
                className="flex items-center gap-1 rounded-full border border-[var(--state-warning)] bg-transparent px-2.5 py-1 text-[var(--state-warning)] transition-colors"
              >
                <AlertCircle className="w-3 h-3" aria-hidden="true" />
                {stats.passportExpired} passport
                {stats.passportExpired > 1 ? "s" : ""} expired
              </button>
            )}
            {stats.passportExpiringSoon > 0 && (
              <button
                type="button"
                onClick={() =>
                  setFilters((f) => ({ ...f, passport_expiring_days: 90 }))
                }
                className="flex items-center gap-1 rounded-full border border-[var(--state-warning)] bg-transparent px-2.5 py-1 text-[var(--state-warning)] transition-colors"
              >
                <AlertCircle className="w-3 h-3" aria-hidden="true" />
                {stats.passportExpiringSoon} expiring in 90d
              </button>
            )}
          </div>
        )}

      <div className={styles.deskStripScroller}>
        <DeskStrip
          count={
            <>
              {filteredClients.length}
              <span className="ml-1.5 text-[10px] text-[var(--tx-secondary)]">
                clients
              </span>
            </>
          }
          countLabel={`${filteredClients.length} clients in view`}
          filters={
            <>
              <StatePill
                tone="wait"
                label="All"
                pressed={
                  !filters.status &&
                  !filters.assigned_to &&
                  !needsOnly &&
                  silentFilter === null
                }
                onClick={() => {
                  setFilters((f) => ({ ...f, status: "", assigned_to: "" }));
                  setNeedsOnly(false);
                  setSilentFilter(null);
                }}
              />
              {currentUserEmail && (
                <StatePill
                  tone="wait"
                  label="Mine"
                  pressed={filters.assigned_to === currentUserEmail}
                  onClick={() =>
                    setFilters((f) => ({
                      ...f,
                      assigned_to:
                        f.assigned_to === currentUserEmail
                          ? ""
                          : currentUserEmail,
                    }))
                  }
                />
              )}
              <StatePill
                tone="wait"
                label="Needs me"
                pressed={needsOnly}
                onClick={() => setNeedsOnly((v) => !v)}
              />
              {(["lead", "active", "completed"] as const).map((status) => (
                <StatePill
                  key={status}
                  tone="wait"
                  label={status.charAt(0).toUpperCase() + status.slice(1)}
                  pressed={filters.status === status}
                  onClick={() =>
                    setFilters((f) => ({
                      ...f,
                      status: f.status === status ? "" : status,
                    }))
                  }
                />
              ))}
            </>
          }
          right={
            <>
              <SearchBox
                value={searchQuery}
                onValueChange={setSearchQuery}
                onDebouncedChange={setDebouncedSearch}
                debounceMs={SEARCH_DEBOUNCE_MS}
                placeholder="Search clients… (press / to focus)"
                ariaLabel="Search clients"
                title="Press / to focus, Escape to clear"
                clearable
              />
              <div
                role="group"
                aria-label="Client views"
                className="flex gap-1"
              >
                {VIEW_MODES.map(({ mode, icon: Icon, aria }) => (
                  <button
                    key={mode}
                    type="button"
                    aria-pressed={viewMode === mode}
                    aria-label={aria}
                    onClick={() => setViewMode(mode)}
                    className={cn(
                      "flex h-11 w-11 items-center justify-center border border-[var(--line-control)]",
                      viewMode === mode
                        ? "text-[var(--tx-pure)] shadow-[inset_0_-3px_0_var(--tx-pure)]"
                        : "text-[var(--tx-secondary)]",
                    )}
                  >
                    <Icon className="w-4 h-4" aria-hidden="true" />
                  </button>
                ))}
              </div>
              <Button
                variant={showFilters ? "default" : "outline"}
                className="gap-2"
                onClick={() => setShowFilters(!showFilters)}
              >
                <Filter className="w-4 h-4" aria-hidden="true" />
                Filters
                {activeFiltersCount > 0 && (
                  <span
                    className="ml-1 px-1.5 py-0.5 text-xs rounded-full text-[var(--bz-on-warm)]"
                    style={{ background: "var(--bz-accent)" }}
                  >
                    {activeFiltersCount}
                  </span>
                )}
              </Button>
            </>
          }
        />
      </div>

      {showFilters && (
        <FilterBar
          activeCount={activeFiltersCount}
          onClearAll={clearFilters}
          className="rounded-xl shadow-xl backdrop-blur-xl transition-all duration-300"
          style={{
            border: "1px solid var(--bz-border)",
            background: "var(--bz-card)",
          }}
          clearLabel={
            <>
              <X className="w-3 h-3" aria-hidden="true" />
              Clear all
            </>
          }
        >
          <FilterSelect
            label="Status"
            value={filters.status}
            onChange={(v) => setFilters({ ...filters, status: v })}
            selectClassName="transition-all duration-300"
            selectStyle={FILTER_SELECT_STYLE}
          >
            <option value="">All statuses</option>
            {CLIENT_STATUSES.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </FilterSelect>
          <FilterSelect
            label="Nationality"
            value={filters.nationality}
            onChange={(v) => setFilters({ ...filters, nationality: v })}
            selectClassName="transition-all duration-300"
            selectStyle={FILTER_SELECT_STYLE}
          >
            <option value="">All nationalities</option>
            {COMMON_NATIONALITIES.map((nat) => (
              <option key={nat} value={nat}>
                {nat}
              </option>
            ))}
          </FilterSelect>
          <FilterSelect
            label="Assigned To"
            value={filters.assigned_to}
            onChange={(v) => setFilters({ ...filters, assigned_to: v })}
            selectClassName="transition-all duration-300"
            selectStyle={FILTER_SELECT_STYLE}
          >
            <option value="">All team members</option>
            {currentUserEmail &&
              !uniqueAssignees.includes(currentUserEmail) && (
                <option value={currentUserEmail}>
                  {teamMemberOptions.find((m) => m.value === currentUserEmail)
                    ?.label || currentUserEmail.split("@")[0]}{" "}
                  (me)
                </option>
              )}
            {uniqueAssignees.map((assignee) => {
              const member = teamMemberOptions.find(
                (m) => m.value === assignee,
              );
              const displayName = member?.label || assignee?.split("@")[0];
              return (
                <option key={assignee} value={assignee}>
                  {displayName}
                  {assignee === currentUserEmail ? " (me)" : ""}
                </option>
              );
            })}
          </FilterSelect>
          <FilterSelect
            label="Passport Expiry"
            value={
              filters.passport_expiring_days === undefined
                ? ""
                : String(filters.passport_expiring_days)
            }
            onChange={(v) =>
              setFilters({
                ...filters,
                passport_expiring_days: v === "" ? undefined : Number(v),
              })
            }
            selectClassName="transition-all duration-300"
            selectStyle={FILTER_SELECT_STYLE}
          >
            <option value="">Any</option>
            <option value="0">Already expired</option>
            <option value="30">Expiring in 30 days</option>
            <option value="90">Expiring in 90 days</option>
            <option value="180">Expiring in 180 days</option>
            <option value="365">Expiring in 1 year</option>
          </FilterSelect>
          <FilterSelect
            label="Last contact"
            value={silentFilter === null ? "" : String(silentFilter)}
            onChange={(v) => setSilentFilter(v === "" ? null : Number(v))}
            selectClassName="transition-all duration-300"
            selectStyle={FILTER_SELECT_STYLE}
          >
            <option value="">Any</option>
            <option value="7">Silent 7+ days</option>
            <option value="30">Silent 30+ days</option>
          </FilterSelect>
        </FilterBar>
      )}

      {/* Sorting (List View Only) */}
      {viewMode === "list" && (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-[var(--tx-secondary)]">Sort by:</span>
          <div className="flex gap-1">
            {[
              { field: "created_at" as SortField, label: "Created" },
              { field: "full_name" as SortField, label: "Name" },
              {
                field: "last_interaction_date" as SortField,
                label: "Last Contact",
              },
              { field: "status" as SortField, label: "Status" },
              { field: "passport_expiry" as SortField, label: "Passport Exp." },
              { field: "active_practices" as SortField, label: "Processes" },
            ].map(({ field, label }) => (
              <button
                key={field}
                type="button"
                onClick={() => toggleSort(field)}
                className={cn(
                  "flex items-center gap-1 rounded-sm border px-3 py-1",
                  sortField === field
                    ? "border-[var(--tx-pure)] text-[var(--tx-pure)]"
                    : "border-[var(--line-control)] text-[var(--tx-secondary)]",
                )}
              >
                {label}
                {sortField === field &&
                  (sortOrder === "asc" ? (
                    <SortAsc className="w-3 h-3" aria-hidden="true" />
                  ) : (
                    <SortDesc className="w-3 h-3" aria-hidden="true" />
                  ))}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* CONTENT AREA */}
      {viewMode === "map" ? (
        <div
          className="rounded-xl overflow-hidden"
          style={{
            border: "1px solid var(--bz-border-hover)",
            height: "calc(100vh - 220px)",
            minHeight: "480px",
          }}
          aria-label="Clients on Prime 3D map"
        >
          <PrimeNexusLayout initialMode="crm" />
        </div>
      ) : isLoading && !clients.length ? (
        <div
          className="rounded-xl p-12 text-center backdrop-blur-sm"
          style={{
            border: "1px solid var(--bz-border-hover)",
            background: "var(--bz-card)",
          }}
        >
          <CRMSkeleton count={6} />
        </div>
      ) : filteredClients.length > 0 ? (
        viewMode === "table" ? (
          <>
            <table className={styles.deskTable}>
              <colgroup>
                <col />
                <col />
                <col />
                <col />
                <col />
                <col />
                <col />
                <col />
              </colgroup>
              <thead>
                <tr>
                  <th>Move</th>
                  <th>
                    <button
                      type="button"
                      className="inline-flex items-center gap-1"
                      onClick={() => toggleSort("full_name")}
                    >
                      Client
                      {sortField === "full_name" &&
                        (sortOrder === "asc" ? (
                          <SortAsc className="h-3 w-3" aria-hidden="true" />
                        ) : (
                          <SortDesc className="h-3 w-3" aria-hidden="true" />
                        ))}
                    </button>
                  </th>
                  <th>
                    <button
                      type="button"
                      className="inline-flex items-center gap-1"
                      onClick={() => toggleSort("status")}
                    >
                      Status
                      {sortField === "status" &&
                        (sortOrder === "asc" ? (
                          <SortAsc className="h-3 w-3" aria-hidden="true" />
                        ) : (
                          <SortDesc className="h-3 w-3" aria-hidden="true" />
                        ))}
                    </button>
                  </th>
                  <th>Nation.</th>
                  <th>Assigned</th>
                  <th>
                    <button
                      type="button"
                      className="inline-flex items-center gap-1"
                      onClick={() => toggleSort("last_interaction_date")}
                    >
                      Contact
                      {sortField === "last_interaction_date" &&
                        (sortOrder === "asc" ? (
                          <SortAsc className="h-3 w-3" aria-hidden="true" />
                        ) : (
                          <SortDesc className="h-3 w-3" aria-hidden="true" />
                        ))}
                    </button>
                  </th>
                  <th>Passport exp.</th>
                  <th style={{ textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredClients.map((client, idx) => {
                  const effectiveStatus = statusOf(client);
                  const isNext = viewerIsNext(
                    {
                      assigned_to: client.assigned_to,
                      status: effectiveStatus as Client["status"],
                    },
                    currentUserEmail,
                  );
                  const tone = clientStatusTone(effectiveStatus);
                  const daysLeft = passportDaysLeft(
                    client.passport_expiry,
                    nowMs,
                  );
                  const pTone = passportTone(daysLeft);
                  const pLabel = passportLabel(daysLeft);
                  const ageDays = lastContactAgeDays(
                    client.last_interaction_date,
                    nowMs,
                  );
                  const cTone = lastContactTone(ageDays);
                  const cLabel = lastContactLabel(ageDays);
                  const displayName =
                    client.full_name || client.email || `Client ${client.id}`;
                  const assignedLabel = client.assigned_to
                    ? teamMemberOptions.find(
                        (m) => m.value === client.assigned_to,
                      )?.label || client.assigned_to.split("@")[0]
                    : "—";

                  return (
                    <tr
                      key={client.id}
                      role="link"
                      tabIndex={0}
                      aria-label={`Open client ${client.full_name || client.email}`}
                      onClick={() => router.push(`/clients/${client.id}`)}
                      onKeyDown={(event) => {
                        // Only the ROW itself opens on Enter/Space. Without
                        // this guard the keystroke that activates a secondary
                        // action inside the row bubbles up and navigates
                        // instead of copying or completing.
                        if (event.target !== event.currentTarget) return;
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          router.push(`/clients/${client.id}`);
                        }
                      }}
                      className={cn(isNext && styles.needsYou)}
                    >
                      <td>
                        {isNext ? (
                          <>
                            <span
                              className="text-[18px] text-[var(--bz-copper-text)]"
                              style={{ ...SERIF }}
                              aria-hidden="true"
                            >
                              A
                            </span>
                            <span className="sr-only">Needs you</span>
                          </>
                        ) : (
                          <Numeral n={idx + 1} tone="wait" />
                        )}
                      </td>
                      <td>
                        <span className="block font-semibold text-[var(--tx-pure)]">
                          {client.full_name}
                        </span>
                        <span className="block text-[11px] text-[var(--tx-secondary)]">
                          {client.email}
                          <span className={styles.collapsedMeta}>
                            {" "}
                            · {client.nationality ?? "—"} · Passport {pLabel}
                          </span>
                        </span>
                      </td>
                      <td>
                        <StatePill tone={tone} label={effectiveStatus} />
                      </td>
                      <td data-label="Nationality">
                        {client.nationality ?? "—"}
                      </td>
                      <td
                        data-label="Assigned"
                        className="truncate"
                        title={client.assigned_to ?? "Unassigned"}
                      >
                        {assignedLabel}
                      </td>
                      <td
                        data-label="Last contact"
                        className={cn(
                          "tabular-nums",
                          cTone === "warning"
                            ? "text-[var(--state-warning)]"
                            : "text-[var(--tx-secondary)]",
                        )}
                        style={TABULAR}
                      >
                        {cLabel}
                      </td>
                      <td
                        data-label="Passport"
                        className={cn(
                          "tabular-nums",
                          pTone === "warning"
                            ? "text-[var(--state-warning)]"
                            : "text-[var(--tx-secondary)]",
                        )}
                        style={TABULAR}
                      >
                        {pLabel}
                      </td>
                      <td
                        className={styles.menuCell}
                        data-menu-cell={client.id}
                        onClick={(event) => event.stopPropagation()}
                      >
                        <div className={styles.rowActions}>
                          <button
                            type="button"
                            className={styles.rowAction}
                            aria-label={`Open ${displayName}`}
                            onClick={(event) => {
                              event.stopPropagation();
                              router.push(`/clients/${client.id}`);
                            }}
                          >
                            <ExternalLink
                              className="h-4 w-4"
                              aria-hidden="true"
                            />
                          </button>
                          <button
                            type="button"
                            className={styles.rowAction}
                            aria-label={`Copy ${displayName} reference`}
                            onClick={(event) => {
                              event.stopPropagation();
                              handleCopyReference(client);
                            }}
                          >
                            <Copy className="h-4 w-4" aria-hidden="true" />
                          </button>
                          <button
                            type="button"
                            className={styles.rowAction}
                            aria-label={`Mark ${displayName} completed`}
                            onClick={(event) => {
                              event.stopPropagation();
                              void handleCompleteClient(client);
                            }}
                          >
                            <Check className="h-4 w-4" aria-hidden="true" />
                          </button>
                        </div>
                        <button
                          type="button"
                          className={styles.rowMenuTrigger}
                          aria-haspopup="true"
                          aria-expanded={openMenuId === client.id}
                          aria-label={`Actions for ${displayName}`}
                          ref={(el) => {
                            if (el) menuTriggerRefs.current.set(client.id, el);
                            else menuTriggerRefs.current.delete(client.id);
                          }}
                          onClick={(event) => {
                            event.stopPropagation();
                            setOpenMenuId((cur) =>
                              cur === client.id ? null : client.id,
                            );
                          }}
                        >
                          <MoreVertical
                            className="h-4 w-4"
                            aria-hidden="true"
                          />
                        </button>
                        <div
                          aria-label={`Actions for ${displayName}`}
                          className={cn(
                            styles.rowMenu,
                            openMenuId === client.id && styles.rowMenuOpen,
                          )}
                        >
                          <button
                            type="button"
                            ref={(el) => {
                              // F5: an else-branch, or the Map keeps a detached
                              // node for every row whose menu was ever opened.
                              if (el)
                                menuFirstItemRefs.current.set(client.id, el);
                              else menuFirstItemRefs.current.delete(client.id);
                            }}
                            onClick={(event) => {
                              event.stopPropagation();
                              router.push(`/clients/${client.id}`);
                              closeMenu(client.id, false);
                            }}
                          >
                            Open
                          </button>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleCopyReference(client);
                              closeMenu(client.id);
                            }}
                          >
                            Copy reference
                          </button>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              void handleCompleteClient(client);
                              closeMenu(client.id);
                            }}
                          >
                            Mark completed
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {hasMore && (
              <div
                ref={loadMoreRef}
                className="flex justify-center py-4 text-xs text-[var(--tx-secondary)]"
              >
                {isLoadingMore && "Loading more…"}
              </div>
            )}
          </>
        ) : (
          <div className="flex-1 overflow-auto">
            {viewMode === "list" ? (
              <VirtualizedClientGrid
                clients={filteredClients}
                loadMoreRef={loadMoreRef}
                isLoadingMore={isLoadingMore}
                hasMore={hasMore}
                totalClients={clients.length}
                isMounted={isMounted}
                onNearBottom={() => {
                  if (hasMore && !isLoading && !isLoadingMore) loadMore();
                }}
              />
            ) : (
              <ClientKanban
                clients={filteredClients}
                onStatusChange={handleStatusChange}
              />
            )}
          </div>
        )
      ) : (
        <EmptyState
          action={
            activeFiltersCount > 0 || searchQuery ? (
              <Button
                variant="outline"
                onClick={clearFilters}
                className="gap-2"
              >
                <X className="w-4 h-4" aria-hidden="true" />
                Clear filters
              </Button>
            ) : (
              <Button onClick={handleNewClient} className="gap-2">
                <UserPlus className="w-4 h-4" aria-hidden="true" />
                Add first client
              </Button>
            )
          }
        >
          {activeFiltersCount > 0 || searchQuery
            ? "No clients match this desk."
            : "No clients yet."}
        </EmptyState>
      )}

      {slip && (
        <Slip
          tone={slip.tone}
          onUndo={slip.onUndo}
          className="fixed bottom-6 right-6 z-50"
        >
          <strong className="block text-[var(--tx-pure)]">{slip.title}</strong>
          {slip.detail && (
            <span className="mt-0.5 block text-[var(--tx-secondary)]">
              {slip.detail}
            </span>
          )}
        </Slip>
      )}
    </div>
  );
}

/**
 * Main page component with error boundary
 */
export default function ClientsPage() {
  return (
    <CRMErrorBoundary section="Clients">
      <ClientsListContent />
    </CRMErrorBoundary>
  );
}
