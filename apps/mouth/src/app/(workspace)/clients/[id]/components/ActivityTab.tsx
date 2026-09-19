"use client";

import React, { useCallback, useMemo, useRef, useState } from "react";
import {
  Calendar,
  FileText,
  Loader2,
  Mail,
  MessageCircle,
  Phone,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import type { Interaction } from "@/lib/api/crm/crm.types";
import {
  DeskStrip,
  EmptyState,
  EYEBROW,
  Field,
  HairlineBody,
  HairlineGrid,
  HairlineHead,
  HairlineRow,
  Notice,
  Slip,
  StatePill,
  TABULAR,
} from "@/components/workspace/r19";
import { WaTimelineTab } from "./WaTimelineTab";

/** R8: how long the Undo slip stays on screen — same window `clients/page.tsx`
 * (`showSlip`, K3a §4.5) already established for this shell; the r19 `Slip`
 * primitive owns no timer of its own (README ~11), so the page that mounts
 * it does. */
const UNDO_WINDOW_MS = 6000;

const CHANNEL_ICON: Record<string, typeof MessageCircle> = {
  whatsapp: MessageCircle,
  chat: MessageCircle,
  email: Mail,
  call: Phone,
  meeting: Calendar,
  note: FileText,
};

/** Same four presets and their summaries as the approved mock's Activity
 * composer (`client-profile-v3.html` `.preset-row`). Only "Called — no
 * answer" names a channel unambiguously in its own label; the other three
 * ("Sent documents", "Follow-up scheduled", "Payment reminder sent") carry
 * no stated channel, so they post as `note` rather than guessing one —
 * see the builder report for this call. */
const QUICK_PRESETS: {
  label: string;
  type: Interaction["interaction_type"];
  summary: string;
}[] = [
  { label: "Called — no answer", type: "call", summary: "Called — no answer" },
  { label: "Sent documents", type: "note", summary: "Sent documents" },
  {
    label: "Follow-up scheduled",
    type: "note",
    summary: "Follow-up scheduled",
  },
  {
    label: "Payment reminder sent",
    type: "note",
    summary: "Payment reminder sent",
  },
];

/** Same age-bucket wording `TimelineTab.tsx` (pre-R8) used. */
function ageLabel(dateStr: string): string {
  const ageDays = Math.floor(
    (Date.now() - new Date(dateStr).getTime()) / 86400000,
  );
  if (ageDays <= 0) return "today";
  if (ageDays === 1) return "1d ago";
  if (ageDays >= 30) return `${Math.floor(ageDays / 30)}mo ago`;
  if (ageDays >= 7) return `${Math.floor(ageDays / 7)}w ago`;
  return `${ageDays}d ago`;
}

/** Maps a failed save/undo to operator-readable copy — never the raw backend
 * `detail` (R8 audit item 2). `err` is whatever `createInteraction`/
 * `deleteInteraction` rejected with; `ApiError` (`lib/api/error-handler.ts`)
 * carries `statusCode`, a plain `Error` (network failure, no response) does
 * not, and falls into the last bucket below. */
function saveFailureMessage(err: unknown): string {
  const statusCode = (err as { statusCode?: number } | null | undefined)
    ?.statusCode;
  if (statusCode === 401)
    return "Your session expired. Sign in again, then press Save — your text is still here.";
  if (statusCode === 403)
    return "You do not have permission to log an interaction for this client. Your text is still here.";
  if (statusCode === 404 || statusCode === 0)
    return "The server did not accept the note. Nothing was saved — your text is still here. Try again in a minute.";
  return "Could not save. Nothing was lost — your text is still here. Try again.";
}

function TimelineList({
  interactions,
  formatDate,
  formatTime,
  clientCreatedAt,
  clientFirstContact,
}: {
  interactions: Interaction[];
  formatDate: (d: string) => string;
  formatTime: (d: string) => string;
  clientCreatedAt?: string;
  clientFirstContact?: string;
}) {
  const [filterType, setFilterType] = useState<string>("all");
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const toggleExpand = (id: number) =>
    setExpandedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const types = useMemo(
    () => Array.from(new Set(interactions.map((i) => i.interaction_type))),
    [interactions],
  );

  const filtered = useMemo(
    () =>
      filterType === "all"
        ? interactions
        : interactions.filter((i) => i.interaction_type === filterType),
    [interactions, filterType],
  );

  const sentimentCount = useMemo(() => {
    const counts: Record<string, number> = { positive: 0, negative: 0 };
    interactions.forEach((i) => {
      if (i.sentiment && counts[i.sentiment] !== undefined)
        counts[i.sentiment]++;
    });
    return counts;
  }, [interactions]);

  if (interactions.length === 0) {
    return (
      <EmptyState
        action={
          (clientCreatedAt || clientFirstContact) && (
            <div className="flex flex-col gap-1 text-[12px] text-[var(--tx-secondary)]">
              {clientCreatedAt && (
                <span>
                  Client added:{" "}
                  <span className="text-[var(--tx-pure)]">
                    {formatDate(clientCreatedAt)}
                  </span>
                </span>
              )}
              {clientFirstContact && (
                <span>
                  First contact:{" "}
                  <span className="text-[var(--tx-pure)]">
                    {formatDate(clientFirstContact)}
                  </span>
                </span>
              )}
            </div>
          )
        }
      >
        No interactions recorded yet. Interactions from WhatsApp, Telegram,
        email, calls, and notes will appear here.
      </EmptyState>
    );
  }

  return (
    <div>
      {(sentimentCount.positive > 0 || sentimentCount.negative > 0) && (
        <p className="mb-2 px-0.5 text-[11px] text-[var(--tx-secondary)]">
          {sentimentCount.positive > 0 && `${sentimentCount.positive} positive`}
          {sentimentCount.positive > 0 && sentimentCount.negative > 0 && " · "}
          {sentimentCount.negative > 0 && `${sentimentCount.negative} negative`}
        </p>
      )}

      {types.length > 1 && (
        <div className="mb-2 flex flex-wrap items-center gap-1.5">
          <StatePill
            tone="wait"
            label={`All (${interactions.length})`}
            pressed={filterType === "all"}
            onClick={() => setFilterType("all")}
          />
          {types.map((t) => (
            <StatePill
              key={t}
              tone="wait"
              label={`${t} (${interactions.filter((i) => i.interaction_type === t).length})`}
              pressed={filterType === t}
              onClick={() => setFilterType(t)}
            />
          ))}
        </div>
      )}

      <HairlineGrid cols="36px minmax(0,1fr)">
        <HairlineHead>
          <span aria-hidden="true" />
          <span>Update</span>
        </HairlineHead>
        <HairlineBody>
          {filtered.map((interaction) => {
            const Icon = CHANNEL_ICON[interaction.interaction_type] || FileText;
            const isExpanded = expandedIds.has(interaction.id);
            const hasLongSummary = (interaction.summary?.length ?? 0) > 120;
            const directionLabel =
              interaction.direction === "inbound"
                ? "In"
                : interaction.direction === "outbound"
                  ? "Out"
                  : null;
            const authorLabel = interaction.team_member
              ? interaction.team_member.split("@")[0]
              : null;
            const channelLabel =
              interaction.channel &&
              interaction.channel !== interaction.interaction_type
                ? `via ${interaction.channel}`
                : null;
            const metaLine = [
              authorLabel,
              directionLabel,
              interaction.sentiment,
              ageLabel(interaction.interaction_date),
              `${formatDate(interaction.interaction_date)} ${formatTime(interaction.interaction_date)}`,
              channelLabel,
            ]
              .filter(Boolean)
              .join(" · ");

            return (
              <HairlineRow key={interaction.id}>
                <span className="flex items-center justify-center">
                  <span
                    className="flex h-[26px] w-[26px] items-center justify-center border border-[var(--bz-border)] text-[var(--tx-pure)]"
                    style={{ borderRadius: 4 }}
                  >
                    <Icon className="h-[13px] w-[13px]" aria-hidden="true" />
                  </span>
                </span>
                <div className="min-w-0 px-2.5 py-2">
                  <span className={cn(EYEBROW, "block")}>
                    {interaction.interaction_type}
                  </span>
                  {interaction.subject && (
                    <p className="mt-0.5 truncate text-[13px] font-semibold text-[var(--tx-pure)]">
                      {interaction.subject}
                    </p>
                  )}
                  {interaction.summary && (
                    <div>
                      <p
                        className={cn(
                          "mt-0.5 text-[13px] text-[var(--tx-pure)]",
                          !isExpanded && hasLongSummary && "line-clamp-2",
                        )}
                      >
                        {interaction.summary}
                      </p>
                      {hasLongSummary && (
                        <button
                          type="button"
                          onClick={() => toggleExpand(interaction.id)}
                          className="mt-0.5 inline-flex min-h-6 items-center text-[11px] text-[var(--tx-secondary)] underline"
                        >
                          {isExpanded ? "Show less" : "Show more"}
                        </button>
                      )}
                    </div>
                  )}
                  <p
                    className="mt-1 text-[11px] text-[var(--tx-secondary)]"
                    style={TABULAR}
                  >
                    {metaLine}
                  </p>
                </div>
              </HairlineRow>
            );
          })}
        </HairlineBody>
      </HairlineGrid>
    </div>
  );
}

export function ActivityTab({
  clientId,
  interactions,
  formatDate,
  formatTime,
  clientCreatedAt,
  clientFirstContact,
  initialSection,
  onInteractionCreated,
  onInteractionRemoved,
  onSaved,
}: {
  clientId: number;
  interactions: Interaction[];
  formatDate: (d: string) => string;
  formatTime: (d: string) => string;
  clientCreatedAt?: string;
  clientFirstContact?: string;
  /** Which legacy tab key opened Activity — seeds the internal Timeline /
   * WhatsApp toggle so both `?tab=timeline` and `?tab=whatsapp` land on the
   * matching section. */
  initialSection: "timeline" | "whatsapp";
  onInteractionCreated: (interaction: Interaction) => void;
  onInteractionRemoved: (id: number) => void;
  /** R8 audit item 6: fired (in addition to `onInteractionCreated`) after a
   * successful save, so the caller can also invalidate the client query —
   * every other create path on this page does (`ClientDetailClient.tsx`
   * `submitLog`/header preset), because the server bumps
   * `clients.last_interaction_date` and the header reads it. */
  onSaved?: () => void;
}) {
  // `initialSection` only seeds this state on MOUNT; a parent that wants a
  // live prop change to take effect (e.g. `?tab=timeline` -> `?tab=whatsapp`
  // without the tab bar unmounting ActivityTab) must remount with a
  // `key={initialSection}`, as `ClientDetailClient.tsx` does.
  const [section, setSection] = useState<"timeline" | "whatsapp">(
    initialSection,
  );

  const [draft, setDraft] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [composerError, setComposerError] = useState<string | null>(null);
  const [slip, setSlip] = useState<{
    interactionId: number;
    label: string;
  } | null>(null);
  const slipTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const dismissSlip = useCallback(() => {
    if (slipTimerRef.current) clearTimeout(slipTimerRef.current);
    slipTimerRef.current = null;
    setSlip(null);
  }, []);

  const showUndoSlip = useCallback((interactionId: number, summary: string) => {
    if (slipTimerRef.current) clearTimeout(slipTimerRef.current);
    setSlip({ interactionId, label: `Logged: "${summary}"` });
    slipTimerRef.current = setTimeout(() => {
      setSlip(null);
      slipTimerRef.current = null;
    }, UNDO_WINDOW_MS);
  }, []);

  const submit = useCallback(
    async (summary: string, type: Interaction["interaction_type"]) => {
      const trimmed = summary.trim();
      if (!trimmed || isSubmitting) return;
      setIsSubmitting(true);
      setComposerError(null);
      try {
        const user = await api.getProfile();
        const created = await api.crm.createInteraction({
          client_id: clientId,
          interaction_type: type,
          summary: trimmed,
          team_member: user.email,
          direction: "outbound",
        });
        onInteractionCreated(created);
        onSaved?.();
        setDraft("");
        showUndoSlip(created.id, trimmed);
      } catch (err) {
        // Known PROD defect (DIAG-activity-logging-404.md): the POST can
        // 404 on the live edge today. This composer is the honest half of
        // that fix — it must never swallow the failure the way the
        // page-header "Log" panel still does (ClientDetailClient.tsx,
        // separate follow-up, not this slice): visible words, the typed
        // text stays, and the success Slip never renders. The message is
        // always product copy (`saveFailureMessage`) — never the raw
        // backend `detail` (R8 audit item 2).
        logger.error("ActivityTab save failed: " + String(err));
        setComposerError(saveFailureMessage(err));
      } finally {
        setIsSubmitting(false);
      }
    },
    [clientId, isSubmitting, onInteractionCreated, onSaved, showUndoSlip],
  );

  const handleUndo = useCallback(() => {
    if (!slip) return;
    const { interactionId } = slip;
    // The Undo window is over either way — dismiss the slip immediately.
    // But the row itself only comes off the list once the DELETE actually
    // resolves (R8 audit item 1a): a 403 (non-admin, `created_by` unset on
    // create — see `crm_interactions.py`) must not silently vanish the row
    // only for `refetchOnWindowFocus` to bring it back later, unexplained.
    dismissSlip();
    void (async () => {
      try {
        const user = await api.getProfile();
        await api.crm.deleteInteraction(interactionId, user.email);
        onInteractionRemoved(interactionId);
      } catch (err) {
        logger.error("ActivityTab undo-delete failed: " + String(err));
        setComposerError(
          "Could not undo — the entry is still saved. Ask an admin to remove it.",
        );
      }
    })();
  }, [dismissSlip, onInteractionRemoved, slip]);

  return (
    <div className="relative space-y-4">
      <div className="space-y-2.5">
        <div className="flex flex-wrap gap-1.5">
          {QUICK_PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              disabled={isSubmitting}
              onClick={() => void submit(preset.summary, preset.type)}
              className="inline-flex h-8 items-center rounded-[2px] border border-[var(--bz-border)] px-2.5 text-[11px] text-[var(--tx-secondary)] hover:border-[var(--line-control)] hover:text-[var(--tx-pure)] disabled:opacity-50"
            >
              {preset.label}
            </button>
          ))}
        </div>

        <div className="flex items-end gap-2">
          <Field
            id="activity-log-field"
            label="Log an update"
            placeholder="What happened?"
            value={draft}
            disabled={isSubmitting}
            required
            hint={draft.trim() ? undefined : "Required to save"}
            wrapperClassName="flex-1"
            onChange={(e) => {
              setDraft(e.target.value);
              if (composerError) setComposerError(null);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void submit(draft, "note");
              }
            }}
          />
          <Button
            size="sm"
            variant="outline"
            disabled={!draft.trim() || isSubmitting}
            onClick={() => void submit(draft, "note")}
            className="mb-1 gap-2"
            aria-label={isSubmitting ? "Saving" : undefined}
          >
            {isSubmitting ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              "Save"
            )}
          </Button>
        </div>

        {composerError && (
          <Notice tone="you" role="alert">
            {composerError}
          </Notice>
        )}
      </div>

      <DeskStrip
        count={section === "timeline" ? interactions.length : undefined}
        countLabel="Activity"
        filters={
          <>
            <StatePill
              tone="wait"
              label={`Timeline (${interactions.length})`}
              pressed={section === "timeline"}
              onClick={() => setSection("timeline")}
            />
            <StatePill
              tone="wait"
              label="WhatsApp"
              pressed={section === "whatsapp"}
              onClick={() => setSection("whatsapp")}
            />
          </>
        }
      />

      {section === "timeline" ? (
        <TimelineList
          interactions={interactions}
          formatDate={formatDate}
          formatTime={formatTime}
          clientCreatedAt={clientCreatedAt}
          clientFirstContact={clientFirstContact}
        />
      ) : (
        // Mounted only while this section is selected — same lazy-on-open
        // fetch WaTimelineTab always had as a directly-rendered tab
        // (`ClientDetailClient.tsx`, pre-R8: `{activeTab === "whatsapp" &&
        // <WaTimelineTab .../>}`); switching away unmounts it and switching
        // back re-fetches, unchanged.
        <WaTimelineTab clientId={clientId} />
      )}

      {slip && (
        <div className="sticky bottom-4 z-30 flex justify-start pb-1 max-[768px]:bottom-16">
          <Slip tone="ok" onUndo={handleUndo} onDismiss={dismissSlip}>
            {slip.label}
          </Slip>
        </div>
      )}
    </div>
  );
}
