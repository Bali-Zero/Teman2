import type { JournalArticle } from "../../content/journal";
import { getDestination } from "../../content/destinations";
import { Card, Container, SectionHeading, TextLink } from "../ui";
import styles from "./Journal.module.css";

export interface JournalIndexProps {
  readonly articles: readonly JournalArticle[];
}

export function JournalIndex({ articles }: JournalIndexProps) {
  const myBaliZero = getDestination("myBaliZero");

  return (
    <>
      <a className={styles.skipLink} href="#journal-content">
        Skip to Journal stories
      </a>
      <header className={styles.siteHeader}>
        <a aria-label="Bali Zero home" className={styles.brand} href="/">
          <img alt="" height="56" src="/assets/logo.png" width="56" />
          <span>The Bali Zero Journal</span>
        </a>
        <nav aria-label="Journal navigation" className={styles.navigation}>
          <a href="/">Home</a>
          <a href="/#services">Services</a>
          <a href={myBaliZero.href}>{myBaliZero.label}</a>
        </nav>
      </header>

      <main id="journal-content">
        <section className={styles.intro} aria-labelledby="journal-title">
          <Container className={styles.introInner} width="wide">
            <p className={styles.eyebrow}>
              Independent perspectives / Indonesia
            </p>
            <h1 id="journal-title">The Bali Zero Journal</h1>
            <p className={styles.introCopy}>
              News and practical analysis from Indonesia. Every story below
              opens at its verified original publication.
            </p>
          </Container>
        </section>

        <Container
          as="section"
          aria-labelledby="latest-stories-title"
          className={styles.indexSection}
          width="wide"
        >
          <SectionHeading
            className={styles.sectionHeading}
            eyebrow="News · Analysis · Guides"
            id="latest-stories-title"
            title="Latest stories"
          />

          {articles.length === 0 ? (
            <Card
              as="div"
              className={styles.emptyState}
              role="status"
              tone="quiet"
            >
              <h3>No verified stories are available yet.</h3>
              <p>
                Source checks are still in progress. Unverified destinations
                are not listed.
              </p>
              <TextLink href="/">Return to the Bali Zero homepage</TextLink>
            </Card>
          ) : (
            <ol className={styles.articleGrid}>
              {articles.map((article, index) => {
                const sourceUrl = article.finalSourceUrl ?? article.sourceUrl;
                return (
                  <li key={article.slug}>
                    <Card className={styles.card}>
                      <a className={styles.cardLink} href={sourceUrl}>
                        <div className={styles.imageFrame}>
                          <img
                            alt={article.image.alt}
                            loading={index === 0 ? "eager" : "lazy"}
                            src={article.image.src}
                          />
                        </div>
                        <div className={styles.cardCopy}>
                          {article.category ? (
                            <p className={styles.eyebrow}>{article.category}</p>
                          ) : null}
                          <h3>{article.title}</h3>
                          <div className={styles.cardMeta}>
                            {article.date ? (
                              <time dateTime={article.date.iso}>
                                {article.date.label}
                              </time>
                            ) : (
                              <span>Publication date unavailable</span>
                            )}
                            <span>
                              Read at source <span aria-hidden="true">↗</span>
                            </span>
                          </div>
                        </div>
                      </a>
                    </Card>
                  </li>
                );
              })}
            </ol>
          )}
        </Container>
      </main>

      <footer className={styles.siteFooter}>
        <p>© 2026 Bali Zero · Bali, Indonesia</p>
        <p>Website development preview</p>
      </footer>
    </>
  );
}
