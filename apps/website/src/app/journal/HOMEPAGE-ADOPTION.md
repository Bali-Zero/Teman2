# Homepage Journal adoption proposal

The coordinator-owned homepage Journal should keep its compact editorial role while delegating the complete inventory to `/journal`.

Recommended adoption after this lane is integrated:

1. Change the existing “Explore the Journal” destination from the legacy external `/news` URL to the local `/journal` index.
2. Keep a small, verified selection on the homepage. Read card metadata from `getPublicJournalArticles()` so image, title, category, date and source destination cannot drift apart.
3. Remove homepage interest filters unless the verified corpus and destination contract prove that those query parameters produce useful results.
4. Do not introduce local `/journal/[slug]` links until authorized article documents exist. Source-only records must continue to open their verified original destinations.
5. Preserve an explicit empty state if no record passes verification.

This is a patch proposal only. `src/components/Journal.tsx`, `src/content/stories.ts` and homepage composition remain coordinator-owned and are intentionally unchanged in this lane.
