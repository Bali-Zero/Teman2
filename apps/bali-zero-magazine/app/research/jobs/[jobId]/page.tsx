import Link from "next/link";
import { notFound } from "next/navigation";

import {
  MagazineShell,
  WorkspaceAccessRequired,
} from "@/components/magazine-shell";
import { requireMagazineViewer } from "@/lib/server/magazine-read-model";
import { publicResearchJob } from "@/lib/server/research-http";
import { createResearchRepository } from "@/lib/server/research-repository";
import { getMagazineBindings } from "@/lib/server/runtime-bindings";

export const dynamic = "force-dynamic";

function displaySelection(values: readonly string[]): string {
  return values.length > 0 ? values.join(" · ") : "None selected";
}

export default async function ResearchJobPage({
  params,
}: Readonly<{ params: Promise<{ jobId: string }> }>) {
  const viewer = await requireMagazineViewer();
  if (viewer === null)
    return (
      <MagazineShell eyebrow="Private workspace">
        <WorkspaceAccessRequired />
      </MagazineShell>
    );
  const jobId = (await params).jobId;
  if (!/^research-job-[A-Za-z0-9-]{16,80}$/.test(jobId)) notFound();
  const db = getMagazineBindings().DB;
  if (db === undefined) throw new Error("Research database is unavailable");
  const storedJob = await createResearchRepository(db).getJob(jobId);
  if (storedJob === null) notFound();
  const job = publicResearchJob(storedJob);
  const isNotebookInsight = job.mode === "notebook_insight";
  return (
    <MagazineShell eyebrow="Research finding">
      <article className="research-finding">
        <Link className="research-back" href="/research">
          Back to Research
        </Link>
        <header>
          <p className="section-label">
            {job.mode.replace("_", " ")} · {job.status}
          </p>
          <h1>{job.result?.summary ?? "Research in progress"}</h1>
          <p>
            Created{" "}
            <time dateTime={job.created_at}>
              {new Date(job.created_at).toLocaleString("en-GB", {
                dateStyle: "long",
                timeStyle: "short",
              })}
            </time>
          </p>
        </header>
        <section
          className="research-brief"
          aria-labelledby="research-brief-heading"
        >
          <div>
            <p className="section-label">Controlled brief</p>
            <h2 id="research-brief-heading">Closed query</h2>
            <p>
              Only public catalog IDs and fixed filters cross the worker
              boundary.
            </p>
          </div>
          <dl>
            <div>
              <dt>Mode</dt>
              <dd>{job.request.mode.replace("_", " ")}</dd>
            </div>
            <div>
              <dt>Template</dt>
              <dd>{job.request.template ?? "structured search"}</dd>
            </div>
            <div>
              <dt>Topics</dt>
              <dd>{displaySelection(job.request.topic_ids)}</dd>
            </div>
            <div>
              <dt>Entities</dt>
              <dd>{displaySelection(job.request.entity_ids)}</dd>
            </div>
            <div>
              <dt>Index tokens</dt>
              <dd>{displaySelection(job.request.index_tokens)}</dd>
            </div>
            <div>
              <dt>Scope</dt>
              <dd>{displaySelection(job.request.facets.domains)}</dd>
            </div>
            <div>
              <dt>Sources</dt>
              <dd>{displaySelection(job.request.facets.source_system_ids)}</dd>
            </div>
            <div>
              <dt>Evidence</dt>
              <dd>{displaySelection(job.request.facets.evidence_types)}</dd>
            </div>
            <div>
              <dt>Confidence</dt>
              <dd>{displaySelection(job.request.facets.confidence)}</dd>
            </div>
            <div>
              <dt>Lifecycle</dt>
              <dd>{displaySelection(job.request.facets.lifecycle_states)}</dd>
            </div>
            <div>
              <dt>Languages</dt>
              <dd>{displaySelection(job.request.facets.languages)}</dd>
            </div>
          </dl>
        </section>
        <aside
          className={`research-uncertainty${isNotebookInsight ? " research-uncertainty--notebook" : ""}`}
        >
          <p className="section-label">
            {isNotebookInsight ? "Notebook Insight" : "Reading note"}
          </p>
          <h2>
            {isNotebookInsight
              ? "Synthesis, not verification"
              : "Evidence first, uncertainty visible"}
          </h2>
          <p>
            {isNotebookInsight
              ? "This DLP-passed synthesis is displayed separately from the published evidence corpus. It cannot change verification or publication status."
              : "Fact, number and analysis labels remain visible. Missing evidence becomes a safe failure, never an unsupported answer."}
          </p>
        </aside>
        {job.result?.status === "failed" && (
          <section className="research-failure">
            <p className="section-label">Safe failure receipt</p>
            <h2>Finding unavailable</h2>
            <p>Code: {job.result.failure?.code.replaceAll("_", " ")}</p>
          </section>
        )}
        {job.result?.status === "completed" && (
          <section className="research-claims">
            <p className="section-label">
              {isNotebookInsight
                ? "Notebook Insight synthesis"
                : "Evidence-bound findings"}
            </p>
            <ol>
              {job.result.claims.map((claim) => (
                <li key={claim.claim_id}>
                  <span>{claim.kind}</span>
                  <h2>{claim.text}</h2>
                  {claim.kind === "numeric" && (
                    <p className="research-number">
                      {claim.numeric_value} {claim.numeric_unit} · as of{" "}
                      {claim.as_of}
                    </p>
                  )}
                  <ul>
                    {claim.evidence.map((evidence) => (
                      <li key={evidence.evidence_id}>
                        <strong>{evidence.publisher}</strong>
                        <p>{evidence.citation}</p>
                        {evidence.canonical_url && (
                          <a href={evidence.canonical_url} rel="noreferrer">
                            Open evidence
                          </a>
                        )}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          </section>
        )}
        {job.result === null && job.status !== "cancelled" && (
          <section className="research-pending">
            <p>
              The Pro worker will claim this closed brief. This page stores no
              free-form prompt or raw NotebookLM output.
            </p>
          </section>
        )}
        {job.result === null && job.status === "cancelled" && (
          <section className="research-failure">
            <p className="section-label">Cancelled</p>
            <h2>Research stopped</h2>
            <p>This closed brief will not be claimed or completed.</p>
          </section>
        )}
      </article>
    </MagazineShell>
  );
}
