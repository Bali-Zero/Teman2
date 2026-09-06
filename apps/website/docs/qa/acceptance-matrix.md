# Website R19 independent QA acceptance matrix

## Scope and authority

- Lane: `05-independent-qa`
- Contract: `website-v1`
- Frozen seed: `687075491cccf496a66da657ed4b16c31d87db41`
- Baseline under test: local production server at `http://127.0.0.1:3105`
- Browser surface: dedicated in-app browser tab; measured CSS viewport widths
- Evidence scope: functional, responsive, keyboard, semantic, console, route, link,
  and asset spot checks. This is not a full WCAG conformance audit.

## Baseline matrix

| Acceptance item                               | Seed status | Evidence                                                                                                                                                                                                                                                                                                                                                                             |
| --------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Frozen seed provenance                        | DONE        | Replacement branch `codex/website-05-independent-qa-app-only` started clean at the exact frozen seed after the first checkpoint used the wrong repository-relative scope.                                                                                                                                                                                                            |
| Fresh isolated install                        | DONE        | `npx --yes npm@11.19.0 ci --workspaces=false --no-audit --no-fund` installed 130 packages. The known `fsevents@2.3.3` build-script warning remained.                                                                                                                                                                                                                                 |
| Existing automated tests                      | DONE        | `npm test`: 3 files and 12 tests passed.                                                                                                                                                                                                                                                                                                                                             |
| TypeScript check                              | DONE        | `npm run typecheck`: exit 0.                                                                                                                                                                                                                                                                                                                                                         |
| Production build                              | DONE        | `npm run build`: exit 0. Seed output contains `/` and `/_not-found`.                                                                                                                                                                                                                                                                                                                 |
| Required route contract                       | IN_PROGRESS | The seed intentionally implements only `/`; the other six milestone routes are pending WEBSITE 02 and WEBSITE 03. Candidate QA requires HTTP 200 HTML for all seven routes.                                                                                                                                                                                                          |
| 360 CSS px responsive pass                    | DONE        | `innerWidth=360`, `clientWidth=360`, `scrollWidth=360`; no document-level horizontal overflow. Mobile menu present.                                                                                                                                                                                                                                                                  |
| 390 CSS px responsive pass                    | DONE        | `innerWidth=390`, `clientWidth=390`, `scrollWidth=390`; no document-level horizontal overflow. Mobile menu present.                                                                                                                                                                                                                                                                  |
| 768 CSS px responsive pass                    | DONE        | `innerWidth=768`, `clientWidth=768`, `scrollWidth=768`; no document-level horizontal overflow. Desktop navigation present.                                                                                                                                                                                                                                                           |
| 1280 CSS px responsive pass                   | DONE        | `innerWidth=1280`, `clientWidth=1280`, `scrollWidth=1280`; no document-level horizontal overflow. Desktop navigation present.                                                                                                                                                                                                                                                        |
| 1440 CSS px responsive pass                   | DONE        | `innerWidth=1440`, `clientWidth=1440`, `scrollWidth=1440`; no document-level horizontal overflow. Desktop navigation present.                                                                                                                                                                                                                                                        |
| Mobile menu keyboard behavior                 | DONE        | At 360 px, Enter opened the menu, Tab moved to `Explore`, and Escape closed it and returned focus to the menu button.                                                                                                                                                                                                                                                                |
| Skip link and visible focus                   | DONE        | At 1440 px, the first Tab exposed `Skip to content` with a 3 px solid outline. Enter followed by Tab moved directly to the first main-content link.                                                                                                                                                                                                                                  |
| Portal tabs                                   | DONE        | Tablist and three tabs expose selected state. End selected Messages; Home then ArrowRight selected Applications and exposed its panel.                                                                                                                                                                                                                                               |
| Journal controls                              | DONE        | Enter on Next changed `01 / 02` to `02 / 02` and retained focus on the named control.                                                                                                                                                                                                                                                                                                |
| Internal fragment targets                     | DONE        | All 17 rendered `#fragment` link instances, representing 11 unique fragments, resolve to an element id.                                                                                                                                                                                                                                                                              |
| Homepage images                               | DONE        | A complete top-to-bottom lazy-load pass at 360 px loaded all 36 rendered images; none completed with `naturalWidth=0`.                                                                                                                                                                                                                                                               |
| Fixed-widget collision                        | BLOCKED     | QA-001: the fixed contact control covers underlying interactive content at every measured width. Owner: WEBSITE 00 — Control room.                                                                                                                                                                                                                                                   |
| Browser console                               | DONE        | No warning or error entries after the homepage interaction pass.                                                                                                                                                                                                                                                                                                                     |
| Semantic spot check                           | DONE        | `lang=en`; one header, navigation, main and footer; one h1; no heading-level jumps; no unnamed links/buttons/fields in the DOM heuristic; one tablist with three tabs.                                                                                                                                                                                                               |
| External destination truth and claim evidence | IN_PROGRESS | WEBSITE 04 reported that the `693 reviews` / `14 August 2026` snapshot is stale, the unauthenticated portal proves only a login surface, and public `/news?...` filters do not filter. The corrected smoke check fails if the stale snapshot, old `Tax Intelligence` label, or unsupported public filter URLs reappear. Exact candidate copy and adopted evidence remain NOT_TESTED. |
| Full seven-route journey pass                 | NOT_TESTED  | Await the coordinator-published integrated candidate SHA.                                                                                                                                                                                                                                                                                                                            |
| Final clean-checkout adoption recommendation  | NOT_TESTED  | Requires all lane outputs integrated and the exact candidate commit published by WEBSITE 00.                                                                                                                                                                                                                                                                                         |

## Existing-test audit and missing coverage

The seed contains 12 component and page tests across three files:

- `Entry.test.tsx` covers the mobile navigation disclosure, Enter/Tab/Escape
  focus flow, menu close behavior, hero category links and the absence of a fake
  text-input affordance.
- `Home.test.tsx` covers portal-tab keyboard navigation, preview/sign-in copy,
  Journal previous/next behavior, the four service links, contextual contact
  parameters and the Surya/Ari context.
- `page.test.tsx` covers homepage fragment ids, the single h1, referenced asset
  existence and the exclusion of Faysha and Sahira.

Those tests do not cover live HTTP status for the seven-route contract, real CSS
viewport behavior, horizontal overflow, fixed-control collision, lazy-image load
completion, browser-console failures, or evidence behind public claims and external
destinations. The dependency-free preview smoke check below covers the route,
fragment, SSR-asset and supported-copy portion; the remaining items require the recorded
browser pass and WEBSITE 04 evidence on the integrated candidate.

## Finding QA-001

- Route: `/`
- Viewports: 360, 390, 768, 1280 and 1440 CSS px
- Steps: load the production preview; scroll through the page while keeping the
  fixed `Talk to Bali Zero` control visible; inspect intersections with other
  interactive rectangles.
- Expected: the fixed contact control remains available without obscuring another
  link or button.
- Actual: the fixed control intersects underlying interactive cards or story/team
  links at sampled scroll positions. At 390 px it covers the Surya E-VOA contact
  card around `scrollY=3679` and the Ari team link around `scrollY=11037`. The same
  class of overlap occurs at 768, 1280 and 1440 px.
- Severity: MEDIUM (P2)
- Evidence: browser rectangle-intersection measurements and visual confirmation at
  390 px; shared evidence record `evidence/05-independent-qa/baseline-browser.json`.
- Exact owner: WEBSITE 00 — Control room, which owns `src/app/page.tsx` and
  `src/app/globals.css`.
- Acceptance for correction: no overlap with any visible interactive element at
  the five required viewport widths during a top-to-bottom scroll pass.

## Reusable preview smoke check

Run against a coordinator-approved production preview:

```sh
cd apps/website && node tests/qa/site-smoke.mjs http://127.0.0.1:3105
```

The script is dependency-free and fails closed when any required route is not an
HTTP 200 HTML response, when a homepage fragment target is missing, when a rendered
homepage asset fails, when a supported homepage invariant changes, when a known stale
Google snapshot or product label reappears, or when the homepage links to unsupported
public Journal filters.
