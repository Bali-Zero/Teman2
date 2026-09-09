"use client";
import { useId, useState } from "react";
import { isArticleSlug } from "../../lib/article-slug";
import { isJournalCategory } from "../../content/journal-categories";
import { buildEmailIntent, buildWhatsAppIntent } from "../../lib/destinations/intents";
import styles from "./ArticleInteraction.module.css";

function canonicalArticle(url: string): string | null {
  try {
    const parsed = new URL(url);
    const parts = parsed.pathname.split("/");
    const lang = parsed.searchParams.get("lang");
    const suffix = parsed.searchParams.getAll("lang").length === 1 && lang && ["id", "it", "fr", "ru"].includes(lang) ? `?lang=${lang}` : "";
    return parsed.origin === "https://balizero.com" && parts.length === 3 && isJournalCategory(parts[1]) && isArticleSlug(parts[2]) && !parsed.username && !parsed.password ? parsed.origin + parsed.pathname + suffix : null;
  } catch { return null; }
}

export function ArticleContextHelp({ title, url, context, questions = [] }: { title: string; url: string; context?: string; questions?: string[] }) {
  const id = useId(), [question, setQuestion] = useState("");
  const canonical = canonicalArticle(url);
  if (!canonical) return null;
  const topic = `${title} (${canonical})${question ? ` — ${question}` : ""}`;
  return <section className={styles.context} aria-labelledby={id}>
    <p className={styles.eyebrow}>Continue with the team</p>
    <h4 id={id}>A question about this article?</h4>
    <p className={styles.note}>Zantara chat is unavailable in this preview. The team can help; the article and your selected question will be included in the draft.</p>
    <div className={styles.identity}><small>About this article</small>{title}</div>
    {context ? <p><small>Topic: {context}</small></p> : null}
    {questions.length ? <ul className={styles.questions}>{questions.slice(0, 12).map((text, i) => <li key={i}><button type="button" className={question === text ? styles.selected : undefined} aria-pressed={question === text} onClick={() => setQuestion(question === text ? "" : text)}>{text}</button></li>)}</ul> : null}
    <p role="status" className={styles.feedback}>{question ? `Selected question: ${question}` : questions.length ? "Choose a question above, or open a draft with the article. Select it again to clear." : "The article will be included in your draft."}</p>
    <div className={styles.draftActions}>
    <a href={buildWhatsAppIntent({ topic })}>Open WhatsApp draft ↗</a>
    <a href={buildEmailIntent({ subject: `Question about: ${title}`, body: topic })}>Open email draft ↗</a>
    </div>
    <p className={styles.note}>Opening a draft does not send it. You can review and edit it before sending.</p>
  </section>;
}

export function ArticleReaderActions({ title, url, includeContextHelp = true }: { title: string; url: string; includeContextHelp?: boolean }) {
  const [copyState, setCopyState] = useState<"idle" | "copying" | "copied" | "failed">("idle");
  const id = useId(), canonical = canonicalArticle(url);
  if (!canonical) return null;
  async function copy(): Promise<void> {
    setCopyState("copying");
    try { await navigator.clipboard.writeText(canonical!); setCopyState("copied"); }
    catch { setCopyState("failed"); }
  }
  return <>
    <section className={`${styles.context} ${styles.share}`} aria-labelledby={id}>
      <h4 id={id}>Keep this article</h4>
      <div className={styles.shareActions}>
      <button type="button" onClick={copy} disabled={copyState === "copying"}>{copyState === "copying" ? "Copying…" : "Copy article link"}</button>
      <a href={buildEmailIntent({ subject: title, body: canonical })}>Open an email with this article ↗</a>
      </div>
      <p role="status" className={styles.feedback}>{copyState === "copied" ? "Article link copied." : copyState === "failed" ? "Copying is unavailable. Select and copy the article address below." : copyState === "copying" ? "Copying the article address…" : "Share the original published article."}</p>
      {copyState === "failed" ? <label>Article address<input readOnly value={canonical} onFocus={(event) => event.currentTarget.select()} /></label> : null}
    </section>
    {includeContextHelp ? <ArticleContextHelp title={title} url={canonical} /> : null}
    <section className={`${styles.context} ${styles.subscription}`} aria-label="Journal newsletter"><div><h4>Journal updates</h4><p>Newsletter signup is unavailable in this preview.</p></div><a href="/journal">Browse the latest Journal stories →</a></section>
  </>;
}
