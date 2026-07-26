"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

import type {
  ResearchCatalog,
  ResearchEvidenceV1,
  ResearchJobView,
  ResearchMode,
  ResearchResultV1,
} from "@/lib/server/research-repository";

type PublicResult = Omit<
  ResearchResultV1,
  "request_hash" | "claim_token" | "fencing_token"
>;
type PublicJob = Omit<
  ResearchJobView,
  | "actor_key"
  | "claim_token"
  | "fencing_token"
  | "lease_deadline"
  | "request_hash"
  | "result"
> &
  Readonly<{ result: PublicResult | null }>;

type Props = Readonly<{
  catalog: ResearchCatalog;
  jobs: readonly PublicJob[];
  evidence: readonly ResearchEvidenceV1[];
  canCreate: boolean;
}>;

function selected(data: FormData, name: string): string[] {
  return data
    .getAll(name)
    .filter((value): value is string => typeof value === "string");
}

function modeLabel(mode: ResearchMode): string {
  return {
    search: "Search",
    compare: "Compare",
    timeline: "Timeline",
    notebook_insight: "Notebook Insight",
  }[mode];
}

export function ResearchWorkbench({
  catalog,
  jobs,
  evidence,
  canCreate,
}: Props) {
  const [mode, setMode] = useState<ResearchMode>("search");
  const [source, setSource] = useState("regulatory-watcher");
  const [status, setStatus] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const recentJobs = useMemo(() => jobs.slice(0, 12), [jobs]);
  const notebookRestricted = mode === "notebook_insight";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canCreate || submitting) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const topics = selected(data, "topics");
    const entities = selected(data, "entities");
    const tokens = notebookRestricted ? [] : selected(data, "tokens");
    setSubmitting(true);
    setStatus("Queuing research job…");
    try {
      const response = await fetch("/api/research/jobs", {
        method: "POST",
        headers: { "content-type": "application/json", "x-magazine-csrf": "1" },
        body: JSON.stringify({
          idempotency_key: `research-ui-${crypto.randomUUID()}`,
          request: {
            schema_version: "research-request.v1",
            mode,
            topic_ids: topics,
            entity_ids: entities,
            index_tokens: tokens,
            template: notebookRestricted ? data.get("template") : null,
            facets: {
              domains: notebookRestricted ? [] : [data.get("domain")],
              source_system_ids: [notebookRestricted ? "notebooklm" : source],
              evidence_types: [data.get("evidence_type")],
              confidence: notebookRestricted ? [] : ["normal"],
              lifecycle_states: notebookRestricted ? [] : ["published"],
              languages: notebookRestricted ? [] : [data.get("language")],
            },
          },
        }),
      });
      const payload = (await response.json()) as {
        job?: { job_id: string };
        error?: string;
      };
      if (!response.ok || payload.job === undefined) {
        setStatus(
          payload.error === "invalid_request"
            ? "Select only registered subjects and a valid mode."
            : "The job could not be queued.",
        );
        return;
      }
      setStatus(
        `Queued ${payload.job.job_id}. Refresh to follow its progress.`,
      );
      form.reset();
    } catch {
      setStatus("The research queue is temporarily unavailable.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="research-room">
      <header className="research-header">
        <p className="section-label">Internal intelligence desk</p>
        <h1>Research room</h1>
        <p>
          Explore published evidence or send a closed, public-intelligence brief
          to the Pro research worker. Client and free-form research stays
          outside this room.
        </p>
      </header>

      <section className="research-grid" aria-label="Research workspace">
        <form className="research-form" onSubmit={submit}>
          <div className="research-section-heading">
            <span>01</span>
            <div>
              <p className="section-label">Controlled brief</p>
              <h2>Build a research job</h2>
            </div>
          </div>
          <label>
            Mode
            <select
              name="mode"
              value={mode}
              onChange={(event) => setMode(event.target.value as ResearchMode)}
              disabled={!canCreate}
            >
              <option value="search">Search</option>
              <option value="compare">Compare</option>
              <option value="timeline">Timeline</option>
              <option value="notebook_insight">Notebook Insight</option>
            </select>
          </label>
          <div className="research-form-pair">
            <label>
              Registered topics
              <select
                name="topics"
                multiple
                size={Math.min(5, catalog.topics.length)}
                disabled={!canCreate}
              >
                {catalog.topics.map((topic) => (
                  <option key={topic.id} value={topic.id}>
                    {topic.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Registered entities
              <select
                name="entities"
                multiple
                size={Math.min(5, catalog.entities.length)}
                disabled={!canCreate}
              >
                {catalog.entities.map((entity) => (
                  <option key={entity.id} value={entity.id}>
                    {entity.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {mode === "notebook_insight" ? (
            <>
              <label>
                Notebook template
                <select
                  name="template"
                  defaultValue="explain"
                  disabled={!canCreate}
                >
                  <option value="explain">Explain</option>
                  <option value="compare">Compare</option>
                  <option value="timeline">Timeline</option>
                </select>
              </label>
              <p className="research-access-note">
                Notebook Insight accepts only NotebookLM and evidence type
                filters. Domain, confidence, lifecycle and language filters are
                unavailable because the cited response cannot prove those
                facets.
              </p>
            </>
          ) : (
            <label>
              Sanitized index tokens
              <select
                name="tokens"
                multiple
                size={Math.min(4, catalog.index_tokens.length)}
                disabled={!canCreate}
              >
                {catalog.index_tokens.map((token) => (
                  <option key={token} value={token}>
                    {token.replace("token:", "").replaceAll("-", " ")}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="research-form-pair research-form-pair--compact">
            {!notebookRestricted && (
              <label>
                Domain
                <select
                  name="domain"
                  defaultValue="compliance"
                  disabled={!canCreate}
                >
                  <option value="immigration">Immigration</option>
                  <option value="company">Company</option>
                  <option value="tax">Tax</option>
                  <option value="property">Property</option>
                  <option value="compliance">Compliance</option>
                </select>
              </label>
            )}
            <label>
              Source
              <select
                name="source"
                value={mode === "notebook_insight" ? "notebooklm" : source}
                onChange={(event) => setSource(event.target.value)}
                disabled={!canCreate || mode === "notebook_insight"}
              >
                <option value="intel-lake">Intel Lake</option>
                <option value="mata-garuda">Mata Garuda</option>
                <option value="regulatory-watcher">Regulatory Watcher</option>
                <option value="notebooklm">NotebookLM</option>
              </select>
            </label>
            <label>
              Evidence
              <select
                name="evidence_type"
                defaultValue="official"
                disabled={!canCreate}
              >
                <option value="official">Official</option>
                <option value="journalism">Journalism</option>
                <option value="research">Research</option>
                <option value="dataset">Dataset</option>
              </select>
            </label>
            {!notebookRestricted && (
              <label>
                Language
                <select name="language" defaultValue="en" disabled={!canCreate}>
                  <option value="en">English</option>
                  <option value="id">Indonesian</option>
                </select>
              </label>
            )}
          </div>
          <button type="submit" disabled={!canCreate || submitting}>
            {submitting ? "Queuing…" : "Queue research"}
          </button>
          {!canCreate && (
            <p className="research-access-note">
              Reader access: published evidence and completed findings are
              available below. Only Analysts can queue jobs.
            </p>
          )}
          {status && (
            <p className="research-feedback" role="status">
              {status}
            </p>
          )}
        </form>

        <aside className="research-guardrails" aria-label="Research guardrails">
          <p className="section-label">Boundary</p>
          <h2>Public intelligence only</h2>
          <dl>
            <div>
              <dt>Input</dt>
              <dd>Registered topic, entity, token and facet IDs</dd>
            </div>
            <div>
              <dt>Notebook</dt>
              <dd>Closed explain, compare or timeline template</dd>
            </div>
            <div>
              <dt>Output</dt>
              <dd>DLP-passed claims with evidence on every fact and number</dd>
            </div>
            <div>
              <dt>Excluded</dt>
              <dd>Client data, free-form prompts and notebook identifiers</dd>
            </div>
          </dl>
        </aside>
      </section>

      <section className="research-ledger">
        <div className="research-section-heading">
          <span>02</span>
          <div>
            <p className="section-label">Queue ledger</p>
            <h2>Recent research jobs</h2>
          </div>
        </div>
        {recentJobs.length === 0 ? (
          <p className="research-empty">No research jobs have been queued.</p>
        ) : (
          <ol className="research-job-list">
            {recentJobs.map((job) => (
              <li key={job.job_id}>
                <div>
                  <span
                    className={`research-status research-status--${job.status}`}
                  >
                    {job.status}
                  </span>
                  <strong>{modeLabel(job.mode)}</strong>
                </div>
                <time dateTime={job.created_at}>
                  {new Date(job.created_at).toLocaleString("en-GB", {
                    dateStyle: "medium",
                    timeStyle: "short",
                  })}
                </time>
                <Link href={`/research/jobs/${job.job_id}`}>Open finding</Link>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="research-evidence">
        <div className="research-section-heading">
          <span>03</span>
          <div>
            <p className="section-label">Published corpus</p>
            <h2>Evidence shelf</h2>
          </div>
        </div>
        {evidence.length === 0 ? (
          <p className="research-empty">
            Published evidence will appear here after the first verified
            edition.
          </p>
        ) : (
          <ol>
            {evidence.map((item) => (
              <li key={item.evidence_id}>
                <span>{item.source_type}</span>
                <strong>{item.publisher}</strong>
                <p>{item.citation}</p>
                {item.canonical_url && (
                  <a href={item.canonical_url} rel="noreferrer">
                    Open primary source
                  </a>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
