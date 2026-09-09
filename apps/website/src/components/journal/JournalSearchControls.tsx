"use client";
import { useEffect, useState } from "react";
import { journalCategories } from "../../content/journal-categories";
import type { JournalIndexProps } from "./JournalIndex";
import styles from "./JournalSearchControls.module.css";

type Props = Pick<
  JournalIndexProps,
  "query" | "status" | "total" | "catalogSize"
> & { count: number };

export function JournalSearchControls({
  query = {},
  status = "ready",
  total,
  catalogSize,
  count,
}: Props) {
  const [pending, setPending] = useState(false);
  useEffect(() => {
    const restore = () => setPending(false);
    window.addEventListener("pageshow", restore);
    return () => window.removeEventListener("pageshow", restore);
  }, []);
  function href(q = query.q, category = query.category): string {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (category) params.set("category", category);
    return `/news${params.size ? `?${params}` : ""}#latest-stories-title`;
  }
  const category = journalCategories.find(
    (item) => item.slug === query.category,
  )?.label;
  return (
    <section className={styles.search} aria-label="Find Journal stories">
      <form
        action="/news#latest-stories-title"
        role="search"
        onSubmit={() => setPending(true)}
        aria-busy={pending}
      >
        <label htmlFor="journal-search">Search the Journal</label>
        <div className={styles.field}>
          <input
            id="journal-search"
            name="q"
            type="search"
            maxLength={120}
            aria-describedby="journal-search-scope"
            placeholder="Search titles and summaries"
            defaultValue={query.q ?? ""}
          />
          {query.category ? (
            <input type="hidden" name="category" value={query.category} />
          ) : null}
          <button type="submit" disabled={pending}>
            {pending ? "Searching…" : "Search"}
            <span aria-hidden="true"> →</span>
          </button>
        </div>
      </form>
      <p id="journal-search-scope" className={styles.scope}>
        Search the complete available archive by title, summary, topic or
        keyword. Article body text is not included.
      </p>
      <nav aria-label="Journal topics" className={styles.topics}>
        <a
          href={href(query.q, "")}
          aria-current={!query.category ? "page" : undefined}
        >
          All stories
        </a>
        {journalCategories.map((item) => (
          <a
            key={item.slug}
            href={href(query.q, item.slug)}
            aria-current={query.category === item.slug ? "page" : undefined}
          >
            {item.label}
          </a>
        ))}
      </nav>
      {query.q || query.category ? (
        <div className={styles.active} aria-label="Active filters">
          <span>Showing</span>
          {query.q ? (
            <a
              href={href("", query.category)}
              aria-label={`Remove search: ${query.q}`}
            >
              “{query.q}” <span aria-hidden="true">×</span>
            </a>
          ) : null}
          {query.category ? (
            <a
              href={href(query.q, "")}
              aria-label={`Remove topic: ${category ?? query.category}`}
            >
              {category ?? query.category} <span aria-hidden="true">×</span>
            </a>
          ) : null}
          <a className={styles.clear} href="/news#latest-stories-title">
            Clear search and filters
          </a>
        </div>
      ) : null}
      <p
        className={styles.count}
        role={pending || status === "ready" ? "status" : undefined}
      >
        {pending ? (
          "Searching the archive…"
        ) : status === "ready" ? (
          <>
            <strong>
              {total !== undefined
                ? `${total} matching ${total === 1 ? "story" : "stories"} · `
                : ""}
              {count} on this page
            </strong>
            {catalogSize !== undefined ? (
              <span> · {catalogSize} archive entries searched</span>
            ) : null}
          </>
        ) : status === "empty" ? (
          <>
            <strong>0 matching stories</strong>
            {catalogSize !== undefined ? (
              <span> · {catalogSize} archive entries searched</span>
            ) : null}
          </>
        ) : (
          "Search results are unavailable. Your search and filters are retained for retry."
        )}
      </p>
    </section>
  );
}
