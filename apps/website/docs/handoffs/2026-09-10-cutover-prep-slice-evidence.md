# Cutover preparation slice — implementation evidence

Date: 10 September 2026  
Scope: `apps/website` only  
Branch state: working tree only; no commit, push, merge or deploy performed.

## Verification summaries

Final `npm test` run, exit 0:

```text
 Test Files  107 passed | 1 skipped (108)
      Tests  1356 passed | 1 skipped (1357)
```

Final `npm run typecheck` run, exit 0:

```text
> @balizero/website-development@0.1.0 typecheck
> tsc --noEmit
```

Formatting:

```text
npx prettier --write <all changed TypeScript, TSX and Markdown files>
```

`git diff --check -- apps/website` also exited 0 with no output. Independent
`cmp` checks for all five copied discovery files exited 0.

## Item status

1. **PASS — LLM discovery files.** Copied all five files byte-for-byte from
   Mouth. `src/app/discovery-files.test.ts` compares lengths and every byte.
2. **PASS — sitemap.** Added the environment-aware sitemap with the specified
   static, visa-tool, category, article, KBLI-code and non-empty sector routes;
   known article and KBLI dates only; URL deduplication; no priority or change
   frequency. `src/app/sitemap.test.ts` verifies 808 catalog fixtures, 1,559
   codes, 21 sectors, exclusions, origin selection, dates and uniqueness.
3. **PASS — robots.** Added preview fail-closed and configured-origin production
   branches with the exact allow/disallow rules and sitemap URL.
   `src/app/robots.test.ts` covers both branches.
4. **PASS — persistent route noindex.** Added explicit noindex/nofollow metadata
   to Visa Oracle unlock/privacy, VOA, Prime, Careers and Press.
   `src/app/cutover-metadata.test.ts` verifies all six.
5. **PASS — metadata gaps.** Added title, description and relative canonical
   metadata for home, every Journal category, KBLI sections/codes, Visa Oracle
   and News. Added `metadataBase` at the root so relative canonicals resolve.
   `src/app/cutover-metadata.test.ts` verifies all route classes.
6. **PASS — duplicate redirects and News canonicalization.** Made News the real
   Journal index; made `/journal` a query-preserving redirect; made legacy About
   redirect to `/about`; rewrote internal links and related destination context
   to `/news`. Redirect, rendering and source-scan tests cover these contracts.
7. **PASS — Second Home alias.** Added the temporary exact redirect to
   `/visa/second-home`. `src/lib/retained-routes.test.ts` verifies the generated
   Next config entry.
8. **PASS — archive scan memo.** Added a five-minute module memo keyed by the
   13-folder `mtimeMs` plus entry-count fingerprint, while retaining folder
   rechecks and exposing `resetArticleArchiveMemo()`. The dedicated test proves
   a second call performs no article `readFile` and a folder mtime change
   invalidates the parsed-list identity.

## Files changed

Configuration, routing and metadata:

- `next.config.ts`
- `src/app/layout.tsx`
- `src/app/page.tsx`
- `src/app/[category]/page.tsx`
- `src/app/[category]/[slug]/page.tsx`
- `src/app/news/page.tsx`
- `src/app/journal/page.tsx`
- `src/app/kbli/[code]/page.tsx`
- `src/app/kbli/sectors/[id]/page.tsx`
- `src/app/robots.ts`
- `src/app/sitemap.ts`
- `src/app/visa-oracle/layout.tsx`
- `src/app/visa-oracle/page.tsx`
- `src/app/visa-oracle/privacy/layout.tsx`
- `src/app/visa-oracle/unlock/layout.tsx`
- `src/app/visa/voa/page.tsx`
- `src/app/prime/page.tsx`
- `src/app/v2/company/about/page.tsx`
- `src/app/v2/company/careers/page.tsx`
- `src/app/v2/company/press/page.tsx`

Journal links, destination context and nearby documentation:

- `src/app/about/page.tsx`
- `src/app/journal/DATA-CONTRACT.md`
- `src/app/journal/HOMEPAGE-ADOPTION.md`
- `src/components/Entry.tsx`
- `src/components/Footer.tsx`
- `src/components/HomeJournal.tsx`
- `src/components/Journal.tsx`
- `src/components/journal/ArticleComponents.tsx`
- `src/components/journal/ArticleReaderActions.tsx`
- `src/components/journal/JournalIndex.tsx`
- `src/components/journal/JournalSearchControls.tsx`
- `src/content/destinations.ts`
- `src/content/journal.ts`
- `src/features/supporting/CompanyPage.tsx`
- `src/lib/destinations/lead-handoff.ts`

Archive implementation:

- `src/lib/server/article-archive.ts`

Tests added or updated:

- `src/app/cutover-metadata.test.ts`
- `src/app/discovery-files.test.ts`
- `src/app/journal/page.test.tsx`
- `src/app/news/internal-links.test.ts`
- `src/app/news/page.test.tsx`
- `src/app/robots.test.ts`
- `src/app/sitemap.test.ts`
- `src/app/v2/company/about/page.test.tsx`
- `src/components/Company.test.tsx`
- `src/components/Entry.test.tsx`
- `src/components/Home.test.tsx`
- `src/components/HomeJournal.test.tsx`
- `src/components/LegacySections.test.tsx`
- `src/components/journal/JournalIndex.search.test.tsx`
- `src/components/journal/JournalSearchControls.test.tsx`
- `src/lib/destinations/contact-context.test.ts`
- `src/lib/destinations/lead-handoff.test.ts`
- `src/lib/retained-routes.test.ts`
- `src/lib/server/article-archive.test.ts`

Copied public files:

- `public/llms.txt`
- `public/llms-full.txt`
- `public/llms-id.txt`
- `public/llms-kbli.txt`
- `public/sitemap-ai.xml`

This evidence file is also new:

- `docs/handoffs/2026-09-10-cutover-prep-slice-evidence.md`

## Deviations and observations

- The localhost HTTP smoke run was not executed because the operator explicitly
  prohibited network calls for this slice. Equivalent deterministic unit tests
  cover sitemap/robots metadata output, copied assets, redirects and category
  metadata. The separate verifier can run the specified HTTP checks.
- Vitest emitted its existing Vite native-config warning and jsdom's
  `Not implemented: navigation to another Document` diagnostic; neither caused
  a test failure. There are no implementation deviations from items 1–8.
