# R19 full-site source inventory

Date: 2026-09-07 WITA. Track B source and destination review.

This inventory describes the current local R19 candidate. It does not authorize
publication, deployment, access changes, or a replacement editorial pipeline.
Track A may change the Journal server contract in parallel; this inventory is
the pre-change presentation baseline, not an assertion that subsequent bytes
remain identical. The initial inventory was read-only. The integrator later
assigned this author the bounded UI batch described in `ui-batch.md`.

## Verified starting state

- Worktree: `/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro`.
- Branch: `codex/website-pro-continuation`.
- Base: `b740b2cc3e94b1a46c9e9811bb369289fc21ea3d`.
- The existing dirty overlay is essential and was preserved.
- The completed checkpoint at `output/checkpoints/2026-09-07-pro-slice/`
  matched all 224 live entries, including bytes, modes, and symlink targets.
  Archive and manifest hashes matched `CHECKPOINT.json`.
- Archive SHA-256:
  `c8f1038464229f7417d8fddce6ea4e1f57542f6cf4affae0c224a964b0e4afdc`.
- The preview listener was PID 12876, bound to `127.0.0.1:3100`; its working
  directory was this worktree's `apps/website`. PIDs are transient.
- `website` SKILL.md, state.md, review-protocol.md, website AGENTS.md, the
  completed Pro handoff, REPORT.md and DECISION.md were read. A targeted
  `website|Magazine|R19` memory registry search returned no matches.

`source-http.json` records a fresh route-level HTTP/HTML check of the inherited
built preview, before the coordinated Track A/B build and restart. It does not
contain the newly written UI fixes. It is not
browser interaction, screenshot, image-decoding, accessibility, or full-suite
evidence. The previous slice's 55 website and 47 architecture passes remain
historical until the integrated batch reruns its affected checks.

## Actual route inventory

| Route | Entry point | Presentation |
| --- | --- | --- |
| `/` | `src/app/page.tsx` | Header, hero, service/tools cards, E-VOA, Second Home, reviews, portal illustration, Journal, founders, contact, footer |
| `/services` | `src/app/services/page.tsx` | `ServicesOverview` in `components/services/ServiceJourneys.tsx` |
| `/services/immigration` | `src/app/services/[slug]/page.tsx` | Shared `ServiceDetail`; immigration content |
| `/services/company-setup` | Same dynamic route | Shared detail; company setup content |
| `/services/tax` | Same dynamic route | Shared detail; tax and accounting content |
| `/services/property` | Same dynamic route | Shared detail; property and due diligence content |
| `/team` | `src/app/team/page.tsx` | Leadership and full team directory |
| `/journal` | `src/app/journal/page.tsx` | `components/journal/JournalIndex.tsx` |

The four slugs are enumerated by `content/service-pages.ts`; unknown slugs use
Next `notFound()`. There are no local `/tools`, `/portal`, or `/contact` pages.
Those visitor surfaces are homepage anchors `/#tools`, `/#client-portal`, and
`/#contact`. The current app contains no form, input, textarea, selector,
search, or filter UI. CSS names for older forms/dialogs are not implemented
capabilities. `ArticleTemplate` and `DesignSystemFixture` are not public routes.
These are scope facts, not missing features requested by the owner.

## Homepage sections and actions

| Order | Component / anchor | Actions and states |
| --- | --- | --- |
| 1 | `Entry.SiteHeader` | Logo to `#main`; Explore to `#tools`; Services, Journal, Our team; external My account. Mobile menu toggles, closes on Escape with focus return, closes after selection and when focus leaves the header. |
| 2 | `Entry.Hero` | Four service detail links; Talk to our team to `#contact`; existing sunset AI illustration. |
| 3 | `Services`, `#services`, `#tools` | Overview link; four cards with local service link, public tool link and contextual WhatsApp link. |
| 4 | `Evoa`, `#evoa` | Public E-VOA destination; Surya contextual WhatsApp link; existing ocean and portrait assets. |
| 5 | `SecondHome`, `#second-home-studio` | Public Studio destination; Ari contextual WhatsApp link; existing book and portrait assets. |
| 6 | `Reviews`, `#google-reviews` | Three links to the same Google listing, all opening a new tab; Adit portrait. No embedded rating/count/testimonial. |
| 7 | `Portal`, `#client-portal` | Public account sign-in link; Documents, Applications and Messages illustration tabs. |
| 8 | `Journal`, `#journal` | Local Journal index; two-story featured carousel; third sample in the main story column at the baseline. |
| 9 | `Team`, `#team` | Compact two-founder band and local `/team` link. |
| 10 | `Contact`, `#contact` | WhatsApp, email and Google Maps links. No contact submission form. |
| 11 | `Footer` | Homepage anchors, Services, Journal, local Team, public About, Google reviews, account, WhatsApp/email/telephone, public legal notices. |

The founder-only instruction applies to the Team band. The approved Ari, Surya
and Adit portraits remain in their separate project/review sections.

## Shared detail and secondary surfaces

`ServiceJourneys.tsx` provides a shared logo/account header, breadcrumb, service
overview and detail pages, and a compact footer. Each detail page has a summary,
who-it-helps text, three questions, an optional tool link, three conversation
steps and repeated contextual WhatsApp actions. Content is supplied by
`content/service-pages.ts`; there is no eligibility engine or quote calculation
inside these pages.

`/team` renders two founders, one board member and thirteen other people: 16 in
total. The owner-excluded pair remains absent. Roles come from the approved
local roster, not newly written biographies. Ari links to Second Home Studio
and Surya to E-VOA on the homepage; the invitation links to `/#contact`.

The Portal illustration uses three buttons with tab roles and a single
tabbable active tab. ArrowLeft/ArrowRight wrap, Home/End select the ends, and
the selected panel is focusable. All panels are explicitly illustrative;
messaging availability is not promised. No account session was accessed.

At this baseline both Journal entry points read `loadJournalFeed()` after
`connection()`. Explicit `WEBSITE_EDITORIAL_FIXTURE=1` supplies synthetic
sample stories; absence produces unavailable rather than historical fallback.
The homepage carousel supports controls and arrow keys. The Journal index has
native source/revision disclosure. Sample destinations are inert and visibly
identified; there is no competing local story route. The distinct component
states are ready, empty, withdrawn, unpublished, unavailable and malformed.
The Track A owner controls any subsequent contract changes.

## Claims and destination evidence boundaries

- Hero and service pages describe guidance and a conversation. They contain
  no quoted price, processing time, guaranteed eligibility, or outcome.
- E-VOA points visitors to the existing service for eligibility, application
  steps and current fees. No local numeric fee or legal rule is introduced.
- The site preserves R19 staff names/roles and owner-supplied project
  responsibilities. This inventory did not independently re-credential staff.
- `Since 2020` is inherited owner-approved R19 copy in the Team introduction
  and homepage footer. This pass did not independently verify the founding
  date. Repetition on company-owned pages is not independent historical
  evidence. No new claim was added.
- Google rating/count values are intentionally absent from R19; the links
  let visitors inspect the current listing. No review text was copied.
- The Portal labels separate illustration from verified account access.
- Journal fixture text is visibly synthetic. Reachability of an external
  article or `noindex` does not authorize publication of new content.
- Public external tools may contain legal, numeric or performance assertions.
  The destination audit checks identity/reachability, not those assertions;
  they must not be imported into R19 as verified facts.

Destination contracts live in `content/destinations.ts`; some older components
also contain the approved href literals directly. The dated
`content/evidence/destinations-2026-09-06.ts` is historical evidence, not a live
health monitor. Telegram is explicitly blocked and is not linked by the
current presentation. See `destination-audit.md` and `destination-http.json`
for this review's narrowly scoped checks.

## Source candidates and subsequent integrator observations

1. Homepage, Services overview/details and Team skip links target a `main`
   without `tabIndex`; Journal already uses `tabIndex={-1}`. The integrator's
   CUA check confirmed that activating the homepage skip link left focus on
   BODY. The assigned patch makes those main elements focusable; integrated
   browser verification after the shared build remains necessary.
2. An unknown service slug returned HTTP 404 but no H1, main or link in parsed
   response HTML, unlike the ordinary unknown-route response with H1 `404`.
   The integrator's hydrated CUA observation disproved a blank-page concern:
   the standard 404 H1 and message are visible. Its default dark appearance and
   lack of Home/Services recovery links were the supported defects. The
   assigned custom not-found UI addresses those, pending rebuilt-preview review.
3. Service header/breadcrumb/card text links have no dedicated minimum target
   height in their CSS. Measure actual mobile targets and spacing rather than
   declaring failure from source alone. The assigned CSS patch is a target
   comfort improvement, not a claim that a WCAG requirement was violated.
4. Desktop/mobile color, wrapping, image crops, portrait edges and section
   density require current visual evidence. Source review cannot approve them.

The integrator owns acceptance of the coordinated implementation batch. This
author executed only the assigned UI changes and focused checks. See
`coverage-draft.md` for attributed pre-change browser observations and remaining
coverage; no independent visual approval is claimed here.
