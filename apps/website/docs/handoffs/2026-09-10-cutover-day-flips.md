# Cutover-day flips — prepared 10 September 2026, Pro

Owner decision (Zero, 2026-09-10: "go"). Prepared in advance on the dedicated
branch `agent/nuzantara/infra/website-cutover-flips` from lane tip
`961ac9e744`. This branch must NOT be merged into `codex/website-pro-continuation`
or deployed until the cutover day: every change below makes the site
indexable or makes a redirect permanent. Local implementation only; commit on
this branch is allowed; no push, merge, arm or deployment. Do not edit
anything under `apps/mouth`, `apps/bali-zero-magazine` or `data/`.

Background: `docs/reviews/2026-09-10-seo-url-migration-map.md` (risks 1 and
2, decisions D1–D4 accepted as recommended). Baseline: 1356 tests passed,
1 skipped; typecheck exit 0.

## Flips, each with its test

1. **Permanent redirects.** `next.config.ts` `redirects()`: every
   `permanent: false` becomes `permanent: true` (Next emits 308). Pages using
   `redirect()` switch to `permanentRedirect()`: `services/visa`,
   `services/company`, `kbli-navigator/[[...retainedPath]]`, `journal`,
   `v2/company/about`. Route handlers: `tax/gap` and `visa-v2` respond 308
   instead of 307; in `visa/[[...retainedPath]]/route.ts` the bare `/visa` →
   `/visa-oracle` becomes 308. `retainedHandoff` (cross-host handoff to the
   legacy origin) stays 307. Update the tests that assert 307 or `redirect`
   for these routes. Test: config entries all `permanent: true`; handler
   responses 308; `retainedHandoff` still 307.
2. **Indexability.** Root `layout.tsx`: remove `robots: { index: false,
follow: false }`; set `title` to `Bali Zero | Immigration, Company Setup,
Tax & Property in Indonesia` with `title.template` `%s | Bali Zero` only if
   it does not double the suffix already present on page titles (check the
   existing `... | Bali Zero` pattern and keep titles single-suffixed).
   `next.config.ts` `headers()`: remove the global `X-Robots-Tag` header entry
   (keep the function if other headers exist; delete it if it becomes empty).
   Test: root metadata has no `robots` noindex; config headers carry no
   `X-Robots-Tag`; the six per-route noindex pages from the prep slice
   (`/visa-oracle/unlock`, `/visa-oracle/privacy`, `/visa/voa`, `/prime`,
   `/v2/company/careers`, `/v2/company/press`) still resolve to `noindex`;
   `/v2/privacy`, `/v2/terms`, `/v2/cookies`, `/visa/privacy`, `/visa/terms`,
   `/prime/proposal/[token]`, `/visa/match/[hash]`, `/visa/clock/[hash]` still
   `noindex`.
3. **D1 — `/visa-oracle` becomes the indexable public selector.** Its metadata
   (added in the prep slice) must have no `robots` noindex and canonical
   `/visa-oracle`; add `/visa-oracle` to `staticPaths` in `sitemap.ts`. Test:
   sitemap contains `/visa-oracle`, still excludes `/visa`, `/visa-oracle/unlock`,
   `/visa-oracle/privacy`.
4. **Nothing else.** No content, design or route changes. `robots.ts` and
   `sitemap.ts` stay environment-bound (they already switch on
   `WEBSITE_PUBLIC_ORIGIN`).

## Acceptance

- `npm run typecheck` exit 0; `npm test` green (baseline 1356 passed, 1
  skipped, adjusted only where a 307/`redirect` assertion had to become
  308/`permanentRedirect`).
- Evidence file `docs/handoffs/2026-09-10-cutover-day-flips-evidence.md` with
  files changed, summary lines, per-flip status and deviations. If the sandbox
  cannot bind a port, say so; the verifier runs the HTTP checks
  (`/services/visa` 308, `/journal` 308, `/tax/gap` 308, `/visa` 308,
  `/kbli-navigator` 308, `/` with no `noindex` meta and no `X-Robots-Tag`,
  `/visa-oracle` indexable, `/visa-oracle/unlock` still noindex, root title).
