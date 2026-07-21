import Link from "next/link";

import type { StoryCardView } from "@/lib/server/magazine-read-model";

type StoryCardProps = Readonly<{
  story: StoryCardView;
  variant?: "hero" | "dispatch" | "domain" | "breaking";
}>;

export function StoryCard({ story, variant = "domain" }: StoryCardProps) {
  const showVisual =
    variant === "hero" || (variant !== "breaking" && story.imageAvailable);

  return (
    <article className={`story-card story-card--${variant}`}>
      {showVisual ? (
        <div
          className={`editorial-visual editorial-visual--${variant}${
            story.imageAvailable ? " editorial-visual--image" : ""
          }`}
        >
          {story.imageAvailable ? (
            // The authenticated same-origin route must not pass through an
            // optimizer, because optimizer requests do not carry the viewer.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`/api/story-media/${encodeURIComponent(story.slug)}`}
              alt={story.imageAlt}
              loading={variant === "hero" ? "eager" : "lazy"}
              fetchPriority={variant === "hero" ? "high" : "auto"}
            />
          ) : (
            <span>Editorial visual pending verified media</span>
          )}
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
