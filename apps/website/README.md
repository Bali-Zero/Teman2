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
npm test
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
- Four explicit service entry paths.
- Contextual contact links for service topics, Surya and Ari.
- Portal feature tabs for documents, applications and messages, including keyboard navigation.
- Journal previous/next controls with coherent story links and content.
- Local section anchors and a skip link.

The portal is an illustrative feature preview, not a signed-in account. Existing external links open the corresponding service, portal, article or contact destination; their destination workflows are outside this app's smoke test.

## Content and integration boundaries

- E-VOA pricing is referred to its service destination, avoiding an unverified fixed price in this app.
- The Google review count, rating and dated snapshot were inherited from Revision 19 and have not been independently verified against Google.
- Journal records are static prototype content; there is no CMS integration yet.
- No customer data, authentication, backend submission or production API integration is implemented.
- Faysha and Sahira are excluded from the team presentation.
- The original paper, green, copper and serif direction is preserved. Imported CSS still contains historical selectors and needs consolidation.

## Validation of this milestone

- 12 tests passed across component and whole-page checks.
- TypeScript validation passed.
- Next.js production build passed.
- Local HTTP response returned 200 with the no-index header.
- Browser smoke checks at observed viewport widths of 812 and 354 CSS pixels found no broken images, unresolved internal anchors or horizontal page overflow.
- Mobile menu and portal tab changes were exercised in the browser; no browser warnings or errors were observed during that check.

This is targeted development validation, not a full accessibility audit, cross-browser certification or production readiness approval.

See [DEVELOPMENT.md](DEVELOPMENT.md) for the next implementation lanes.
