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

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";

import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import type { CreateClientParams } from "@/lib/api/crm/crm.types";
import {
  CellStack,
  DeskStrip,
  EmptyState,
  FOCUS,
  HairlineBody,
  HairlineGrid,
  HairlineHead,
  HairlineRow,
  Masthead,
  Notice,
  StatePill,
  TABULAR,
  type PillTone,
} from "@/components/workspace/r19";

import { classifyResolvedDecideError } from "./decide-error";
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

/**
 * Copper means "the signed-in viewer is the next actor" — derived from the
 * VIEWER and the RECORD together, NEVER from the decision/status alone. The
 * backend's GET /queue docstring (apps/backend-rag/backend/app/routers/
 * intake_review.py) says: "Admins see the entire queue. A non-admin sees
 * ONLY rows from their own chats (intake_queue.received_by == caller) ...
 * NULL-received_by docs (shared business line + Drive) are admin-only." So
 * for an admin the queue is GLOBAL, and an unresolved row received by a
 * DIFFERENT operator is not theirs to act on — painting it copper from the
 * decision alone would be copper-from-status, the exact violation this
 * window exists to remove. `ownedByViewer` carries that fact in.
 */
function decisionMeta(
  decision: string,
  ownedByViewer: boolean,
): { tone: PillTone; label: string } {
  if (!ownedByViewer) return { tone: "wait", label: "Another operator" };
  if (decision === "AUTO_ATTACH") return { tone: "ours", label: "Matched" };
  if (decision === "NO_MATCH" || decision === "AMBIGUOUS")
    return { tone: "you", label: "Needs you" };
  return { tone: "wait", label: decision || "Pending" };
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
 * Build a pre-filled new-client form from the document's OCR-extracted fields.
 *
 * The intake extract schema keys (``name`` / ``company_name`` / ``passport_no`` /
 * ``dob`` / ``expiry`` / ``nationality``) are NOT the CRM column names — this is the
 * exact translation the backend enricher applies
 * (``backend/services/intake/client_enricher.py::ENRICHMENT_MAP``). We mirror it on
 * the client so a reviewer never has to retype what the document already says.
 * Values may be wrapped as ``{value: ...}`` (confidence envelope); ``fieldToString``
 * unwraps that. Nothing is invented: a missing key stays an empty, editable field.
 */
function prefillFromExtractedFields(
  fields: Record<string, unknown>,
): CreateClientParams {
  const pick = (...keys: string[]): string => {
    for (const key of keys) {
      if (key in fields) {
        const s = fieldToString(fields[key]).trim();
        if (s) return s;
      }
    }
    return "";
  };
  const companyName = pick("company_name");
  const personName = pick("name", "full_name", "holder_name");
  return {
    // Prefer the person's name; fall back to the company name so the form is never blank.
    full_name: personName || companyName,
    nationality: pick("nationality"),
    passport_number: pick("passport_no", "passport_number", "kitas_no"),
    passport_expiry: pick("expiry", "passport_expiry"),
    date_of_birth: pick("dob", "date_of_birth"),
    company_name: companyName || undefined,
    client_type: companyName && !personName ? "company" : "individual",
    phone: "",
    email: "",
  };
}

/**
 * Terminal proposal statuses — a proposal that has already been processed and
 * can never be claimed again (migration 212 CHECK: review_pending |
 * review_claimed | routed | rejected | dead). `routed` is the SUCCESS terminal.
 */
const TERMINAL_STATUSES = new Set(["routed", "rejected", "dead"]);

/** Human-facing label for a terminal status used in the read-only notice. */
function terminalLabel(status: string): string {
  switch (status) {
    case "routed":
      return "already filed";
    case "rejected":
      return "rejected";
    case "dead":
      return "discarded";
    default:
      return `already ${status}`;
  }
}

/**
 * The `/claim` 409 — DISTINCT from the approve/reject 409 above. The backend
 * raises HTTP 409 with detail=`Proposal not claimable (status=<s>,
 * lease_owner=<o>)`; the api client surfaces that detail verbatim into
 * Error.message (api/client.ts:371). We key off the stable "not claimable"
 * phrase — NOT off "409", which never appears in the message.
 */
function isNotClaimable(e: unknown): boolean {
  return e instanceof Error && /not claimable/i.test(e.message);
}

/** Extract the `status=<s>` token from a "not claimable" 409 detail string. */
function statusFromClaimError(e: unknown): string | null {
  if (!(e instanceof Error)) return null;
  const m = /status=([a-z_]+)/i.exec(e.message);
  return m ? m[1] : null;
}

/**
 * Page-local wrapper over the shared `Notice` (never editing it directly).
 * `tone="warn"` borrows Notice's muted "wait" shape but recolours it to
 * `--state-warning` — a failed load or a validation problem reports a
 * FAILURE, which is urgency, not ownership, so it must never read as
 * copper ("the viewer is the next actor on a record"). Every other tone
 * passes straight through to `Notice` unchanged.
 */
function DeskNotice({
  tone,
  role,
  className,
  children,
}: {
  tone: "you" | "ok" | "wait" | "warn";
  role?: "alert" | "status";
  className?: string;
  children: ReactNode;
}) {
  if (tone === "warn") {
    return (
      <Notice
        tone="wait"
        role={role}
        className={cn(
          "border-[var(--state-warning)] text-[var(--state-warning)]",
          className,
        )}
      >
        {children}
      </Notice>
    );
  }
  return (
    <Notice tone={tone} role={role} className={className}>
      {children}
    </Notice>
  );
}

export default function ReviewPage() {
  const router = useRouter();

  // ── Ownership: viewer AND record, never the record alone (see the
  // decisionMeta docstring above for the backend contract this derives
  // from). Read fresh every render — the same idiom `api.getUserProfile()`
  // already uses elsewhere on this desk (dashboard/page.tsx:333).
  const profile = api.getUserProfile();
  const viewerEmail = profile?.email?.trim().toLowerCase() ?? "";
  const viewerRole = profile?.role?.trim().toLowerCase() ?? "";
  const viewerIsAdmin = viewerRole === "admin" || viewerRole === "owner";
  function ownsRow(receivedBy: string | null | undefined): boolean {
    const rb = receivedBy?.trim().toLowerCase() ?? "";
    if (!viewerEmail) return false; // unknown viewer never earns copper
    if (rb) return rb === viewerEmail;
    return viewerIsAdmin; // NULL received_by rows are admin-only by contract
  }
  const [items, setItems] = useState<ProposalSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [detail, setDetail] = useState<ProposalDetail | null>(null);
  const [claimToken, setClaimToken] = useState<string | null>(null);
  // Read-only reason when a proposal is opened WITHOUT a live claim (terminal
  // status, or claimed by another reviewer). null ⇒ the open is editable.
  const [readOnlyReason, setReadOnlyReason] = useState<string | null>(null);
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
  // ── "Create new client" inline form (NO_MATCH leads with this) ──────────
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState<CreateClientParams>({
    full_name: "",
  });
  const [createBusy, setCreateBusy] = useState(false);

  // ── Desk strip: presentation-only filter + search over the fetched queue.
  // No new request — both narrow the SAME `items` array the queue already
  // holds. Default "all" + empty search show every row, unchanged from
  // before this restyle.
  const [queueFilter, setQueueFilter] = useState<"all" | "you" | "matched">(
    "all",
  );
  const [queueSearch, setQueueSearch] = useState("");

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
      // Identity boundary, not a cosmetic choice: a failed reload (401/403,
      // or an account switch) must never leave a PREVIOUS viewer's rows
      // on screen under a fresh "N documents are waiting for your
      // decision" heading with copper pills painted for someone else.
      setItems([]);
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

  // ── Open: detail FIRST, claim only when claimable, seed the panel ────────
  //
  // Viewing is decoupled from claiming. We ALWAYS fetch the read-only detail
  // first (GET requires only RBAC, never a lease) so the operator can open any
  // authorised proposal — including terminal ones (routed/rejected/dead) and
  // ones another reviewer holds live. We attempt the 15-min claim ONLY when the
  // proposal is in a claimable state; on success the panel is editable, on a
  // 409 (raced / live-claimed by someone else) we fall back to read-only. A
  // failed claim is NEVER an error toast — the document still opens.
  const openDetail = useCallback(
    async (proposalId: number) => {
      setBusy(proposalId);
      setError(null);
      setNotice(null);
      setClaimToken(null);
      setReadOnlyReason(null);
      // A fresh open must re-seed the destination (even re-opening the
      // same proposal); the seed effect owns the one-shot per proposal.
      destinationSeededRef.current = null;
      try {
        // 1) Fetch the detail first — this works for any authorised proposal,
        //    regardless of status or lease ownership.
        const d = await api.get<ProposalDetail>(
          `/api/intake/review/${proposalId}`,
        );

        // 2) Claim only when the proposal is not in a terminal state. The
        //    backend atomically handles steal-expired / renew-own / 409-other,
        //    so we just attempt it for any non-terminal status.
        let token: string | null = null;
        let roReason: string | null = null;
        if (TERMINAL_STATUSES.has(d.status)) {
          roReason = `This proposal is ${terminalLabel(d.status)} — view only.`;
          // Prune the now-terminal row from the in-memory list. A proposal can
          // turn terminal because ANOTHER operator decided it while this page
          // was open — loadQueue() only re-runs after *our* own decide, so the
          // stale row lingers as a clickable zombie that always reopens
          // read-only. Dropping it here keeps the queue honest without a full
          // refetch (the backend WHERE status='review_pending' already excludes
          // it, so a reload would drop it too — this just does it eagerly).
          setItems((prev) => prev.filter((p) => p.proposal_id !== proposalId));
        } else {
          try {
            const claim = await api.post<ClaimResponse>(
              `/api/intake/review/${proposalId}/claim`,
              {},
            );
            token = claim.claim_token;
          } catch (claimErr) {
            if (isNotClaimable(claimErr)) {
              // Lost the race between list-load and click. Distinguish a
              // status that turned terminal from a live claim by another.
              const st = statusFromClaimError(claimErr);
              if (st && TERMINAL_STATUSES.has(st)) {
                roReason = `This proposal is ${terminalLabel(st)} — view only.`;
                // Same as the up-front terminal branch: another operator drove
                // it to a terminal state mid-session — prune the zombie row.
                setItems((prev) =>
                  prev.filter((p) => p.proposal_id !== proposalId),
                );
              } else {
                // Live claim held by a DIFFERENT reviewer — the row is NOT
                // terminal, it is legitimately still pending for them; keep it
                // in the list (it may free up when their lease expires).
                roReason = "Claimed by another reviewer — view only.";
              }
            } else {
              // A real claim failure (404/500/network). Detail already loaded;
              // surface a soft read-only notice rather than hiding the document.
              roReason = "Could not claim this proposal — view only.";
              logger.warn(
                "review claim failed (detail still shown)",
                {
                  component: "ReviewPage",
                  action: "openDetail",
                  metadata: { proposalId },
                },
                claimErr instanceof Error
                  ? claimErr
                  : new Error(String(claimErr)),
              );
            }
          }
        }

        setClaimToken(token);
        setReadOnlyReason(roReason);
        setDetail(d);
        setPreviewFailed(false);
        setShowOcr(false);
        setSearch("");
        setSearchResults([]);
        setFieldEdits({});
        // Lead with the create form ONLY when nothing matched; with a candidate
        // (even a weak one) the reviewer can still open it as a secondary option.
        setShowCreateForm((d.entity_candidates?.length ?? 0) === 0);
        setCreateForm(prefillFromExtractedFields(d.extracted_fields ?? {}));
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
        // Only the detail GET reaching here is a true failure (the claim has
        // its own catch above and never re-throws).
        setError("Could not open the document.");
        logger.error(
          "review detail load failed",
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
    setReadOnlyReason(null);
    setSelectedClient(null);
    setPractices([]);
    setSelectedPracticeId("");
    setSelectedGroup("other");
    setSelectedCategoryCode("");
    setFieldEdits({});
    setShowCreateForm(false);
    setCreateForm({ full_name: "" });
  }, [detail, claimToken]);

  const decide = useCallback(
    async (action: "approve" | "reject", clientOverride?: EntityCandidate) => {
      if (!detail || !claimToken) return;
      // A just-created client is passed explicitly: React state (selectedClient)
      // has not flushed yet, so the approve body must read the override.
      const approveClient = clientOverride ?? selectedClient;
      setBusy(detail.proposal_id);
      setError(null);
      setNotice(null);
      try {
        if (action === "approve") {
          const body: Record<string, unknown> = { claim_token: claimToken };
          if (approveClient) body.client_id = approveClient.client_id;
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
              `✓ Document filed to ${approveClient?.full_name ?? "client"}.`,
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
        setReadOnlyReason(null);
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
          setReadOnlyReason(null);
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

  // ── Create a NEW client from the document, then file the doc to it ───────
  // Reuses the canonical create path (`api.crm.createClient`, same as
  // clients/new) and the SAME approve flow — no parallel writer.
  const createAndApprove = useCallback(async () => {
    if (!detail || !claimToken) return;
    const name = (createForm.full_name ?? "").trim();
    if (name.length < 2) {
      setError(
        "Enter the client's name (at least 2 characters) before creating.",
      );
      return;
    }
    setCreateBusy(true);
    setError(null);
    setNotice(null);
    try {
      const user = await api.getProfile();
      if (!user?.email) {
        setError("Could not identify you — please re-login, then retry.");
        return;
      }
      // Drop empty optional fields so the backend keeps them NULL, not "".
      const payload: CreateClientParams = { full_name: name };
      const opt: (keyof CreateClientParams)[] = [
        "nationality",
        "passport_number",
        "passport_expiry",
        "date_of_birth",
        "phone",
        "email",
        "company_name",
      ];
      for (const k of opt) {
        const v = createForm[k];
        if (typeof v === "string" && v.trim())
          (payload as unknown as Record<string, unknown>)[k] = v.trim();
      }
      payload.client_type = createForm.client_type ?? "individual";
      payload.lead_source = "whatsapp";
      const created = await api.crm.createClient(payload, user.email);
      const newClient: EntityCandidate = {
        client_id: created.id,
        full_name: created.full_name,
        email: created.email ?? null,
        phone: created.phone ?? null,
        nationality: created.nationality ?? null,
        assigned_to: created.assigned_to ?? user.email,
      };
      setSelectedClient(newClient);
      setShowCreateForm(false);
      // File the document to the brand-new client via the existing approve path.
      await decide("approve", newClient);
    } catch (e) {
      setError("Could not create the client. Please retry.");
      logger.error(
        "review create-client failed",
        { component: "ReviewPage", action: "createAndApprove" },
        e instanceof Error ? e : new Error(String(e)),
      );
    } finally {
      setCreateBusy(false);
    }
  }, [detail, claimToken, createForm, decide]);

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
  // Bearer header, so a direct src 401s (the browser shows a connection-refused
  // error). Fetch the blob WITH the token, then preview via a local object URL.
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

  // ── Desk strip derived state ──────────────────────────────────────────
  const queueItems = useMemo(() => {
    const byFilter = items.filter((it) => {
      if (queueFilter === "all") return true;
      // Filter on the SAME computed tone the row itself paints, so a filter
      // can never select a row the row does not also paint copper.
      const { tone } = decisionMeta(it.decision, ownsRow(it.received_by));
      return queueFilter === "you" ? tone === "you" : tone === "ours";
    });
    const q = queueSearch.trim().toLowerCase();
    if (!q) return byFilter;
    return byFilter.filter((it) =>
      (it.doc_type || "document").toLowerCase().includes(q),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, queueFilter, queueSearch, viewerEmail, viewerIsAdmin]);

  // How many of the loaded rows are actually THIS viewer's to decide. On an
  // admin, whose queue is global, this is smaller than items.length.
  const yoursCount = useMemo(
    () => items.filter((it) => ownsRow(it.received_by)).length,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [items, viewerEmail, viewerIsAdmin],
  );

  // A computed sentence, and it disappears rather than claim something the
  // data cannot prove (fusion §6) — nothing is rendered while still loading.
  //
  // It counts what the VIEWER owns, not what loaded. The render found the
  // reason: with one row received by a different operator, the old sentence
  // said "3 documents are waiting for your decision" directly above a row
  // the page itself marked "Another operator". A masthead that claims
  // ownership the rows deny is the same defect as copper-from-status, one
  // typographic level up.
  const queueSubtitle = loading
    ? undefined
    : items.length === 0
      ? "Nothing is waiting for you."
      : yoursCount === 0
        ? `Nothing here is yours to decide — ${items.length} in the queue.`
        : yoursCount === items.length
          ? `${yoursCount} document${yoursCount === 1 ? "" : "s"} ${yoursCount === 1 ? "is" : "are"} waiting for your decision.`
          : `${yoursCount} of ${items.length} documents ${yoursCount === 1 ? "is" : "are"} waiting for your decision.`;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <Masthead
        eyebrow="Intake"
        title="Document review"
        subtitle={queueSubtitle}
        right={
          <button
            type="button"
            onClick={() => router.push("/dashboard")}
            className={cn(
              "rounded-md border border-[var(--bz-border)] px-3 py-1.5 text-[13px] text-[var(--tx-pure)]",
              "hover:bg-[var(--bz-card-hover)]",
              FOCUS,
            )}
          >
            ← Back
          </button>
        }
        className="mb-6"
      />

      {error && (
        // A load failure has no record to own — colour here reports a
        // FAILURE (urgency), never ownership, so this borrows
        // --state-warning via DeskNotice rather than copper.
        <DeskNotice tone="warn" role="alert" className="mb-4">
          {error}
        </DeskNotice>
      )}
      {notice && (
        <Notice tone="ok" role="status" className="mb-4">
          {notice}
        </Notice>
      )}

      {loading ? (
        <p className="text-[13px] text-[var(--tx-secondary)]">Loading…</p>
      ) : !error && items.length === 0 ? (
        <EmptyState>Nothing is waiting for you.</EmptyState>
      ) : (
        <>
          <DeskStrip
            count={queueItems.length}
            countLabel={`${queueItems.length} in the queue`}
            filters={
              // DeskStrip clips its filter group with overflow-hidden and lets
              // `right` keep its width, so at 390 the render showed ONLY "All"
              // — "Needs you" and "Matched" were cut off and unreachable, with
              // no way to scroll to them. The primitive is not this window's to
              // edit, so the scroller is page-local, inside the slot the
              // primitive hands us. Every filter stays reachable on a phone.
              <div className="flex min-w-0 items-center gap-1.5 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                <StatePill
                  tone="ink"
                  label="All"
                  pressed={queueFilter === "all"}
                  onClick={() => setQueueFilter("all")}
                />
                <StatePill
                  tone="you"
                  label="Needs you"
                  pressed={queueFilter === "you"}
                  onClick={() => setQueueFilter("you")}
                />
                <StatePill
                  tone="ours"
                  label="Matched"
                  pressed={queueFilter === "matched"}
                  onClick={() => setQueueFilter("matched")}
                />
              </div>
            }
            right={
              <input
                type="search"
                value={queueSearch}
                onChange={(e) => setQueueSearch(e.target.value)}
                placeholder="Search document type…"
                aria-label="Search review queue"
                className={cn(
                  // Narrower on a phone so the three filters keep their room;
                  // the placeholder still names what it searches.
                  "h-8 w-28 rounded border border-[var(--bz-border)] bg-transparent px-2 text-[12px] md:w-44",
                  "text-[var(--tx-pure)] placeholder:text-[var(--tx-secondary)]",
                  "focus:outline-none focus:border-[var(--bz-copper)]",
                  FOCUS,
                )}
              />
            }
          />
          {/* Below 768px the Operator and Received columns LEAVE the grid and
              their values move onto the row's secondary line — moved, not
              hidden, which is the concept's own 1360 collapse one breakpoint
              down. Measured before this cure: the five fixed columns summed
              past the viewport and /review scrolled sideways at 390
              (scrollWidth 742, clientWidth 390) on a dev server.

              Operator is 200px and Received 145px because at 170/130 the
              render truncated EVERY operator to "member@exam…" and the
              longest source+date to "whatsapp · 9/13/2…", while the 1.8fr
              document column sat half empty. The slack comes out of that
              column, which shrinks without losing a word.

              Status is 176px, not 130px, because the widest pill this page
              can paint is the WORD "Another operator" — the muted state a
              row takes when the viewer did not receive it. At 130px the
              render showed that pill lapping over the operator beside it.
              A column has to fit the longest word its own law can produce. */}
          <HairlineGrid
            cols="minmax(180px,1.4fr) 176px 200px 145px 92px"
            className="max-md:[--cols:minmax(0,1fr)_auto]"
          >
            <HairlineHead>
              <span>Document</span>
              <span className="max-md:hidden">Status</span>
              <span className="max-md:hidden">Operator</span>
              <span className="max-md:hidden">Received</span>
              <span className="sr-only">Actions</span>
            </HairlineHead>
            <HairlineBody>
              {queueItems.map((it) => {
                const candidate = it.entity_candidates?.[0];
                const { tone, label } = decisionMeta(
                  it.decision,
                  ownsRow(it.received_by),
                );
                const received = it.created_at
                  ? new Date(it.created_at).toLocaleDateString()
                  : "";
                const reviewLabel = busy === it.proposal_id ? "…" : "Review";
                return (
                  <HairlineRow
                    key={it.proposal_id}
                    // Below 768px BOTH of the grid's action slots stand down
                    // and the control moves onto the row's own secondary
                    // line. The reason is measured, not aesthetic: the
                    // reserved actions cell claimed 176px of a 390px row and
                    // pushed the grid to scrollWidth 396. One control is live
                    // at any width — hover button from md up, touch arrow
                    // from md up on a pointer that cannot hover, and the
                    // always-visible line button below md, which depends on
                    // no hover at all.
                    actions={
                      <button
                        type="button"
                        disabled={busy === it.proposal_id}
                        onClick={() => void openDetail(it.proposal_id)}
                        className={cn(
                          "min-h-8 rounded-md border border-[var(--bz-border)] px-3 text-[12px] font-[650] text-[var(--tx-pure)]",
                          "hover:bg-[var(--bz-card-hover)] disabled:opacity-60 max-md:hidden",
                          FOCUS,
                        )}
                      >
                        {reviewLabel}
                      </button>
                    }
                    touchAction={
                      <button
                        type="button"
                        disabled={busy === it.proposal_id}
                        onClick={() => void openDetail(it.proposal_id)}
                        aria-label={`Review ${it.doc_type || "document"}`}
                        className="grid h-11 w-11 place-items-center text-[var(--tx-secondary)] max-md:hidden"
                      >
                        →
                      </button>
                    }
                  >
                    <div className="min-w-0">
                      <CellStack
                        primary={it.doc_type || "document"}
                        secondary={
                          candidate
                            ? `Proposed client: ${candidate.full_name}`
                            : // "— needs a decision" was cut to "No client
                              // matched" because CellStack truncates its
                              // secondary and at 390 the render showed
                              // "No client matched — needs a d…". The dropped
                              // half is not lost: the copper pill beside it
                              // already says "Needs you", which is the WORD
                              // the colour law requires. This line carries the
                              // REASON, the pill carries the call.
                              "No client matched"
                        }
                      />
                      {/* The dropped columns, relocated for a phone. Exactly
                          one copy of each value is in the accessibility tree
                          at any width. */}
                      <span className="mt-1 flex flex-wrap items-center gap-2 md:hidden">
                        <StatePill tone={tone} label={label} />
                        <span className="text-[11px] text-[var(--tx-secondary)]">
                          Operator: {formatOperator(it.received_by)}
                        </span>
                        <span
                          className="text-[11px] text-[var(--tx-secondary)]"
                          style={TABULAR}
                        >
                          {it.source}
                          {received ? ` · ${received}` : ""}
                        </span>
                        {/* The phone's control. Always visible, 44px, named
                            by the document it opens so a screen reader can
                            tell two rows apart. */}
                        <button
                          type="button"
                          disabled={busy === it.proposal_id}
                          onClick={() => void openDetail(it.proposal_id)}
                          aria-label={`Review ${it.doc_type || "document"}`}
                          className={cn(
                            "min-h-11 rounded-md border border-[var(--bz-border)] px-3 text-[12px] font-[650] text-[var(--tx-pure)]",
                            "disabled:opacity-60",
                            FOCUS,
                          )}
                        >
                          {reviewLabel}
                        </button>
                      </span>
                    </div>
                    <span className="max-md:hidden">
                      <StatePill tone={tone} label={label} />
                    </span>
                    {/* No "Operator:" prefix here — the column header two
                        rows up already says OPERATOR, and carrying the word
                        as well cost ~70px and truncated every address to
                        "member@example.t…" at 1440. The phone copy KEEPS the
                        prefix, because on the secondary line the values run
                        together with no header to name them. */}
                    <span className="truncate text-[12px] text-[var(--tx-secondary)] max-md:hidden">
                      {formatOperator(it.received_by)}
                    </span>
                    <span
                      className="truncate text-[12px] text-[var(--tx-secondary)] max-md:hidden"
                      style={TABULAR}
                    >
                      {it.source}
                      {received ? ` · ${received}` : ""}
                    </span>
                  </HairlineRow>
                );
              })}
            </HairlineBody>
          </HairlineGrid>
          {queueItems.length === 0 && (
            <EmptyState>No document matches this filter.</EmptyState>
          )}
        </>
      )}

      {detail && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center"
          style={{ background: "var(--surface-overlay)" }}
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
                {/* Ownership AND actionability: a terminal status or a 409
                    claim conflict makes the detail read-only for ANY
                    reason, and copper must never coexist with "view only" —
                    so a read-only detail always renders muted with the
                    reason word, and only a claimable, viewer-owned detail
                    can render copper. */}
                <StatePill
                  {...(!claimToken
                    ? {
                        tone: "wait" as PillTone,
                        label: readOnlyReason ?? "View only",
                      }
                    : decisionMeta(
                        detail.decision,
                        ownsRow(detail.received_by),
                      ))}
                />
              </h2>
              <button
                type="button"
                onClick={() => void closeDetail()}
                style={{ color: "var(--bz-text-3)" }}
              >
                ✕
              </button>
            </div>

            {readOnlyReason && (
              <Notice tone="wait" role="status" className="mb-3">
                {readOnlyReason}
              </Notice>
            )}

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

                {/* Create-new-client lead — primary action for NO_MATCH.
                    "Help, don't dump the decision": when nothing matched we lead
                    with a prefilled create form instead of an error. */}
                {(showCreateForm ||
                  (detail.entity_candidates?.length ?? 0) === 0) && (
                  <div
                    className="rounded-md border p-3"
                    style={{
                      borderColor: "var(--bz-accent)",
                      background: "var(--bz-surface)",
                    }}
                  >
                    <h3
                      className="mb-1 text-sm font-semibold"
                      style={{ color: "var(--bz-text-1)" }}
                    >
                      ➕ New client
                    </h3>
                    <p
                      className="mb-2 text-xs"
                      style={{ color: "var(--bz-text-2)" }}
                    >
                      No existing client matched — is this a new client? Create
                      one from the document data:
                    </p>
                    <div className="space-y-1.5">
                      {(
                        [
                          ["full_name", "Name"],
                          ["nationality", "Nationality"],
                          ["passport_number", "Passport / KITAS no."],
                          ["date_of_birth", "Date of birth"],
                          ["passport_expiry", "Expiry"],
                          ["phone", "Phone"],
                          ["email", "Email"],
                        ] as [keyof CreateClientParams, string][]
                      ).map(([key, label]) => (
                        <div key={key} className="flex items-center gap-2">
                          <span
                            className="w-36 shrink-0 truncate text-xs"
                            style={{ color: "var(--bz-text-3)" }}
                          >
                            {label}
                          </span>
                          <input
                            className="w-full rounded border px-2 py-1 text-xs"
                            style={{
                              borderColor: "var(--bz-border)",
                              background: "var(--bz-surface)",
                              color: "var(--bz-text-1)",
                            }}
                            placeholder={
                              key === "full_name" ? "required" : "optional"
                            }
                            value={(createForm[key] as string) ?? ""}
                            onChange={(e) =>
                              setCreateForm((prev) => ({
                                ...prev,
                                [key]: e.target.value,
                              }))
                            }
                          />
                        </div>
                      ))}
                    </div>
                    <button
                      type="button"
                      disabled={
                        createBusy ||
                        busy === detail.proposal_id ||
                        !claimToken ||
                        (createForm.full_name ?? "").trim().length < 2
                      }
                      onClick={() => void createAndApprove()}
                      // Copper is NEVER a fill (globals.css's own comment on
                      // --bz-accent says so) — the outlined treatment already
                      // used on this page's Reject/Back buttons, recoloured
                      // to copper instead of a solid background.
                      className={cn(
                        "mt-3 w-full rounded-md border border-[var(--bz-copper)] px-4 py-2 text-sm font-medium text-[var(--bz-copper-text)]",
                        "hover:bg-[var(--bz-card-hover)] disabled:opacity-60",
                        FOCUS,
                      )}
                    >
                      {createBusy
                        ? "Creating…"
                        : "➕ Create new client + file this document"}
                    </button>
                  </div>
                )}

                {/* Candidate clients */}
                <div>
                  <h3
                    className="mb-1 text-sm font-medium"
                    style={{ color: "var(--bz-text-1)" }}
                  >
                    {(detail.entity_candidates?.length ?? 0) === 0
                      ? "Or attach to an existing client"
                      : "Client"}
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
                                ? "var(--bz-accent)"
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

                  {/* Secondary "create new" affordance when candidates exist
                      (the homonym case: "or create new"). */}
                  {(detail.entity_candidates?.length ?? 0) > 0 &&
                    !showCreateForm && (
                      <button
                        type="button"
                        onClick={() => setShowCreateForm(true)}
                        className="mt-2 text-xs underline"
                        style={{ color: "var(--bz-accent)" }}
                      >
                        ➕ None of these — create a new client
                      </button>
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
                      ? "var(--state-success)"
                      : "var(--state-warning)",
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
                    disabled={
                      busy === detail.proposal_id ||
                      !claimToken ||
                      !selectedClient
                    }
                    onClick={() => void decide("approve")}
                    className="flex-1 rounded-md px-4 py-2 text-sm font-medium text-white"
                    style={{
                      background: "var(--state-success)",
                      opacity:
                        busy === detail.proposal_id ||
                        !claimToken ||
                        !selectedClient
                          ? 0.5
                          : 1,
                    }}
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    disabled={busy === detail.proposal_id || !claimToken}
                    onClick={() => void decide("reject")}
                    className={cn(
                      "flex-1 rounded-md border border-[var(--bz-border)] px-4 py-2 text-sm font-medium text-[var(--tx-pure)]",
                      "hover:bg-[var(--bz-card-hover)] disabled:opacity-60",
                      FOCUS,
                    )}
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
