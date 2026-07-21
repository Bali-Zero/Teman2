import Link from "next/link";

import type { StoryCardView } from "@/lib/server/magazine-read-model";

type StoryCardProps = Readonly<{
  story: StoryCardView;
  variant?: "hero" | "dispatch" | "domain" | "breaking";
}>;

export function StoryCard({ story, variant = "domain" }: StoryCardProps) {
  return (
    <article className={`story-card story-card--${variant}`}>
      {variant === "hero" ? (
        <div
          className="editorial-visual"
          role="img"
          aria-label={story.imageAlt}
        >
          <span>Editorial visual pending verified media</span>
        </div>
      ) : null}
      <div className="story-card-copy">
        <p className="story-meta">
          <span>{story.domain.replaceAll("-", " & ")}</span>
          {story.coverageState === "partial" ? <b>Partial</b> : null}
        </p>
        <h3>
          <Link href={`/stories/${encodeURIComponent(story.slug)}`}>
            {story.title}
          </Link>
        </h3>
        <p className="story-deck">{story.deck}</p>
        {variant === "hero" ? (
          <p className="story-summary">{story.summary}</p>
        ) : null}
      </div>
    </article>
  );
}
