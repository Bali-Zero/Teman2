# Bali Zero website — development application

An isolated Next.js implementation of the approved design direction from Homepage Revision 19. This is the development foundation for the public website, with React components and working navigation rather than a standalone HTML mockup.

## Isolation

- Branch: `agent/air-m5/infra/website-r19`.
- Worktree: `/Users/balizero/nuzantara/.worktrees/infra-website-r19`.
- Initial base: cached `origin/main` at `61641c428f`; the worktree broker did not refresh the remote successfully. This is not a claim of parity with the latest remote main.
- All implementation files live in `apps/website`. Root workspace configuration and deployment configuration are unchanged.
- The app is not registered in the root workspace or connected to a deployment project.
- Development and preview servers bind to `127.0.0.1:3100`.
- Responses carry `X-Robots-Tag: noindex, nofollow, noarchive`; page metadata also disables indexing. These directives are not access control.

No merge, push, deployment or production integration is part of this milestone.

## Run

Use Node.js 22.12 or newer and npm 11.19.0. Run these commands from this directory:

```sh
npx --yes npm@11.19.0 ci --workspaces=false
npm run dev
```

Open `http://127.0.0.1:3100`.

```sh
npm test -- --maxWorkers=1 --no-file-parallelism
npm run typecheck
npm run build
```

The coordinator repeated installation from the standalone lockfile with npm 11.19.0 on Node.js 22.22.3. It installed 130 packages successfully. npm reported an unapproved install script for optional fsevents; no script approval override was used. Validation on another operating system remains separate.

## Structure

- `src/app`: page composition, metadata and global styles.
- `src/components`: header, entry paths, services, E-VOA, Second Home Studio, reviews, portal preview, Journal, team, contact and footer.
- `src/content`: typed service and story records.
- `public/assets`: the referenced Revision 19 imagery.
- `source-manifest.json`: source and asset provenance with checksums.

## Working behavior

- Mobile navigation with keyboard dismissal and focus restoration.
- Local `/services` overview and four service routes: immigration, company-setup, tax and property.
- Contextual contact links for service topics, Surya and Ari.
- Clearly labelled portal interface illustrations with keyboard-accessible tabs and a separate account sign-in link.
- Local `/journal` index and homepage carousel sharing six verified source records.
- Local section anchors and a skip link.

The portal is an illustrative feature preview, not a signed-in account. Existing external links open the corresponding service, portal, article or contact destination; their destination workflows are outside this app's smoke test.

## Content and integration boundaries

- E-VOA pricing is referred to its service destination, avoiding an unverified fixed price in this app.
- The stale Google rating snapshot was removed; visitors can open the current Google listing.
- Journal titles, dates, categories and destinations were checked against their published sources. Full articles open at source; local article bodies and CMS integration remain outside this milestone. Unsupported external filters were removed.
- No customer data, authentication, backend submission or production API integration is implemented.
- Faysha and Sahira are excluded from the team presentation.
- The original paper, green, copper and serif direction is preserved. Shared design primitives use scoped CSS. Historical homepage CSS remains; migration is documented in `docs/design-system`.
- The unrelated Telegram destination is blocked and absent from the UI.
- External destination and pricing authority evidence lives in `src/content/evidence` and `docs/integrations`; no client workflow or current price is promised by this preview.

## Validation and checkpoint

Run a standalone clean install, serialized tests, typecheck and production build before freezing a candidate. The independent QA suite is `node tests/qa/site-smoke.mjs http://127.0.0.1:3105`; its acceptance matrix is in `docs/qa`. The exact validated commit, outcomes, local preview and evidence paths are recorded by the coordinator in `development-control/integration.json` beside the original R19 source folder.

The initial seed passed 12 tests, typecheck, build and asset-provenance checks. Subsequent integrated checks supersede that baseline; use the exact candidate report rather than extrapolating from the seed. Five concurrent test workers timed out during host saturation; serialized execution avoids that contention.

This is targeted development validation, not a full accessibility audit, cross-browser certification or production readiness approval. The 22 original assets remain byte-identical (approximately 29 MB); payload optimization is a separate milestone.

See [DEVELOPMENT.md](DEVELOPMENT.md) for ownership, routes and the release boundary.
