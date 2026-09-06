import type { JournalArticleDocument } from "../../content/journal";
import { TextLink } from "../ui";
import styles from "./Journal.module.css";

export interface ArticleTemplateProps {
  readonly article: JournalArticleDocument;
}

export function ArticleTemplate({ article }: ArticleTemplateProps) {
  const { metadata } = article;
  const sourceUrl = metadata.finalSourceUrl ?? metadata.sourceUrl;

  return (
    <article
      className={styles.articleTemplate}
      data-indexing={article.indexing}
      data-verification-status={metadata.verificationStatus}
    >
      {metadata.verificationStatus === "development-only" ? (
        <p className={styles.fixtureNotice} role="status">
          Development fixture — not published or indexed
        </p>
      ) : null}
      <header className={styles.articleHeader}>
        {metadata.category ? (
          <p className={styles.eyebrow}>{metadata.category}</p>
        ) : null}
        <h1>{metadata.title}</h1>
        <p className={styles.standfirst}>{article.standfirst}</p>
        {metadata.date ? (
          <time dateTime={metadata.date.iso}>{metadata.date.label}</time>
        ) : (
          <p className={styles.unknownMetadata}>Publication date unavailable</p>
        )}
      </header>
      <img
        alt={metadata.image.alt}
        className={styles.articleHero}
        src={metadata.image.src}
      />
      <div className={styles.articleBody}>
        {article.sections.map((section) => (
          <section key={section.heading}>
            <h2>{section.heading}</h2>
            {section.paragraphs.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </section>
        ))}
      </div>
      <footer className={styles.articleSource}>
        <TextLink href={sourceUrl}>View the original source</TextLink>
      </footer>
    </article>
  );
}
