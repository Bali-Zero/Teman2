import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { ArticleTemplate } from "../../../components/journal/ArticleTemplate";
import { loadPublicArticleResult } from "../../../lib/server/public-editorial";
import { articleLocales, isArticleLocale, loadAuthoredTranslations } from "../../../lib/server/article-translations";
import styles from "../../../components/journal/Journal.module.css";
import readerUi from "../../../components/journal/ArticleReader.module.css";
import localeUi from "../../../components/journal/ArticleLocales.module.css";
import "../../../styles/brand-fonts.css";
import { SiteShell } from "../../../components/SiteShell";

type Props = { params: Promise<{ category: string; slug: string }>; searchParams?: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { category, slug } = await params;
  const query = await searchParams;
  const lang = query?.lang ?? "en";
  if (!isArticleLocale(lang)) return { title: "Bali Zero Journal", robots: { index: false, follow: false } };
  const result = await loadPublicArticleResult(category, slug);
  if (result.status !== "ready") return { title: "Article unavailable", robots: { index: false, follow: false } };
  const translated = lang === "en" ? undefined : (await loadAuthoredTranslations(category, slug))[lang];
  const article = translated ?? result.article;
  return { title: article.metadata.title, description: article.standfirst, alternates: { canonical: article.metadata.sourceUrl } };
}

export default async function ArticlePage({ params, searchParams }: Props) {
  await connection();
  const { category, slug } = await params;
  const query = await searchParams;
  const requestedLocale = query?.lang ?? "en";
  if (!isArticleLocale(requestedLocale)) notFound();
  const result = await loadPublicArticleResult(category, slug);
  if (result.status === "missing") notFound();
  // A local translation never revives a withdrawn or unavailable base record.
  const translations: Awaited<ReturnType<typeof loadAuthoredTranslations>> = result.status === "ready" ? await loadAuthoredTranslations(category, slug) : {};
  const translated = translations[requestedLocale];
  const locale = translated ? requestedLocale : "en";
  const article = translated ?? (result.status === "ready" ? result.article : null);
  const href = `/${category}/${slug}`;
  const suffix = requestedLocale === "en" ? "" : `?lang=${requestedLocale}`;
  return <SiteShell mainId="article-content" className={styles.indexTheme}>
    <main id="article-content" tabIndex={-1}>
      {article ? <>
      <nav aria-label="Breadcrumb" className={`${styles.breadcrumb} ${readerUi.breadcrumb}`}><a href="/journal">Journal</a><span aria-hidden="true">/</span><a href={`/journal?category=${category}`}>{article.metadata.category}</a></nav>
      <nav className={localeUi.languages} aria-label="Article language"><span>Read in</span>{Object.entries(articleLocales).filter(([key]) => key === "en" || translations[key as keyof typeof articleLocales]).map(([key, label]) => <a key={key} href={href + (key === "en" ? "" : `?lang=${key}`)} lang={key} hrefLang={key} aria-current={locale === key ? "page" : undefined}>{label}</a>)}</nav>
      {requestedLocale !== "en" && !translated ? <p role="status" className={localeUi.notice}>The {articleLocales[requestedLocale]} edition is not available here. You are reading the English article.</p> : null}
      <ArticleTemplate article={article} locale={locale} />
      <section className={`${styles.readNext} ${readerUi.readNext}`}><h2>Continue reading</h2><a href={`/journal?category=${category}`}>More in {article.metadata.category} <span aria-hidden="true">↗</span></a></section>
      </> : <section className={styles.readNext}>
        <p className={styles.eyebrow}>The Bali Zero Journal</p>
        <h1>This story is temporarily unavailable.</h1>
        <p role="status">We could not load the article. Please try again in a moment.</p>
        <p><a href={href + suffix}>Try again</a></p>
        <p><a href={`/legacy${href}${suffix}`}>Read the original article <span aria-hidden="true">↗</span></a></p>
      </section>}
    </main>
  </SiteShell>;
}
