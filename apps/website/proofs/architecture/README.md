# Publishing boundary proofs

Run from `apps/website` with Node >=22.12 and npm >=11:

```sh
npm ci
npm run test:architecture
```

Run inside the complete repository worktree: the proof imports the actual
`apps/mouth/src/lib/blog/articles.ts` reader and copies the unchanged
`apps/mouth/src/content/articles/tech/fintech-payments-indonesia.mdx` article
into an owned temporary directory. Three synthetic records characterize draft,
missing-date and no-index behavior. The directory is removed after the suite.

The proof uses the website's declared `gray-matter` dependency. The legacy
reader's `next/cache` is deliberately replaced by a pass-through function;
backend fetch returns 503 to exercise the local MDX fallback. Neither cache
invalidation nor the production backend is tested.

A one-record adapter restores explicit publishing metadata from the raw MDX.
The same Journal renders with direct delivery and actual loopback HTTP delivery.
The HTTP server binds an ephemeral localhost port and closes after the test.
This is a rendering/data-contract comparison, not a deployment benchmark.

Two characterization assertions document undesirable legacy behavior: the draft
is listed and an undated record acquires a date. Passing means the defect was
reproduced; it does not approve that behavior or prove exposure in production.

The v1 decoder remains an isolated characterization. The homepage now consumes
the separate Magazine v2 boundary described below.

## Magazine v2 integration (current)

magazine-publication.test.tsx executes the actual publication repository against
real migrations in an in-memory SQLite database. Fixtures use repository staging
and finalization, plus synthetic rights/visibility setup. Tests cover current
amendments behind historical edition pins, deduplication, malformed dates and
evidence, unavailable reads, unpublished/quarantined records, late withdrawal and
rights revocation. No production DB, ingress authorization or R2 bytes are tested.

magazine-integration.test.tsx continues through the strict v2 decoder and both
real Journal components. It verifies inert fixture destinations, public-field
allowlisting, source/revision rendering, and distinct terminal states without
stale cards. The default server loader is unavailable; sample content requires
WEBSITE_EDITORIAL_FIXTURE=1 explicitly. The sample is never an error fallback.

Verified locally with Node 26.5.0 and npm 11.19.0 installation. The package minimum
Node 22.12 is not a tested compatibility claim for node:sqlite. Run the complete
worktree, because the fixture resolves sibling Magazine migrations. Run typecheck
and build sequentially: Next recreates .next/types during build.
