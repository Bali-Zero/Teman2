"use client";
import { useState } from "react";
import { ArticleDestination } from "./journal/ArticleDestination";
import { FeedNotice } from "./journal/FeedNotice";
import type { EditorialFeed } from "../lib/editorial-feed";
import type { JournalArticle } from "../content/journal";
export function Journal({
  articles,
  indexHref = "/journal",
  status = articles.length ? "ready" : "empty",
  fixture = false,
  featuredCount = 2,
}: {
  articles: readonly JournalArticle[];
  indexHref?: string;
  status?: EditorialFeed["status"];
  fixture?: boolean;
  featuredCount?: number;
}) {
  const [index, setIndex] = useState(0);
  const visible = status === "ready" ? articles : [];
  const stories = visible.slice(0, featuredCount);
  const currentIndex = index % Math.max(stories.length, 1);
  const current = stories[currentIndex];
  const [lead, archive, ...side] = visible.slice(featuredCount);
  function move(delta: number) {
    if (stories.length > 1) {
      setIndex((value) => (value + delta + stories.length) % stories.length);
    }
  }
  return (
    <div className="wrap">
      <section className="journal" id="journal">
        <div className="masthead">
          <div className="topline">
            <span className="eyebrow">
              {"Independent perspectives / Indonesia"}
            </span>
            <span className="eyebrow">{"News · Analysis · Guides"}</span>
          </div>
          <h2 aria-label="The Bali Zero Journal" className="journal-title">
            <span aria-hidden="true" className="journal-the">
              {"The"}
            </span>
            <span aria-hidden="true" className="journal-brand">
              <img
                alt=""
                className="brand-logo-3-img"
                src="/assets/brand-3.png"
              />
              <span>{"ALI"}</span>
              <span className="brand-zero">
                {"ZER"}
                <span className="brand-om-circle"></span>
              </span>
            </span>
            <span aria-hidden="true" className="journal-word">
              {"Journal"}
            </span>
          </h2>
        </div>
        <div className="journal-sub">
          <p>{"News and practical insight from Indonesia."}</p>
          <a className="textlink" href={indexHref}>
            {"Explore the Journal "}
            <span aria-hidden="true">{"↗"}</span>
          </a>
        </div>
        <FeedNotice status={status} fixture={fixture} />
        <div className={`editorial-grid${side.length ? "" : " editorial-grid-compact"}`}>
          {current ? (
            <article
              aria-label="Featured editorial stories"
              aria-roledescription="carousel"
              onKeyDown={(event) => {
                if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
                  event.preventDefault();
                  move(event.key === "ArrowRight" ? 1 : -1);
                }
              }}
              className="feature"
              tabIndex={0}
            >
              {current.image ? <img
                alt={current.image.alt}
                id="feature-image"
                src={current.image.src}
                loading="lazy"
              /> : null}
              <div className="feature-copy">
                <span className="eyebrow" id="feature-category">
                  {current.category}
                </span>
                <h3>
                  <ArticleDestination article={current} id="feature-link" inline>
                    {current.title}
                  </ArticleDestination>
                </h3>
                {current.editorial?.amended ? <p className="article-amended">Amended · Revision {current.editorial.revision}</p> : null}
                {fixture ? <p>Sample story</p> : null}
                {current.date ? (
                  <time id="feature-date" dateTime={current.date.iso}>
                    {current.date.label}
                  </time>
                ) : null}
              </div>
              {stories.length > 1 ? <div className="carousel-controls">
                <button
                  aria-label="Previous editorial story"
                  id="previous-story"
                  onClick={() => move(-1)}
                >
                  {"←"}
                </button>
                <span aria-live="polite" id="story-counter">
                  {String(currentIndex + 1).padStart(2, "0") +
                    " / " +
                    String(stories.length).padStart(2, "0")}
                </span>
                <button
                  aria-label="Next editorial story"
                  id="next-story"
                  onClick={() => move(1)}
                >
                  {"→"}
                </button>
              </div> : null}
            </article>
          ) : null}
          <div className="news-main">
            {lead ? (
              <article>
                <StoryLink article={lead} />
                <StoryDate article={lead} fixture={fixture} />
              </article>
            ) : null}
            {archive ? (
              <ArticleDestination className="archive-pick" article={archive}>
                {archive.image ? <img
                  alt={archive.image.alt}
                  loading="lazy"
                  src={archive.image.src}
                /> : null}
                <div>
                  <p className="article-category">{archive.category}</p>
                  <h3>{archive.title}</h3>
                  <StoryDate article={archive} fixture={fixture} />
                </div>
              </ArticleDestination>
            ) : null}
          </div>
          {side.length ? <div className="news-side">
            <span className="eyebrow">On our radar</span>
            {side.map((article, position) => (
              <article key={article.slug}>
                <span aria-hidden="true" className="story-index">
                  {String(position + 1).padStart(2, "0")}
                </span>
                <StoryLink article={article} />
                <StoryDate article={article} fixture={fixture} />
              </article>
            ))}
          </div> : null}
        </div>
      </section>
    </div>
  );
}

function StoryLink({ article }: { article: JournalArticle }) {
  return (
    <ArticleDestination article={article} className="story-destination">
      {article.image ? <img alt={article.image.alt} loading="lazy" src={article.image.src} /> : null}
      {article.category ? (
        <p className="article-category">{article.category}</p>
      ) : null}
      <h3>{article.title}</h3>
    </ArticleDestination>
  );
}

function StoryDate({ article, fixture = false }: { article: JournalArticle; fixture?: boolean }) {
  return article.date ? (
    <p className="article-meta">
      {fixture ? <span>Sample story · </span> : null}
      {article.editorial?.amended ? <span>Amended · </span> : null}
      <time dateTime={article.date.iso}>{article.date.label}</time>
    </p>
  ) : null;
}
