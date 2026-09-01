import type { CSSProperties } from "react";

/**
 * MERAH PUTIH — the DAY token set (identity law R4).
 *
 * Spec: `research/design/2026-08-27-r4-identity-merah-putih-token-spec.md`
 * Winning rendering direction: «Cap Dinas» v2 (contest 2026-08-30,
 * `research/design/2026-08-30-merah-putih-rendering-contest-result.md`).
 *
 * WHY THIS FILE EXISTS (and why it is not an edit to `rumahVars.ts`):
 * `rumahVars` is the older "Rumah Putih" set — same warm paper and ink, but its
 * accent is the NAVY `#1e3863`, which R4 RETIRES from the whole public
 * perimeter. Editing rumahVars would silently repaint the homepage and the blog,
 * which are not in this lane's perimeter. So: same scoping contract, new set.
 *
 * SCOPING CONTRACT (do NOT break it — inherited from rumahVars.ts):
 *   - Apply `MERAH_PUTIH_DAY_VARS` INLINE on the converted route's own top-level
 *     wrapper, NEVER on a shared `layout.tsx`. CSS custom properties inherit, so
 *     everything inside the wrapper resolves the day values while NavShell and
 *     Footer — DOM ancestors that read `--nav-bg` / `--footer-bg` — keep the
 *     shell's own theme.
 *   - The wrapper this lands on already carries `data-funnel="visa"`, which the
 *     shared theme paints via `[data-theme="editorial"] [data-funnel="visa"]`
 *     (`packages/core/tokens/themes/editorial.css:56`) → navy gradient ground and
 *     the RETIRED red `#ff3344`. An inline style on that same element beats that
 *     selector, so the override needs no `!important` and no theme fork.
 *   - No file under `packages/core/tokens/` changes. Other routes are untouched.
 *
 * CONTRAST (WCAG 2.x, every ratio COMPUTED — R4 §4 forbids estimating them;
 * recomputed against these exact values by
 * `scripts/tests/test_merah_putih_day_contrast.py`, which goes red on any PR that
 * touches this file if a pair below drifts — via `.github/workflows/
 * merah-putih-day-contrast.yml`. That workflow was added 2026-08-31; before it, this
 * sentence read "fails the build", and it was FALSE: no workflow named the guard at
 * all, so the only place it ran was a nightly `continue-on-error` sweep that gates
 * nothing. Prose claiming enforcement that CI does not back is worth less than no
 * claim at all, because it stops the next reader from checking — which is why the
 * replacement is deliberately narrow: that check is ADVISORY. It RUNS and it goes
 * RED, visibly, on the pull request; it is not a required context and does not block
 * the merge queue. Do not upgrade this sentence to "blocks" without first putting the
 * context into branch protection):
 *   ink       #16213a on carta 14.79 · on elevated 16.00
 *   ink-soft  #475372 on carta  7.07 · on elevated  7.64
 *   muted     #6f6a5e on carta  4.98
 *   merah        #C8102E on carta 5.44 · white on it 5.88
 *   merah-action #D01033 on carta 5.11 · white on it 5.52
 *   merah-press  #c40020 on carta 5.77 · white on it 6.24
 *   eligible #16683f 6.29 · likely #2a6f97 5.08 · conditional #7a5209 6.39
 *   error    #a83a44 5.79 · white on it 6.26
 *   border-input #7a8093 on carta 3.64 · on elevated 3.94  (≥3 non-text bar)
 *   hairline #e3e1da on carta 1.21 — DECORATIVE ONLY, never the sole identifier
 *     of an interactive component (WCAG 2.2 SC 1.4.11). Interactive boundaries
 *     use `--border-strong`. This is the trap that made `#ddd8cb` (1.32) unusable
 *     as a component border even though the winning mockup paints dividers with it.
 *   RETIRED  #ff3344 on carta 3.34 — fails AA; this is what we are removing.
 */
export const MERAH_PUTIH_DAY_VARS = {
  // ── Grounds ────────────────────────────────────────────────────────────────
  // Overrides editorial's navy GRADIENT with a flat carta; `-solid` matters for
  // the components that read the solid form (nav band, print).
  "--surface-base": "#f7f6f2",
  "--surface-base-solid": "#f7f6f2",
  "--surface-raised": "#ffffff",
  "--surface-sunken": "#efece4",
  "--surface-deep": "#efece4",
  "--surface-overlay": "rgba(247, 246, 242, 0.94)",
  "--surface-scrim": "rgba(22, 33, 58, 0.45)",
  "--bz-elevated": "#ffffff",

  // ── Ink ────────────────────────────────────────────────────────────────────
  "--text-primary": "#16213a",
  "--text-secondary": "#475372",
  "--text-tertiary": "#6f6a5e",
  "--foreground": "#16213a",
  "--text-on-accent": "#ffffff",

  // ── Boundaries ─────────────────────────────────────────────────────────────
  // subtle/default are DECORATIVE (1.21 / 1.42 on carta). Anything that
  // identifies an interactive component must read `--border-strong` (3.64).
  "--border-subtle": "#e3e1da",
  "--border-default": "#d5d0c2",
  "--border-strong": "#7a8093",

  // ── Aliases that MUST be restated, not inherited ──────────────────────────
  // `semantic.css` declares these at :root as `var(--text-secondary)` /
  // `var(--border-subtle)`. A var() inside a custom-property declaration is
  // substituted using the cascade AT THE DECLARING ELEMENT — so an alias
  // declared at :root resolves against :ROOT's values and hands its
  // already-computed result down by inheritance. Overriding --text-secondary
  // on a wrapper deep in the tree therefore does NOT move the alias: it would
  // keep the dark theme's value while everything around it turned to paper.
  // These two are the most-consumed tokens in this perimeter (42 and 36 uses),
  // so the leak would have been wide and quiet. Restated with the same values
  // their sources take above.
  "--color-text-muted": "#475372",
  "--color-border-subtle": "#e3e1da",

  // ── A SECOND, UNRELATED VOCABULARY THAT LANDS INSIDE THIS WRAPPER ────────
  // `ConsentBanner` (apps/mouth/src/components/visa/ConsentBanner.tsx) renders
  // as a descendant of BOTH converted wrappers, and it speaks the portal's
  // "Warm Depth" token family — NOT the funnel's. `--tx-secondary` and
  // `--bz-accent` are plain hexes declared once at :root in
  // apps/mouth/src/app/globals.css (#94a3b8 / #d4845a), tuned for a dark
  // ground, and `[data-theme="editorial"]` never overrides them.
  //
  // So they are NOT an alias trap like the two above — they are a whole
  // vocabulary the day set did not know it had to answer for. MEASURED on the
  // day ground before this line existed: banner body text 2.56:1, links
  // 2.90:1, and white on the dismiss button 2.90:1 — all under the 4.5:1
  // floor, on a fixed-bottom consent bar every non-consented visitor sees.
  //
  // TWO OF THOSE THREE ARE THIS MIGRATION'S DOING; THE THIRD IS NOT, and the
  // first version of this comment blamed all three (corrected 2026-08-31 after
  // measuring the OLD design). Body text and links are ours: #94a3b8 measured
  // 6.25:1 against the navy it was chosen for and 2.56:1 against paper — the
  // ground moved, the token did not. The dismiss BUTTON is white on
  // `--bz-accent`, and both of those colours are element-local: a page-ground
  // change cannot move that ratio at all. A walk of the pre-migration
  // production measured that same button at 2.9:1 — it was already failing,
  // and this token mapping now fixes a defect that predates the lane rather
  // than one it introduced. Keeping the true and the false attribution in one
  // sentence would have taught the next reader that a ground change can break
  // an element-local pair, which is exactly the reasoning error to avoid here.
  //
  // Restated here rather than edited in ConsentBanner, deliberately: that
  // component is shared with the rest of the /visa funnel, which is still on
  // the dark theme and is a different lane's perimeter. Overriding the tokens
  // on OUR wrapper fixes our two routes and cannot reach anyone else's.
  // Of the components that speak this vocabulary, only ConsentBanner is
  // imported by these two pages (VisaChat, QuestionCounter and WhatsAppCTA
  // live on routes this wrapper never touches) — verified, not assumed.
  "--tx-secondary": "#475372", // 7.64:1 on the banner's white ground
  "--bz-accent": "#D01033", // 5.52:1 as a link, and white on it as a button

  // ── The red family (R4 §3) ────────────────────────────────────────────────
  // STRUCTURE (brand marks, progress fill, rules) vs ACTION (CTA, links) are
  // two duties, never interchangeable — and selection is NEVER red (R4 §4.5).
  "--accent-funnel": "#C8102E",
  "--accent-funnel-text": "#D01033",
  "--cta-bg": "#D01033",
  "--cta-bg-hover": "#c40020",
  "--cta-primary-bg": "#D01033",
  "--text-link": "#D01033",

  // ── Semantic states (R4 §3) ───────────────────────────────────────────────
  "--state-success": "#16683f",
  "--state-likely": "#2a6f97",
  "--state-info": "#2a6f97",
  "--state-warning": "#7a5209",
  "--state-danger": "#a83a44",
  "--state-error": "#a83a44",
  "--color-error": "#a83a44",

  // WhatsApp is the ICON of the human exit — never a green button with white
  // text on it (white on #25d366 measures 1.98). The ink is what carries text.
  "--accent-whatsapp": "#25d366",
  "--accent-whatsapp-ink": "#0d3a1f",

  // ── Shell ─────────────────────────────────────────────────────────────────
  // The funnel header is slim ON CARTA — never a red band (R4 §4.3 restraint
  // budget). The full-bleed merah band is the home hero's single exception.
  "--nav-bg": "#f7f6f2",
  "--footer-bg": "#f7f6f2",
  "--footer-text": "#475372",

  // ── Typography ────────────────────────────────────────────────────────────
  // `/visa/layout.tsx` forces Montserrat on the whole visa funnel via an inline
  // `fontFamily`. R4 retires Montserrat from the web. We neutralise it HERE, on
  // our own wrapper, rather than editing the shared visa layout — the rest of
  // the funnel is a different lane's perimeter.
  // Inter and Cormorant are self-hosted and mounted on <html> by the root
  // layout; no IBM Plex Mono webfont exists in this repo (packages/core/fonts
  // ships exactly 4: cormorant, inter, league-spartan, montserrat), and loading
  // a fifth face is a perf decision of its own, not one to smuggle into a
  // palette change.
  // CORRECTED 2026-09-01: the previous wording claimed `--font-mono` "resolves
  // to ui-monospace — the same fallback every other mono surface in this app
  // already uses" and cited a PENDING-ARMS entry. Both were false, and together
  // they made an omission read as a settled decision. The token DOES exist
  // (packages/core/tokens/primitives.css) as `"IBM Plex Mono", ui-monospace,
  // Menlo, monospace`, with ~29 consumers elsewhere in the app, every one of
  // them naming Plex FIRST — so using it here would need no new file and would
  // put this surface exactly where those 29 already are. No ledger row for
  // "Plex" or "font-mono" exists.
  //
  // SETTLED 2026-09-01 (Zero, Legge 5 — «dobbiamo restare coerenti e non
  // passare a plex mono»): the divergence the paragraph above left open is now
  // a decision, not an omission. IDR amounts on THESE TWO ROUTES keep the
  // surface's own faces with `tabular-nums` + `tnum` (VerdictPanel and the
  // landing already render them that way); coherence of one small surface beat
  // adding a second numeric voice to it. `--font-mono` is NOT deprecated and
  // its ~29 consumers elsewhere are untouched, the VOA payment screen still
  // renders IDR in mono, and the never-wrap-mid-amount constraint is
  // typeface-independent and still binds here. The hero statistics are the
  // deliberate counter-example — prose figures, NOT a column, and
  // second-home/page.test.tsx pins them proportional; the ruling is about the
  // price figures, not about every digit on the page. Written down in
  // research/design/2026-08-27-r4-identity-merah-putih-token-spec.md (the
  // amendment note under the typography table) — this comment is the pointer,
  // that file is the law.
  fontFamily: "var(--font-sans), Inter, ui-sans-serif, system-ui, sans-serif",
} as CSSProperties;

/**
 * Marker className paired with `MERAH_PUTIH_DAY_VARS` on every converted
 * wrapper, so scoped CSS (and the print stylesheet) can target the day scope
 * without re-stating the whole selector chain.
 */
export const MERAH_PUTIH_DAY_CLASS = "merah-putih-day";

/**
 * The wrapper cannot paint its own ancestors, and <body> is an ancestor.
 *
 * MEASURED 2026-08-31 on the running app, which is the only reason this exists:
 * with the wrapper correctly carta, `getComputedStyle(document.body)` still
 * returned `rgb(29, 39, 59)` — the shared editorial navy — on BOTH routes, and
 * body was 88px taller than the wrapper on each. That is a navy band under the
 * content, plus a navy page in print and behind overscroll rubber-banding.
 *
 * `:has()` keeps the cure scoped to exactly the pages that opted in: no route
 * without a `.merah-putih-day` wrapper is affected, so this stays a route-level
 * change and never becomes a global stylesheet edit. Where `:has()` is
 * unsupported the page simply keeps today's behaviour — the same navy it has
 * now, never something worse.
 *
 * Inject with `<style>{MERAH_PUTIH_DAY_BODY_CSS}</style>` inside the wrapper.
 */
export const MERAH_PUTIH_DAY_BODY_CSS = `
body:has(.merah-putih-day) {
  background: #f7f6f2;
  color: #16213a;
}
@media print {
  body:has(.merah-putih-day) {
    background: #ffffff;
  }
}
`;
