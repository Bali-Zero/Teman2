export interface ActionQueueRow {
  action_id: number;
  client_id: number | null;
  practice_id: number | null;
  conversation_id: number | null;
  action_type: string;
  reason: string;
  recommended_action: string;
  suggested_message_draft: string | null;
  due_at: string | null;
  evidence: Record<string, unknown> | unknown[] | null;
  owner: string | null;
  priority: number;
  status: "open" | "snoozed" | "done" | "dismissed";
  snoozed_until: string | null;
  dismiss_reason: string | null;
  resolution_notes: string | null;
  created_at: string;
  resolved_at: string | null;
  client_full_name: string | null;
  practice_kind: string | null;
}

export interface ActionQueueListResponse {
  items: ActionQueueRow[];
  limit: number;
  offset: number;
  total: number;
}

export interface ActionQueueOwnersResponse {
  owners: string[];
}

export interface ActionPatchRequest {
  status?: "open" | "snoozed" | "done" | "dismissed";
  snooze_days?: number;
  snoozed_until?: string;
  owner?: string;
  dismiss_reason?: string;
  resolution_notes?: string;
}

export type SortField = "priority" | "due_at" | "created_at";
export type SortOrder = "asc" | "desc";
