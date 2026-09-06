"use client";
import { useState } from "react";
import { stories } from "../content/stories";
import {
  getPublicJournalArticles,
  type JournalArticle,
} from "../content/journal";
export function Journal() {
  const [index, setIndex] = useState(0);
  const current = stories[index];
  const [lead, archive, ...side] = getPublicJournalArticles().slice(2);
  function move(delta: number) {
    setIndex((value) => (value + delta + stories.length) % stories.length);
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
          <a className="textlink" href="/journal">
            {"Explore the Journal "}
            <span aria-hidden="true">{"↗"}</span>
          </a>
        </div>
        <div className="editorial-grid">
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
              <img
                alt={current.image.alt}
                id="feature-image"
                src={current.image.src}
                loading="lazy"
              />
              <div className="feature-copy">
                <span className="eyebrow" id="feature-category">
                  {current.category}
                </span>
                <h3>
                  <a
                    href={current.finalSourceUrl ?? current.sourceUrl}
                    id="feature-link"
                  >
                    {current.title}
                  </a>
                </h3>
                {current.date ? (
                  <time id="feature-date" dateTime={current.date.iso}>
                    {current.date.label}
                  </time>
                ) : null}
              </div>
              <div className="carousel-controls">
                <button
                  aria-label="Previous editorial story"
                  id="previous-story"
                  onClick={() => move(-1)}
                >
                  {"←"}
                </button>
                <span aria-live="polite" id="story-counter">
                  {String(index + 1).padStart(2, "0") +
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
              </div>
            </article>
          ) : (
            <p role="status">No stories are available at the moment.</p>
          )}
          <div className="news-main">
            {lead ? (
              <article>
                <StoryLink article={lead} />
                <StoryDate article={lead} />
              </article>
            ) : null}
            {archive ? (
              <a
                className="archive-pick"
                href={archive.finalSourceUrl ?? archive.sourceUrl}
              >
                <img
                  alt={archive.image.alt}
                  loading="lazy"
                  src={archive.image.src}
                />
                <div>
                  <p className="article-category">{archive.category}</p>
                  <h3>{archive.title}</h3>
                  <StoryDate article={archive} />
                </div>
              </a>
            ) : null}
          </div>
          <div className="news-side">
            {side.length ? <span className="eyebrow">On our radar</span> : null}
            {side.map((article, position) => (
              <article key={article.slug}>
                <span aria-hidden="true" className="story-index">
                  {String(position + 1).padStart(2, "0")}
                </span>
                <StoryLink article={article} />
                <StoryDate article={article} />
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function StoryLink({ article }: { article: JournalArticle }) {
  return (
    <a href={article.finalSourceUrl ?? article.sourceUrl}>
      <img alt={article.image.alt} loading="lazy" src={article.image.src} />
      {article.category ? (
        <p className="article-category">{article.category}</p>
      ) : null}
      <h3>{article.title}</h3>
    </a>
  );
}

function StoryDate({ article }: { article: JournalArticle }) {
  return article.date ? (
    <p className="article-meta">
      <time dateTime={article.date.iso}>{article.date.label}</time>
    </p>
  ) : null;
}
