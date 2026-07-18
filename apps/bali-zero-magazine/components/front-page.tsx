import Link from "next/link";

import type { FrontPageView } from "@/lib/server/magazine-read-model";

import { StoryCard } from "./story-card";
import { SystemStatusStrip } from "./system-status-strip";

type FrontPageProps = Readonly<{
  page: FrontPageView;
  archive?: boolean;
}>;

function editionDate(value: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

export function FrontPage({ page, archive = false }: FrontPageProps) {
  const edition = page.edition;
  return (
    <div className="front-page">
      {archive && edition ? (
        <section className="archive-banner">
          <p className="section-label">Edition archive</p>
          <h1>{`Immutable revision ${edition.revision}`}</h1>
          <p>Current visibility and rights overlays apply.</p>
        </section>
      ) : null}

      <header className="edition-header">
        <p>{edition ? editionDate(edition.date) : "Workspace edition"}</p>
        <div className="edition-badges">
          {edition?.kind === "quiet" ? <span>Quiet edition</span> : null}
          {edition?.coverageState === "partial" ? (
            <span>Partial coverage</span>
          ) : null}
        </div>
      </header>

      {edition?.readerNotices.map((notice) => (
        <p className="reader-notice" key={notice}>
          {notice}
        </p>
      ))}

      {page.breaking.length > 0 ? (
        <aside className="breaking-strip" aria-labelledby="breaking-title">
          <div>
            <p className="section-label">Live editorial desk</p>
            <h2 id="breaking-title">Breaking</h2>
          </div>
          {page.breaking.map((story) => (
            <StoryCard key={story.slug} story={story} variant="breaking" />
          ))}
        </aside>
      ) : null}

      {edition === null ? (
        <section className="empty-edition">
          <p className="section-label">Publication desk</p>
          <h1>No published edition yet</h1>
          <p>
            The front page will appear when a verified revision is promoted.
          </p>
        </section>
      ) : edition.kind === "quiet" ? (
        <section className="quiet-edition">
          <p className="section-label">Quiet edition</p>
          <h1>No verified developments cleared the publication threshold</h1>
          <p>
            Coverage remains monitored; the desk has not manufactured a
            headline.
          </p>
        </section>
      ) : page.hero ? (
        <section className="morning-file" aria-labelledby="morning-file-title">
          <div className="morning-file-label">
            <p className="section-label">Lead dossier</p>
            <h1 id="morning-file-title">The Morning File</h1>
          </div>
          <StoryCard story={page.hero} variant="hero" />
          {page.dispatches.length > 0 ? (
            <div className="dispatch-column" aria-label="Morning dispatches">
              {page.dispatches.slice(0, 3).map((story) => (
                <StoryCard key={story.slug} story={story} variant="dispatch" />
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="domain-grid" aria-label="Editorial domains">
        {page.sections.map((section) => (
          <section className="domain-section" key={section.key}>
            <h2>{section.label}</h2>
            {section.stories.length > 0 ? (
              section.stories
                .slice(0, 2)
                .map((story) => <StoryCard key={story.slug} story={story} />)
            ) : (
              <p className="domain-quiet">
                No verified dispatch in this edition.
              </p>
            )}
          </section>
        ))}
      </div>

      {page.curiosity ? (
        <section className="curiosity-block">
          <p className="section-label">The Detail Everyone Missed</p>
          <h2>{page.curiosity.curiosityText}</h2>
          <Link href={`/stories/${encodeURIComponent(page.curiosity.slug)}`}>
            Read the supporting dossier
          </Link>
        </section>
      ) : null}

      <SystemStatusStrip
        systems={page.sourceSystems}
        unavailable={page.unavailable}
      />
    </div>
  );
}
