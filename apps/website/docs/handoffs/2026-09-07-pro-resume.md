# Website continuation on Pro

Owner handoff: 2026-09-07. Code and documents are English; owner communication is Italian.

## Mandate

Recover the Bali Zero Magazine editorial engine. Build the bodywork ourselves,
consistent with the approved R19 website. Keep development isolated from main
and production. This mandate does not authorize a release, merge, auto-merge,
production mutation, or outward publication.

## Exact continuation location

- Source machine: Air-M5.
- Source worktree: `/Users/balizero/nuzantara/.worktrees/infra-website-r19`.
- Committed baseline: `b740b2cc3e94b1a46c9e9811bb369289fc21ea3d`.
- Source branch: `agent/air-m5/infra/website-r19`.
- Pro repository: `/Users/nuzantara/nuzantara`.
- Pro continuation worktree: `/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro`.
- Pro continuation branch: `codex/website-pro-continuation`.
- Transfer package: `/Users/nuzantara/website-handoffs/2026-09-07-r19/`.

The baseline plus working-tree overlay is the checkpoint. HEAD alone does not
include the current Team implementation, publishing proof, shared skill or
reviews. The package contains a Git bundle, a binary patch, a file overlay,
checksums and a source-file manifest. Preserve the uncommitted state; do not
discard it because the branch has a clean-looking baseline commit.

## Completed work to preserve

- R19 public homepage, service journeys and Journal index.
- Compact homepage founder band; full existing roster on `/team`.
- Faysha and Sahira excluded by owner instruction. Do not reintroduce them.
- Ari owns Second Home Studio; Surya owns E-VOA.
- Warm paper, forest, copper, editorial type, original logo, ocean and book.
- Photographic background removal authorized for portraits; no synthetic fake
  transparency or replacement faces.
- Shared `.agents/skills/website` instructions and vendor discovery aliases.
- Production comparison, actual Claude/Gemini panel reports and synthesis.
- Journal accepts records from its server parent. The homepage still consumes
  the checked snapshot; the strict feed decoder is not a live integration.
- Isolated proof compares direct/HTTP consumption with a real legacy MDX reader.

## Read in order

1. Applicable repository instructions, `apps/website/AGENTS.md` and
   `.agents/skills/website/SKILL.md` with `references/state.md`.
2. `apps/website/docs/reviews/2026-09-07-website-report.md`.
3. `apps/website/docs/reviews/2026-09-07-architecture-proof.md`.
4. `apps/website/docs/reviews/2026-09-07-magazine-legacy-review.md`.
5. `apps/website/docs/reviews/2026-09-07-production-transplant.md`.
6. `apps/website/docs/reviews/2026-09-07-panel/REPORT.md` and adjudication as needed.

## New focus: one useful editorial engine

Inspect `apps/bali-zero-magazine/lib/server/magazine-read-model.ts`, public
reading/media routes, publication visibility and correction contracts, plus
`apps/zantara-media/zantara_media/magazine/`. Compare with the existing MDX/backend
feed proof before selecting an adapter. Do not duplicate collection or publishing.

Preserve approved publication state, takedowns, source evidence, real dates,
corrections and authorized media. Exclude internal jobs, raw source packets,
NotebookLM identifiers, client PII, credentials and operational workspace data
from the public website contract. Do not assume the old public API is suitable
without reading its actual behavior.

Known defects to avoid: failure rendered as empty edition; draft inclusion;
invented fallback dates; demo articles on read failure; internal publishing
vocabulary in customer UI. Source-level defects do not prove current production
exposure. The supplied Magazine deployment displayed a private access screen,
while newer repository code describes public editorial access; version parity
remains unverified. Do not change access policy to bypass that screen.

Start with one end-to-end development slice: approved editorial record ->
explicit adapter -> validated public feed -> current R19 Journal. Carry article
canonical URLs and image rights/visibility correctly. Decide whether article
detail remains at its existing destination before adding another article route.
Keep publication authorization separate from link reachability and noindex.

Deployment topology remains open. Reusing the engine does not require importing
the old visual app or coupling marketing to authenticated providers. Preserve
useful user outcomes; improve inherited architecture when evidence supports it.

## Verification and resources

Prior recorded checks: 55 website tests, 5 architecture tests, typecheck and
optimized build passed; desktop/mobile Journal checks passed. These are prior
observations, not fresh Pro results. Re-run on Pro after dependency installation.

From `apps/website`: `npm ci`, `npm test -- --maxWorkers=1 --no-file-parallelism`,
`npm run test:architecture`, `npm run typecheck`, `npm run build`.
Inspect declared Node/npm versions first. Do not modify the lockfile merely
because the machine changed. Check port 3100 ownership before starting a single
preview with `npm start`. Reopen localhost in the Pro app; M5 localhost is a
different process. Do not copy node_modules, build caches or secrets from M5.

Project skill aliases are relative. Global aliases may still be absent or point
elsewhere on Pro: inspect them and use the canonical file directly rather than
overwriting an unrelated installed skill. Historical evidence contains M5 paths;
resolve the same repository-relative files in the Pro worktree. Visual evidence
is included in the transfer package's `output/playwright` files.

Do not reopen the six archived app tasks or start a large model panel by default.
Use bounded independent reviews when needed; send specific research questions to
Gemini through the sanctioned subscription route. Record actual model provenance.
The final UI can be independently reviewed by Claude; do not self-approve release.

## Required handback

Record the exact checkpoint, changed files, source-to-public-field mapping,
tests actually run, desktop/mobile evidence, unresolved deployment questions and
the next bounded slice. Preserve the one-preview resource policy. Deliver code
and an updated handoff; the production cutover stays outside this mandate.
