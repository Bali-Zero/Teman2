export type WhatsAppExportReviewStatus =
  | "parsed"
  | "reviewing"
  | "completed"
  | "failed"
  | "archived"
  | "pending"
  | "approved"
  | "rejected"
  | "ignored"
  | string;

export interface WhatsAppExportCounts {
  contacts?: number;
  documents?: number;
  messages?: number;
  yopo_cases?: number;
  pending?: number;
  approved?: number;
  rejected?: number;
}

export interface WhatsAppExportReviewBatch {
  id: string;
  source_label?: string | null;
  source_basename?: string | null;
  review_status?: WhatsAppExportReviewStatus | null;
  confidence?: number | null;
  reasons?: string[] | null;
  counts?: WhatsAppExportCounts | null;
  total_contacts?: number | null;
  total_documents?: number | null;
  total_messages?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface WhatsAppExportReviewItem {
  id: string;
  batch_id?: string | null;
  source_label?: string | null;
  source_basename?: string | null;
  masked_phone?: string | null;
  display_name?: string | null;
  suggested_client?: string | null;
  suggested_client_id?: string | null;
  suggested_practice?: string | null;
  suggested_practice_id?: string | null;
  confidence?: number | null;
  reasons?: string[] | null;
  review_status?: WhatsAppExportReviewStatus | null;
  counts?: WhatsAppExportCounts | null;
  body_excerpt?: string | null;
}

export type WhatsAppExportContact = WhatsAppExportReviewItem;
export type WhatsAppExportDocument = WhatsAppExportReviewItem;
export type WhatsAppExportMessage = WhatsAppExportReviewItem;

export interface WhatsAppExportYopoCase {
  contacts: WhatsAppExportContact[];
  documents: WhatsAppExportDocument[];
  messages: WhatsAppExportMessage[];
  recap: {
    contact_count?: number;
    document_count?: number;
    message_count?: number;
    review_status?: WhatsAppExportReviewStatus;
  };
}

export type WhatsAppExportReviewKind =
  | "batches"
  | "contacts"
  | "documents"
  | "messages"
  | "yopo-case";

export interface WhatsAppExportListParams {
  batchId?: string;
  limit?: number;
  offset?: number;
  status?: WhatsAppExportReviewStatus;
}

export interface WhatsAppExportActionParams {
  kind: "contacts" | "documents";
  id: string;
  approvedClientId?: string | null;
  approvedPracticeId?: string | null;
  reason?: string;
}

interface ListEnvelope<T> {
  items?: T[];
  results?: T[];
  data?: T[];
}

interface BackendBatch {
  id: number | string;
  label?: string | null;
  source_label?: string | null;
  source_basename?: string | null;
  review_status?: string | null;
  counts?: WhatsAppExportCounts | null;
  total_contacts?: number | null;
  total_documents?: number | null;
  total_messages?: number | null;
  created_at?: string | null;
}

interface BackendReviewItem {
  id: number | string;
  batch_id?: number | string | null;
  source_label?: string | null;
  source_basename?: string | null;
  masked_phone?: string | null;
  display_name?: string | null;
  title?: string | null;
  document_type?: string | null;
  body_excerpt?: string | null;
  suggested_client?: string | null;
  suggested_client_id?: number | string | null;
  approved_client_id?: number | string | null;
  suggested_practice?: string | null;
  suggested_practice_id?: number | string | null;
  match_confidence?: number | null;
  confidence?: number | null;
  reasons?: string[] | null;
  review_status?: string | null;
}

interface BackendYopoCase {
  contacts?: BackendReviewItem[];
  documents?: BackendReviewItem[];
  messages?: BackendReviewItem[];
  recap?: WhatsAppExportYopoCase["recap"];
}

const BASE_PATH = "/api/whatsapp-export";

function buildQuery(params: WhatsAppExportListParams = {}): string {
  const search = new URLSearchParams();
  if (params.batchId) search.set("batch_id", params.batchId);
  if (params.limit != null) search.set("limit", String(params.limit));
  if (params.offset != null) search.set("offset", String(params.offset));
  if (params.status) search.set("status", params.status);
  const query = search.toString();
  return query ? `?${query}` : "";
}

function isListEnvelope<T>(payload: unknown): payload is ListEnvelope<T> {
  return (
    typeof payload === "object" &&
    payload !== null &&
    ("items" in payload || "results" in payload || "data" in payload)
  );
}

function asList<T>(payload: T[] | ListEnvelope<T>): T[] {
  if (Array.isArray(payload)) return payload;
  return payload.items ?? payload.results ?? payload.data ?? [];
}

function stringId(value: number | string | null | undefined): string | null {
  if (value === null || value === undefined) return null;
  return String(value);
}

function mapBatch(batch: BackendBatch): WhatsAppExportReviewBatch {
  const counts = batch.counts ?? {
    contacts: batch.total_contacts ?? 0,
    documents: batch.total_documents ?? 0,
    messages: batch.total_messages ?? 0,
  };
  return {
    id: String(batch.id),
    source_label: batch.source_label ?? batch.label ?? null,
    source_basename: batch.source_basename ?? null,
    review_status: batch.review_status ?? null,
    counts,
    created_at: batch.created_at ?? null,
  };
}

function mapReviewItem(item: BackendReviewItem): WhatsAppExportReviewItem {
  const suggestedClientId =
    stringId(item.suggested_client_id) ?? stringId(item.approved_client_id);
  const suggestedPracticeId = stringId(item.suggested_practice_id);
  return {
    id: String(item.id),
    batch_id: stringId(item.batch_id),
    source_label: item.source_label ?? item.document_type ?? null,
    source_basename: item.source_basename ?? null,
    masked_phone: item.masked_phone ?? null,
    display_name: item.display_name ?? item.title ?? null,
    suggested_client:
      item.suggested_client ??
      (suggestedClientId ? `Client #${suggestedClientId}` : null),
    suggested_client_id: suggestedClientId,
    suggested_practice:
      item.suggested_practice ??
      (suggestedPracticeId ? `Practice #${suggestedPracticeId}` : null),
    suggested_practice_id: suggestedPracticeId,
    confidence: item.confidence ?? item.match_confidence ?? null,
    reasons: item.reasons ?? null,
    review_status: item.review_status ?? null,
    body_excerpt: item.body_excerpt ?? null,
  };
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${BASE_PATH}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  if (!response.ok) {
    const payload = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    const message =
      typeof payload?.detail === "string"
        ? payload.detail
        : `WhatsApp export API unavailable (${response.status})`;
    throw new Error(message);
  }

  if (response.status === 204) return {} as T;
  return (await response.json()) as T;
}

export async function listWhatsAppExportBatches(
  params: WhatsAppExportListParams = {},
): Promise<WhatsAppExportReviewBatch[]> {
  const payload = await requestJson<
    BackendBatch[] | ListEnvelope<BackendBatch>
  >(`/batches${buildQuery(params)}`);
  return asList(payload).map(mapBatch);
}

export async function listWhatsAppExportContacts(
  params: WhatsAppExportListParams = {},
): Promise<WhatsAppExportContact[]> {
  const payload = await requestJson<
    BackendReviewItem[] | ListEnvelope<BackendReviewItem>
  >(`/contacts${buildQuery(params)}`);
  return asList(payload).map(mapReviewItem);
}

export async function listWhatsAppExportDocuments(
  params: WhatsAppExportListParams = {},
): Promise<WhatsAppExportDocument[]> {
  const payload = await requestJson<
    BackendReviewItem[] | ListEnvelope<BackendReviewItem>
  >(`/documents${buildQuery(params)}`);
  return asList(payload).map(mapReviewItem);
}

export async function listWhatsAppExportMessages(
  params: WhatsAppExportListParams = {},
): Promise<WhatsAppExportMessage[]> {
  const payload = await requestJson<
    BackendReviewItem[] | ListEnvelope<BackendReviewItem>
  >(`/messages${buildQuery(params)}`);
  return asList(payload).map(mapReviewItem);
}

export async function getWhatsAppExportYopoCase(
  params: WhatsAppExportListParams = {},
): Promise<WhatsAppExportYopoCase | null> {
  const payload = await requestJson<BackendYopoCase | null>(
    `/yopo-case${buildQuery(params)}`,
  );
  if (payload === null) return null;
  return {
    contacts: (payload.contacts ?? []).map(mapReviewItem),
    documents: (payload.documents ?? []).map(mapReviewItem),
    messages: (payload.messages ?? []).map(mapReviewItem),
    recap: payload.recap ?? {},
  };
}

export async function listWhatsAppExportYopoCase(
  params: WhatsAppExportListParams = {},
): Promise<WhatsAppExportYopoCase | null> {
  return await getWhatsAppExportYopoCase(params);
}

export async function approveWhatsAppExportReview(
  params: WhatsAppExportActionParams,
): Promise<void> {
  if (params.kind === "contacts") {
    if (!params.approvedClientId) {
      throw new Error("Contact approval requires a suggested client.");
    }
    await requestJson(
      `/contacts/${encodeURIComponent(params.id)}/approve-match`,
      {
        method: "POST",
        body: JSON.stringify({
          approved_client_id: Number(params.approvedClientId),
          note: params.reason,
        }),
      },
    );
    return;
  }

  await requestJson(
    `/documents/${encodeURIComponent(params.id)}/approve-link`,
    {
      method: "POST",
      body: JSON.stringify({
        approved_client_id: params.approvedClientId
          ? Number(params.approvedClientId)
          : undefined,
        approved_practice_id: params.approvedPracticeId
          ? Number(params.approvedPracticeId)
          : undefined,
        note: params.reason,
      }),
    },
  );
}

export async function rejectWhatsAppExportReview(
  params: WhatsAppExportActionParams,
): Promise<void> {
  await requestJson(`/${params.kind}/${encodeURIComponent(params.id)}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason: params.reason }),
  });
}
