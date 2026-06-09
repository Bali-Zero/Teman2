"use client";

/**
 * Document review page (INTAKE FASE 5A).
 *
 * The login gate (workspace/GateScreen.tsx) blocks entry when documents await
 * review but, until now, had no page to send the reviewer to (the button
 * deep-linked to /process — a loop). This page consumes the existing backend
 * /api/intake/review/* endpoints so a team member can claim, inspect (OCR +
 * proposed client) and approve/reject each pending document, clearing the gate.
 *
 * Auth + transport reuse the shared `api` client (httpOnly cookie + bearer).
 * RBAC is server-enforced: a non-admin only sees proposals whose candidate
 * client is assigned to them; NO_MATCH/AMBIGUOUS are admin-only.
 *
 * NOTE: approvals are dry-run while INTAKE_WRITER_ENABLED is OFF (backend
 * default) — the page surfaces that explicitly so a reviewer is never misled
 * into thinking a commit hit the CRM.
 */

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

interface EntityCandidate {
  client_id: number;
  full_name: string;
  assigned_to?: string | null;
}

interface ProposalSummary {
  proposal_id: number;
  doc_type: string;
  decision: string;
  source: string;
  status: string;
  entity_candidates: EntityCandidate[];
  extracted_fields: Record<string, unknown>;
  created_at: string;
}

interface OcrPage {
  page_number: number;
  text: string;
}

interface ProposalDetail extends ProposalSummary {
  ocr_pages?: OcrPage[];
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

export default function ReviewPage() {
  const router = useRouter();
  const [items, setItems] = useState<ProposalSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [detail, setDetail] = useState<ProposalDetail | null>(null);
  const [claimToken, setClaimToken] = useState<string | null>(null);

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
      setError("Impossibile caricare la coda di revisione.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const openDetail = useCallback(async (proposalId: number) => {
    setBusy(proposalId);
    setError(null);
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
    } catch (e) {
      const msg =
        e instanceof Error && /409/.test(e.message)
          ? "Documento già preso in carico da un altro revisore."
          : "Impossibile aprire il documento.";
      setError(msg);
      logger.error(
        "review claim/detail failed",
        { component: "ReviewPage", action: "openDetail" },
        e instanceof Error ? e : new Error(String(e)),
      );
    } finally {
      setBusy(null);
    }
  }, []);

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
  }, [detail, claimToken]);

  const decide = useCallback(
    async (action: "approve" | "reject") => {
      if (!detail || !claimToken) return;
      setBusy(detail.proposal_id);
      setError(null);
      try {
        if (action === "approve") {
          const res = await api.post<ApproveResponse>(
            `/api/intake/review/${detail.proposal_id}/approve`,
            { claim_token: claimToken },
          );
          if (res.dry_run) {
            setError(
              "✓ Approvato in modalità prova (dry-run): il documento NON è ancora scritto nel CRM (INTAKE_WRITER_ENABLED spento).",
            );
          }
        } else {
          await api.post(`/api/intake/review/${detail.proposal_id}/reject`, {
            claim_token: claimToken,
          });
        }
        setDetail(null);
        setClaimToken(null);
        await loadQueue();
      } catch (e) {
        setError(`Azione "${action}" fallita. Riprova.`);
        logger.error(
          "review decide failed",
          { component: "ReviewPage", action },
          e instanceof Error ? e : new Error(String(e)),
        );
      } finally {
        setBusy(null);
      }
    },
    [detail, claimToken, loadQueue],
  );

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1
          className="text-2xl font-semibold"
          style={{ color: "var(--bz-text-1)" }}
        >
          Document review
        </h1>
        <button
          type="button"
          onClick={() => router.push("/process")}
          className="rounded-md border px-3 py-1.5 text-sm"
          style={{ borderColor: "var(--bz-border)", color: "var(--bz-text-2)" }}
        >
          ← Back
        </button>
      </div>

      {error && (
        <div
          className="mb-4 rounded-md border px-4 py-2 text-sm"
          style={{ borderColor: "var(--bz-border)", color: "var(--bz-text-1)" }}
        >
          {error}
        </div>
      )}

      {loading ? (
        <p style={{ color: "var(--bz-text-3)" }}>Caricamento…</p>
      ) : items.length === 0 ? (
        <p style={{ color: "var(--bz-success, #2e9e6b)" }}>
          ✓ Nessun documento da revisionare.
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
                        {it.doc_type || "documento"}
                      </span>
                      <DecisionBadge decision={it.decision} />
                    </div>
                    <p
                      className="mt-1 text-sm"
                      style={{ color: "var(--bz-text-2)" }}
                    >
                      {candidate
                        ? `Cliente proposto: ${candidate.full_name}`
                        : "Nessun cliente trovato — richiede decisione"}
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
                    {busy === it.proposal_id ? "…" : "Apri"}
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
            className="max-h-[85vh] w-full max-w-2xl overflow-auto rounded-xl border p-5"
            style={CARD}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <h2
                className="text-lg font-medium"
                style={{ color: "var(--bz-text-1)" }}
              >
                {detail.doc_type || "documento"}{" "}
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

            <p className="mb-3 text-sm" style={{ color: "var(--bz-text-2)" }}>
              {detail.entity_candidates?.[0]
                ? `Cliente proposto: ${detail.entity_candidates[0].full_name}`
                : "Nessun cliente trovato — richiede decisione manuale."}
            </p>

            {detail.ocr_pages && detail.ocr_pages.length > 0 && (
              <div
                className="mb-4 max-h-64 overflow-auto rounded-md border p-3 text-xs whitespace-pre-wrap"
                style={{
                  borderColor: "var(--bz-border)",
                  color: "var(--bz-text-2)",
                  background: "var(--bz-surface)",
                }}
              >
                {detail.ocr_pages
                  .map((p) => `— pagina ${p.page_number} —\n${p.text}`)
                  .join("\n\n")}
              </div>
            )}

            <div className="flex gap-3">
              <button
                type="button"
                disabled={busy === detail.proposal_id}
                onClick={() => void decide("approve")}
                className="flex-1 rounded-md px-4 py-2 text-sm font-medium text-white"
                style={{
                  background: "var(--bz-success, #2e9e6b)",
                  opacity: busy === detail.proposal_id ? 0.6 : 1,
                }}
              >
                Approva
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
                Rifiuta
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
