# Independent local visual review

Served model: claude-opus-5. Final response below is preserved verbatim.
Reviewed images are frozen in output/playwright/website-r19-pro/reviewed-before-fixes/.
The sibling review-resolution.md records the subsequent bounded fixes.

## What I inspected

**Images** (all six, via Read): `journal-desktop.png` (1440×2397, shown to me at 1202 wide), `journal-mobile.png` (390×2363, shown at 330), `amendment-desktop.png` and `amendment-mobile.png` (native detail — used for all small-text reading), `home-journal-desktop.png`, `home-journal-mobile.png`.

**Files**: `src/components/Journal.tsx`, `src/components/journal/JournalIndex.tsx`, `ArticleDestination.tsx`, `FeedNotice.tsx`, `journal/Journal.module.css`, `src/lib/editorial-feed.ts` (v2), plus for corroboration `src/app/journal/page.tsx`, `src/lib/server/journal-feed.ts`, `src/lib/server/magazine-fixture.ts`, `ui/Container.tsx`, `styles/design-system.module.css`, and `app/globals.css` (lines 1–2323, 3600–4510, 4700–6499).

## Release blockers for this local fixture slice

**None.** No broken image frame, no leaked private fixture string, no false source link, no invisible focus.

## Should fix in this slice

**1. Label in Name failure on the Journal header brand link — Medium (a11y, WCAG 2.5.3 A)**
`JournalIndex.tsx:24-27` — `<a aria-label="Bali Zero home">` wraps visible text "The Bali Zero Journal". The accessible name doesn't contain the visible label, so voice-control users saying the visible words can't activate it.
*Fix*: drop the `aria-label` (the `<span>` names the link), or use `aria-label="The Bali Zero Journal — Bali Zero home"`.

**2. Double horizontal gutter on the /journal hero — Medium (visual)**
`Journal.module.css:51` — `.intro` adds `5%` padding-inline *and* nests a `Container`. At 1440 the hero copy starts at 136px while the "Selected stories" rule and cards start at 64px (`min(100% - 2×clamp(1.25rem,5vw,4rem), 82.5rem)`); at 390 it's ~39px vs 20px. Visible in `journal-desktop.png` (eyebrow/H1 left edge vs the rule below) and `journal-mobile.png`.
*Fix*: `padding: clamp(4.5rem,10vw,8rem) 0 clamp(3.5rem,7vw,6rem);` — the inner Container already sets the gutter (the background band stays full-bleed). Header/footer also sit at 5% (72px) vs content 64px; worth unifying.

## Low / cosmetic

**3. Orphan rule under image-less cards — Low.** `journal-desktop.png` right column: "Room to read" text ends ~y=1105 but its bottom rule sits ~y=1500. Cause: `.card{height:100%}` (`Journal.module.css:124-132`) stretching to a row height set by the 16:9 lead image. *Trigger*: any row mixing an image card with text-only cards (the fixture always does). *Fix*: `align-items: start` on `.articleGrid` (`:107`).

**4. Hierarchy inversion on desktop /journal — Low (stylistic).** The lead headline renders ~410px below the secondary card's headline, so the first `<ol>` item reads as subordinate. *Fix (optional)*: tighten `.articleGrid > li:first-child .imageFrame` to ~21/9, or put the lead's eyebrow+title above its image.

**5. Home grid reserves an empty third column — Low.** `Journal.tsx:149-160`: with 3 stories `side` is empty, but `.news-side` still renders and `.editorial-grid` keeps `minmax(0,0.75fr)` (`globals.css:3658-3663`) — the dead space right of "Notes in the margin" in `home-journal-desktop.png`. *Fix*: render `.news-side` only when `side.length`, plus `.editorial-grid:has(> :nth-child(2):last-child){grid-template-columns:minmax(0,1.35fr) minmax(0,1fr)}`.

**6. Carousel slide 2 collapses ~300px, and is unphotographed — Low (evidence gap).** Only story 1 has artwork, so pressing "Next editorial story" drops `.feature > img` (`height:300px`, `globals.css:3675-3683`) and the card shrinks, shifting content below. The text-only feature path (`globals.css:6498`) is the one claimed behaviour no supplied screenshot shows. *Fix*: capture that slide; optionally give `.feature` a min-height so slides match.

**7. Hover affordance on a deliberately non-clickable card — Low (trust).** `Journal.module.css:160` `.cardLink:hover .imageFrame img{transform:scale(1.018)}` still fires on the fixture `<div>` from `ArticleDestination.tsx:7`, implying a link that isn't there. *Fix*: scope to `a.cardLink:hover`.

**8. Skip-link target not focusable — Low.** `JournalIndex.tsx:35` `<main id="journal-content">` has no `tabIndex={-1}`; focus can stay on the link in Safari. *Fix*: add `tabIndex={-1}`.

**9. `<ol>` with `list-style:none` loses list semantics in Safari/VoiceOver — Low.** `JournalIndex.tsx:68` + `Journal.module.css:113`. *Fix*: `role="list"`.

**10. No per-card synthetic marker on the home page — Low (trust).** /journal marks every card "Sample story" (`JournalIndex.tsx:100`); `Journal.tsx` relies only on the section note, so an isolated home card reads as a real dated story ("Notes in the margin · Amended · 2 September 2026"). *Fix*: pass `fixture` into `StoryDate`/feature meta.

**11. Mobile header target spacing — Low (WCAG 2.2 2.5.8, borderline).** `Journal.module.css:288-299`: nav links are ~18px tall and ~7px below the brand link. *Fix*: `min-height:24px` / `padding:0.4rem 0` on `.navigation a`.

**12. Fixture copy repeats — optional.** Identical "Why it matters" sentence and "GENERAL" eyebrow on all three cards (`magazine-fixture.ts:76,79`) makes the pattern look like boilerplate rather than demonstrating it.

## Verified good (no action)

Missing images produce clean text layouts, not empty frames (`JournalIndex.tsx:74`, cards 2–3 on both breakpoints). Fixture titles and evidence URLs are inert: `ArticleDestination.tsx:6-8` returns a `div`/`span` for `development-only`, and `JournalIndex.tsx:109` never renders the URL in fixture mode — no `example.org` leak, publisher shown as text with "Local design proof; not a news source". Amendment is honest: "Amended · Revision 2" plus dated Revision 1/2, no invented correction prose, and the card date matches the last revision (enforced at `editorial-feed.ts:140`). Focus is visible everywhere I could trace it (`globals.css:6432`, `:3872`, `summary:focus-visible` at `:52-59`); the counter is a polite live region and arrow handling is scoped to the focused card. No WITHDRAWN/UNPUBLISHED/PRIVATE fixture strings appear in any screenshot. Alt text is non-deceptive: "Abstract paper, forest and copper shapes — original local preview artwork". Meta text ≈4.9:1 and copper ≈5.6:1 on paper by hand calculation — passing at their sizes.

## Future production requirements (not this slice)

Non-fixture mode wraps title + summary + why-it-matters + meta in a single `<a>` (`ArticleDestination.tsx:8`), producing very long accessible link names, and external destinations get no rel/target treatment — both need work before transport is armed. Real amendments will need visible "what changed" prose, which the fixture correctly omits. Cover-image delivery (CORP) remains unproven, so the text-led layout is the right interim.

## Limitations

Static, read-only: I ran nothing, used no screen reader or contrast tool — contrast figures are hand-computed approximations. My viewer downscaled the two full pages (1440→1202, 390→330), so pixel measurements carry roughly ±10px; the gutter numbers in finding 2 are corroborated by CSS arithmetic, the header-vs-content 8px is within measurement error. Both home crops are cut at the right edge ("Explore the Journal ↗" clipped) — I read that as a crop boundary, not overflow, and could not verify the right edge from these files. Not covered by any image: carousel slide 2, any non-ready feed state, hover and focus rendering. A middle range of `globals.css` (~2324–3599, 4511–4699) is unread, so a later override there could change my CSS-based conclusions.

**Verdict: acceptable for local fixture proof.** This is not production approval and certifies nothing about a cutover.
