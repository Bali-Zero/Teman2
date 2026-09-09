# Local MDX article loader — 10 September 2026, Pro

Owner decision (Zero, 2026-09-10, "ok loader"): the public website must serve
the editorial archive from the MDX files already in this repository, not from
the legacy `balizero.com` API. Local implementation only in
`infra-website-r19-pro`, branch `codex/website-pro-continuation`. Commit on the
lane branch is fine. No push, merge, auto-merge, arm, deployment, production
configuration change or outbound message. Do not edit anything under
`apps/mouth`; the MDX archive is read, never moved or rewritten.

## Why

`src/lib/server/public-editorial.ts` and `public-catalog.ts` read every article
and the whole catalog through `readEditorialJson()` → `editorialUpstreamOrigin()`.
On any public hostname that origin is `null` unless `WEBSITE_LEGACY_ORIGIN` and
`WEBSITE_PUBLIC_ORIGIN` point at an independent legacy host, so 814 sitemap
article URLs, `/news`, `/journal` and the six category indexes would render the
"temporarily unavailable" placeholder at cutover. The composed, reviewed
articles are on disk: `apps/mouth/src/content/articles/<folder>/<slug>.mdx`,
808 English editions across 13 folders (`immigration` 309, `business` 162,
`business_regulations` 82, `tax-legal` 66, `lifestyle` 53, `tax` 50, `property`
30, `emerging_trends` 25, `tech` 20, `digital-nomad` 5, `bali_news` 2, `news` 2,
`social_media` 2), plus 2,565 `<slug>.<locale>.mdx` translations that
`article-translations.ts` already reads. Do not use an LLM for any part of
this: it is a deterministic file read.

## Reuse, do not reinvent

- `src/lib/server/article-translations.ts` already owns the archive root
  (`path.resolve(process.cwd(), "../mouth/src/content/articles")`), the
  `realpath` containment check, the `articleFolders` category → folder map, the
  `categoryAliases` normalisation and `decodeAuthoredTranslation()` (gray-matter
  frontmatter → `decodePublicArticle()` input). Add the English edition to that
  module or a sibling; keep one archive root and one containment rule.
- `decodePublicArticle()` in `public-editorial.ts` stays the single publication
  gate: `status === "published"` (default when the frontmatter omits it),
  `noIndex` absent or `false`, valid non-future `publishedAt`, demo slugs and
  `test-article` excluded, cover image through `retainedImage()`.
- Do NOT import `apps/mouth/src/lib/blog/articles.ts`: its `ARTICLES_PATH` is
  bound to `process.cwd()` of the Mouth app and it wraps reads in
  `unstable_cache`. The website runs with `cwd = apps/website`.

## Frontmatter observed (`property/leasehold-vs-freehold.mdx`)

`title`, `slug`, `description`, `excerpt`, `category`, `tags[]`,
`publishedAt` ("2026-01-15"), `updatedAt`, `author{name,role,avatar}`,
`featured`, `image{src,alt}` (some files use `coverImage`/`coverImageAlt`),
`seo{...}`, optional `readingTime`, `aiGenerated`, `noIndex`, `status`.
Identity: category from the folder via the inverse of `articleFolders`, slug
from the filename; a frontmatter `slug`/`category` that disagrees with the path
is rejected, as the translation decoder already does.

## Required behaviour

1. `loadPublicArticleResult(category, slug)`: read
   `<root>/<folder>/<slug>.mdx` for each folder of the category first. If a
   file exists and decodes → `ready`. If a file exists and is rejected by the
   gate (draft, future, noIndex) → `missing`, never fall through to the API. If
   no file exists → current API path unchanged (this keeps the scraper-published
   `news_*` slugs, which have no MDX). If the API is unreachable and no file
   exists → `unavailable`, as today.
2. `loadPublicCatalog()`: list the archive from disk (808 rows: category from
   folder, slug from filename, `title`, `excerpt`, `tags`, `publishedAt` from
   frontmatter, excluding translations `*.<xx>.mdx`), then append API rows whose
   `category/slug` is not already on disk. If the API is unreachable, return the
   disk rows alone; never throw because the legacy origin is missing. Keep
   `selectCatalog()`, ranking and pagination unchanged.
3. `loadPublicJournalFeed()` and `home-editorial.ts` must render from the disk
   catalog with `fetch` unavailable.
4. Never call `editorialUpstreamOrigin()` before the local read; the local path
   must work with `WEBSITE_LEGACY_ORIGIN` unset on a non-localhost host.
5. Path safety identical to translations: `realpath` inside the archive root,
   `isArticleSlug`, `isJournalCategory`, size cap 250 000 bytes.

## Tests (vitest, no network)

Add to `public-editorial.test.ts` and `public-catalog.test.ts`:

- `serves a published English MDX edition without calling fetch` — stub
  `fetch` with `vi.fn()` that throws; `loadPublicArticleResult("property",
"leasehold-vs-freehold")` is `ready`, title matches the frontmatter,
  `fetch` not called.
- `falls back to the legacy API only when no MDX file exists` — slug absent on
  disk, mocked API 200 → `ready`; mocked API 404 → `missing`.
- `rejects an MDX edition the publication gate refuses and does not consult the
API` — temp archive root with `status: draft` and with a future `publishedAt`.
- `lists the archive from disk when the legacy origin is unavailable` —
  `loadPublicCatalog()` length ≥ 808, every row a valid category/slug, no
  `*.id.mdx`/`*.it.mdx` identities, `fetch` not called or failing.
- `refuses traversal outside the archive root` — `../` and symlink escape.

Keep every existing test green: baseline is 1045 passed, 1 skipped (96 files)
and `npm run typecheck` exit 0.

## Evidence to report in the handoff

- `npm test` and `npm run typecheck` output lines.
- With the dev server on 127.0.0.1:3100 and `WEBSITE_LEGACY_ORIGIN` unset:
  `curl -s -o /dev/null -w '%{http_code}' -H 'Host: preview.example'
http://127.0.0.1:3100/property/leasehold-vs-freehold` → 200 and the page
  title from the frontmatter; `/news` → 200 with real stories, not the empty
  state.
- Count of disk rows in the catalog and count of API-only rows appended.

## Out of scope here

The 503 status for the `unavailable` branch, the 307 → 308 flips, the
`sitemap.ts`/`robots.ts` and per-route `noindex` work are listed in
`docs/reviews/2026-09-10-seo-url-migration-map.md` and belong to the separate
cutover-prep slice.
