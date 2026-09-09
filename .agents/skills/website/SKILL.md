---
name: website
description: Develop, review, or resume the Bali Zero public website, its R19 implementation, team page, ecosystem coverage, and future production transplant. Use for homepage UI/UX, public navigation, website acceptance checks, and cross-model website handoffs.
---

# Bali Zero website corner

One shared source for every agent working on the public website. Resolve this
file's real path before following relative references through an installed alias.

## Resume

1. Read [current state](references/state.md). Verify the working directory,
   branch, changes, and preview response before treating that snapshot as current.
2. Read the applicable repository and `apps/website/AGENTS.md` instructions.
   Keep work inside the dedicated website worktree. Existing owner mandate is
   local development only: no main changes, merge, auto-merge, or deployment.
3. Inspect the relevant content and component, not the entire repository.
   Read the installed framework documentation before changing framework behavior.
4. For design changes, use the [design principles](../design/SKILL.md), while
   retaining the approved R19 direction and current implementation. Older study
   snapshots do not supersede this corner's dated state.
5. Make the smallest complete change, verify it, and update the state reference
   and handoff with actual observations. Do not turn review suggestions into
   approved decisions without distinguishing them.

## Product contract

- The homepage helps visitors find a service, use a relevant tool, understand
  the people behind the company, and reach the team. Existing clients have a
  clearly separate route to My Bali Zero.
- Keep the warm paper, forest, copper, editorial typography, and original brand
  assets. Judge hierarchy and clarity before adding decoration or more sections.
- Homepage Team is a compact band with only the two founder portraits. Full
  staff information belongs on `/team`. Faysha and Sahira are excluded from the
  published roster by owner instruction. Do not invent biographies.
- Ari owns Second Home Studio; Surya owns E-VOA. Preserve these project links.
  Portrait fixes use photographic background removal authorized by the owner;
  check real alpha and edges against the actual section background.
- My Bali Zero is intended to explain documents, applications/next steps, and
  contact with the team. Validate capabilities before promising them. A preview
  illustration is not proof that a feature is live, nor proof that it is absent.
- Never invent prices, reviews, processing times, client counts, testimonials,
  credentials, legal eligibility, security guarantees, or team information.
  Separate verified facts, inferences, proposals, and unresolved checks.
- Scope public ecosystem coverage to a visitor need and a verified destination.
  Internal infrastructure does not automatically belong on the homepage.

## Change and acceptance loop

Assign explicit file ownership when parallel work is requested. Share contracts
and findings; do not overwrite sibling changes. Run the smallest relevant tests,
then the full website suite, type check, and build once for the integrated batch.
Inspect desktop and mobile, keyboard navigation, route responses, overflow, and
image decoding. Load lazy images before judging full-page screenshots.

Keep one lightweight preview. Close temporary browsers and review subprocesses
after use. Heavy computation stays on the designated workhorse machine.

## Production transplant

Owner decision, 2026-09-07: reuse the Magazine editorial engine and build its
public presentation in the approved R19 website design. Do not import the old
Magazine visual shell or its public/internal navigation. Inspect and adapt the
engine's useful publication, evidence, media and revision contracts; do not
preserve known defects or create a competing publishing pipeline by default.
Resume on Pro using `apps/website/docs/handoffs/2026-09-07-pro-resume.md`.

Read the [production comparison](../../../apps/website/docs/reviews/2026-09-07-production-transplant.md)
before proposing integration. Verify the live deployment identifier and inspect
that exact source revision; local main is not evidence of production parity.
Inventory host rewrites, public routes, indexed URLs, APIs, authentication,
cookies, metadata, analytics, and redirects. Preserve useful user outcomes and
external contracts, not historical implementation mistakes. For each surface,
record whether to keep, fix, replace, or retire it and the evidence for that
decision. Broken behavior is a defect to resolve, not a compatibility target.

The owner explicitly wants this migration to improve the architecture and UX.
Compare scoped integration in the existing app with a separate marketing app;
choose on verified dependencies, isolation, maintenance, and migration costs.
The existing shared host shell is a dependency to assess, not an immutable
architecture mandate. Any replacement needs an explicit routing, authentication,
SEO, observability, and rollback contract before implementation of the cutover.

Do not replace the deployed application merely because the standalone website
builds. Prepare a bounded public-surface diff and a rollback plan. Preview
`noindex` is deliberate; production indexing changes belong to the future release
gate. No live migration is authorized by this corner.

## Research and independent review

Follow [review protocol](references/review-protocol.md). Actual model calls must
be labeled with requested and served model, inputs, tools, limitations, and time.
A reviewer asks precise questions; the research reviewer investigates primary
sources and counterarguments; the final synthesis reconciles evidence and
disagreements. Never present multiple roles of one model as multiple vendors.

## Handoff

Record changed paths, tests, visual evidence, known gaps, processes left running,
and the next bounded task. Keep client PII, secrets, and raw operational data out
of shared material. Preserve completed work across sessions without restarting
old audits or reopening completed tasks unnecessarily.
