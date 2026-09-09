# Homepage review: clearer journeys, not more sections

Date: 2026-09-07 WITA. Status: adjudicated design recommendations for the isolated development website. This report does not authorize release or production changes.

## Decision

The homepage has a distinctive visual foundation worth preserving: the warm editorial typography, original Bali Zero mark, ocean E-VOA scene, sculptural Second Home book and visible human ownership. The next improvement is clearer decision-making, not another visual redesign or a larger inventory of products.

The ecosystem is already broadly represented. What remains under-explained is the relationship between **getting advice, using a tool and continuing an existing client relationship**. Clarifying those three actions will do more than adding more names, logos or large sections.

The approved team change is appropriate: retain a compact founder introduction on the homepage and put the complete directory on `/team`. It shortens a visually repetitive section without removing the human trust layer. This decision was already made by the owner and is not presented as a new panel discovery.

## Migration principle: preserve outcomes, improve implementation

Continuity means users retain working URLs, documents, sessions, publishing, tools and a comprehensible next step. It does **not** mean retaining historical defects, confusing navigation, unsafe measurement defaults, unscoped styles or obsolete architecture. Existing behavior is evidence to inspect, not a requirement to copy. Classify each dependency as a user contract to preserve, an implementation to replace, or a defect to correct.

Integration into the existing `apps/mouth` public shell is a candidate supported by the current shared-host/API evidence, not an immutable architecture requirement. Compare it against alternatives using explicit routing, session, content, performance, maintainability and rollback trade-offs before fixing the integration plan. A better architecture is acceptable when it preserves the necessary outcomes and its migration risks are demonstrated and controlled.

## What was actually reviewed

- Current source snapshot at worktree HEAD `b740b2cc3e94b1a46c9e9811bb369289fc21ea3d`, with file hashes in `source-manifest.json`. Uncommitted development work means the manifest, not HEAD alone, identifies the input.
- The complete desktop homepage at 1440px, after the browser scrolled and decoded images, before team compaction. Archived as `home-baseline-desktop.png` with a hash in `visual-evidence.json`.
- The production transplant audit in the sibling report, including deployed commit `dc7189f4af09857a6d7fbe26e33f3f553921c216`, public route observations and source-backed infrastructure constraints.
- Actual Claude Opus5 (returned model ID `claude-opus-5`) and Gemini Pro (`gemini-3.1-pro-high` requested and initialized by Antigravity; no separate backend model ID exposed) consultations, not multiple agents presented as different vendors. Exact invocation, returned model identity, raw responses and executed research tools are retained in this directory.

Claude’s final visual pass read the complete baseline image and explicitly limited fine-text judgments because the image was downscaled. The orchestrating reviewer also inspected the new compact mobile founder band after implementation; this was not a second external-model review of the updated full page.

This is an expert review with research, not a usability study. No customer accounts, client records, conversion dataset or live analytics were accessed. Static desktop inspection cannot prove mobile usability, keyboard quality, image performance or business impact.

## Priorities for the next development cycle

| Priority | Change | Why it matters | Evidence and acceptance test |
| --- | --- | --- | --- |
| Before integration | Keep “Journal” as the editorial label while reconciling it with the established `/news` destination; preserve article and tool routes | Production `/journal` currently returns a soft 404 despite HTTP 200 | Verified production audit. Test page identity and meaningful destination content, not status alone |
| P1 | Give each service card a clear hierarchy: service explanation first, self-service check second, conversation available as support | Four cards currently mix categories, product names, multiple buttons and human contact | Source and visual observation. In first-click tasks, users should correctly distinguish requesting help from starting a tool without coaching |
| P1 | Explain My Bali Zero with concrete verified outcomes: documents, application progress, team communication | The current illustration carries repeated qualification while the benefit remains abstract | Source observation plus product-code evidence. Validate each promise against actual product behavior, then ask returning clients to explain what they can do there in their own words |
| P1 | Preserve one coherent assistant/contact entry and its context when integrating | Production has ZantaraFAB; new contact affordances could compete with it | Verified production source. Test a service-to-contact journey and confirm one floating entry, correct destination and useful context without sensitive information |
| P2 | Tighten visual rhythm after team compaction: service-card actions, review spacing and portal emphasis | Section alternation already exists; service-card accent competition, review spacing and portal illustration hierarchy deserve refinement | Desktop judgment, not a measured defect. Compare two prototypes in task-based review and examine whether users notice the next useful action |
| P2 | Make “after arrival” visible within immigration/company journeys | E-VOA and Second Home tell an arrival story; continuing obligations and client follow-through are less explicit | Verified Visa Clock route and existing portal/service scope. Add a contextual link or sentence, then test a renewal/stay-duration scenario |

P1/P2 here rank design work. They are not production incident severities. A preference for a header contact button or visible prices is not a P0 outage.

## Specific design direction

**Hero and service cards.** The visual pass identified the service cards as the most crowded and chromatically inconsistent row. Test a more unified accent treatment; an exact color-count limit is a design choice, not an accessibility requirement. Keep the question-led hero. Its four choices provide immediate orientation. Avoid making the next section feel like the same choice expressed in four product brands. Lead cards with the need or outcome, retain the product name underneath, and make “explore the service”, “use the check” and “talk to the team” visibly different actions. Preserve the Visa Oracle name; a descriptive subtitle is sufficient to clarify what the current tool does. Naming a product does not require claiming that it makes a final eligibility determination.

**E-VOA and Second Home.** Preserve the ocean and book: they create two recognizable moments and distinguish short arrival from a longer life decision. Surya and Ari support the human relationship without needing large additional portraits. Keep their links contextual. Do not restore an unverified price, timing promise or regulatory condition just to strengthen the layout. Authoritative pricing integration and approved scope can support clearer expectations later.

**Reviews.** Keep the real person and Google destination. Avoid repeating several near-identical Google actions at equal visual weight. One principal review action plus a quiet source link should be prototyped. Do not manufacture ratings, counts or testimonials, and do not revive an outdated snapshot because the old composition looked fuller.

**Portal.** “Your vault” becomes useful when a visitor understands what goes into it and what happens next. Explain the concrete outcomes once, show a small coherent illustration, and make sign-in unmistakable. Retain a concise illustration label where needed; remove development-specific caveats from customer-facing copy only after the represented capability is checked. Public login reachability is not proof that authenticated workflows are absent, and source code alone is not proof that every account has every capability.

**Journal, founders and contact.** Keep the editorial contrast and varied article sizes. Connect the cards to the real publishing feed at integration rather than freezing a curated list. Founder images should introduce people and lead to the complete team page; the homepage should not become a staff catalogue. The final contact section should give a clear next action and use the same contact hierarchy as the rest of the site.

## Ecosystem placement

| Capability | Appropriate visibility | Reason |
| --- | --- | --- |
| Immigration, company setup, tax, property | Homepage, leading by user need | Core public service families already present |
| Visa Oracle, KBLI Navigator, tax calendar, property eligibility | Secondary actions within their service context | Useful self-service routes; do not need a second product wall |
| E-VOA and Second Home Studio | Existing distinctive homepage sections | Established product journeys and different user intentions |
| My Bali Zero | Clear homepage entry for existing clients | Documents, progress and human continuity can differentiate the relationship when verified |
| Visa Clock | Immigration/after-arrival context; optional small link on home | Public destination verified; a full new hero would be disproportionate |
| Renewals, reporting, ongoing company support | Service detail and portal context first | Worth confirming with operations; not evidence that another standalone tool is missing |
| Journal/news archive and existing articles | Homepage editorial preview plus `/news` | Trust, discovery and existing URL continuity |
| Zantara assistant/contact | One explicitly chosen entry mechanism | Preserve current user journey and avoid duplicate floating controls |
| Staff systems, internal APIs, assessment internals, unreleased products | Not public homepage content | Technical existence does not establish a public benefit or release readiness |

## Research conclusions that survive verification

Useful research here supplies measurement and interaction principles, not a promise that a design will increase revenue.

- Links should explain their purpose through their text or accessible context. Apply this to service versus check versus conversation labels. This supports accessibility and comprehension; it does not prescribe a particular button color. [W3C, link purpose in context](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html).
- Define task starts, endpoints and denominators. An eligibility result and an abandoned transaction are not interchangeable. Keep tool completion, advisor contact and a qualified enquiry as separate observations. [GOV.UK, measuring completion rate](https://www.gov.uk/service-manual/measuring-success/measuring-completion-rate).
- Combine observed task success and time with qualitative user research. Government-service guidance is transferable as a method; it is not controlled evidence that a Bali Zero commercial landing page will convert better. [GOV.UK, measuring service success](https://www.gov.uk/service-manual/measuring-success/measuring-the-success-of-your-service).

Peer websites may demonstrate a design convention, but their existence does not prove effectiveness. No competitor pricing, audience statistic or regulatory statement is adopted as Bali Zero business truth in this report.

## Proposed validation loop

1. Freeze the updated founder-only version and capture desktop and mobile with all assets loaded. Preserve this as the comparison baseline.
2. Check six realistic tasks: visitor visa, business setup, ongoing tax support, property check, existing-client documents and finding a person. Observe first action, misroutes, completion and explanation of what happens next.
3. Compare one focused alternative at a time: card action hierarchy, portal explanation, then contact entry. Do not change the hero, order, copy and controls simultaneously and attribute any result to one of them.
4. Define consent-aware events for service selection, tool start, tool completion, portal sign-in intent and contact intent. A WhatsApp click is not a qualified lead or sale. Preserve the existing production measurement contracts during integration.
5. Establish real baseline traffic and completion rates before calculating an experiment duration or minimum detectable effect. The panel has no evidence for a 20%, 30%, 40% or 50% uplift, and makes no such prediction.

## Disagreements, rejected claims and limits

Claude's first source-only pass overstated the lack of contact access, treated absolute Journal links as traffic leakage and made visible pricing an unjustified P0. Hero and contextual contact routes exist; the real editorial issue is URL compatibility. These findings were corrected before acceptance.

Gemini's first pass executed nine web searches but supplied no direct primary links or page-reading evidence. It also produced unsupported legal, demographic and regulatory claims and arbitrary numerical uplift estimates. That report is marked **REJECTED** and retained only to make the review auditable. No licensing disclaimer can be declared to eliminate all risk; no legal conclusion from that draft was used to alter the site.

The Gemini correction pass executed nine further web searches but canceled when Antigravity denied its first page-read request. A completed tool-state event did not prove that the page was read: the final response explicitly recorded `read_url` denial. Primary UX pages were instead opened through the orchestrator’s authorized web tool. This limitation is retained rather than presented as successful autonomous deep page research. A final Gemini synthesis then completed successfully using the independently verified source packet, with no tool calls, and formally retracted its earlier unsupported claims. Its remaining measurement suggestions were also adjudicated: eligibility rules are not mechanically applied to document-upload journeys, and a soft 404 requires page-content checks.

The homepage does not need to expose every piece of Nuzantara. It needs to make the right public capability easy to find, state its outcome accurately, and carry the user into the existing platform without losing context. This is the accepted design direction; exact visual changes remain prototypes to validate.
