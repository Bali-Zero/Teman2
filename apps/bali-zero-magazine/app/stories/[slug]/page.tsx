import { notFound } from "next/navigation";

import { EvidenceDrawer } from "@/components/evidence-drawer";
import {
  MagazineShell,
  WorkspaceAccessRequired,
} from "@/components/magazine-shell";
import {
  readStoryDetail,
  requireMagazineViewer,
} from "@/lib/server/magazine-read-model";

export const dynamic = "force-dynamic";

type StoryPageProps = Readonly<{
  params: Promise<{ slug: string }>;
}>;

function readableTimestamp(value: string | null): string {
  if (value === null) return "Not recorded";
  return `${new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Makassar",
  }).format(new Date(value))} WITA`;
}

function titleCase(value: string): string {
  return value
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export default async function StoryPage({ params }: StoryPageProps) {
  const viewer = await requireMagazineViewer();
  if (viewer === null) {
    return (
      <MagazineShell eyebrow="Private workspace">
        <WorkspaceAccessRequired />
      </MagazineShell>
    );
  }

  const { slug } = await params;
  const detail = await readStoryDetail(slug);
  if (detail === null) notFound();

  return (
    <MagazineShell
      eyebrow={`${detail.story.domain.replaceAll("-", " ")} dossier`}
    >
      <article className="story-page">
        <header className="story-page-header">
          <p className="section-label">Verified dossier</p>
          <h1>{detail.story.title}</h1>
          <p className="story-page-deck">{detail.story.deck}</p>
          <div className="story-state-line">
            <span>{detail.currentVisibility}</span>
            <span>{detail.story.confidence} confidence</span>
            <time dateTime={detail.updatedAt}>
              Updated{" "}
              {new Date(detail.updatedAt).toLocaleDateString("en-GB", {
                day: "numeric",
                month: "long",
                year: "numeric",
                timeZone: "UTC",
              })}
            </time>
          </div>
          <dl className="story-metadata" aria-label="Publication metadata">
            <div>
              <dt>Section</dt>
              <dd>{titleCase(detail.section)}</dd>
            </div>
            <div>
              <dt>Severity</dt>
              <dd>{titleCase(detail.story.severity)}</dd>
            </div>
            <div>
              <dt>Lifecycle</dt>
              <dd>{titleCase(detail.lifecycleState)}</dd>
            </div>
            <div>
              <dt>Coverage</dt>
              <dd>{titleCase(detail.story.coverageState)}</dd>
            </div>
            <div>
              <dt>Event time</dt>
              <dd>
                {detail.eventOccurredAt === null
                  ? "Unavailable — source packet did not declare an occurrence time."
                  : readableTimestamp(detail.eventOccurredAt)}
              </dd>
            </div>
            <div>
              <dt>First seen</dt>
              <dd>{readableTimestamp(detail.firstSeenAt)}</dd>
            </div>
            <div>
              <dt>Verified</dt>
              <dd>{readableTimestamp(detail.verifiedAt)}</dd>
            </div>
            <div>
              <dt>Published</dt>
              <dd>{readableTimestamp(detail.story.publishedAt)}</dd>
            </div>
          </dl>
        </header>

        <div className="story-page-grid">
          <div className="story-narrative">
            <p className="story-lede">{detail.story.summary}</p>
            <section aria-labelledby="why-title">
              <p className="section-label">Operational reading</p>
              <h2 id="why-title">Why it matters</h2>
              <p>{detail.story.whyItMatters}</p>
            </section>
          </div>
          <aside
            className="story-contributors"
            aria-labelledby="contributors-title"
          >
            <p className="section-label">Provenance</p>
            <h2 id="contributors-title">Contributing systems</h2>
            {detail.contributors.length > 0 ? (
              <ul>
                {detail.contributors.map((contributor) => (
                  <li key={contributor}>{contributor}</li>
                ))}
              </ul>
            ) : (
              <p>No contributor label is cleared for publication.</p>
            )}
          </aside>
        </div>

        <section className="visual-provenance" aria-labelledby="visual-title">
          <p className="section-label">Image record</p>
          <h2 id="visual-title">Visual provenance</h2>
          {detail.imageProvenance ? (
            <dl>
              <div>
                <dt>Source</dt>
                <dd>{detail.imageProvenance.source}</dd>
              </div>
              <div>
                <dt>Alt text</dt>
                <dd>{detail.imageProvenance.altText}</dd>
              </div>
              <div>
                <dt>Created</dt>
                <dd>{readableTimestamp(detail.imageProvenance.createdAt)}</dd>
              </div>
            </dl>
          ) : (
            <p>No verified, rights-approved visual is currently visible.</p>
          )}
        </section>

        <EvidenceDrawer claims={detail.claims} />

        <section className="revision-note" aria-labelledby="timeline-title">
          <div>
            <p className="section-label">Revision record</p>
            <h2 id="timeline-title">Publication timeline</h2>
            <p>Append-only publication lifecycle and visibility overlays.</p>
          </div>
          {detail.timeline.length > 0 ? (
            <ol className="publication-timeline">
              {detail.timeline.map((event, index) => (
                <li key={`${event.kind}-${event.version}-${index}`}>
                  <strong>{event.label}</strong>
                  <span>Revision {event.version}</span>
                  <time dateTime={event.occurredAt}>
                    {readableTimestamp(event.occurredAt)}
                  </time>
                </li>
              ))}
            </ol>
          ) : (
            <p>No earlier publication event is recorded.</p>
          )}
        </section>
      </article>
    </MagazineShell>
  );
}
