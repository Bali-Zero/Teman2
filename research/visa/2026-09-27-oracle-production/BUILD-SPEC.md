---
adversarial_review: exempt-mission-process-record # ORACLE-PROD-20260927 process record (spec, progress, freeze or round log) for a code release, not a research deliverable; the reviewed object is the code, whose council and final-gate verdicts are in evidence/2026-09/agent-air-m5-mouth-oracle-prod-0927-d995492b/
---

# BUILD-SPEC — Visa Oracle atlas into production (ORACLE-PROD-20260927, Phase A)

Author: Dux Opus 5.5 xhigh. Consumer: one Sonnet 5 implementer, single writer in
`/Users/balizero/nuzantara/.worktrees/mouth-oracle-prod-0927`. Governing spec: `WINDOW-SPEC.md` (same dir).

Paths below: `R` = `apps/mouth/src/app/(visa-oracle)/visa-oracle` (quote the parentheses in shells).
`P` = `/Users/balizero/nuzantara/.worktrees/mouth-oracle-atlas-0927/research/visa/2026-09-27-branching-atlas/prototype`
(frozen, READ-ONLY — visual reference: `P/src/App.jsx`, `QuestionControls.jsx`, `Outcome.jsx`, `scenes.js`,
`atlas.css`, `refinements.css`, `permit.css`, `journey.css`). Never copy its Vite app, `canonical/` helpers,
`?qa=1` hook, `/api/evaluate` fetch, `LOCAL_SIGNED_PACK_PREVIEW` check, balizero.com/contact link or its
simplified lifecycle.

## 0. Invariants (a violation = the build fails review)

1. Presentation only. Do NOT modify: `_lib/flow.ts`, `tree.ts`, `fact-mapper.ts`, `engine-adapter.ts`,
   `engine-adapter.test.ts` (sibling PR #7504), `engine-response.ts`, `evaluation-*.ts`, `consent-store.ts`,
   `resume-store.ts`, `telemetry.ts`, `runtime-mode.ts`, `shadow-*.ts`, `outcome-*.ts`, `i18n.ts`,
   `countries.ts`, API routes, `layout.tsx`, `page.tsx`, `privacy/`, `unlock/`, any package.json/lockfile,
   any backend. No new npm dependency.
2. `OracleShellRuntime` keeps every existing effect/callback byte-for-byte in behaviour: evaluation effect,
   idempotency/cache, SHADOW/CURATED fail-closed, internal preview, resume opt-in/expiry, identity clearing,
   `leaveOutcome`, telemetry. You change JSX/markup/classes and add purely presentational state
   (scene preview, motion pause, route dialog). Question ids and public API contracts unchanged.
3. Every existing test must pass UNCHANGED: `npx vitest run "src/app/(visa-oracle)"` baseline on Pro =
   45 files / 1229 tests green (2026-09-27T08:54Z). Do not edit existing test files. Add new tests only.
4. Accessible names that tests pin (exact): framing CTA = `translate(lang,"framing.cta")` ("Start"/"Mulai");
   in_indonesia options = their i18n labels ("Yes, I’m here", "No, I’m planning ahead"); holds_stay_permit
   options "Yes"/"No"; category tiles = exactly `q.category.opt.*` labels (glyphs/arrows `aria-hidden`, no
   extra text in the name); exactly ONE button matching `/^back$/i` on a question screen (QuestionScreen's own);
   exactly one `notsure.trigger` button; checkbox "Save my interview on this device for 2 hours" with the full
   `SESSION_COPY.resume` sentence VISIBLE on framing; "Clear saved interview"; "Talk to a consultant" toggle with
   `aria-expanded` + `#oracle-consultant-panel`; badge text "Visa decision support" rendered; LanguageToggle and
   ThemeToggle kept (e2e `visa-oracle-state-colours.spec.ts` pins the dark theme machinery: root
   `data-oracle-theme` + `data-oracle-theme-ready`); "Retry verified evaluation", "Edit answers"
   (`verdict.edit_answers`), "Start over"; loading text "Checking the verified Visa Oracle engine…".
5. Keep class hooks used by tests/e2e: `.oracle-root`, `.oracle-main__content` (the content column — e2e checks
   no descendant overflows 320px), `.oracle-headline`, `.oracle-confirmation__row`, `.oracle-verdict-card`,
   `.oracle-verdict-chip`, `.oracle-outcome*`, `.oracle-disclaimer`, `.oracle-footer`, all OutcomeSheet /
   ConfirmationCard / ConsentHandoff internals (do not restructure those components; restyle via CSS).
6. Every question heading still receives focus on mount (QuestionScreen already does; ConfirmationCard too).
7. `oracle.css`: do NOT add any new declaration of `--oracle-state-*` tokens anywhere (the token test parses
   the file and the e2e colour fence measures them). Do not delete existing rules. Append a new section.
8. No LLM reasoning text, no application-portal links, no invented prices/timelines/approval claims, no fake
   persistence claims. Scenery never decides or implies eligibility. Synthetic data only in tests.
9. Never run `npm install`/`npm ci` anywhere. Heavy commands run on Pro (see §7), never on M5.

## 1. Assets

Copy the 19 WebPs byte-exact from `P/public/assets/*.webp` to `apps/mouth/public/static/visa-oracle/atlas/`
(names unchanged: retirement, watershed, work, business, confluence, diaspora, family, identity, invest, other,
remote, second_home, study, tourism, indonesia, world, permit-paper, permit-depth, logo). NO png. Verify each
sha256 equals `sha256` in `P/../optimized-assets.json`. Public URL base: `/static/visa-oracle/atlas/`.

## 2. New `R/_lib/atlas-scenes.ts` (pure TS, no React)

- `ATLAS_ASSET_BASE = "/static/visa-oracle/atlas/"`, `ATLAS_ASSETS` = readonly list of the 19 filenames.
- `ATLAS_BRANCHES: Record<CategoryKey, { family: "Crossing"|"Terraces"|"Courtyards"; glyph: string /*SVG path d*/; asset: string }>`
  for all 11 `CATEGORY_KEYS` (import from `tree.ts`); glyph paths verbatim from `P/src/scenes.js`.
- `type AtlasSceneId = "entry"|"world"|"paper"|"watershed"|"identity"|"stay"|"confluence"|CategoryKey`,
  `type AtlasSceneLayout = "stage"|"landscape"`.
- `projectAtlasScene(node: OracleNode, facts: OracleFacts, previewCategory?: string|null)` →
  `{ id, layout, asset, labelKey: AtlasCopyKey | null }`, mirroring `P/src/scenes.js` `projectScene`:
  framing→entry(stage, indonesia.webp); in_indonesia→world(stage, world.webp); holds_stay_permit→paper(stage,
  permit-paper.webp); category→watershed(landscape, `${preview}.webp` if preview is a valid category else
  watershed.webp, label "Choose your direction"); review_gate & confirmation→confluence ("One last check" /
  "Your route"); verdict→confluence ("Your next chapter"); nationalities|birth_date|guardian_consent→identity
  ("A little about you"); any other question with a valid `facts.category`→that category's landscape (label =
  branch name); otherwise→stay(landscape, permit-paper.webp, "Here, in Indonesia" if facts.in_indonesia==="yes"
  else "Planning ahead"). Unknown/invalid category values fall back safely (never throw).
- `ATLAS_COPY: Record<"en"|"id", Record<AtlasCopyKey,string>>` + `atlasCopy(lang, key, vars?)` (`{q}` interpolation).
  Keys and values (EN / ID):
  - tools: "Your route"/"Rute Anda"; "Pause motion"/"Jeda animasi"; "Resume motion"/"Lanjutkan animasi";
    "Close your route"/"Tutup rute Anda"; route heading "The way you came."/"Jalan yang Anda tempuh.";
    "Explore another direction"/"Jelajahi arah lain"; "Change"/"Ubah"; "Change: {q}"/"Ubah: {q}";
    empty ledger "No answers yet."/"Belum ada jawaban."
  - scene labels: "Choose your direction"/"Pilih arah Anda"; "A little about you"/"Sedikit tentang Anda";
    "Here, in Indonesia"/"Di sini, di Indonesia"; "Planning ahead"/"Merencanakan ke depan";
    "One last check"/"Satu pemeriksaan terakhir"; "Your route"/"Rute Anda"; "Your next chapter"/"Babak Anda
    berikutnya"; "One more detail"/"Satu detail lagi"; hub line "Many directions. One beginning."/"Banyak arah.
    Satu awal."
  - branch name / line (EN / ID):
    tourism "A little further"/"Sedikit lebih jauh" · "Across islands. Into possibility."/"Melintasi pulau. Menuju kemungkinan."
    business "Room for ideas"/"Ruang untuk gagasan" · "Where conversations become possibilities."/"Tempat percakapan menjadi peluang."
    work "Build your next chapter"/"Bangun babak berikutnya" · "A different horizon for your working life."/"Cakrawala baru bagi kehidupan kerja Anda."
    invest "Ground to build on"/"Landasan untuk membangun" · "An idea takes shape, one layer at a time."/"Sebuah gagasan terbentuk, lapis demi lapis."
    remote "Work, with a wider horizon"/"Bekerja, dengan cakrawala lebih luas" · "Connected to your work. Open to somewhere new."/"Tetap terhubung dengan pekerjaan. Terbuka pada tempat baru."
    family "Closer, together"/"Lebih dekat, bersama" · "Two paths. A place to meet."/"Dua jalan. Satu tempat bertemu."
    retirement "A different rhythm"/"Irama yang berbeda" · "More room for the life ahead."/"Ruang lebih lapang untuk hidup ke depan."
    second_home "A place to return to"/"Tempat untuk kembali" · "Your own corner of a wider world."/"Sudut Anda sendiri di dunia yang lebih luas."
    study "A world to discover"/"Dunia untuk dijelajahi" · "New perspectives begin here."/"Perspektif baru dimulai di sini."
    diaspora "A thread that leads home"/"Benang yang menuntun pulang" · "Where your story finds another connection."/"Tempat kisah Anda menemukan ikatan lain."
    other "A path of your own"/"Jalan Anda sendiri" · "Let’s find the shape of your journey."/"Mari temukan bentuk perjalanan Anda."
  - decorative map labels: islands Sumatra, Kalimantan, Sulawesi, Java/Jawa, Bali, Papua (positions from
    `P/src/App.jsx` islandLabels); continents NORTH AMERICA/AMERIKA UTARA, SOUTH AMERICA/AMERIKA SELATAN,
    EUROPE/EROPA, AFRICA/AFRIKA, ASIA/ASIA, AUSTRALIA/AUSTRALIA (worldLabels positions); place label
    "Indonesia".

## 3. New `R/_components/OracleScenery.tsx` ("use client", decoration only)

Props: `{ scene: AtlasScene; motion: boolean; language }`. Root `<div className="oracle-atlas-scenery" aria-hidden="true">`;
NO focusable descendants, no text a screen reader needs.
- layout "stage": port `P/src/App.jsx` legacy art: two maps (`indonesia.webp` island, `world.webp` globe) whose
  visibility is driven by CSS from `data-scene` (entry/world/paper) so entry→world crossfades; decorative
  labels (islands on entry, continents on world); permit art (paper still + depth preload + the SVG
  `paper-layers` with `clipPath` — use a unique id via `useId()`), and the layered paper arrival when entering
  paper from world with motion on and both images loaded (port `paperArrival` logic locally from scene
  transitions; it must never gate navigation).
- layout "landscape": port `Scenery` from `P/src/App.jsx` (preload `new Image()`, WAAPI arrival 520 ms only if
  `motion` and the image loaded <400 ms, cancel animations when motion turns off, keep previous image until the
  next loads, image error → no image, paper background remains) + `.oracle-atlas-scene-wash`.
- Export `AtlasGlyph({ category })` (svg `aria-hidden`, `focusable="false"`, path from ATLAS_BRANCHES, fallback other).
- Export `AtlasBranchCaption({ category, language, hub? })` (aside, `aria-hidden`, glyph + branch line; hub
  variant shows hovered branch line or the hub line).

## 4. New `R/_components/AtlasRoute.tsx` ("use client")

Native `<dialog className="oracle-atlas-route" aria-labelledby=…>` exposing an imperative `open(opener)` via
`forwardRef`/`useImperativeHandle` (or a controlled `open` prop). Content: eyebrow "Your route", h2 "The way you
came.", an ordered ledger of answered questions in HISTORY order (unique ids from `state.history` question
nodes whose fact is defined) — prompt via `questionPromptI18nKey`+`translate`, value via ConfirmationCard's
exported `formatFactDisplay` (check its signature), each with a "Change" button (`aria-label` "Change: {prompt}")
→ `onEdit(questionId)` then close; if `facts.category` is set, a `<details>` "Explore another direction" with the
other 10 category buttons (label = `q.category.opt.*`) → `onSelectCategory(key)` then close. Close button
(aria-label "Close your route"), backdrop click closes, Escape closes; focus returns to the opener on the
dialog's `close` event (NOT `onCancel` — Safari). jsdom lacks `showModal`: fall back to `setAttribute("open","")`
when `typeof dialog.showModal !== "function"`.

## 5. `R/_components/QuestionScreen.tsx` — additive props only

Add optional `presentation?: "default"|"world"|"permit"|"watershed"` (default "default") and
`onPreviewOption?: (key: string|null) => void`. Root gets `data-presentation={presentation}`. With "default"
the rendered DOM must stay identical to today. Only the options markup changes per presentation:
- "world" (in_indonesia): each option = `<button type="button" className="oracle-atlas-choice" data-answer={key}>
  <span className="oracle-atlas-pin" aria-hidden="true"/><span className="oracle-atlas-pill">{label}<span aria-hidden="true"> →</span></span></button>`
  inside the existing `role="group"` wrapper (class `oracle-options oracle-atlas-choices`).
- "permit" (holds_stay_permit): `<button className="oracle-atlas-permit-answer" data-answer={key}>{label}</button>`
  inside the group (class `oracle-options oracle-atlas-permit-options`).
- "watershed" (category, kind tiles): each tile `<button className="oracle-tile oracle-atlas-branch" data-category={key}
  onPointerEnter={e=>e.pointerType==="mouse"&&onPreviewOption?.(key)} onFocus={()=>onPreviewOption?.(key)}>
  <AtlasGlyph category={key}/><span>{label}</span><span className="oracle-atlas-branch__arrow" aria-hidden="true">↗</span></button>`;
  group `onMouseLeave={()=>onPreviewOption?.(null)}`; accessible name must equal the label exactly.
Back, notices, conflict alert, h1+hint, WhyWeAsk, HUMAN_CONTEXT notice and NotSure stay exactly where they are.

## 6. `R/_components/OracleShell.tsx` — markup of `OracleShellRuntime` (+ hydration placeholder)

- Presentational state: `previewCategory` (reset on every step change), `motionPaused` (header Pause/Resume;
  effective `motion = !reducedMotion && !motionPaused`), route dialog ref + opener.
- `scene = projectAtlasScene(current, state.facts, current is category question ? previewCategory : null)`.
- Root `<div className="oracle-root oracle-atlas" data-oracle-theme={theme} data-funnel="visa"
  data-scene={scene.id} data-scene-layout={scene.layout} data-motion={motion?"on":"paused"} …>`; the
  hydration placeholder root also gets `oracle-atlas`.
- On step change (`kind+questionId` key) scroll to top via `document.documentElement.scrollTop = 0` (no
  `window.scrollTo` — jsdom noise).
- Header `.oracle-topbar.oracle-atlas-header`: brand (logo `<img alt="">` + "BALI ZERO"), badge (existing
  `oracle-badge` with title), centred wordmark `Visa <em>Oracle</em>` (hidden on stage scenes, where the stage
  has its own), tools: "Your route" (only when at least one answered question exists and not on framing),
  Pause/Resume motion, Clear saved interview (existing condition), LanguageToggle, ThemeToggle.
- ConsultantContact: same component and props. Before an outcome exists render it in a header-adjacent slot
  styled as a compact floating tool (toggle button; panel as an anchored card, scrollable, z-index above
  scenery); when `outcome` exists render it INSIDE `.oracle-main__content` after OutcomeSheet (inline "plan this
  with Bali Zero" position, open by default as today).
- Remove LivingTree and PathsCounter from the render (files stay; their unit tests keep passing). Remove now
  unused imports.
- `<main className="oracle-main oracle-atlas-main">` contains `<OracleScenery …/>` (always mounted, so stage
  crossfades animate) and `<div className="oracle-main__content">`:
  - framing (entry stage): `<h1 className="oracle-headline oracle-atlas-entry__title" tabIndex={-1}>Visa <em>Oracle</em></h1>`,
    `<p>` framing.title, `<p>` framing.body (small), Start button (existing handler, name = framing.cta, breathing
    copper dot `aria-hidden`), save opt-in: checkbox + label `resumeOptIn` + visible small `resume` sentence.
  - question: stage questions (in_indonesia → presentation "world", holds_stay_permit → "permit") also render a
    decorative `aria-hidden` stage wordmark; landscape questions render eyebrow (`pendingFollowUp===questionId` →
    "One more detail", else scene label) then QuestionScreen (category → "watershed" + `onPreviewOption`) and,
    on desktop, `AtlasBranchCaption` (hub variant on category; branch variant when a category is chosen).
  - confirmation: eyebrow + decorative route ribbon (glyph of chosen category) + existing ConfirmationCard.
  - verdict: eyebrow "Your next chapter"; loading = existing status text with a decorative orbit; then
    VerdictReveal + OutcomeSheet + ConsultantContact + existing action row (retry / Edit answers / Start over)
    + `<details>` "Explore another direction" (other categories → `handleSelectCategory`).
- AtlasRoute dialog rendered once at root level with `onEdit={handleEdit}` and `onSelectCategory={handleSelectCategory}`.
- Footer unchanged (`.oracle-footer`, disclaimer + privacy link).

## 7. `R/oracle.css` — append section `/* ─── Atlas presentation (ORACLE-PROD-20260927) ─── */`

Port the prototype CSS (`atlas.css`, `refinements.css`, `permit.css`, `journey.css`) under `.oracle-root.oracle-atlas`
with the new class names (`oracle-atlas-*`). Rules:
- Palette through tokens so both themes work. Light: `.oracle-root.oracle-atlas[data-oracle-theme="light"]` re-points
  NON-state tokens: `--oracle-bg:#f7f4ee; --oracle-bg-elevated:#fffaf4; --oracle-ink:#233d52; --oracle-ink-muted:#53616b;
  --oracle-ink-faint:#5a6772; --oracle-border:rgba(35,61,82,.16); --oracle-border-strong:#b8b2a5; --oracle-focus-ring:#233d52`
  plus atlas vars `--atlas-copper:#9d4e38; --atlas-rule:#b8b2a5; --atlas-serif:Baskerville,"Iowan Old Style",Georgia,serif;
  --atlas-art-filter:none`. Dark (`[data-oracle-theme="dark"]`): a night-atlas palette (bg #111a21, elevated #18232c,
  ink #efe8da, muted #c9c1ae, faint #aaa290, borders rgba(239,232,218,.16/.28), copper #e3a482, focus #efe8da,
  `--atlas-art-filter:brightness(.45) saturate(.85)`); all atlas colours must come from these vars. Contrast ≥ 4.5:1
  for text in both themes (axe runs in e2e).
- Stage layout (`[data-scene-layout="stage"]`): `.oracle-atlas-main` = the prototype `.atlas` box
  (`width:min(100vw,160dvh); aspect-ratio:1.6; container-type:inline-size; margin-inline:auto; position:relative;
  overflow:hidden`), header overlays its top (absolute, translucent). Entry/world/permit positions from the prototype
  (`%`/`cqw`). QuestionScreen parts positioned by `[data-presentation="world"|"permit"]` selectors: title block at the
  prototype's question-title/permit h2 position, options at the pin positions (`[data-answer="no"]` = left 24.3% top
  77.3% slate; `[data-answer="yes"]` = left 80.6% top 66.7% copper, with the "Indonesia" place label), NotSure at
  bottom-right, Back at bottom-left, WhyWeAsk anchored bottom-centre (expands upward), HUMAN_CONTEXT notice under the
  permit buttons. ≤700px: port the prototype's mobile rules; flow layout is acceptable for entry if absolute
  placement would overlap (framing body + long resume sentence must be fully visible, no overlap, no horizontal
  overflow at 320/390px).
- Landscape layout: prototype `journey.css` (`scene-art` behind at 100dvh/min 820px with wash; content column
  `min(550px,49vw)` with 126px top padding; ≤700px image band 290px under the 64px header then content). Map
  `.oracle-main__content` to `.scene-content`. Branch board 2-col grid; option cards like `.answer-option`; inputs,
  checklists, confirmation rows, candidate cards, outcome reasons, legal sources, consultant card, route dialog,
  details/summary styled per journey.css. Headline: serif 400, `clamp(32px,3.9vw,59px)`.
- Motion: arrival/breathe/crossfade animations only on decoration; `[data-motion="paused"]` and
  `@media (prefers-reduced-motion: reduce)` stop them (scoped to `.oracle-atlas`, never global). Motion never
  controls navigation.
- Print: keep existing print rules working (hide scenery/header tools in print).

## 8. New tests (Vitest, jsdom, synthetic only)

- `R/_lib/atlas-scenes.test.ts`: all 11 categories have glyph+asset; projection table (framing, in_indonesia,
  holds_stay_permit, category with/without/invalid preview, identity ids, review_gate, confirmation, verdict,
  post-category question per category, pre-category onshore question yes/no); every referenced asset is in
  ATLAS_ASSETS and exists under `apps/mouth/public/static/visa-oracle/atlas/`; no PNG there; EN/ID copy key parity,
  non-empty; `atlasCopy` interpolation.
- `R/_components/OracleScenery.test.tsx`: aria-hidden root, no focusable descendants, stage vs landscape, image
  error leaves no img, motion off → no `animate` call.
- `R/_components/AtlasRoute.test.tsx`: ledger order = history; Change calls onEdit + closes + focus returns to
  opener; alternatives exclude the current category and call onSelectCategory; ID copy.
- `R/_components/QuestionScreen.atlas.test.tsx`: exact accessible names per presentation; watershed preview on focus
  and mouse pointerenter (not touch) and reset on mouseleave; default presentation unchanged (no data-answer pins).
- `R/_components/OracleShell.atlas.test.tsx` (mock evaluation like OracleShell.test.tsx does): data-scene walk
  entry→world→paper→identity→watershed→category landscape→confluence; Pause toggles `data-motion`; Your route →
  Change on an earlier answer prunes stale answers via the reducer (e.g. change category from work to tourism and
  the work-only question disappears from the ledger); Indonesian header/tool copy; framing shows resume sentence and
  unchecked checkbox.

## 9. Pro execution (never heavy work on M5)

Pro mirror worktree (broker): `/Users/nuzantara/nuzantara/.worktrees/mouth-oracle-prod-0927-pro` (origin/main
a837bd4dc6, node_modules symlinked). Sync from M5 with rsync of the changed paths only, e.g.
`rsync -a --delete "<M5 R>/" "pro:<Pro R>/"` and the atlas asset dir; prefix remote commands with
`export PATH=/opt/homebrew/bin:$PATH;`. Commands (from `apps/mouth`): `npx vitest run "src/app/(visa-oracle)"`,
`npx tsc --noEmit -p tsconfig.json` (report only errors in touched files vs baseline), `npx eslint "src/app/(visa-oracle)"`.
Do not run `next build`/Playwright — the Dux runs those.

## 10. Report back

Files changed/added with line counts, test counts before/after, tsc/eslint results (exact), any deviation from this
spec with the reason, and open risks. Do not commit, push, or touch any other worktree.
