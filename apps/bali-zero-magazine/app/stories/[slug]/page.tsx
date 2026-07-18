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

        <EvidenceDrawer claims={detail.claims} />

        <section className="revision-note" aria-labelledby="revision-title">
          <p className="section-label">Revision record</p>
          <h2 id="revision-title">
            {detail.hasSupersededHistory
              ? "Supersedes an earlier revision"
              : "First published revision"}
          </h2>
          <p>
            The narrative above is the current visible version. Earlier
            revisions remain immutable in the publication ledger.
          </p>
        </section>
      </article>
    </MagazineShell>
  );
}
