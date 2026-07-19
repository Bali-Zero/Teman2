"use client";

import { useState } from "react";

import type { OperationIntentKind } from "@/lib/server/operations-repository";

type Health = Readonly<{
  observed_at: string;
  collectors: readonly Readonly<{
    collector_id: string;
    health: string;
    latest_success_at: string | null;
  }>[];
  edition: Readonly<{
    current_edition_id: string | null;
    current_revision: number;
  }>;
  breaking: Readonly<{ queued_count: number; active_revision: number }>;
  research_queue: Readonly<Record<string, number>>;
  failed_intents: Readonly<Record<string, number>>;
  audit_anchor: Readonly<{ stream_seq: number; updated_at: string | null }>;
}>;

type Intent = Readonly<{
  intent_id: string;
  intent_kind: OperationIntentKind;
  target_id: string;
  status: string;
  reason_code: string;
  created_at: string;
}>;

const reasonByKind = {
  rerun_collector: "collector_recovery",
  rebuild_edition: "edition_recovery",
  quarantine_story: "content_safety",
  release_story: "gates_reverified",
  refresh_research_job: "research_recovery",
} as const;

export function OperationsBoard({
  health,
  intents,
  canCreate,
}: Readonly<{
  health: Health;
  intents: readonly Intent[];
  canCreate: boolean;
}>) {
  const [kind, setKind] = useState<OperationIntentKind>("rerun_collector");
  const [targetId, setTargetId] = useState("");
  const [message, setMessage] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const numeric = 0;
    const params =
      kind === "rerun_collector"
        ? { collector_id: "regulatory-watcher", failed_run_id: targetId }
        : kind === "rebuild_edition"
          ? { edition_id: targetId, expected_revision: numeric }
          : kind === "refresh_research_job"
            ? { research_job_id: targetId }
            : {
                story_id: targetId,
                story_version: 1,
                expected_visibility_seq: numeric,
              };
    const response = await fetch("/api/operations/intents", {
      method: "POST",
      headers: { "content-type": "application/json", "x-magazine-csrf": "1" },
      body: JSON.stringify({
        schema_version: "ops-intent-request.v1",
        intent_kind: kind,
        idempotency_key: `ops-ui-${kind}-${crypto.randomUUID()}`,
        reason_code: reasonByKind[kind],
        expires_at: new Date(Date.now() + 3_600_000).toISOString(),
        params,
      }),
    });
    setMessage(response.ok ? "Intent queued." : "Intent rejected.");
  }

  return (
    <div className="research-room operations-room">
      <section className="research-hero">
        <p className="section-label">Read-only control plane</p>
        <h1>Operations</h1>
        <p>
          Health is visible to every workspace role. Only a current Operator can
          queue a typed intent; Sites never runs the effect.
        </p>
      </section>
      <section className="research-results" aria-label="Operations health">
        <article>
          <h2>Collector freshness</h2>
          <p>{health.collectors.length} collectors observed</p>
        </article>
        <article>
          <h2>Edition state</h2>
          <p>
            {health.edition.current_edition_id ?? "No current edition"} ·
            revision {health.edition.current_revision}
          </p>
        </article>
        <article>
          <h2>Breaking queue</h2>
          <p>{health.breaking.queued_count} published entries</p>
        </article>
        <article>
          <h2>Research queue</h2>
          <p>
            {health.research_queue.queued ?? 0} queued ·{" "}
            {health.research_queue.claimed ?? 0} claimed
          </p>
        </article>
        <article>
          <h2>Failed intents</h2>
          <p>
            {health.failed_intents.failed ?? 0} failed ·{" "}
            {health.failed_intents.outcome_unknown ?? 0} outcome unknown
          </p>
        </article>
        <article>
          <h2>Audit anchor freshness</h2>
          <p>
            Sequence {health.audit_anchor.stream_seq} ·{" "}
            {health.audit_anchor.updated_at ?? "No anchor"}
          </p>
        </article>
      </section>
      {canCreate ? (
        <form className="research-composer" onSubmit={submit}>
          <h2>Queue a typed intent</h2>
          <label>
            Intent kind
            <select
              value={kind}
              onChange={(event) =>
                setKind(event.target.value as OperationIntentKind)
              }
            >
              {Object.keys(reasonByKind).map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Stable target ID
            <input
              required
              value={targetId}
              onChange={(event) => setTargetId(event.target.value)}
              pattern="[a-z][a-z0-9-]{15,95}"
            />
          </label>
          <button type="submit">Queue intent</button>
          <p aria-live="polite">{message}</p>
        </form>
      ) : null}
      <section
        className="research-results"
        aria-label="Recent operation intents"
      >
        <h2>Recent intents</h2>
        {intents.map((intent) => (
          <article key={intent.intent_id}>
            <strong>{intent.intent_kind}</strong>
            <p>
              {intent.target_id} · {intent.status} · {intent.reason_code}
            </p>
          </article>
        ))}
      </section>
    </div>
  );
}
