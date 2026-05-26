"use client";

import type { SortField, SortOrder } from "@/types/wa-action";

interface Props {
  owner: string;
  onOwnerChange: (v: string) => void;
  owners: string[];
  status: string;
  onStatusChange: (v: string) => void;
  minPriority: number;
  onMinPriorityChange: (v: number) => void;
  search: string;
  onSearchChange: (v: string) => void;
  sort: SortField;
  onSortChange: (v: SortField) => void;
  order: SortOrder;
  onOrderChange: (v: SortOrder) => void;
}

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "open", label: "Open" },
  { value: "snoozed", label: "Snoozed" },
  { value: "done", label: "Done" },
  { value: "dismissed", label: "Dismissed" },
];

export function ActionsFilters({
  owner,
  onOwnerChange,
  owners,
  status,
  onStatusChange,
  minPriority,
  onMinPriorityChange,
  search,
  onSearchChange,
  sort,
  onSortChange,
  order,
  onOrderChange,
}: Props) {
  const labelCls =
    "block text-[10px] uppercase tracking-wide text-neutral-500 mb-1";
  const fieldCls =
    "w-full rounded border border-neutral-700 bg-neutral-900 px-2.5 py-1.5 text-xs text-neutral-100 focus:outline-none focus:border-neutral-500";

  return (
    <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
      <div>
        <label className={labelCls} htmlFor="filter-owner">
          Owner
        </label>
        <select
          id="filter-owner"
          className={fieldCls}
          value={owner}
          onChange={(e) => onOwnerChange(e.target.value)}
        >
          <option value="">All owners</option>
          {owners.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className={labelCls} htmlFor="filter-status">
          Status
        </label>
        <select
          id="filter-status"
          className={fieldCls}
          value={status}
          onChange={(e) => onStatusChange(e.target.value)}
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className={labelCls} htmlFor="filter-priority">
          Min priority ({minPriority || "any"})
        </label>
        <input
          id="filter-priority"
          type="range"
          min={0}
          max={10}
          step={1}
          value={minPriority}
          onChange={(e) => onMinPriorityChange(Number(e.target.value))}
          className="w-full accent-blue-500"
        />
      </div>

      <div className="md:col-span-2">
        <label className={labelCls} htmlFor="filter-search">
          Search reason / action
        </label>
        <input
          id="filter-search"
          type="text"
          className={fieldCls}
          placeholder="e.g. visa, kitas, follow up"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>

      <div>
        <label className={labelCls} htmlFor="filter-sort">
          Sort
        </label>
        <div className="flex gap-1">
          <select
            id="filter-sort"
            className={fieldCls}
            value={sort}
            onChange={(e) => onSortChange(e.target.value as SortField)}
          >
            <option value="priority">Priority</option>
            <option value="due_at">Due date</option>
            <option value="created_at">Created</option>
          </select>
          <button
            type="button"
            onClick={() => onOrderChange(order === "asc" ? "desc" : "asc")}
            className="px-2 rounded border border-neutral-700 bg-neutral-900 text-xs text-neutral-300 hover:bg-neutral-800"
            aria-label="Toggle sort order"
          >
            {order === "desc" ? "↓" : "↑"}
          </button>
        </div>
      </div>
    </div>
  );
}
