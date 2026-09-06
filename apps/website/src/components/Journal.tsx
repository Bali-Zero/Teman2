"use client";
import { useState } from "react";
import { stories } from "../content/stories";
export function Journal() {
  const [index, setIndex] = useState(0);
  const current = stories[index];
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
          <p>{"Daily news and practical insight from Indonesia."}</p>
          <a className="textlink" href="https://balizero.com/news">
            {"Explore the Journal "}
            <span aria-hidden="true">{"↗"}</span>
          </a>
        </div>
        <div className="editorial-grid">
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
              alt={current.title}
              id="feature-image"
              src={current.image}
              loading="lazy"
            />
            <div className="feature-copy">
              <span className="eyebrow" id="feature-category">
                {current.category}
              </span>
              <h3>
                <a href={current.url} id="feature-link">
                  {current.title}
                </a>
              </h3>
              <p id="feature-date">{current.date}</p>
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
                {String(index + 1).padStart(2, "0") + " / 02"}
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
          <div className="news-main">
            <article>
              <a href="https://balizero.com/business/indonesias-kbli-2025-shake-up-the-transition-rules-every-business-must-know">
                <img
                  alt="Published cover for the KBLI 2025 transition story"
                  loading="lazy"
                  src="/assets/kbli.jpg"
                />
                <p className="article-category">{"Business / What changes"}</p>
                <h3>
                  {
                    "Indonesia’s KBLI 2025 Shake-Up: The Transition Rules Every Business Must Know"
                  }
                </h3>
              </a>
              <p className="article-meta">{"04 September 2026 · 3 min read"}</p>
            </article>
            <a
              className="archive-pick"
              href="https://balizero.com/business/the-it-escape-route"
            >
              <img
                alt="The IT Escape Route editorial cover"
                loading="lazy"
                src="/assets/it.png"
              />
              <div>
                <p className="article-category">{"From the archive"}</p>
                <h3>{"The IT Escape Route"}</h3>
                <p className="article-meta">{"23 June 2026"}</p>
              </div>
            </a>
          </div>
          <div className="news-side">
            <span className="eyebrow">{"On our radar"}</span>
            <article>
              <span aria-hidden="true" className="story-index">
                {"01"}
              </span>
              <a href="https://balizero.com/visas/bali-immigration-brings-permit-services-to-discovery-mall">
                <img
                  alt="Published cover of the Discovery Mall immigration story"
                  loading="lazy"
                  src="/assets/immigration.jpg"
                />
                <p className="article-category">{"Immigration"}</p>
                <h3>
                  {"Bali Immigration Brings Permit Services to Discovery Mall"}
                </h3>
              </a>
              <p className="article-meta">{"11 July 2026"}</p>
            </article>
            <article>
              <span aria-hidden="true" className="story-index">
                {"02"}
              </span>
              <a href="https://balizero.com/business/indonesias-nib-the-one-business-id-every-investor-must-have">
                <img
                  alt="Published NIB business registration story cover"
                  loading="lazy"
                  src="/assets/nib.jpg"
                />
                <p className="article-category">{"Business essentials"}</p>
                <h3>
                  {
                    "Indonesia’s NIB: The One Business ID Every Investor Must Have"
                  }
                </h3>
              </a>
              <p className="article-meta">{"11 July 2026"}</p>
            </article>
          </div>
        </div>
        <div className="interests">
          <span className="eyebrow">{"Follow your interests"}</span>
          <a href="https://balizero.com/news?category=trends">{"AI & Tech"}</a>
          <a href="https://balizero.com/news?category=visas">{"Visas"}</a>
          <a href="https://balizero.com/news?q=pt+pma">{"PT PMA"}</a>
          <a href="https://balizero.com/news?category=taxes">{"Tax"}</a>
          <a href="https://balizero.com/news?q=kitas">{"KITAS"}</a>
          <a href="https://balizero.com/news?category=property">{"Property"}</a>
          <a href="https://balizero.com/news?q=digital+nomad">
            {"Digital nomads"}
          </a>
        </div>
      </section>
    </div>
  );
}
