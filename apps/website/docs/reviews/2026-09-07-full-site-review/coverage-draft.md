# R19 full-site review coverage draft

Date: 2026-09-07 WITA. This is a coverage plan and source/HTTP baseline, not a
completed browser review. The integrator records actual browser results and
supported fixes separately. Track A owns Journal server/contract work.

## Coverage and current evidence

| Surface | Required browser check | Evidence held by this author |
| --- | --- | --- |
| All eight implemented routes | 1440px and 390px layout, one H1/main, heading order, readable text, no overflow, images loaded and decoded, useful next action, preview noindex | Source inventory and loopback HTTP/HTML only |
| Homepage hero/header | Navigation at desktop and mobile, all four starting points, contact anchor, Escape/focus/menu close, sticky-header anchor visibility | Source only |
| Services/tools homepage | All four local service and external tool destinations; contextual contact intents; no fake in-page form | Source and destination HTTP checks |
| E-VOA and Second Home | Existing artwork/portrait crop, mobile order, correct Surya/Ari contact context, external destination identity | Source and destination HTTP checks |
| Google Reviews | Current link target, no copied numeric rating/count, decoded Adit portrait, clear new-tab action | Source and HTTP reachability where available |
| Portal | Three tabs by pointer and keyboard; selected/hidden states; ArrowLeft/Right, Home/End; visible illustration disclosure; account login destination | Source and public HTTP only |
| Homepage Journal | Next/Previous and arrow keys, counter announcement, card with/without image, fixture disclosure, no unusable fake link affordance | Source only; earlier slice evidence is historical |
| Services overview | Four cards, breadcrumb, contextual WhatsApp action, narrow/mobile wrapping | Source and loopback HTTP/HTML |
| Every service detail | Full content/CTA pass on immigration, company-setup, tax and property; optional tool label/destination; three questions and three next steps | Source and loopback HTTP/HTML |
| Team | Full 16-person roster, owner exclusions, crops and portrait decoding, Ari/Surya links, invitation, mobile grid | Source and loopback HTTP/HTML |
| Journal index | Sources/revisions with Enter/Space, source/date disclosure, card with/without image, sample identity, safe unavailable variants | Source only; Track A final contract may change fixture behavior |
| Contact/footer | Working section anchors, verified public contact hrefs, legal/about destinations; no message/email/call actually sent | Source and destination HTTP checks |
| Unknown route/detail | Useful readable 404 and route back where implemented; no blank screen | HTTP 404 observed; visual result pending |

The implemented routes are `/`, `/services`, `/services/immigration`,
`/services/company-setup`, `/services/tax`, `/services/property`, `/team`, and
`/journal`. Do not invent `/tools`, `/portal`, `/contact`, or a local article
route to make this matrix look broader. Test their existing homepage anchors.

## Integrator CUA observations before the shared rebuild

These were reported by `/root`, who operated CUA. This source-inventory author
did not execute or independently verify them. They refer to the inherited
built preview, not the newly written UI batch. Screenshot archiving is owned
by the capture worker; this subsection is a message-derived observation log.

- At actual CSS 390 × 843, the mobile menu opened; Escape closed it, returned
  focus to Menu and set `aria-expanded=false`. Selecting Services reached the
  local overview.
- Portal keyboard flow: Documents → ArrowRight → Applications → End →
  Messages → Tab focused the `portal-messages` panel.
- Journal carousel Next changed `01 / 02` to `02 / 02`; ArrowLeft restored the
  first story. On `/journal`, Enter opened Sources and revisions, showing
  September 1 revision 1 and September 2 revision 2 with visible focus. Images
  decoded and observed warning/error logs were empty.
- Meet our team opened `/team`, with the 16-person roster. Ari's Second Home
  and Surya's E-VOA links returned to the matching homepage sections at top
  105px below a 72px sticky header, without occlusion.
- Company setup, tax and property were legible without overflow at mobile
  width. `/team` and `/services` had no overflow at 360 × 800. At 768px,
  homepage navigation fit and the hero layout remained clear. UL/OL child
  elements were LI.
- Homepage Skip to content left BODY focused. The unknown service slug showed
  a standard visible 404, disproving the source-only blank-page suspicion;
  it lacked recovery links and used the default dark appearance.

The focus and 404 findings informed the assigned fixes. All final changed
routes still need checks against the rebuilt integrated preview.

## Browser execution plan

1. Use the single owned loopback preview. Rediscover process ownership before
   replacing it. Keep temporary browser sessions bounded and close them.
2. Visit all eight routes at 1440px and 390px. Scroll through every section to
   trigger lazy images before testing `complete`, `naturalWidth` and `decode()`.
3. Stress the header, service details and Team at 360px. Inspect the full page
   as well as readable section crops; a very tall scaled screenshot is not
   sufficient evidence for text, controls or portrait quality.
4. Check keyboard interaction: skip link, mobile menu Escape/focus, Portal tab
   sequence, Journal carousel and source/revision details. Preserve focus on
   intentional navigation and provide visible focus indicators.
5. Inspect every local CTA and homepage anchor. For external destinations,
   record the public page identity and any sign-in requirement. Do not submit
   forms, send messages, dial, authenticate or bypass access screens.
6. Check Journal ready and unavailable/failure presentation using the agreed
   local fixture/test arrangement. Do not add demo fallback after service
   failure or confuse synthetic data with production integration.
7. After the one coordinated change batch, rerun the affected suites and
   website/architecture checks, then optimized build and typecheck sequentially.
   Record real test totals and failures rather than copying prior counts.
8. Capture final desktop/mobile screenshots and compare accepted findings.
   Separate builder verification from any independent visual reassessment.

## Review contract

The website skill directs reviewers to
`.agents/skills/website/references/review-protocol.md`. The protocol requires:

- Advanced critique covering hierarchy, conversion, trust, accessibility,
  visual quality, page length, mobile usage and ecosystem omissions; precise
  observations, counterarguments and concrete research questions.
- Focused Gemini research of those questions with current primary sources
  and actual browsing evidence. A sourced answer without observed browsing
  is not a verified research pass. Reuse existing relevant research and only
  open a new question when the current review exposes one.
- Visual reassessment using real screenshots rather than only JSX/CSS;
  correct findings caused by lazy loading, preview safeguards or stale assets.
- A synthesis distinguishing defects, plausible experiments, owner decisions
  and production blockers; explain disagreements rather than averaging scores.

The protocol does not mandate Claude by name. A Claude visual review through
the sanctioned subscription CLI can supply independent critique, but its
receipt must record vendor, requested model, actually observed served model,
time, exact input scope, tools, execution status and limitations. A model's
self-description is not backend attestation. No new paid API credentials.
Processes must remain bounded. A code-only reviewer is not a visual reviewer;
final builder screenshots are not an independent re-review.

The packet should contain current route inventory, owner constraints, CTA
destinations, desktop/mobile images with lazy content decoded, and the
production comparison. Identify old versus current Team inputs explicitly.
The independent reviewer should have a read-only scope and designated report
location. No client data, credentials or raw operational records belong in it.

## Out of scope

No design restart, new services, biographies, editorial/legal assertions,
production connectivity or release action follows from this review. Preserve
the approved palette, typography, logo, ocean and book imagery, founder band,
full team and project ownership. Track A and Track B share an integration
checkpoint; neither overwrites the other's files or the completed checkpoint.
