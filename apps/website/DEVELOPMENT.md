# Website development checkpoint

The R19 homepage, five service routes and Journal index are assembled locally under contract `website-v1`. The app remains isolated from the root workspace and production deployment configuration.

## Routes

| Route                     | Purpose                                                      |
| ------------------------- | ------------------------------------------------------------ |
| `/`                       | R19 homepage, team, contacts and compact editorial selection |
| `/services`               | Four service journeys                                        |
| `/services/immigration`   | Immigration and residence planning                           |
| `/services/company-setup` | Company setup discussion                                     |
| `/services/tax`           | Tax and accounting discussion                                |
| `/services/property`      | Property and due-diligence discussion                        |
| `/journal`                | Six source-bound editorial records                           |

No local article detail route is exposed. The reusable article template has an explicitly excluded development fixture until authorized article content exists. Unknown service slugs return 404.

## Ownership

| Task                                  | Exclusive responsibility                                                      |
| ------------------------------------- | ----------------------------------------------------------------------------- |
| WEBSITE 00 — Control room             | Existing homepage, shared configuration and integration ledger                |
| WEBSITE 01 — Design system            | `components/ui`, `styles`, `docs/design-system`                               |
| WEBSITE 02 — Service journeys         | Service routes, components and `content/service-pages.ts`                     |
| WEBSITE 03 — Journal                  | Journal route, components and `content/journal.ts`                            |
| WEBSITE 04 — Content and integrations | Destination registry, builders, source evidence and integration documentation |
| WEBSITE 05 — Independent QA           | `docs/qa`, `tests/qa` and independent candidate evidence                      |

All paths above are relative to `apps/website/src` unless they begin with `docs` or `tests`. Each lane commits in its own local worktree. Only reviewed focused commits enter the coordinator worktree; no whole-worktree merges are used.

## Acceptance and remaining work

The coordinator freezes a clean commit after fresh installation, serialized tests, typecheck, production build and original-asset checksum verification. Independent QA tests that exact commit on port 3105, including all seven routes, five viewport widths, keyboard flows, content caveats, console output and the removal of the overlapping fixed contact action. The user preview stays on port 3100. Final evidence and the disposition belong to `development-control/integration.json` and the independent report.

Original imagery and legacy homepage CSS are preserved deliberately. A subsequent performance milestone can introduce reviewed image derivatives and consolidate historical selectors against the R19 visual baseline. CMS, account authentication, payments, CRM and production API wiring are outside the present scope. Review counts and pricing are not cached as public claims.

## Release boundary

No push, PR, merge, auto-merge or deploy is authorized by this checkpoint. A local QA pass does not authorize a release. Production integration requires a separate mandate and independent Claude verification under the repository's external-agent contract.
