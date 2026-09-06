# Website development plan

## Milestone 1 — implemented

The Revision 19 homepage is now a component-based Next.js application in an isolated worktree. Navigation, service entry paths, portal feature tabs and Journal controls have automated coverage. The main checkout and existing deployment configuration are unchanged.

## Milestone 2 — parallel implementation lanes

Each lane should receive a bounded assignment and exclusive file ownership. Changes to shared page composition, global styles and dependency files stay with the coordinating session. These are planned lanes, not currently running jobs.

| Lane             | Responsibility                                                                 | Reviewable result                                                                                        |
| ---------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| Service journeys | Immigration, company setup, tax and property landing pages                     | A visitor can choose a service, understand the next step and reach a contextual contact or existing tool |
| Journal          | Article model, listing and article templates                                   | Consistent titles, images, dates, category labels and working article destinations                       |
| Design system    | Consolidate inherited CSS, responsive rules, typography and shared controls    | Reusable components with keyboard, mobile and visual checks                                              |
| Integration      | Verify external destinations, review snapshot and authoritative pricing source | A documented content contract with verified sources and explicit fallback behavior                       |

Start with service journeys and design-system cleanup in separate ownership areas. Integrate each lane into this development branch only after reviewing its diff and tests.

## Acceptance checks for the next milestone

1. Each service page has a clear purpose, expected next step and one primary action.
2. Navigation works between homepage and new local pages without dead ends.
3. Prices and regulated claims have authoritative sources; unsupported details are omitted.
4. Desktop, tablet and narrow mobile views are checked for wrapping, clipping and fixed-widget collisions.
5. Keyboard navigation and visible focus are checked throughout interactive flows.
6. A clean dependency installation reproduces tests, type checking and build.
7. Large image payloads and inherited CSS are reduced without changing the approved visual direction.

## Release boundary

Keep this application outside the production deployment configuration. Do not push to main, merge, arm auto-merge or deploy as part of development. Production integration requires its own explicit mandate and independent review.
