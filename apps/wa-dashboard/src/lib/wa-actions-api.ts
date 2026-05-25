import type {
  ActionPatchRequest,
  ActionQueueListResponse,
  ActionQueueOwnersResponse,
  ActionQueueRow,
  SortField,
  SortOrder,
} from "@/types/wa-action";

export interface ListActionsParams {
  owner?: string;
  status?: string;
  min_priority?: number;
  action_type?: string;
  search?: string;
  sort?: SortField;
  order?: SortOrder;
  limit?: number;
  offset?: number;
}

function buildQuery(
  params: Record<string, string | number | undefined>,
): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

export async function fetchActions(
  params: ListActionsParams,
): Promise<ActionQueueListResponse> {
  const url = `/api/wa/actions${buildQuery({ ...params })}`;
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(`fetchActions failed: ${detail}`);
  }
  return (await res.json()) as ActionQueueListResponse;
}

export async function fetchOwners(): Promise<ActionQueueOwnersResponse> {
  const res = await fetch("/api/wa/actions/owners", { credentials: "include" });
  if (!res.ok) {
    throw new Error(`fetchOwners failed: HTTP ${res.status}`);
  }
  return (await res.json()) as ActionQueueOwnersResponse;
}

export async function patchAction(
  actionId: number,
  payload: ActionPatchRequest,
): Promise<ActionQueueRow> {
  const res = await fetch(`/api/wa/actions/${actionId}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(`patchAction failed: ${detail}`);
  }
  return (await res.json()) as ActionQueueRow;
}
