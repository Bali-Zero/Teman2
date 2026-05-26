"use client";

import { useState } from "react";
import { patchAction } from "@/lib/wa-actions-api";
import type { ActionQueueRow } from "@/types/wa-action";
import { DismissDialog } from "./DismissDialog";

interface Props {
  row: ActionQueueRow;
  expanded: boolean;
  onToggleExpand: () => void;
  onMutated: () => void;
}

const STATUS_BADGE: Record<string, string> = {
  open: "bg-blue-950/60 text-blue-300 border-blue-900/60",
  snoozed: "bg-amber-950/60 text-amber-300 border-amber-900/60",
  done: "bg-emerald-950/60 text-emerald-300 border-emerald-900/60",
  dismissed: "bg-neutral-900/80 text-neutral-500 border-neutral-800",
};

function priorityColor(p: number): string {
  if (p >= 8) return "bg-red-950/70 text-red-300";
  if (p >= 6) return "bg-orange-950/70 text-orange-300";
  if (p >= 4) return "bg-yellow-950/70 text-yellow-300";
  return "bg-neutral-800 text-neutral-400";
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function evidenceMsgIds(ev: unknown): number[] {
  if (!ev || typeof ev !== "object") return [];
  const obj = ev as Record<string, unknown>;
  const candidates = obj.msg_ids ?? obj.message_ids ?? obj.messages;
  if (Array.isArray(candidates)) {
    return candidates
      .map((v) => (typeof v === "number" ? v : Number(v)))
      .filter((n) => Number.isFinite(n));
  }
  return [];
}

export function ActionRow({ row, expanded, onToggleExpand, onMutated }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissOpen, setDismissOpen] = useState(false);
  const [ownerDraft, setOwnerDraft] = useState(row.owner ?? "");
  const [editingOwner, setEditingOwner] = useState(false);

  async function callPatch(payload: Parameters<typeof patchAction>[1]) {
    setBusy(true);
    setError(null);
    try {
      await patchAction(row.action_id, payload);
      onMutated();
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }

  async function handleDone() {
    const notes =
      window.prompt("Resolution notes (optional):", "") ?? undefined;
    await callPatch({ status: "done", resolution_notes: notes });
  }

  async function handleSnooze(days: number) {
    await callPatch({ status: "snoozed", snooze_days: days });
  }

  async function handleAssignSave() {
    setEditingOwner(false);
    if (ownerDraft.trim() === (row.owner ?? "")) return;
    await callPatch({ owner: ownerDraft.trim() || "unassigned" });
  }

  async function handleDismissConfirm(reason: string) {
    setDismissOpen(false);
    await callPatch({ status: "dismissed", dismiss_reason: reason });
  }

  const msgIds = evidenceMsgIds(row.evidence);
  const firstMsgId = msgIds.length > 0 ? msgIds[0] : null;

  return (
    <>
      <tr className="hover:bg-neutral-900/40 transition-colors">
        <td className="px-3 py-2 align-top">
          <button
            type="button"
            onClick={onToggleExpand}
            className="text-neutral-500 hover:text-neutral-300"
            aria-label={expanded ? "Collapse" : "Expand"}
          >
            {expanded ? "▾" : "▸"}
          </button>
        </td>
        <td className="px-3 py-2 align-top">
          {row.client_id ? (
            <a
              href={`/?client_id=${row.client_id}`}
              className="text-blue-400 hover:text-blue-300"
              title={`client_id ${row.client_id}`}
            >
              {row.client_full_name || `#${row.client_id}`}
            </a>
          ) : (
            <span className="text-neutral-600">—</span>
          )}
        </td>
        <td className="px-3 py-2 align-top text-neutral-300">
          {row.practice_id ? (
            <span title={`practice_id ${row.practice_id}`}>
              {row.practice_kind || `#${row.practice_id}`}
            </span>
          ) : (
            <span className="text-neutral-600">—</span>
          )}
        </td>
        <td className="px-3 py-2 align-top text-neutral-400 font-mono text-[11px]">
          {row.action_type}
        </td>
        <td className="px-3 py-2 align-top text-neutral-200 max-w-[20ch]">
          <div className="truncate" title={row.reason}>
            {row.reason}
          </div>
        </td>
        <td className="px-3 py-2 align-top text-neutral-200 max-w-[28ch]">
          <div className="truncate" title={row.recommended_action}>
            {row.recommended_action}
          </div>
        </td>
        <td className="px-3 py-2 align-top text-neutral-400 whitespace-nowrap">
          {formatDate(row.due_at)}
        </td>
        <td className="px-3 py-2 align-top">
          {editingOwner ? (
            <input
              type="text"
              autoFocus
              value={ownerDraft}
              onChange={(e) => setOwnerDraft(e.target.value)}
              onBlur={handleAssignSave}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleAssignSave();
                if (e.key === "Escape") {
                  setEditingOwner(false);
                  setOwnerDraft(row.owner ?? "");
                }
              }}
              className="w-24 rounded border border-neutral-700 bg-neutral-900 px-1.5 py-0.5 text-[11px] text-neutral-100"
            />
          ) : (
            <button
              type="button"
              onClick={() => setEditingOwner(true)}
              className="text-neutral-300 hover:text-neutral-100 underline-offset-2 hover:underline"
              title="Click to reassign"
            >
              {row.owner || "unassigned"}
            </button>
          )}
        </td>
        <td className="px-3 py-2 align-top text-center">
          <span
            className={`inline-block rounded px-1.5 py-0.5 font-mono text-[11px] ${priorityColor(row.priority)}`}
          >
            {row.priority}
          </span>
        </td>
        <td className="px-3 py-2 align-top">
          <span
            className={`inline-block rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${STATUS_BADGE[row.status] || STATUS_BADGE.open}`}
          >
            {row.status}
          </span>
        </td>
        <td className="px-3 py-2 align-top text-right">
          <div className="flex items-center justify-end gap-1">
            <button
              type="button"
              disabled={busy || row.status === "done"}
              onClick={handleDone}
              className="rounded border border-emerald-900/60 bg-emerald-950/40 px-2 py-0.5 text-[11px] text-emerald-200 hover:bg-emerald-900/40 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Done
            </button>
            <SnoozeMenu disabled={busy} onSnooze={handleSnooze} />
            <button
              type="button"
              disabled={busy || row.status === "dismissed"}
              onClick={() => setDismissOpen(true)}
              className="rounded border border-neutral-700 bg-neutral-900 px-2 py-0.5 text-[11px] text-neutral-300 hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Dismiss
            </button>
          </div>
        </td>
      </tr>

      {expanded && (
        <tr className="bg-neutral-900/40">
          <td colSpan={11} className="px-6 py-3">
            <div className="space-y-2 text-[11px] text-neutral-300">
              {row.suggested_message_draft && (
                <div>
                  <div className="text-neutral-500 uppercase tracking-wide text-[10px] mb-1">
                    Suggested message draft
                  </div>
                  <pre className="rounded bg-neutral-950 border border-neutral-800 p-2 whitespace-pre-wrap text-neutral-200">
                    {row.suggested_message_draft}
                  </pre>
                </div>
              )}
              {row.resolution_notes && (
                <div>
                  <div className="text-neutral-500 uppercase tracking-wide text-[10px] mb-1">
                    Resolution notes
                  </div>
                  <div className="text-neutral-200">{row.resolution_notes}</div>
                </div>
              )}
              {row.dismiss_reason && (
                <div>
                  <div className="text-neutral-500 uppercase tracking-wide text-[10px] mb-1">
                    Dismiss reason
                  </div>
                  <div className="text-neutral-200">{row.dismiss_reason}</div>
                </div>
              )}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-1 text-neutral-400">
                <div>
                  Created:{" "}
                  <span className="text-neutral-200">
                    {formatDate(row.created_at)}
                  </span>
                </div>
                {row.snoozed_until && (
                  <div>
                    Snoozed until:{" "}
                    <span className="text-neutral-200">
                      {formatDate(row.snoozed_until)}
                    </span>
                  </div>
                )}
                {row.resolved_at && (
                  <div>
                    Resolved:{" "}
                    <span className="text-neutral-200">
                      {formatDate(row.resolved_at)}
                    </span>
                  </div>
                )}
                {row.conversation_id && (
                  <div>
                    Conv:{" "}
                    <span className="text-neutral-200 font-mono">
                      #{row.conversation_id}
                    </span>
                  </div>
                )}
              </div>
              {firstMsgId !== null && (
                <div>
                  <a
                    href={`/?message_id=${firstMsgId}`}
                    className="text-blue-400 hover:text-blue-300 text-[11px]"
                  >
                    → Open first message (#{firstMsgId})
                  </a>
                  {msgIds.length > 1 && (
                    <span className="ml-2 text-neutral-500">
                      ({msgIds.length} message evidence rows)
                    </span>
                  )}
                </div>
              )}
              <div>
                <div className="text-neutral-500 uppercase tracking-wide text-[10px] mb-1">
                  Evidence (raw)
                </div>
                <pre className="rounded bg-neutral-950 border border-neutral-800 p-2 overflow-x-auto text-[10px] text-neutral-400">
                  {JSON.stringify(row.evidence, null, 2)}
                </pre>
              </div>
            </div>
          </td>
        </tr>
      )}

      {error && (
        <tr>
          <td colSpan={11} className="px-3 py-1">
            <div className="text-[11px] text-red-300">Error: {error}</div>
          </td>
        </tr>
      )}

      {dismissOpen && (
        <DismissDialog
          actionId={row.action_id}
          onConfirm={handleDismissConfirm}
          onCancel={() => setDismissOpen(false)}
        />
      )}
    </>
  );
}

function SnoozeMenu({
  disabled,
  onSnooze,
}: {
  disabled: boolean;
  onSnooze: (days: number) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative inline-block">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="rounded border border-amber-900/60 bg-amber-950/40 px-2 py-0.5 text-[11px] text-amber-200 hover:bg-amber-900/40 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Snooze ▾
      </button>
      {open && (
        <div
          className="absolute right-0 mt-1 z-10 w-28 rounded border border-neutral-700 bg-neutral-900 shadow-lg"
          onMouseLeave={() => setOpen(false)}
        >
          {[1, 3, 7, 14, 30].map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => {
                setOpen(false);
                onSnooze(d);
              }}
              className="block w-full text-left px-3 py-1 text-[11px] text-neutral-300 hover:bg-neutral-800"
            >
              {d} day{d === 1 ? "" : "s"}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
