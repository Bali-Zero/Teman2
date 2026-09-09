# Website development and review handoff

Date: 2026-09-07 WITA. Scope: isolated R19 website development. No main changes,
push, merge, auto-merge or production deployment were performed in this batch.

## Owner's migration principle

This is an opportunity to improve the system. Preserve useful user outcomes and
external contracts; fix or replace historical mistakes. Existing implementation
is evidence, not a mandatory architecture. Every integration decision should
identify what to keep, fix, replace or intentionally retire, with acceptance
checks for the affected journey.

The choice between scoped integration in `apps/mouth` and a separate marketing
application remains open. Compare both against routing, content, session
isolation, dependencies, maintainability and reversible release requirements.
Do not confuse the smaller initial diff with the better long-term architecture.

## Delivered

- Shared canonical skill: `.agents/skills/website/SKILL.md`, with current state,
  acceptance and model-review references. Codex, Claude, Gemini/Antigravity,
  Kimi and Qwen aliases resolve to the same source. See
  [installation and invocation notes](../website-corner.md). Command syntax
  varies by client; installing aliases does not prove five live sessions loaded
  the skill. The skill validator passed.
- Homepage Team is a compact founder band, with exactly two portraits and a
  dedicated `/team` link. Header and footer point to the Team page.
- `/team` contains 16 people: two founders, one board member and 13 staff, with
  existing roles and the owner-provided Ari/Surya project links. Faysha and Sahira
  are excluded. Detailed biographies remain a verified-content task; none were
  invented. A small viewport crop removes adjacent-row artifacts in the reused
  portrait atlas without modifying the source photographs.
- [Production comparison](2026-09-07-production-transplant.md) identifies the
  real deployed commit, public URLs, shared-host dependencies and keep/fix/replace
  decisions, with both integration options and their conditions.
- [Advanced model report](2026-09-07-panel/REPORT.md) includes actual Claude
  Opus5 and Gemini Pro consultations, research, disagreements and corrected
  conclusions. [Provenance](2026-09-07-panel/provenance.json) retains the limits.

## Findings to act on

The strongest visual assets are the editorial identity, ocean E-VOA section,
Second Home book and human project ownership. Keep those recognizable moments.

The next design work should clarify the service-card action hierarchy and
explain My Bali Zero through verified outcomes: documents, application progress
and team communication. Consolidate assistant/contact entry and add after-arrival
context within the relevant service journey. A larger product catalogue on the
homepage is not supported by the review.

Production `/journal` currently returns a soft 404 while `/news` is the established
editorial entry. Reconcile the label and route intentionally. Likewise reconcile
the new service paths with existing URLs, connect the real publishing source,
isolate marketing styles and dependencies, and reassess consent and promotion
behavior rather than copying them into the new site.

## Verification

- Website suite: 10 test files, 47 tests passed.
- Type check and optimized build passed. Build repeated after the final CSS crop.
- Eight preview routes returned HTTP 200 and retained
  `X-Robots-Tag: noindex, nofollow, noarchive`.
- Home and Team page checked at 360, 390, 768 and 1440px: no horizontal overflow.
- Founder band: exactly two images at each width; height 152px at 1440px,
  approximately 248px at 768px, and 380px at 360/390px.
- Team page: 17 decoded image elements (16 portraits plus logo), no broken
  images; excluded names absent.
- Mobile navigation opens; Escape closes it and restores button focus; the
  Our team link reaches `/team`.
- Desktop/mobile screenshots captured with lazy images loaded. Temporary
  photographic atlas edge artifacts were corrected during visual QA.

Visual evidence is local under `output/playwright/` in the worktree:
`home-final-desktop.png`, `home-final-mobile.png`, `team-band-desktop.png`,
`team-band-mobile.png`, `team-page-desktop.png`, `team-page-mobile.png`.

## Evidence limits

The external Claude visual pass covered the pre-compaction desktop homepage;
the updated founder band and dedicated Team page were visually checked by the
implementation session. This is not customer usability research or a conversion
experiment, and there is no evidence for an uplift percentage.

Gemini executed 18 searches across two passes, but Antigravity denied page
reading. The reviewer independently opened primary UX sources and supplied them
to Gemini for a completed corrected synthesis. Unsupported legal, demographic
and numerical claims from its first response were rejected, not adopted.

Production inspection was public and unauthenticated. Portal feature promises,
authenticated journeys, authoritative pricing, hosting settings and promotion
controls still require targeted verification before integration. The review
does not validate legal eligibility or pricing.

## Next bounded cycle

1. Compare the two architecture candidates with a small isolated proof covering
   a marketing page, real editorial content and a product deep link. Decide based
   on dependencies and measured behavior, not historical convention.
2. Prototype clearer service-card actions and verified portal outcomes, keeping
   the approved visual direction. Review realistic visitor and returning-client
   tasks before broadening the design.
3. Turn the selected architecture into a route/content/auth/measurement contract
   with intentional corrections and rollback criteria. Production release is a
   separate mandate.

Keep a single built preview on `http://127.0.0.1:3100/`. Model review processes
have exited. Do not restart the completed review sessions automatically.
