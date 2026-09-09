# R19 full-site coverage matrix

> Active-work update — palette and typography design now supersedes final review closure. Journal local technical proof is complete, and the CTA CSS correction has passing focused proof. The independent follow-up was interrupted after the owner redirect: exit 143, status `no_final_result`, no verdict; the first FAIL is preserved as history. A distinct pre-design WIP checkpoint is now authorized at `output/checkpoints/2026-09-07-pre-design`, with acceptance pending and archive/hash verification assigned to its owner. This matrix remains dated evidence, not approval of later design changes. No completion handoff or state acceptance update is made.

Date: 2026-09-07 (WITA). **NOT ACCEPTED: independent Claude found a blocking desktop/tablet homepage CTA overlap. Correction and follow-up review are pending.** No row asserts production transport use or release readiness.

## Evidence basis

- **FINAL:** replacement fixture preview, single loopback listener PID 10597, exact worktree, final metrics/screenshots.
- **FOCUSED:** final browser interaction receipts, distinct from source assertions/unit tests.
- **PARENT:** coordinating reviewer's independent observations on replacement build, attributed explicitly.
- **BASELINE:** older built preview, retained in `browser-baseline.md`; not verification of final code.

Main metrics: `output/playwright/website-r19-full-site/final/metrics.json`. Focused metrics: same `final/focused-metrics.json`, SHA256 `595ba30801c83a675b10aa552ca851e7271882e35b32961060b01004c50ec4ad`. Screenshot inventory: same `final/screenshot-manifest.json`, 73 PNGs with dimensions/hashes. Integrated verification: `final-evidence-verification.json` in this review directory.

## All valid routes

Every FINAL cell returned 200 + noindex, with zero document overflow, image decode failure, or page/console error. Desktop 1440×1000, mobile 390×900, tablet 768×900; Chromium 152.0.7977.82. Eight routes × three widths = 24 views. The 31 aborted request events remain in the traces and are not described as zero network failures.

| Route | Desktop | Mobile | Tablet | Selected 360px / focused scope |
| --- | --- | --- | --- | --- |
| `/` | FINAL PASS | FINAL PASS | FINAL PASS | Capture homepage 360×800/menu; PARENT no overflow, Escape/focus, skip, Portal, Journal, anchors |
| `/services` | FINAL PASS | FINAL PASS | FINAL PASS | Four unique service names; skip/next Tab; no new full 360px route claim |
| `/services/immigration` | FINAL PASS | FINAL PASS | FINAL PASS | Skip/next Tab; PARENT navigation and final desktop PNG |
| `/services/company-setup` | FINAL PASS | FINAL PASS | FINAL PASS | Capture selected 360×800 stress; skip/next Tab |
| `/services/tax` | FINAL PASS | FINAL PASS | FINAL PASS | Skip/next Tab; no separate final 360px claim |
| `/services/property` | FINAL PASS | FINAL PASS | FINAL PASS | Skip/next Tab; no separate final 360px claim |
| `/team` | FINAL PASS | FINAL PASS | FINAL PASS | PARENT selected 360px no overflow, 16 names, Ari/Surya; skip/next Tab |
| `/journal` | FINAL PASS | FINAL PASS | FINAL PASS | PARENT selected 360px no overflow, amended disclosure/dates; fixture active |

The 360px scope is selected, not an eight-route fourth-width sweep. Baseline-only 360px observations remain historical.

## Homepage sections

All sections appear in the reviewed-build full-page matrix. Eight content anchors also have focused 1440/390 captures, totaling 16 section images. Independent Claude returned FAIL for a real CTA overlap; these metrics are scoped measurements, not visual acceptance or proof of a later correction.

| Section | Current coverage | Interaction / limit |
| --- | --- | --- |
| Header/navigation | FINAL three widths; FOCUSED 360px; PARENT keyboard | Menu Escape collapses and restores focus |
| Hero/four service pathways | Matrix measurements pass; PARENT mobile viewport PNG | **Claude FAIL: “Explore all services →” obscured at desktop/tablet; open blocker** |
| Services/tools `#tools` | FINAL + FOCUSED 1440/390 | Lifted tool-card overlap requires correction; local routes/external destinations audited separately |
| E-VOA `#evoa` | FINAL + FOCUSED 1440/390 | Surya anchor below header; no external application |
| Second Home `#second-home-studio` | FINAL + FOCUSED 1440/390 | Ari anchor below header; no eligibility answers |
| Reviews `#google-reviews` | FINAL + FOCUSED 1440/390 | Destination reachability; ratings/counts not certified |
| Portal `#client-portal` | FINAL + FOCUSED 1440/390; PARENT keyboard | ArrowRight/End/Tab; external My stops at login |
| Journal `#journal` | FINAL + FOCUSED 1440/390; PARENT keyboard | Carousel/revision disclosure; mobile element-image sticky-header artifact retained, full homepage input substituted |
| Team `#team` | FINAL + FOCUSED 1440/390 | Founder-only homepage imagery; full roster on `/team` |
| Contact `#contact` | FINAL + FOCUSED 1440/390 | Intents checked; no email/call/message |
| Footer | FINAL three widths | Policy/destination inventory; not legal-content certification |

## Keyboard, missing routes, and presentation

| Check | Final result | Evidence scope |
| --- | --- | --- |
| Skip on homepage, Team, Services, four details | PASS 7/7 reach MAIN; next Tab reaches anchor | FOCUSED; PARENT homepage |
| Mobile menu selected 360px | PASS Escape, collapsed state, focus | FOCUSED + PARENT |
| Portal keys | PASS Documents → Applications → Messages; Tab into panel | PARENT current build |
| Journal carousel keys | PASS Next 01/02 → 02/02; ArrowLeft 01/02 | PARENT current build |
| Journal disclosure | PASS Enter opens; revision 1 September 1, revision 2 September 2 | PARENT; synthetic fixture, not real news |
| Service accessible names | PASS four distinct names | FOCUSED + integrated tests |
| Service targets | Two header links 44px; contact 48px | FOCUSED header/PARENT contact; not whole-site claim |
| Two unknown-route probes | PASS four desktop/mobile 404 cases with Home/Services recovery and no overflow | FOCUSED; tablet screenshots also captured |
| Team/anchors | PASS 16 names, 3 leadership + 13 others; Ari/Surya below header | PARENT current build |
| Images | Zero decode failures across 24 views; no broken Journal images observed | FINAL + PARENT |
| Browser errors | Zero valid-route page/console errors; 31 aborted requests retained | FINAL; 34 aborts including probes; two 404 console messages from deliberate unknown routes |
| PNG visual review | PARENT found no overlap in four selected PNGs; Claude found blocking homepage overlap outside that sample | See `claude-visual-review.md` and `review-resolution.md`; do not infer whole-site visual PASS |
| Contrast | Earlier limited solid-pair measurements remain BASELINE | Not full accessibility/image-background/focus/hover audit |
| Journal non-ready states | Passed integrated architecture/consumer tests | Not all failures displayed by normal ready preview fixture |

## External destinations

The destination audit observed 200 after redirects for these 15 public destinations, plus seven PARENT public first-screen inspections. This is reachability/identity evidence, separate from final local build tests. No authenticated/transactional workflow was exercised.

| Destination | URL / purpose | Boundary |
| --- | --- | --- |
| E-VOA | `https://balizero.com/visa/voa` | Entry reachable;no application/payment |
| Second Home | `https://balizero.com/visa/second-home/studio` | Studio entry;no answers/outcome |
| My | `https://my.balizero.com/`→portal login-upgraded | Authentication screen;no account/features |
| Visa Oracle | `https://visa.balizero.com/`→`https://balizero.com/visa` | Relevant redirected selection;no recommendation outcome |
| KBLI | `https://balizero.com/kbli` | Navigator entry;no classification accuracy proof |
| Tax | `https://tax.balizero.com/` | Calendar reachable;freshness/legal dates unverified |
| Property | `https://balizero.com/property/eligibility` | Checker entry;no coordinates/outcome |
| News | `https://balizero.com/news` | Legacy destination;distinct from local Journal |
| Google reviews | `https://maps.app.goo.gl/whiMUTNchcDR5naz8` | Bali Zero Google destination;ratings/counts uncertified |
| Office map | `https://maps.google.com/?q=Bali+Zero+Kerobokan` | Map reachable;address not independently certified |
| About | `https://balizero.com/v2/company/about` | Page presence;historical claims unverified |
| Legacy Team | `https://balizero.com/team` | Presence;approved local roster parity not asserted |
| Privacy | `https://balizero.com/v2/privacy` | Document presence;not legal review |
| Terms | `https://balizero.com/v2/terms` | Document presence;not legal review |
| Cookies | `https://balizero.com/v2/cookies` | Document presence;implementation not certified |

WhatsApp, email, and telephone were link intents only; no sends/calls. Telegram was not probed after blocked access. Production Magazine canonical admission is not established by these 15 checks; its separate local simulation and limits are in `journal-contract.md`.

## Acceptance ledger

| Boundary | Result |
| --- | --- |
| Track A local contract/actual v2 HTTP consumer | PASS focused 46/46 independently repeated; production factory unwired |
| Integrated Website suite | PASS 56/56 in 12 files; actual logs/hash verified |
| Integrated architecture suite | PASS 93/93 in 4 files; actual logs/hash verified |
| Shared build/post-build typecheck | PASS; single build, no duplicate rebuild |
| Final routes/focused browser | PASS named scope; 24 views, focused receipt, 73 PNG inventory |
| Independent boundary | PASS; GET framing/server-only findings closed |
| Independent Claude visual/copy review | **FAIL: real homepage CTA overlap; correction and follow-up pending** |
| REPORT,coverage,handoff,state disk/hash verification | **PENDING after verdict/final edits** |
| Production release/transport arming | **NOT REQUESTED / NOT PERFORMED** |
