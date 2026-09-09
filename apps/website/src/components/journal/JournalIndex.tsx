import { JournalSearchControls } from "./JournalSearchControls";
import { ArticleDestination } from "./ArticleDestination";
import { FeedNotice } from "./FeedNotice";
import type { EditorialFeed } from "../../lib/editorial-feed";
import type { JournalArticle } from "../../content/journal";
import { getDestination } from "../../content/destinations";
import { Card, Container, SectionHeading, TextLink } from "../ui";
import styles from "./Journal.module.css";
import indexUi from "./JournalIndex.module.css";
import "../../styles/brand-fonts.css";
import { journalCategories } from "../../content/journal-categories";
import { SiteShell } from "../SiteShell";
import { editorialExcerpt } from "../../lib/editorial-excerpt";

export interface JournalIndexProps {
  readonly articles: readonly JournalArticle[];
  readonly status?: EditorialFeed["status"];
  readonly fixture?: boolean;
  readonly query?: { q?: string; category?: string; page?: number };
  readonly hasMore?: boolean;
  readonly catalogSize?: number;
  readonly total?: number;
}

export function JournalIndex({
  articles,
  status = articles.length ? "ready" : "empty",
  fixture = false,
  query = {},
  hasMore = false,
  catalogSize,
  total,
}: JournalIndexProps) {
  const page = query.page ?? 1;
  function journalHref(category = query.category ?? "", nextPage = 1) {
    const params = new URLSearchParams();
    if (query.q) params.set("q", query.q);
    if (category) params.set("category", category);
    if (nextPage > 1) params.set("page", String(nextPage));
    return `/news${params.size ? `?${params}` : ""}#latest-stories-title`;
  }

  const showcase =
    status === "ready" &&
    !query.q &&
    !query.category &&
    page === 1 &&
    articles.length >= 3;
  const archiveArticles = showcase ? articles.slice(3) : articles;
  function renderStory(article: JournalArticle, index: number) {
    return (
      <li key={article.slug}>
        <Card className={styles.card}>
          <ArticleDestination article={article} className={styles.cardLink}>
            {article.image ? (
              <div className={styles.imageFrame}>
                <img
                  alt={article.image.alt}
                  loading={index === 0 ? "eager" : "lazy"}
                  src={article.image.src}
                />
              </div>
            ) : null}
            <div className={styles.cardCopy}>
              {article.category ? (
                <p className={styles.eyebrow}>{article.category}</p>
              ) : null}
              <h3>{article.title}</h3>
              {article.summary ? (
                <p className={styles.summary}>
                  {editorialExcerpt(article.summary)}
                </p>
              ) : null}
              {article.editorial ? (
                <>
                  <p className={styles.summary}>{article.editorial.summary}</p>
                  <p className={styles.why}>
                    <strong>Why it matters</strong>{" "}
                    {article.editorial.whyItMatters}
                  </p>
                  {article.editorial.amended ? (
                    <p className="article-amended">
                      Amended · Revision {article.editorial.revision}
                    </p>
                  ) : null}
                </>
              ) : null}
              <div className={styles.cardMeta}>
                {article.date ? (
                  <time dateTime={article.date.iso}>{article.date.label}</time>
                ) : (
                  <span>Publication date unavailable</span>
                )}
                <span>
                  {fixture ? (
                    "Sample story"
                  ) : (
                    <>
                      {article.localHref ? "Read story" : "Read at source"}{" "}
                      <span aria-hidden="true">↗</span>
                    </>
                  )}
                </span>
              </div>
            </div>
          </ArticleDestination>
          {article.editorial ? (
            <details className={styles.evidence}>
              <summary>Sources and revisions</summary>
              <ul>
                {article.editorial.evidence.map((source, position) => (
                  <li key={position}>
                    {source.url && !fixture ? (
                      <a href={source.url}>{source.publisher}</a>
                    ) : (
                      <strong>{source.publisher}</strong>
                    )}
                    {source.citation ? <p>{source.citation}</p> : null}
                  </li>
                ))}
              </ul>
              <ol aria-label="Publication revisions">
                {article.editorial.revisions.map((revision) => (
                  <li key={revision.version}>
                    Revision {revision.version} published ·{" "}
                    <time dateTime={revision.publishedAt.iso}>
                      {revision.publishedAt.label}
                    </time>
                  </li>
                ))}
              </ol>
            </details>
          ) : null}
        </Card>
      </li>
    );
  }

  return (
    <SiteShell
      mainId="journal-content"
      className={`${styles.indexTheme} ${indexUi.editorial}`}
    >
      <main id="journal-content" tabIndex={-1}>
        <section
          className={`${styles.intro} ${indexUi.masthead}`}
          aria-labelledby="journal-title"
        >
          <Container className={styles.introInner} width="wide">
            <p className={styles.eyebrow}>
              Independent perspectives / Indonesia
            </p>
            <h1 id="journal-title">The Bali Zero Journal</h1>
            <p className={styles.introCopy}>
              A closer look at life, business and the decisions that shape your
              time in Indonesia.
            </p>
          </Container>
        </section>

        <Container
          as="section"
          aria-labelledby="latest-stories-title"
          className={`${styles.indexSection} ${indexUi.edition}`}
          width="wide"
        >
          {showcase ? (
            <section
              className={indexUi.leadStories}
              aria-labelledby="edition-stories-title"
            >
              <div className={indexUi.editionHeading}>
                <h2 id="edition-stories-title">Selected stories</h2>
                <a href="#latest-stories-title">Browse the archive ↓</a>
              </div>
              <ol className={indexUi.showcase} role="list">
                {articles.slice(0, 3).map(renderStory)}
              </ol>
            </section>
          ) : null}
          <SectionHeading
            className={styles.sectionHeading}
            eyebrow="News · Analysis · Guides"
            id="latest-stories-title"
            title={
              query.q
                ? `Results for “${query.q}”`
                : query.category
                  ? (journalCategories.find(
                      (item) => item.slug === query.category,
                    )?.label ?? "Selected stories")
                  : showcase
                    ? "Explore the archive"
                    : "Selected stories"
            }
          />

          <JournalSearchControls
            query={query}
            status={status}
            total={total}
            catalogSize={catalogSize}
            count={articles.length}
          />
          {status === "empty" && page > 1 ? (
            <p role="status" className={styles.noResults}>
              There are no stories on page {page}. Return to an earlier page or
              change your search.
            </p>
          ) : status === "empty" && (query.q || query.category) ? (
            <p role="status" className={styles.noResults}>
              No stories match this selection. Try another topic or search.
            </p>
          ) : (
            <FeedNotice status={status} fixture={fixture} />
          )}
          {status !== "ready" ? (
            <Card as="div" className={styles.emptyState} tone="quiet">
              {status === "unavailable" || status === "malformed" ? (
                <TextLink href={journalHref(query.category, page)}>
                  Try this search again
                </TextLink>
              ) : null}
              <TextLink
                href={query.q || query.category ? "/news" : "/legacy/news"}
              >
                {query.q || query.category
                  ? "View all stories"
                  : "Visit Bali Zero News"}
              </TextLink>
            </Card>
          ) : (
            <ol
              className={`${styles.articleGrid} ${indexUi.results}`}
              role="list"
            >
              {archiveArticles.map(renderStory)}
            </ol>
          )}
          {page > 1 || hasMore ? (
            <nav aria-label="Journal pages" className={styles.pagination}>
              {page > 1 ? (
                <a href={journalHref(query.category, page - 1)}>← Previous</a>
              ) : (
                <span />
              )}
              <span>Page {page}</span>
              {hasMore ? (
                <a href={journalHref(query.category, page + 1)}>Next →</a>
              ) : (
                <span />
              )}
            </nav>
          ) : null}
          <section
            className={indexUi.tools}
            aria-labelledby="journal-tools-title"
          >
            <h2 id="journal-tools-title">Explore a practical question</h2>
            <p>
              These open Bali Zero tools. To filter articles, use the topics
              above.
            </p>
            <nav aria-label="Bali Zero tools">
              {(
                ["visaOracle", "kbliNavigator", "taxIntelligence"] as const
              ).map((key) => {
                const tool = getDestination(key);
                return (
                  <a key={key} href={tool.href}>
                    {tool.label} ↗
                  </a>
                );
              })}
            </nav>
          </section>
        </Container>
      </main>
    </SiteShell>
  );
}
