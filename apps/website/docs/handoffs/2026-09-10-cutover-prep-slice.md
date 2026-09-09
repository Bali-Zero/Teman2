# Cutover preparation slice — 10 September 2026, Pro

Owner decision (Zero, 2026-09-10: "go"). Local implementation only, branch
`agent/nuzantara/infra/website-mdx-loader` on top of `8a9184e367` (local MDX
loader). Commit is allowed on this branch; no push, merge, arm, deployment or
production configuration change. Do not edit anything under `apps/mouth`,
`apps/bali-zero-magazine` or `data/`. Everything here is safe to ship before
the cutover day; the cutover-only flips (307 → 308, removal of the global
noindex, root title, `/visa` → `/visa-oracle`) are explicitly NOT part of this
slice. Source of truth for every item: `docs/reviews/2026-09-10-seo-url-migration-map.md`.

## Items, each with its test

1. **LLM discovery files (orphans today).** Copy verbatim from
   `apps/mouth/public/`: `llms.txt`, `llms-full.txt`, `llms-id.txt`,
   `llms-kbli.txt`, `sitemap-ai.xml` into `apps/website/public/`. Test: the five
   files exist and are byte-identical to the Mouth originals.
2. **`src/app/sitemap.ts`.** Base URL `process.env.WEBSITE_PUBLIC_ORIGIN` else
   `https://balizero.com`. Entries, no `priority`/`changeFrequency`, `lastModified`
   only where known:
   - static: `/`, `/services`, `/services/immigration`, `/services/company-setup`,
     `/services/tax`, `/services/property`, `/news`, `/team`, `/contact`, `/about`,
     `/kbli`, `/kbli-explorer`, `/kbli/sectors`, `/kbli/builder`, `/kbli/decoder`,
     `/property/eligibility`, `/tax-calendar`, `/taxes/gap`, `/book`, `/zoning`,
     `/privacy`, `/terms`, `/llms.txt`, `/llms-full.txt`, `/llms-id.txt`;
   - visa tools: `/visa/match`, `/visa/clock`, `/visa/second-home`,
     `/visa/second-home/id`, `/visa/second-home/it`, `/visa/second-home/studio`;
   - the six category indexes `/{visas,business,taxes,property,living,trends}`;
   - every article from `loadPublicCatalog()` (disk rows plus API-only rows),
     `lastModified` = `publishedAt`; exclude anything `decodePublicArticle` would
     refuse is NOT required here (catalog rows are already base editions);
   - every KBLI code from `getAllCodes()` in `src/features/kbli/catalog.server.ts`
     as `/kbli/<code>`, `lastModified` from `data/kbli-dataset-version.json` when
     readable, else omitted; every sector from `getSections()` with
     `codeCount > 0` and `/^[A-Z]$/` as `/kbli/sectors/<id>`.
     Never include: `/services/visa`, `/services/company`, `/visa`, `/journal`,
     `/v2/*`, `/visa-oracle*`, `/visa/voa`, `/prime*`, `/legacy/*`, `/api/*`, any
     `?lang=` variant. Test: counts (≥ 808 articles, 1559 codes, 21 sectors),
     forbidden paths absent, base URL follows the env variable, no duplicates.
3. **`src/app/robots.ts`, environment-bound.** When `WEBSITE_PUBLIC_ORIGIN` is
   unset (preview): `Disallow: /` for all agents, no sitemap line. When set:
   `Allow: /` plus the production disallow list (`/api/`, `/_next/`, `/*?tag=`,
   `/*&tag=`, `/dashboard`, `/clients`, `/chat`, `/settings`, `/analytics`,
   `/intelligence`, `/whatsapp`, `/email`, `/documents`, `/knowledge`, `/cases`,
   `/omnichannel`, `/admin`, `/login`, `/portal/login`, `/portal/login-upgraded`,
   `/legacy/`, `/visa-oracle/unlock`), `Allow: /_next/static/`, `/_next/image`,
   the three llms files, and `sitemap: <origin>/sitemap.xml`. Test both branches.
4. **Per-route noindex that must survive the removal of the global one.** Add
   `robots: { index: false, follow: false }` to the metadata of
   `/visa-oracle/unlock`, `/visa-oracle/privacy`, `/visa/voa`, `/prime`,
   `/v2/company/careers`, `/v2/company/press` (pages or their nearest layout;
   `visa/voa` and `prime` may need a `generateMetadata`/`metadata` export
   added). Test: rendered metadata of each carries `noindex`.
5. **Metadata gaps (dev title leaks).** Add `metadata`/`generateMetadata` with
   `title`, `description` and `alternates.canonical` (path-relative, e.g.
   `/visas`) to: `/` (home), `[category]` (one per category, label from
   `journal-categories.ts`), `kbli/sectors/[id]` (section name from
   `getSections()`), `kbli/[code]` (add `description` from the English title and
   `canonical`), `/visa-oracle`, `/news`. Titles follow the existing pattern
   `<Page> | Bali Zero`. Test: each page's metadata has a non-default title and
   the expected canonical.
6. **Duplicates → preview redirects (307 now, flipped at cutover).**
   `src/app/v2/company/about/page.tsx` becomes `redirect("/about")`.
   `src/app/journal/page.tsx` becomes a redirect to `/news` preserving the query
   string (`?category=`, `?q=`, `?page=`); `src/app/news/page.tsx` becomes the
   real page (move the current journal implementation there; keep the "Journal"
   label in the UI). Rewrite every internal `href` that points at `/journal` or
   `/journal?…` to `/news` (breadcrumb, "Continue reading", JournalIndex,
   Header/Footer, tests). Test: `/journal?category=taxes` → 307 `/news?category=taxes`;
   no remaining `"/journal` string in `src/` except the redirect route.
7. **Internal alias bug.** Add `["/visa/second-home-e33", "/visa/second-home"]`
   to the `exact` list in `next.config.ts` (permanent: false like the others),
   so it no longer leaves for the legacy origin. Test: config redirect present.
8. **Archive scan memo.** `listAuthoredEnglishArticles()` in
   `src/lib/server/article-archive.ts` re-reads 808 files per request. Add a
   module-level memo: fingerprint = the `mtimeMs` and entry count of the 13
   archive folders (one `stat` + one `readdir` each); reuse the parsed list while
   the fingerprint is unchanged and younger than 5 minutes; expose
   `resetArticleArchiveMemo()` for tests. Test: second call does not call
   `readFile` (spy), a changed folder mtime invalidates.

## Deliberately excluded, with reason

- HTTP 503 for the `unavailable` article branch: an App Router page cannot set
  a 503 status; with the local loader the branch now only covers the six
  scraper `news_*` slugs, which stay `noindex` on the placeholder. Leave as is.
- `/visa` → `/visa-oracle` permanence and `/visa-oracle` indexability (D1),
  the 307 → 308 flips, the root layout title and the global `robots`/`X-Robots-Tag`
  removal: cutover day only.

## Acceptance

- `npm run typecheck` exit 0; `npm test` green (baseline 1343 passed, 1 skipped)
  plus the new tests above.
- Dev server on 127.0.0.1:3101 with `WEBSITE_PUBLIC_ORIGIN` unset:
  `/sitemap.xml` 200 with ≥ 2,400 `<loc>`; `/robots.txt` 200 containing
  `Disallow: /`; `/llms.txt` 200; `/journal?category=taxes` 307 to
  `/news?category=taxes`; `/v2/company/about` 307 to `/about`;
  `/visa/second-home-e33` 307 to `/visa/second-home`; `/visas` title no longer
  "Bali Zero — Website development". If the sandbox refuses to bind the port,
  say so and provide the equivalent unit evidence; the verifier runs the HTTP
  checks.
- Write `docs/handoffs/2026-09-10-cutover-prep-slice-evidence.md`: files
  changed, test and typecheck summary lines, item-by-item status, deviations.
