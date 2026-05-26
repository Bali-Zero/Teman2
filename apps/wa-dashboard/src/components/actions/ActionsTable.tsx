"use client";

import { useState } from "react";
import { ActionRow } from "./ActionRow";
import type { ActionQueueRow } from "@/types/wa-action";

interface Props {
  rows: ActionQueueRow[];
  onMutated: () => void;
}

export function ActionsTable({ rows, onMutated }: Props) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  if (rows.length === 0) return null;

  return (
    <div className="overflow-x-auto rounded border border-neutral-800">
      <table className="w-full text-xs">
        <thead className="bg-neutral-900 text-neutral-400 uppercase tracking-wide">
          <tr>
            <th className="px-3 py-2 text-left font-medium w-10"></th>
            <th className="px-3 py-2 text-left font-medium">Client</th>
            <th className="px-3 py-2 text-left font-medium">Practice</th>
            <th className="px-3 py-2 text-left font-medium">Type</th>
            <th className="px-3 py-2 text-left font-medium">Reason</th>
            <th className="px-3 py-2 text-left font-medium">Recommended</th>
            <th className="px-3 py-2 text-left font-medium">Due</th>
            <th className="px-3 py-2 text-left font-medium">Owner</th>
            <th className="px-3 py-2 text-center font-medium w-14">Prio</th>
            <th className="px-3 py-2 text-left font-medium w-20">Status</th>
            <th className="px-3 py-2 text-right font-medium w-56">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-800/60">
          {rows.map((row) => (
            <ActionRow
              key={row.action_id}
              row={row}
              expanded={expandedId === row.action_id}
              onToggleExpand={() =>
                setExpandedId(
                  expandedId === row.action_id ? null : row.action_id,
                )
              }
              onMutated={onMutated}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
