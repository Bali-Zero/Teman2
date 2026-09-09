import type { JournalArticleDocument } from "../../content/journal";
import { ArticleBody } from "./ArticleBody";
import { headingId, parseArticle, type ReadingNode } from "./article-model";
import { safeArticleUrl } from "./article-urls";
import styles from "./ArticleReader.module.css";
import { ArticleReaderActions } from "./ArticleReaderActions";
import { publishedEditionHref } from "../../lib/retained-routes";
import { editorialExcerpt } from "../../lib/editorial-excerpt";

export interface ArticleTemplateProps { readonly article: JournalArticleDocument; readonly locale?: string }

function hasContextHelp(nodes: ReadingNode[]): boolean {
  return nodes.some((node) => node.kind === "component" && (node.name === "AskZantara" || hasContextHelp(node.children)));
}

export function ArticleTemplate({ article, locale = "en" }: ArticleTemplateProps) {
  const { metadata } = article;
  const sourceUrl = metadata.finalSourceUrl ?? metadata.sourceUrl;
  const document = parseArticle(article.markdown ?? "", metadata.title);
  const used = new Map(document.headingIds.map((id) => [id, 1]));
  const sections = article.sections.map((section) => ({ ...section, id: headingId(section.heading, used) }));
  const headings = [...document.headings, ...sections.map((section) => ({ id: section.id, text: section.heading, depth: 2 }))];
  const reading = metadata.reading;
  const contentsGroups = headings.reduce<Array<{ heading: typeof headings[number]; children: typeof headings }>>((groups, heading) => {
    if (heading.depth === 3 && groups.length) groups[groups.length - 1].children.push(heading);
    else groups.push({ heading, children: [] });
    return groups;
  }, []);
  const contents = <ol>{contentsGroups.map(({ heading, children }) => <li key={heading.id}>
    <a href={`#${heading.id}`}>{heading.text}</a>
    {children.length ? <details className={styles.contentsGroup}><summary>{children.length} subsections</summary><ol>{children.map((child) => <li key={child.id} className={styles.subheading}><a href={`#${child.id}`}>{child.text}</a></li>)}</ol></details> : null}
  </li>)}</ol>;
  return <article lang={locale} className={styles.reader} data-indexing={article.indexing} data-verification-status={metadata.verificationStatus}>
    {metadata.verificationStatus === "development-only" ? <p className={styles.presentationNote} role="status">Development fixture — not published or indexed</p> : null}
    <div className={styles.opening}>
    <header className={styles.header}>
      {metadata.category ? <p className={styles.eyebrow}>{metadata.category} <span aria-hidden="true">/</span> The Bali Zero Journal</p> : null}
      <h1>{metadata.title}</h1>
      {article.standfirst ? <p className={styles.standfirst}>{editorialExcerpt(article.standfirst, 380)}</p> : null}
    </header>
      <div className={styles.metadata} aria-label="Article information">
        {reading?.author ? <p className={styles.byline}>By <strong>{reading.author.name}</strong>{reading.author.role ? <span>{reading.author.role}</span> : null}</p> : null}
        <p>{metadata.date ? <>Published <time dateTime={metadata.date.iso}>{metadata.date.label}</time></> : "Publication date unavailable"}{reading?.minutes ? <span> · {reading.minutes} min read</span> : null}</p>
        {reading?.updated && reading.updated.iso !== metadata.date?.iso ? <p>Updated <time dateTime={reading.updated.iso}>{reading.updated.label}</time></p> : null}
        {reading?.reviewedBy ? <p>Reviewed by {reading.reviewedBy}</p> : null}
        {reading?.aiGenerated ? <p>AI-assisted article{reading.reviewedBy ? " · reviewer credited above" : ""}</p> : null}
        {reading?.disclosure ? <p>{reading.disclosure}</p> : null}
      </div>
    {metadata.image ? <figure className={styles.hero}><img alt={metadata.image.alt} src={metadata.image.src} /></figure> : null}
    </div>
    <div className={styles.readingLayout}>
      {headings.length ? <aside className={styles.contentsRail}><nav aria-label="Article contents"><p className={styles.contentsTitle}>On this page</p>{contents}<a className={styles.backToTitle} href="#article-content">Back to top ↑</a></nav></aside> : <div />}
      <div className={styles.readingColumn}>
        {headings.length ? <details className={styles.mobileContents}><summary>On this page <span>{headings.length} sections</span></summary><nav aria-label="Mobile article contents">{contents}</nav></details> : null}
        {article.markdown ? <ArticleBody source={article.markdown} originalUrl={sourceUrl} document={document} title={metadata.title} /> : null}
        <div className={styles.prose}>{sections.map((section) => <section key={section.id}><h2 id={section.id} tabIndex={-1}>{section.heading}</h2>{section.paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)}</section>)}</div>
        <footer className={styles.footer}>
          {metadata.editorial?.evidence.length ? <div className={styles.sourceNote}><p className={styles.noteLabel}>Sources</p><ul>{metadata.editorial.evidence.map((evidence, index) => <li key={index}>{evidence.url && safeArticleUrl(evidence.url) ? <a href={safeArticleUrl(evidence.url)}>{evidence.publisher}</a> : evidence.publisher}{evidence.citation ? ` — ${evidence.citation}` : ""}</li>)}</ul></div> : null}
          {metadata.verificationStatus !== "development-only" ? <p className={styles.edition}>Published by Bali Zero · <a href={publishedEditionHref(sourceUrl)}>View the published edition</a></p> : null}
          <ArticleReaderActions title={metadata.title} url={metadata.sourceUrl} includeContextHelp={!hasContextHelp(document.nodes)} />
        </footer>
      </div>
    </div>
  </article>;
}
