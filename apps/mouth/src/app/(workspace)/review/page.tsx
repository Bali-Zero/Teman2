"use client";

/**
 * Document review page (INTAKE flow v2 — "the exact document, the exact destination").
 *
 * Each team member sees THEIR queue (server-enforced by intake_queue.received_by:
 * own mirrored chat + official-line docs backfilled to the client's consultant).
 * Opening a document claims a 15-min lease, then the reviewer:
 *
 *   1. SEES the original document (image/PDF streamed from the Pro reader via
 *      /api/intake/review/{id}/blob; OCR text as fallback/toggle);
 *   2. confirms or corrects WHAT it is (extracted fields, inline editable);
 *   3. decides WHERE it goes — candidate clients (radio), free client search,
 *      practice picker ("archive only" allowed);
 *   4. reads the destination summary ("→ Client · Practice") and Approves,
 *      or Rejects with an optional reason (audited server-side).
 *
 * Approve sends {client_id, practice_id, document_category, document_subtype,
 * final_fields} — the backend writer (INTAKE_WRITER_ENABLED-gated) commits
 * atomically or records a dry-run audit; the page surfaces dry-run explicitly
 * so nobody is misled.
 *
 * Auth + transport reuse the shared `api` client (httpOnly cookie + bearer).
 * The <img>/<iframe> preview rides the same-origin SSO cookie.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

import {
  categoriesForGroup,
  categoryGroups,
  driveFolderLabel,
  formatOperator,
  formatPracticeOption,
  groupLabel,
  inferDestinationFromDocType,
  type DocumentCategory,
} from "./destination";

interface EntityCandidate {
  client_id: number;
  full_name: string;
  assigned_to?: string | null;
  email?: string | null;
  phone?: string | null;
  nationality?: string | null;
}

/** "Walter · +39 339… · IT" — the human disambiguators for homonym-heavy CRM. */
function clientMeta(c: {
  phone?: string | null;
  email?: string | null;
  nationality?: string | null;
}): string {
  return [c.phone, c.email, c.nationality].filter(Boolean).join(" · ");
}

interface ProposalSummary {
  proposal_id: number;
  doc_type: string;
  decision: string;
  source: string;
  status: string;
  received_by?: string | null;
  entity_candidates: EntityCandidate[];
  extracted_fields: Record<string, unknown>;
  created_at: string;
}

interface OcrPage {
  page_number: number;
  text: string;
}

interface RoutingInfo {
  client_id?: number | null;
  practice_id?: number | null;
  practice_hint?: { practice_type_code?: string; status?: string } | null;
}

interface ProposalDetail extends ProposalSummary {
  ocr_pages?: OcrPage[];
  routing?: RoutingInfo;
  mime_type?: string | null;
  byte_size?: number | null;
}

interface ClaimResponse {
  proposal_id: number;
  claim_token: string;
  lease_expires_at: string;
}

interface ApproveResponse {
  proposal_id: number;
  dry_run: boolean;
  outcome: string;
  status: string;
}

interface ClientSearchItem {
  client_id: number;
  full_name: string;
  assigned_to?: string | null;
  email?: string | null;
  phone?: string | null;
  nationality?: string | null;
  score: number;
}

interface PracticeItem {
  practice_id: number;
  practice_type_code: string;
  title?: string | null;
  status: string;
}

interface DocumentCategoriesResponse {
  items?: DocumentCategory[];
}

const CARD = {
  borderColor: "var(--bz-border)",
  background: "var(--bz-card, var(--bz-surface))",
} as const;

function DecisionBadge({ decision }: { decision: string }) {
  const color =
    decision === "AUTO_ATTACH"
      ? "var(--bz-success, #4db87a)"
      : decision === "NO_MATCH" || decision === "AMBIGUOUS"
        ? "var(--bz-error, #d95f5a)"
        : "var(--bz-warning, #d4923a)";
  return (
    <span
      className="rounded px-2 py-0.5 text-xs font-medium"
      style={{ border: `1px solid ${color}`, color }}
    >
      {decision}
    </span>
  );
}

/** Render the extracted-field value as an editable string. */
function fieldToString(v: unknown): string {
  if (v == null) return "";
  if (
    typeof v === "object" &&
    v !== null &&
    "value" in (v as Record<string, unknown>)
  ) {
    const inner = (v as Record<string, unknown>).value;
    return inner == null ? "" : String(inner);
  }
  return String(v);
}

/**
 * Detect the "the proposal already left the claimable state" 409, so a retry
 * after a transient blip (whose write already committed) is shown as an
 * informational refresh, NOT a red "action failed" error.
 *
 * The backend guard (shared by approve AND reject) raises HTTP 409 with
 * detail=`Proposal must be review_claimed (status=<actual>).`; the api client
 * surfaces that detail verbatim into Error.message. We anchor on the stable
 * "must be review_claimed" phrase, then branch on the terminal status:
 *   - status=routed   → the document was already approved & filed.
 *   - status=rejected → the proposal was already rejected.
 * Any other status (e.g. review_pending) or a different error (network/500,
 * "Claim lease expired", etc.) returns null and stays on the normal error path.
 */
export function classifyResolvedDecideError(
  message: string | undefined | null,
): "already_filed" | "already_rejected" | null {
  if (!message || !message.includes("must be review_claimed")) return null;
  if (message.includes("status=routed")) return "already_filed";
  if (message.includes("status=rejected")) return "already_rejected";
  return null;
}

export default function ReviewPage() {
  const router = useRouter();
  const [items, setItems] = useState<ProposalSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [detail, setDetail] = useState<ProposalDetail | null>(null);
  const [claimToken, setClaimToken] = useState<string | null>(null);
  // Seed the destination (group+category) exactly ONCE per opened proposal,
  // so a manual Profile-group / Category change is never clobbered by the
  // doc_type re-inference. Keyed by proposal_id; re-seeds for a new document.
  const destinationSeededRef = useRef<number | null>(null);

  // ── Decision-panel state ────────────────────────────────────────────────
  const [selectedClient, setSelectedClient] = useState<EntityCandidate | null>(
    null,
  );
  const [practices, setPractices] = useState<PracticeItem[]>([]);
  const [selectedPracticeId, setSelectedPracticeId] = useState<number | "">("");
  const [fieldEdits, setFieldEdits] = useState<Record<string, string>>({});
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<ClientSearchItem[]>([]);
  const [categories, setCategories] = useState<DocumentCategory[]>([]);
  const [selectedGroup, setSelectedGroup] = useState("other");
  const [selectedCategoryCode, setSelectedCategoryCode] = useState("");
  const [showOcr, setShowOcr] = useState(false);
  const [previewFailed, setPreviewFailed] = useState(false);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<{ items: ProposalSummary[] }>(
        "/api/intake/review/queue?status=review_pending&limit=50",
      );
      setItems(res.items ?? []);
    } catch (e) {
      logger.error(
        "review queue load failed",
        { component: "ReviewPage", action: "loadQueue" },
        e instanceof Error ? e : new Error(String(e)),
      );
      setError("Could not load the review queue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const loadCategories = useCallback(async () => {
    try {
      const res = await api.get<
        DocumentCategoriesResponse | DocumentCategory[]
      >("/api/intake/review/document-categories");
      setCategories(Array.isArray(res) ? res : (res.items ?? []));
    } catch (e) {
      setCategories([]);
      logger.warn("document categories load failed", {
        component: "ReviewPage",
        action: "loadCategories",
        metadata: { error: String(e) },
      });
    }
  }, []);

  useEffect(() => {
    void loadCategories();
  }, [loadCategories]);

  // ── Open: claim + detail + seed the decision panel ──────────────────────
  const openDetail = useCallback(
    async (proposalId: number) => {
      setBusy(proposalId);
      setError(null);
      setNotice(null);
      // A fresh open must re-seed the destination (even re-opening the
      // same proposal); the seed effect owns the one-shot per proposal.
      destinationSeededRef.current = null;
      try {
        // Claim first (15-min lease) so approve/reject have a valid token.
        const claim = await api.post<ClaimResponse>(
          `/api/intake/review/${proposalId}/claim`,
          {},
        );
        setClaimToken(claim.claim_token);
        const d = await api.get<ProposalDetail>(
          `/api/intake/review/${proposalId}`,
        );
        setDetail(d);
        setPreviewFailed(false);
        setShowOcr(false);
        setSearch("");
        setSearchResults([]);
        setFieldEdits({});
        const inferredDestination = inferDestinationFromDocType(
          d.doc_type,
          categories,
        );
        setSelectedGroup(inferredDestination.group);
        setSelectedCategoryCode(inferredDestination.categoryCode);
        // Seed destination: routing's resolved client, else the first candidate.
        const routedId = d.routing?.client_id ?? null;
        const seed =
          d.entity_candidates?.find((c) => c.client_id === routedId) ??
          d.entity_candidates?.[0] ??
          null;
        setSelectedClient(seed);
        setSelectedPracticeId(
          seed && routedId === seed.client_id && d.routing?.practice_id
            ? d.routing.practice_id
            : "",
        );
      } catch (e) {
        const msg =
          e instanceof Error && /409/.test(e.message)
            ? "Already claimed by another reviewer."
            : "Could not open the document.";
        setError(msg);
        logger.error(
          "review claim/detail failed",
          { component: "ReviewPage", action: "openDetail" },
          e instanceof Error ? e : new Error(String(e)),
        );
      } finally {
        setBusy(null);
      }
    },
    [categories],
  );

  useEffect(() => {
    // Re-derive the destination from doc_type ONCE per proposal, after the
    // category list has loaded. The ref guard (not selectedCategoryCode)
    // ensures a manual group/category switch is never re-inferred away.
    if (!detail || categories.length === 0) return;
    if (destinationSeededRef.current === detail.proposal_id) return;
    destinationSeededRef.current = detail.proposal_id;
    const inferredDestination = inferDestinationFromDocType(
      detail.doc_type,
      categories,
    );
    setSelectedGroup(inferredDestination.group);
    setSelectedCategoryCode(inferredDestination.categoryCode);
  }, [categories, detail]);

  // ── Practice list follows the selected client ───────────────────────────
  useEffect(() => {
    if (!selectedClient) {
      setPractices([]);
      setSelectedPracticeId("");
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const res = await api.get<{ items: PracticeItem[] }>(
          `/api/intake/review/clients/${selectedClient.client_id}/practices`,
        );
        if (!cancelled) {
          const nextPractices = res.items ?? [];
          setPractices(nextPractices);
          setSelectedPracticeId((current) =>
            nextPractices.some((p) => p.practice_id === current) ? current : "",
          );
        }
      } catch {
        if (!cancelled) {
          setPractices([]);
          setSelectedPracticeId("");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedClient]);

  // ── Debounced client search ──────────────────────────────────────────────
  useEffect(() => {
    const q = search.trim();
    if (q.length < 2) {
      setSearchResults([]);
      return;
    }
    const t = setTimeout(() => {
      void (async () => {
        try {
          const res = await api.get<{ items: ClientSearchItem[] }>(
            `/api/intake/review/clients/search?q=${encodeURIComponent(q)}`,
          );
          setSearchResults(res.items ?? []);
        } catch {
          setSearchResults([]);
        }
      })();
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const closeDetail = useCallback(async () => {
    if (detail && claimToken) {
      try {
        await api.post(
          `/api/intake/review/${detail.proposal_id}/release?claim_token=${encodeURIComponent(claimToken)}`,
          {},
        );
      } catch {
        /* best-effort release; lease expires on its own */
      }
    }
    setDetail(null);
    setClaimToken(null);
    setSelectedClient(null);
    setPractices([]);
    setSelectedPracticeId("");
    setSelectedGroup("other");
    setSelectedCategoryCode("");
    setFieldEdits({});
  }, [detail, claimToken]);

  const decide = useCallback(
    async (action: "approve" | "reject") => {
      if (!detail || !claimToken) return;
      setBusy(detail.proposal_id);
      setError(null);
      setNotice(null);
      try {
        if (action === "approve") {
          const body: Record<string, unknown> = { claim_token: claimToken };
          if (selectedClient) body.client_id = selectedClient.client_id;
          // practice_id key is ALWAYS sent on approve: an explicit null means
          // "archive only" and must not fall back to routing's hint server-side.
          body.practice_id =
            selectedPracticeId === "" ? null : selectedPracticeId;
          body.document_category = selectedGroup;
          if (selectedCategoryCode)
            body.document_subtype = selectedCategoryCode;
          if (Object.keys(fieldEdits).length > 0)
            body.final_fields = fieldEdits;
          const res = await api.post<ApproveResponse>(
            `/api/intake/review/${detail.proposal_id}/approve`,
            body,
          );
          if (res.dry_run) {
            setNotice(
              "✓ Approved in dry-run mode: the destination was recorded in the audit, but nothing was written to the CRM yet (INTAKE_WRITER_ENABLED is off).",
            );
          } else if (res.outcome === "committed") {
            setNotice(
              `✓ Document filed to ${selectedClient?.full_name ?? "client"}.`,
            );
          } else {
            setNotice(`Approve outcome: ${res.outcome}.`);
          }
        } else {
          const reason =
            window.prompt("Reason for rejecting (optional):") ?? "";
          await api.post(`/api/intake/review/${detail.proposal_id}/reject`, {
            claim_token: claimToken,
            reason,
          });
        }
        setDetail(null);
        setClaimToken(null);
        setSelectedClient(null);
        await loadQueue();
      } catch (e) {
        // Idempotent path: a transient blip may have hidden a response whose
        // write already committed. Retrying then hits the backend 409 guard
        // (status=routed/rejected). Surface that as an informational refresh,
        // never a red failure that invites confusing re-clicks.
        const resolved = classifyResolvedDecideError(
          e instanceof Error ? e.message : String(e),
        );
        if (resolved) {
          setNotice(
            resolved === "already_rejected"
              ? "This document was already rejected — refreshing the queue."
              : "This document was already filed — refreshing the queue.",
          );
          setDetail(null);
          setClaimToken(null);
          setSelectedClient(null);
          await loadQueue();
        } else {
          setError(`Action "${action}" failed. Please retry.`);
          logger.error(
            "review decide failed",
            { component: "ReviewPage", action },
            e instanceof Error ? e : new Error(String(e)),
          );
        }
      } finally {
        setBusy(null);
      }
    },
    [
      detail,
      claimToken,
      selectedClient,
      selectedPracticeId,
      selectedGroup,
      selectedCategoryCode,
      fieldEdits,
      loadQueue,
    ],
  );

  // ── Destination summary (the "exact flow" line) ──────────────────────────
  const selectedPractice = useMemo(
    () => practices.find((p) => p.practice_id === selectedPracticeId) ?? null,
    [practices, selectedPracticeId],
  );
  const groupOptions = useMemo(() => categoryGroups(categories), [categories]);
  const groupCategories = useMemo(
    () => categoriesForGroup(categories, selectedGroup),
    [categories, selectedGroup],
  );
  const selectedCategory = useMemo(
    () =>
      groupCategories.find(
        (category) => category.code === selectedCategoryCode,
      ) ?? null,
    [groupCategories, selectedCategoryCode],
  );
  const destinationLabel = useMemo(() => {
    if (!selectedClient) return "No destination — pick a client (or Reject)";
    const categoryLabel = selectedCategory
      ? selectedCategory.name
      : "no category selected";
    const practiceLabel = selectedPractice
      ? formatPracticeOption(selectedPractice)
      : "client document archive";
    return `${selectedClient.full_name} → ${groupLabel(selectedGroup)} / ${categoryLabel} → ${practiceLabel}`;
  }, [selectedCategory, selectedClient, selectedGroup, selectedPractice]);

  // Authenticated blob preview: an <iframe>/<img> request cannot carry the
  // Bearer header, so a direct src 401s ("Connessione negata"). Fetch the
  // blob WITH the token, then preview via a local object URL.
  const [blobUrl, setBlobUrl] = useState<string>("");
  useEffect(() => {
    if (!detail) {
      setBlobUrl("");
      return;
    }
    let revoked: string | null = null;
    let cancelled = false;
    (async () => {
      try {
        const token = api.getToken();
        const res = await fetch(
          `/api/intake/review/${detail.proposal_id}/blob`,
          {
            headers: token ? { Authorization: `Bearer ${token}` } : undefined,
            credentials: "include",
          },
        );
        if (!res.ok) throw new Error(`blob HTTP ${res.status}`);
        const blob = await res.blob();
        if (cancelled) return;
        revoked = URL.createObjectURL(blob);
        setBlobUrl(revoked);
        setPreviewFailed(false);
      } catch (e) {
        logger.warn("blob preview fetch failed", {
          component: "ReviewPage",
          action: "blobFetch",
          metadata: { proposalId: detail.proposal_id, error: String(e) },
        });
        if (!cancelled) {
          setBlobUrl("");
          setPreviewFailed(true);
        }
      }
    })();
    return () => {
      cancelled = true;
      if (revoked) URL.revokeObjectURL(revoked);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail?.proposal_id]);
  const mime = detail?.mime_type ?? "";
  const isImage = mime.startsWith("image/");
  const isPdf = mime === "application/pdf";
  const fields = detail?.extracted_fields ?? {};
  const fieldKeys = Object.keys(fields);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1
          className="text-2xl font-semibold"
          style={{ color: "var(--bz-text-1)" }}
        >
          Document review
        </h1>
        <button
          type="button"
          onClick={() => router.push("/dashboard")}
          className="rounded-md border px-3 py-1.5 text-sm"
          style={{ borderColor: "var(--bz-border)", color: "var(--bz-text-2)" }}
        >
          ← Back
        </button>
      </div>

      {error && (
        <div
          className="mb-4 rounded-md border px-4 py-2 text-sm"
          style={{
            borderColor: "var(--bz-error, #d95f5a)",
            color: "var(--bz-text-1)",
          }}
        >
          {error}
        </div>
      )}
      {notice && (
        <div
          className="mb-4 rounded-md border px-4 py-2 text-sm"
          style={{
            borderColor: "var(--bz-success, #2e9e6b)",
            color: "var(--bz-text-1)",
          }}
        >
          {notice}
        </div>
      )}

      {loading ? (
        <p style={{ color: "var(--bz-text-3)" }}>Loading…</p>
      ) : !error && items.length === 0 ? (
        <p style={{ color: "var(--bz-success, #2e9e6b)" }}>
          ✓ No documents to review.
        </p>
      ) : (
        <ul className="space-y-3">
          {items.map((it) => {
            const candidate = it.entity_candidates?.[0];
            return (
              <li
                key={it.proposal_id}
                className="rounded-xl border p-4"
                style={CARD}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span
                        className="font-medium"
                        style={{ color: "var(--bz-text-1)" }}
                      >
                        {it.doc_type || "document"}
                      </span>
                      <DecisionBadge decision={it.decision} />
                      <span
                        className="text-xs"
                        style={{ color: "var(--bz-text-3)" }}
                      >
                        {it.source}
                        {it.created_at
                          ? ` · ${new Date(it.created_at).toLocaleDateString()}`
                          : ""}
                      </span>
                    </div>
                    <p
                      className="mt-1 text-sm"
                      style={{ color: "var(--bz-text-2)" }}
                    >
                      {candidate
                        ? `Proposed client: ${candidate.full_name}`
                        : "No client matched — needs a decision"}
                    </p>
                    <p
                      className="mt-1 text-xs"
                      style={{ color: "var(--bz-text-3)" }}
                    >
                      Operator: {formatOperator(it.received_by)}
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={busy === it.proposal_id}
                    onClick={() => void openDetail(it.proposal_id)}
                    className="shrink-0 rounded-md border px-4 py-2 text-sm font-medium"
                    style={{
                      borderColor: "var(--bz-border)",
                      background: "var(--bz-surface)",
                      color: "var(--bz-text-1)",
                      opacity: busy === it.proposal_id ? 0.6 : 1,
                    }}
                  >
                    {busy === it.proposal_id ? "…" : "Review"}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {detail && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center"
          style={{ background: "rgba(0,0,0,0.55)" }}
          onClick={() => void closeDetail()}
        >
          <div
            className="max-h-[92vh] w-full max-w-5xl overflow-auto rounded-xl border p-5"
            style={CARD}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <h2
                className="text-lg font-medium"
                style={{ color: "var(--bz-text-1)" }}
              >
                {detail.doc_type || "document"}{" "}
                <DecisionBadge decision={detail.decision} />
              </h2>
              <button
                type="button"
                onClick={() => void closeDetail()}
                style={{ color: "var(--bz-text-3)" }}
              >
                ✕
              </button>
            </div>

            <div className="grid gap-5 md:grid-cols-2">
              {/* ── LEFT: the exact document ──────────────────────────── */}
              <div>
                {!previewFailed && !blobUrl && (isImage || isPdf) && (
                  <div
                    className="flex w-full items-center justify-center rounded-md border text-xs"
                    style={{
                      borderColor: "var(--bz-border)",
                      color: "var(--bz-text-3)",
                      height: "60vh",
                    }}
                  >
                    Loading document…
                  </div>
                )}
                {!previewFailed && blobUrl && isImage && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={blobUrl}
                    alt={detail.doc_type || "document"}
                    className="w-full rounded-md border object-contain"
                    style={{
                      borderColor: "var(--bz-border)",
                      maxHeight: "60vh",
                    }}
                    onError={() => setPreviewFailed(true)}
                  />
                )}
                {!previewFailed && blobUrl && isPdf && (
                  <iframe
                    src={blobUrl}
                    title="document preview"
                    className="w-full rounded-md border"
                    style={{ borderColor: "var(--bz-border)", height: "60vh" }}
                  />
                )}
                {(previewFailed || (!isImage && !isPdf)) && (
                  <p
                    className="mb-2 text-xs"
                    style={{ color: "var(--bz-text-3)" }}
                  >
                    No visual preview available — showing the OCR text.
                  </p>
                )}

                {(previewFailed || (!isImage && !isPdf) || showOcr) &&
                  detail.ocr_pages &&
                  detail.ocr_pages.length > 0 && (
                    <div
                      className="mt-2 max-h-64 overflow-auto rounded-md border p-3 text-xs whitespace-pre-wrap"
                      style={{
                        borderColor: "var(--bz-border)",
                        color: "var(--bz-text-2)",
                        background: "var(--bz-surface)",
                      }}
                    >
                      {detail.ocr_pages
                        .map((p) => `— page ${p.page_number} —\n${p.text}`)
                        .join("\n\n")}
                    </div>
                  )}

                {(isImage || isPdf) && !previewFailed && (
                  <button
                    type="button"
                    onClick={() => setShowOcr((s) => !s)}
                    className="mt-2 text-xs underline"
                    style={{ color: "var(--bz-text-3)" }}
                  >
                    {showOcr ? "Hide OCR text" : "Show OCR text"}
                  </button>
                )}
              </div>

              {/* ── RIGHT: the exact destination ──────────────────────── */}
              <div className="space-y-4">
                {/* Extracted fields (editable) */}
                {fieldKeys.length > 0 && (
                  <div>
                    <h3
                      className="mb-1 text-sm font-medium"
                      style={{ color: "var(--bz-text-1)" }}
                    >
                      Extracted fields
                    </h3>
                    <div className="space-y-1">
                      {fieldKeys.map((k) => (
                        <div key={k} className="flex items-center gap-2">
                          <span
                            className="w-36 shrink-0 truncate text-xs"
                            style={{ color: "var(--bz-text-3)" }}
                            title={k}
                          >
                            {k}
                          </span>
                          <input
                            className="w-full rounded border px-2 py-1 text-xs"
                            style={{
                              borderColor: "var(--bz-border)",
                              background: "var(--bz-surface)",
                              color: "var(--bz-text-1)",
                            }}
                            value={fieldEdits[k] ?? fieldToString(fields[k])}
                            onChange={(e) =>
                              setFieldEdits((prev) => ({
                                ...prev,
                                [k]: e.target.value,
                              }))
                            }
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Candidate clients */}
                <div>
                  <h3
                    className="mb-1 text-sm font-medium"
                    style={{ color: "var(--bz-text-1)" }}
                  >
                    Client
                  </h3>
                  {detail.entity_candidates?.length ? (
                    <div className="space-y-1">
                      {detail.entity_candidates.map((c) => (
                        <label
                          key={c.client_id}
                          className="flex cursor-pointer items-center gap-2 rounded border px-2 py-1.5 text-sm"
                          style={{
                            borderColor:
                              selectedClient?.client_id === c.client_id
                                ? "var(--bz-accent, #d4845a)"
                                : "var(--bz-border)",
                            color: "var(--bz-text-1)",
                          }}
                        >
                          <input
                            type="radio"
                            name="client"
                            checked={selectedClient?.client_id === c.client_id}
                            onChange={() => {
                              setSelectedClient(c);
                              setSelectedPracticeId(
                                detail.routing?.client_id === c.client_id &&
                                  detail.routing?.practice_id
                                  ? detail.routing.practice_id
                                  : "",
                              );
                            }}
                          />
                          <span className="min-w-0">
                            {c.full_name}
                            {clientMeta(c) && (
                              <span
                                className="block truncate text-xs"
                                style={{ color: "var(--bz-text-3)" }}
                              >
                                {clientMeta(c)}
                              </span>
                            )}
                          </span>
                          {c.assigned_to && (
                            <span
                              className="ml-auto text-xs"
                              style={{ color: "var(--bz-text-3)" }}
                            >
                              {c.assigned_to}
                            </span>
                          )}
                        </label>
                      ))}
                    </div>
                  ) : (
                    <p
                      className="text-sm"
                      style={{ color: "var(--bz-text-3)" }}
                    >
                      No automatic match — search the client below.
                    </p>
                  )}

                  {/* Free client search */}
                  <input
                    className="mt-2 w-full rounded border px-2 py-1.5 text-sm"
                    style={{
                      borderColor: "var(--bz-border)",
                      background: "var(--bz-surface)",
                      color: "var(--bz-text-1)",
                    }}
                    placeholder="Search client by name, phone or email…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                  {searchResults.length > 0 && (
                    <ul
                      className="mt-1 max-h-40 overflow-auto rounded border text-sm"
                      style={{ borderColor: "var(--bz-border)" }}
                    >
                      {searchResults.map((r) => (
                        <li key={r.client_id}>
                          <button
                            type="button"
                            className="w-full px-2 py-1.5 text-left hover:opacity-80"
                            style={{ color: "var(--bz-text-1)" }}
                            onClick={() => {
                              setSelectedClient({
                                client_id: r.client_id,
                                full_name: r.full_name,
                                assigned_to: r.assigned_to,
                                email: r.email,
                                phone: r.phone,
                                nationality: r.nationality,
                              });
                              setSelectedPracticeId("");
                              setSearch("");
                              setSearchResults([]);
                            }}
                          >
                            <span className="flex items-baseline justify-between gap-2">
                              <span>{r.full_name}</span>
                              {r.assigned_to ? (
                                <span
                                  className="text-xs"
                                  style={{ color: "var(--bz-text-3)" }}
                                >
                                  {r.assigned_to}
                                </span>
                              ) : null}
                            </span>
                            {clientMeta(r) && (
                              <span
                                className="block truncate text-xs"
                                style={{ color: "var(--bz-text-3)" }}
                              >
                                {clientMeta(r)}
                              </span>
                            )}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* Destination category */}
                <div>
                  <h3
                    className="mb-1 text-sm font-medium"
                    style={{ color: "var(--bz-text-1)" }}
                  >
                    Destination
                  </h3>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <label
                      className="text-xs"
                      style={{ color: "var(--bz-text-3)" }}
                    >
                      Profile group
                      <select
                        className="mt-1 w-full rounded border px-2 py-1.5 text-sm"
                        style={{
                          borderColor: "var(--bz-border)",
                          background: "var(--bz-surface)",
                          color: "var(--bz-text-1)",
                        }}
                        value={selectedGroup}
                        onChange={(e) => {
                          setSelectedGroup(e.target.value);
                          setSelectedCategoryCode("");
                        }}
                      >
                        {groupOptions.map((group) => (
                          <option key={group} value={group}>
                            {groupLabel(group)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label
                      className="text-xs"
                      style={{ color: "var(--bz-text-3)" }}
                    >
                      Category
                      <select
                        className="mt-1 w-full rounded border px-2 py-1.5 text-sm"
                        style={{
                          borderColor: "var(--bz-border)",
                          background: "var(--bz-surface)",
                          color: "var(--bz-text-1)",
                        }}
                        value={selectedCategoryCode}
                        disabled={groupCategories.length === 0}
                        onChange={(e) =>
                          setSelectedCategoryCode(e.target.value)
                        }
                      >
                        <option value="">
                          {groupCategories.length === 0
                            ? "No categories available"
                            : "Select category"}
                        </option>
                        {groupCategories.map((category) => (
                          <option key={category.code} value={category.code}>
                            {category.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <p
                    className="mt-1 text-xs"
                    style={{ color: "var(--bz-text-3)" }}
                  >
                    Drive folder: {driveFolderLabel(selectedGroup)}
                  </p>
                </div>

                {/* Practice picker */}
                {selectedClient && practices.length > 0 && (
                  <div>
                    <h3
                      className="mb-1 text-sm font-medium"
                      style={{ color: "var(--bz-text-1)" }}
                    >
                      Practice
                    </h3>
                    <select
                      className="w-full rounded border px-2 py-1.5 text-sm"
                      style={{
                        borderColor: "var(--bz-border)",
                        background: "var(--bz-surface)",
                        color: "var(--bz-text-1)",
                      }}
                      value={selectedPracticeId}
                      onChange={(e) =>
                        setSelectedPracticeId(
                          e.target.value === "" ? "" : Number(e.target.value),
                        )
                      }
                    >
                      <option value="">
                        Document archive only (no practice)
                      </option>
                      {practices.map((p) => (
                        <option key={p.practice_id} value={p.practice_id}>
                          {formatPracticeOption(p)}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Destination summary — the exact flow */}
                <div
                  className="rounded-md border px-3 py-2 text-sm"
                  style={{
                    borderColor: selectedClient
                      ? "var(--bz-success, #2e9e6b)"
                      : "var(--bz-warning, #d4923a)",
                    color: "var(--bz-text-1)",
                  }}
                >
                  <span
                    className="text-xs"
                    style={{ color: "var(--bz-text-3)" }}
                  >
                    This document will be filed to:
                  </span>
                  <br />
                  <strong>{destinationLabel}</strong>
                </div>

                <div className="flex gap-3">
                  <button
                    type="button"
                    disabled={busy === detail.proposal_id || !selectedClient}
                    onClick={() => void decide("approve")}
                    className="flex-1 rounded-md px-4 py-2 text-sm font-medium text-white"
                    style={{
                      background: "var(--bz-success, #2e9e6b)",
                      opacity:
                        busy === detail.proposal_id || !selectedClient
                          ? 0.5
                          : 1,
                    }}
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    disabled={busy === detail.proposal_id}
                    onClick={() => void decide("reject")}
                    className="flex-1 rounded-md px-4 py-2 text-sm font-medium text-white"
                    style={{
                      background: "var(--bz-error, #d95f5a)",
                      opacity: busy === detail.proposal_id ? 0.6 : 1,
                    }}
                  >
                    Reject
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
