"use client";

import { useState } from "react";

interface Props {
  actionId: number;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}

export function DismissDialog({ actionId, onConfirm, onCancel }: Props) {
  const [reason, setReason] = useState("");
  const trimmed = reason.trim();

  return (
    <tr>
      <td colSpan={11} className="px-6 py-3 bg-neutral-900/70">
        <div className="max-w-xl rounded border border-neutral-700 bg-neutral-950 p-4">
          <div className="text-sm text-neutral-200 mb-2">
            Dismiss action #{actionId}
          </div>
          <label
            className="block text-[10px] uppercase tracking-wide text-neutral-500 mb-1"
            htmlFor={`dismiss-reason-${actionId}`}
          >
            Reason (required)
          </label>
          <textarea
            id={`dismiss-reason-${actionId}`}
            autoFocus
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. duplicate, false positive, client already handled offline…"
            className="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-xs text-neutral-100 focus:outline-none focus:border-neutral-500"
          />
          <div className="mt-3 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="rounded border border-neutral-700 bg-neutral-900 px-3 py-1 text-xs text-neutral-300 hover:bg-neutral-800"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={trimmed.length === 0}
              onClick={() => onConfirm(trimmed)}
              className="rounded border border-red-900/60 bg-red-950/40 px-3 py-1 text-xs text-red-200 hover:bg-red-900/40 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Confirm dismiss
            </button>
          </div>
        </div>
      </td>
    </tr>
  );
}
