"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ActionsFilters } from "@/components/actions/ActionsFilters";
import { ActionsTable } from "@/components/actions/ActionsTable";
import { fetchActions, fetchOwners } from "@/lib/wa-actions-api";
import type { SortField, SortOrder } from "@/types/wa-action";

const PAGE_SIZE = 50;

export default function ActionsPage() {
  const [owner, setOwner] = useState<string>("");
  const [status, setStatus] = useState<string>("open");
  const [minPriority, setMinPriority] = useState<number>(0);
  const [search, setSearch] = useState<string>("");
  const [sort, setSort] = useState<SortField>("priority");
  const [order, setOrder] = useState<SortOrder>("desc");
  const [page, setPage] = useState<number>(0);

  const queryParams = useMemo(
    () => ({
      owner: owner || undefined,
      status: status || undefined,
      min_priority: minPriority > 0 ? minPriority : undefined,
      search: search.trim() || undefined,
      sort,
      order,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    }),
    [owner, status, minPriority, search, sort, order, page],
  );

  const actionsQuery = useQuery({
    queryKey: ["wa-actions", queryParams],
    queryFn: () => fetchActions(queryParams),
    staleTime: 15_000,
  });

  const ownersQuery = useQuery({
    queryKey: ["wa-actions", "owners"],
    queryFn: fetchOwners,
    staleTime: 60_000,
  });

  const total = actionsQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-100">
      <header className="border-b border-neutral-800 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-semibold">
              WA Copilot — Action Queue
            </h1>
            <p className="text-xs text-neutral-500 mt-0.5">
              {actionsQuery.isLoading
                ? "Loading…"
                : `${total} action${total === 1 ? "" : "s"} (page ${page + 1}/${totalPages})`}
            </p>
          </div>
          <a
            href="/"
            className="text-xs text-neutral-400 hover:text-neutral-200 transition"
          >
            ← Inbox
          </a>
        </div>
      </header>

      <section className="px-6 py-4 border-b border-neutral-800 bg-neutral-925">
        <ActionsFilters
          owner={owner}
          onOwnerChange={(v) => {
            setOwner(v);
            setPage(0);
          }}
          owners={ownersQuery.data?.owners ?? []}
          status={status}
          onStatusChange={(v) => {
            setStatus(v);
            setPage(0);
          }}
          minPriority={minPriority}
          onMinPriorityChange={(v) => {
            setMinPriority(v);
            setPage(0);
          }}
          search={search}
          onSearchChange={(v) => {
            setSearch(v);
            setPage(0);
          }}
          sort={sort}
          onSortChange={setSort}
          order={order}
          onOrderChange={setOrder}
        />
      </section>

      <section className="px-6 py-4">
        {actionsQuery.isError && (
          <div className="rounded border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
            Failed to load: {String((actionsQuery.error as Error)?.message)}
          </div>
        )}
        {actionsQuery.data && (
          <ActionsTable
            rows={actionsQuery.data.items}
            onMutated={() => actionsQuery.refetch()}
          />
        )}
        {!actionsQuery.isLoading && actionsQuery.data?.items.length === 0 && (
          <div className="text-center text-sm text-neutral-500 py-12">
            No actions match the current filters.
          </div>
        )}

        <nav className="flex items-center justify-between mt-4 text-xs">
          <button
            type="button"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            className="px-3 py-1 rounded border border-neutral-700 text-neutral-300 hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ← Previous
          </button>
          <span className="text-neutral-500">
            Page {page + 1} of {totalPages}
          </span>
          <button
            type="button"
            disabled={page + 1 >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="px-3 py-1 rounded border border-neutral-700 text-neutral-300 hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Next →
          </button>
        </nav>
      </section>
    </main>
  );
}
