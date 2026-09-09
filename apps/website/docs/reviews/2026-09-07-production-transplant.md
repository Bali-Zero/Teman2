# Website production transplant audit

Date: 2026-09-07, WITA. Scope: the R19 development website, the current public production website, and the frontend infrastructure they depend on. This is a preparation report, not a deployment authorization.

## Executive decision

**Preserve working user journeys and public contracts; improve or replace the implementation where it is weak. Keep developing independently, and choose the production integration architecture against explicit evidence. Do not replace the existing Vercel project with `apps/website` as it stands.**

Production is substantially more than a homepage. The `apps/mouth` application contains the public editorial archive, KBLI pages, visa tools, property eligibility, authentication, API forwarding, and hostname routing for several Bali Zero products. The new application is a deliberately isolated marketing preview. Replacing one application with the other would remove contracts that the visual prototype does not implement.

A homepage-only replacement inside `apps/mouth/src/app/(marketing)/page.tsx` is the smallest initial change and a candidate for the lowest migration risk. It is not an automatic architecture mandate: the existing root couples marketing to host themes, providers, analytics and authenticated applications. A separate marketing deployment can be preferable if it demonstrably reduces that coupling and has a complete route, content and release boundary. Either approach must preserve outcomes without reproducing historical mistakes. Journal, service and team redesigns can follow separately with explicit URL compatibility.

## Evidence and provenance

The audit used local code inspection and unauthenticated public HTTP GET requests only. No deployment, DNS, session, database or production configuration was changed. No customer account was opened.

| Evidence | Observed state |
| --- | --- |
| Development worktree HEAD | `b740b2cc3e94b1a46c9e9811bb369289fc21ea3d`; active uncommitted sibling work may advance the website after this snapshot |
| Local main HEAD | `5f64f2c2e74b6605b83fa33f18c7668589e1b710` |
| Production commit | `dc7189f4af09857a6d7fbe26e33f3f553921c216`, returned by [the live health endpoint](https://balizero.com/api/health) in two separate requests |
| Production commit corroboration | The commit exists locally. Its health route reports `VERCEL_GIT_COMMIT_SHA`, captured at module scope |
| Critical code parity | No diff between deployed commit and local main for proxy, Next configuration, root layout, marketing homepage, sitemap, robots, login route, API catch-all and API client inspected here |
| Hosting evidence | Public responses identify Vercel; `apps/mouth/vercel.json` and the deployment README identify the Next application and build/promotion mechanism |

**Local main is not the deployed commit.** The verified parity of the specific files above permits their use as production evidence; it does not establish parity for the whole repository.

Important source locations, relative to the repository root:

- `apps/mouth/src/app/(marketing)/page.tsx`: current homepage, metadata, dynamic editorial selection and funnel initialization.
- `apps/mouth/src/app/(marketing)/layout.tsx`: marketing wrapper, without an additional shared header/footer.
- `apps/mouth/src/proxy.ts`: hostname routing, login boundaries, canonicalization and legacy routes.
- `apps/mouth/next.config.ts`: redirects, security headers, image pipeline and deployment tracing.
- `apps/mouth/src/app/layout.tsx`: root metadata, structured data, font loading, analytics, providers and theme handling.
- `apps/mouth/src/app/sitemap.ts` and `robots.ts`: public search surface and private-route exclusions.
- `apps/mouth/src/app/api/auth/login/route.ts`, `api/[...path]/route.ts`, `lib/api/client.ts`: authentication, cookies and API contracts.
- `apps/mouth/README.md:30`: staged builds and promotion process.
- `apps/website/next.config.ts`, `src/app/layout.tsx`, `src/app/globals.css`, `src/content/destinations.ts`: preview safeguards, styling and destination inventory.

## Public route compatibility

| Surface | Live observation | Transplant requirement |
| --- | --- | --- |
| Apex `/` | 200, indexable homepage, canonical apex | Replace presentation while retaining correct metadata and shared infrastructure |
| `www.balizero.com/` | 308 to apex | Preserve canonical redirect |
| `/news` | 200, editorial index | Keep as the established editorial entry point |
| `/journal` | 200 with title `Page not found`, matched by the category route | Do not interpret HTTP 200 as a valid page; decide whether Journal is a label for `/news` or a new canonical route with redirects |
| `/services/visa`, `/services/company` | Established production service paths, also in the sitemap | New preview uses `/services/immigration` and `/services/company-setup`; reconcile before release |
| `/services/tax`, `/services/property` | Established production service paths | Preserve URLs when replacing their presentation |
| `/{category}/{slug}` | Existing article routing and production MDX archive | Retain article URLs, content, metadata and category navigation |
| `/kbli-navigator` | 308 to `/kbli` | Keep historical links functional |
| `/kbli`, `/kbli/*` | Large indexed tool and content surface | Preserve existing handlers, data files, sector pages and generated sitemap entries |
| `/visa/voa` | 200, Visa on Arrival | Current E-VOA destination is valid; avoid introducing duplicate eligibility/application flows |
| `/visa/second-home/studio` | 200, Second Home Studio | Preserve the product route and links into it |
| `/visa/clock` | 200, Visa Stay Calculator & Overstay Clock | Available contextual utility; preserve even if not featured on the homepage |
| `/property/eligibility` | 200, Property Eligibility Check | Existing property tool destination is valid |
| `/team` | 200, Team | Keep a dedicated destination when condensing homepage portraits |
| `/v2/company/about` | 200, About Bali Zero | Preserve company-story links or redirect intentionally |
| `/v2/privacy`, `/v2/terms`, `/v2/cookies` | All 200 with corresponding policy titles | New footer links are valid; preserve them or migrate with explicit redirects |

The live sitemap returned **2,423 URL entries**, independently confirmed in a second fetch; **1,581 entries are under `/kbli/`**. These are sitemap entries, not a claim about the number of KBLI codes or currently indexed Google pages. A homepage release must not reduce that inventory accidentally.

The current homepage also preserves section anchors `#visa`, `#kbli`, `#tax`, `#property` and `#news`. The preview uses different IDs, including `#tools`, `#services`, `#client-portal` and `#main`. Retain old anchor targets or provide equivalent named anchors so inbound fragment links still land in the right place.

## Hostnames, login and APIs

| Hostname | Public observation | Boundary |
| --- | --- | --- |
| `balizero.com` | Marketing, editorial and public tools | Public website entry point |
| `visa.balizero.com` | 302 to apex `/visa` | Existing visa product entry route |
| `tax.balizero.com` | 200, internally matched `/tax-calendar` | Dedicated tax-calendar host rewrite |
| `my.balizero.com` | Redirect chain to `/portal/login-upgraded`, then 200 | Client portal; homepage should deep-link, not recreate login |
| `kita.balizero.com` | Redirect to `/login`, then 200; `noindex, nofollow` | Staff application boundary |

The proxy also defines Prime, Zantara, mobile and assessment hostname behavior. Their current deployment aliases were not individually verified. Mail, calendar, drive and knowledge references must not be assumed to share the same deployment merely because they appear in routing code.

Production login sets `nz_access_token` as HttpOnly, Secure, SameSite=Lax with a production default domain of `.balizero.com`; the domain can be configured. CSRF handling uses `nz_csrf_token`. The API client includes credentials. Preserve functioning sign-in, session continuity and CSRF protections, not the broad cookie domain as an unquestionable design rule. A marketing release under the apex must avoid caching authenticated responses or exposing session material to client scripts. Narrower cookie scope is a potential improvement requiring its own verified SSO/session transition; this audit does not authorize or prove that change safe.

The Next API catch-all forwards to the backend, supports long-running/SSE requests and has explicit authorization precedence. Its anonymous Visa Oracle evaluation path strips authentication-related headers and limits payload size. Next configuration explicitly warns against adding a broad `/api` rewrite that bypasses this route handler. None of these behaviors exists in the standalone marketing preview.

Authenticated end-to-end behavior was not tested because this audit used public evidence only. A later release gate needs authorized test-account validation for portal login, staff login, logout, session expiry, CSRF and cross-host redirects.

## Preserve outcomes; fix or replace implementation

The preservation boundary is user-facing behavior: links keep working, published content remains discoverable, people can sign in and complete existing tasks, and operators can observe and reverse a release. It is not a freeze on the old component tree, global providers, cookie scope, build root, schema generator or promotion machinery. The following decisions distinguish observed faults from improvements that still require evaluation.

| Area | Preserve | Replace or adapt | Unresolved release condition |
| --- | --- | --- | --- |
| Homepage | Canonical URL, meaningful anchor destinations, measurable conversions | New hierarchy, typography, illustrations, concise founder strip; simplify root dependencies | Visual/mobile review and conversion measurement parity |
| Team | `/team`, approved names, roles and portraits | Long homepage directory becomes a compact founder line plus team link | Dedicated page content completeness; excluded people stay excluded |
| Editorial | Published content, article URLs, publication state, feeds and discovery | Card styling and selection UI; the MDX adapter can be retained or replaced behind a tested content contract | Preview's curated story set must connect to the real editorial pipeline |
| SEO | Canonicals, social metadata, verification, valid structured data, robots and sitemap coverage | Refresh only claims supported by approved business evidence | Remove preview noindex from production only; retain it on previews |
| Brand/assets | Approved identities, logos, product destinations | Namespace new assets and scope CSS to the marketing surface | Confirm image dimensions, compression, licensing and font consistency |
| Auth/API | Successful sign-in, secure sessions, CSRF protection, API semantics and streaming | Reduce public-page exposure to auth concerns; cookie or handler redesign requires an explicit transition | Authorized regression tests required |
| Measurement | Ability to measure journeys, errors and page performance | Consolidate event taxonomy; deliberately choose consent and analytics behavior | Consent policy decision and before/after dashboard baseline |
| Hosting | Stable public/product destinations and reversible releases | Choose integrated or separate deployment; replace uncontrolled promotion behavior if confirmed | Actual Vercel settings, ownership and promotion controls need verification |

| Decision | Observed evidence | Required improvement or acceptance check |
| --- | --- | --- |
| Keep the public content contract | Live sitemap has 2,423 entries and production serves real articles and tools | Account for every established URL: retained, intentionally redirected, or deliberately retired; do not require exact count parity if changes are justified |
| Fix soft-404 behavior | `/journal` returns 200 with `Page not found` | Valid Journal destination or explicit redirect; unknown routes return a real 404 with correct indexability |
| Fix environment-sensitive SEO | Preview has development title and global noindex; production has schema and metadata spread across layouts | Explicit preview/production metadata policy; validate final HTML for duplicate, stale or unsupported structured claims |
| Replace unscoped marketing CSS | Preview styles generic `body`, `img`, links and headings | Isolate styles under a marketing boundary; avoid changes leaking into tools, portal or editorial pages |
| Improve dependency separation | Production root mounts multiple providers and host-theme behavior around marketing | Inventory required homepage dependencies; keep only what marketing consumes or move marketing into its own app if that is cleaner |
| Reassess consent implementation | Root immediately updates analytics storage from denied to granted | Select and document intended consent behavior with appropriate review; test actual event delivery instead of copying the script |
| Replace frozen editorial selection dependency | Preview uses curated imports; production uses publishing data with fallback | A tested content adapter that receives approved live publishing changes without manual homepage edits |
| Improve session isolation carefully | Current production cookie defaults to `.balizero.com` | Assess narrower scope against real SSO requirements; preserve active journeys with transition tests before any change |
| Make promotion and rollback explicit | README describes staged builds plus periodic Mini promotion | Verify actual behavior; ensure a hold/rollback cannot be silently superseded, regardless of which app owns the homepage |
| Simplify contact surfaces | Current homepage has ZantaraFAB; new homepage has a contact entry | One clear contact system with measurable routing, avoiding competing floating controls |

### SEO and content details

The live homepage emits Organization, ProfessionalService, WebSite, AggregateRating and related structured data. Production root layout also supplies metadata, Open Graph/Twitter fields, language alternates, verification entries, feed links and LLM discovery links. These must be reviewed as a complete page output after transplantation; blindly copying them can duplicate schema or retain unsupported claims.

The new app intentionally has global `X-Robots-Tag: noindex, nofollow, noarchive` and `robots: { index: false, follow: false }`, plus a development title. Shipping these unchanged would make the replacement non-indexable. Conversely, removing them from the preview now would be premature. Use an explicit environment-bound indexability policy at integration.

The live homepage obtains real articles through `getAllArticles` and `content/homepage-layout.json`, with fallback selection. The preview imports curated story content. A visually successful new Journal cannot silently replace that publishing dependency with a frozen list.

### Fonts, assets and CSS

Production self-hosts Inter and Cormorant through `packages/core/fonts`, and applies host-dependent theme logic. The preview uses system sans fonts and Georgia, with unscoped selectors for `body`, `img`, `a`, `h1` and other global elements. Importing its stylesheet at the production root would affect the portal, tools and editorial pages.

Use a marketing-specific wrapper and scoped component styles, reconcile tokens deliberately, and keep header/footer composition within the marketing route group. Namespace the new images rather than assuming `/assets` filenames will remain collision-free. Preserve production image optimization, remote allowlists and cache headers; measure page transfer size and LCP with real compressed assets before release.

### Analytics and consent

The deployed root has environment-gated Google Analytics, route tracking, Web Vitals reporting and monitoring providers. The marketing page initializes the home funnel and its WhatsApp CTA records `home_whatsapp_cta`. The preview has no equivalent production measurement integration.

The root consent script initializes analytics as denied and immediately updates analytics storage to granted; ads storage remains denied. This is observed implementation, not a legal-compliance verdict. Carrying it into the replacement requires a deliberate privacy-policy/consent decision. Do not infer an active GA property merely from the presence of GA code; production environment values and received events were not inspected.

## Ecosystem coverage: what the homepage should explain

The preview already covers the four core service families and links to Visa Oracle, KBLI, tax calendar, property eligibility, E-VOA, Second Home Studio and My Bali Zero. It does not need a larger wall of product logos.

The useful missing or under-explained connections are:

1. **Service versus tool:** make it clear when a link starts a self-service check and when it requests professional help. Keep the service page and tool as distinct actions with distinct labels.
2. **After arrival:** the live Visa Clock is a verified utility beyond obtaining a visa. It fits inside the immigration journey or a service page, rather than becoming another large homepage section.
3. **Editorial continuity:** preserve `/news`, categories, article discovery and feeds. “Journal” can remain the user-facing label without requiring a new canonical URL.
4. **The full human team:** a compact founder strip should point clearly to `/team`; staff detail and larger photography belong there. This supports the user's desired reduction in homepage length.
5. **Ongoing client work:** the My Bali Zero entry should explain documents, application progress and contact with the team using verified product capabilities. The preview correctly labels its UI illustration; public login reachability alone does not prove every depicted feature is available to every account.
6. **Existing assistant continuity:** the current homepage includes `ZantaraFAB`. Decide explicitly whether the new contact entry replaces it, preserves it or routes to it. Avoid two competing floating contact controls.

KBLI builder/decoder/sector pages and other specialist tools exist in the codebase. Their depth should remain reachable within the appropriate product; their mere existence is not evidence that each deserves homepage promotion. Internal staff tools, assessment pages and unreleased products should not be exposed to fill perceived whitespace.

## Future cutover sequence

1. **Freeze a verifiable baseline.** Record deployed commit, alias target, domain inventory, redirects, sitemap inventory, key HTML metadata, traffic/conversion baseline and product smoke-test results. Re-run this audit against the actual release candidate; today's evidence is not a permanent deployment record.
2. **Choose and build the release boundary.** Compare scoped integration and a separate marketing deployment using the decision table below. Scope styles, namespace assets and connect real editorial data in either case. Preserve route and session outcomes, and explicitly replace legacy internals where supported by evidence. Keep independent review and the current no-main/no-production boundary.
3. **Resolve URL decisions before page expansion.** Keep `/news` and production service slugs unless there is an approved migration reason. If changing canonical URLs, prepare one-hop redirects, internal-link updates, sitemap updates and canonical metadata together.
4. **Validate a production-like preview.** Exercise apex plus hostname-dependent routes, metadata/schema, old anchors, mobile navigation, keyboard interactions, image loading, article links, redirects and CSP behavior. Confirm previews stay non-indexable. Use authorized accounts for login/session tests in their own controlled lane.
5. **Prepare rollback and promotion control.** Identify a known-good immutable deployment and the authorized promotion mechanism. The repository README describes staged Vercel builds followed by Mini's `mini.vercel_autopromote` every 15 minutes. Verify the actual running mechanism and coordinate a temporary promotion hold for the release/rollback window, so a rollback is not immediately superseded by the next automatic promotion.
6. **Release only through the established review/ship authority.** The user has not authorized a production cutover in this task. A future authorized owner verifies the complete candidate, promotes the intended deployment and monitors key journeys.
7. **Prove live, then close the release.** Verify the live commit, indexability, canonical URL, accounted-for sitemap changes and critical product journeys. Monitor real errors and conversion events against the baseline. Execute the prepared rollback if release criteria fail; do not repair DNS or rewrite authentication under pressure.

### Architecture decision: two viable candidates

| Candidate | Benefit | Cost or risk | Select when |
| --- | --- | --- | --- |
| Scoped marketing integration inside `apps/mouth` | Smallest initial routing change; existing articles, public tools and deployment contracts remain reachable in one application | Retains shared-build blast radius and root coupling unless actively reduced; new global CSS or providers could affect other products | Marketing dependencies can be isolated cleanly, page performance meets the agreed budget, and independent product smoke tests prove no regression |
| Separate marketing application with explicit routing/content boundaries | Independent release cadence, smaller marketing dependency surface, clearer ownership and potentially simpler public-page runtime | Needs an exact apex path map for editorial/tools/API, asset/cache boundaries, content adapter, cookie handling, monitoring and coordinated rollback across deployments | A bounded proof demonstrates stable deep links and sessions, clean routing without broad fallback mistakes, publishing continuity, measurable isolation benefits and an operable release/rollback process |

The separate option need not recreate every tool: product hosts and existing public paths can continue to their current owner through a deliberately designed boundary. That boundary must be proved, not inferred from the hostname. Conversely, integrated deployment does not require preserving all root providers or old CSS. Choose based on a small production-like proof and measured complexity/performance, not inertia or a desire to rewrite everything. Current evidence establishes that an application-directory swap is unsafe; it does not establish that a separate app is inherently worse.

## Release blockers and explicit unknowns

- The standalone app is **not a production replacement**: preview noindex, development metadata, missing production host/API infrastructure and different service/editorial routes remain intentional gaps.
- Exact Vercel dashboard root settings, current domain-to-deployment aliases, branch environment variables and the live state of the Mini promotion job have not been authenticated or inspected.
- The report does not prove authenticated portal/staff workflows, backend availability under load, GA event reception, Search Console indexing or conversion performance.
- Current public HTTP status alone is insufficient: `/journal` demonstrates a soft-404 response. Route smoke tests must verify page identity as well as status.
- Production marketing claims, review counts, prices and regulatory statements are not validated by their appearance on the live website. Keep source-backed content discipline during migration.
- The scoped homepage candidate does not inherently require DNS, backend or cookie migration. A separate deployment introduces hosting/routing decisions; either candidate that changes session scope or backend contracts needs a reviewed transition plan.

**Readiness conclusion:** the development lane is ready to continue design and component work. Use the transplant to remove demonstrated weaknesses while preserving user outcomes. Select the architecture after a bounded proof of routing, content, session and release boundaries; do not treat either the old implementation or the new standalone app as automatically production-ready.
