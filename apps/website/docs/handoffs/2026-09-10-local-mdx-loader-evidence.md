# Local MDX loader evidence — 10 September 2026

## Files changed

- `src/lib/server/article-archive.ts`
- `src/lib/server/article-translations.ts`
- `src/lib/server/public-editorial.ts`
- `src/lib/server/public-catalog.ts`
- `src/lib/server/public-editorial.test.ts`
- `src/lib/server/public-catalog.test.ts`
- `src/lib/server/home-editorial.test.ts`
- `docs/handoffs/2026-09-10-local-mdx-loader-evidence.md`

The pre-existing handoff and SEO review files were not edited. No file outside
`apps/website` was written.

## Acceptance evidence

Final `npm test` exit code: `0`.

```text
Test Files  99 passed | 1 skipped (100)
     Tests  1343 passed | 1 skipped (1344)
```

The suite contains the five new handoff tests with their exact required names.
The assigned worktree has more existing tests than the 1,045-test snapshot in
the handoff; the final total is therefore 1,343 passed rather than 1,050.

Final `npm run typecheck` exit code: `0`.

```text
> @balizero/website-development@0.1.0 typecheck
> tsc --noEmit
```

The disk-only catalog probe executed the production loader with the legacy
fetch stubbed to fail and reported:

```text
disk_catalog_rows=808
```

API-only rows appended in that no-origin probe: `0`. No network content call
was made. Existing mocked legacy-catalog tests continue to cover API-only row
loading and pagination.

Because the sandbox refused a listener on `127.0.0.1:3100`, an additional
temporary server-layer smoke test exercised the same Journal and Home loaders
with legacy fetch forced to fail. It passed and was removed after execution:

```text
Test Files  1 passed (1)
     Tests  1 passed (1)
```

The smoke confirmed a ready Journal result for
`property/leasehold-vs-freehold` and a non-empty ready Home feed without a
working legacy origin.

## Deviations

- The requested HTTP `curl` checks on port 3100 could not run. The exact
  `npm run dev` attempt failed before startup with
  `listen EPERM: operation not permitted 127.0.0.1:3100`; this execution
  sandbox does not permit binding a local listener. No preview process was
  left running. The deterministic server-layer smoke above covers the loader
  behavior, but it is not presented as HTTP route evidence.
- `home-editorial.ts` required no source change: its existing implementation
  already consumes `loadPublicCatalog()` and `loadPublicArticleResult()`. The
  temporary no-origin smoke verified that composition directly.
