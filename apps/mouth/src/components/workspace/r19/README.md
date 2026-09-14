# R19 "TEPAT FORTE" primitives — the kita workspace contract

v2 of the module SAETTA-R19K window K1b (PR-K1b) shipped as "SIAP". Window
**K1c-bis** took it to v2 against the frozen fusion render
`R19-KITA-20260914/fusion/02-dashboard.html` /
`03-clients-list.html` (search the `<style>` block for "TEPAT FORTE fusion
layer"). Windows K2–K5 **import from here and do not re-invent** — this
module is the fusion K2–K5 import, not a page re-implementing the same
shapes. If a page needs a shape this module does not have, add it here in
that page's PR rather than beside the page — a second copy is how two visual
systems start.

`(workspace)/garuda-voa/r19.tsx` is the page-local ancestor of `Notice`,
`Masthead` and `StatePill`. It stays where it is until **K5** migrates that
console; nothing here imports from it, and it imports nothing from here.

---

## 1. The token contract

These primitives read **only** the names below. They are declared by the two
`[data-product="kita"]` theme blocks in `app/globals.css`. A surface that is
not `data-product="kita"` may leave some of them undefined, so do not mount
these on the portal.

**Ground** — `--bz-base` (paper) · `--bz-card` (card) · `--bz-card-hover`

**Type** — `--tx-pure` (ink) · `--tx-secondary` (muted) · `--font-serif`
(Fraunces) · `--font-sans` (Manrope)

**Lines** — `--bz-border` (hairline) · `--line-control` (a control boundary;
the hairline fails SC 1.4.11's 3:1 under a control, which is why this exists)

**The four meanings** — `--state-success` (done, forest) · `--state-info`
(ours/moving, slate) · `--bz-copper` and `--bz-copper-text` (needs you) ·
`--tx-secondary` (waiting) · `--state-warning` (the middle step of the one
ordered scale, not a fifth hue)

**On a fill** — `--bz-on-warm`, `--bz-base` (the selected filter's paper text)

**Shadow** — `--bz-shadow-card` (one per page, on the slip)

`--state-danger` resolves to copper on kita and every dangerous state carries a
WORD. **There is no red in this module.** `--bz-neon-purple` resolves to slate.

### Laws this module encodes

1. **Copper is a person, not a status.** It means _you are the next actor_,
   derived from the viewer and the record together, never from a raw status
   string. Where ownership is not derivable, use `wait`.
2. **Copper is never a fill.** It is text, an outline, a numeral, a pip or the
   96×4 masthead rule. The only filled pills are `tone="ink"` and the
   `selected` filter (v2: INK with paper text).
3. **Colour never travels alone.** Every tone carries a word.
4. **Fraunces never touches a label, a cell or a button.** It is mastheads,
   numerals, section headings and the empty-state sentence.

---

## 2. The primitives

| Export                                       | Shape                                                                                                       | Notes                                                                                                                                                                                                     |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Masthead`                                   | copper 96×4 rule · copper eyebrow · 40/42 Fraunces h1 · `sub` · `actions` slot                              | the copper rule lives here, which is why a page never drops it. v2 renamed `subtitle`→`sub`, `right`→`actions` (free rename, zero importers on origin/main)                                               |
| `Eyebrow`                                    | 10px/650/.14em uppercase                                                                                    |                                                                                                                                                                                                           |
| `StatePill`                                  | `tone` of `ok · ours · you · wait · ink`, `label`                                                           | inert `<span>` with a diamond pip by default, SQUARE (2px radius, never a circle); pass `pressed` and it becomes `<button aria-pressed>` with an INK fill + paper text (v2; v1 was slate) and a leading ✓ |
| `DeskStrip`                                  | 44px sticky bar: 22px Fraunces `count` · `FILTER` group · `right`                                           | filters are a `role="group"`; the selected pill's ink fill + `aria-pressed` live in `StatePill` — this strip only groups them                                                                             |
| `HairlineGrid`                               | sets `--cols` and (when `id` is given) `data-hgrid={id}`                                                    | wrap `HairlineHead` + `HairlineBody`; pass `colsCollapsed` + `id` for the scoped narrow-viewport collapse (see §"Collapse contract" below)                                                                |
| `HairlineHead`                               | sticky column heads, **sibling** of the body, INK 1px rule                                                  | so a virtualized scroller can take the body later                                                                                                                                                         |
| `HairlineRow`                                | 44px row, `actions` on hover/focus, `touchAction` always-on for `hover:none`                                | hover is the wrong gate on a tablet; pass `href` + `onActivate` to make the whole row activatable (see §"Row activation" below)                                                                           |
| `CellStack`                                  | primary + secondary inside one cell, optional `collapsed` slot                                              | truncates; give long values a `title`; `collapsed` reappears on the secondary line when the grid narrows                                                                                                  |
| `NumberedList` / `Numeral` / `OrdinalMargin` | Fraunces numerals in three sizes (`kpi` 44/38 · `count` 22 · `ordinal` 18), tone `wait · you · done · ours` | numbering is presentational; the caller supplies the order. `owned` on `NumberedList` is the ownership margin — see below                                                                                 |
| `LedgerSection`                              | numbered section head (`OrdinalMargin` + Fraunces `<h2>` + `actions`) over a body                           | TEPAT's section grammar — the section-level counterpart to `NumberedList`'s row ordinal                                                                                                                   |
| `Stamp`                                      | rotated outline, `tone="forest"` (`Reviewed · Bali Zero · date`) or `tone="copper"` (`Needs you`)           | forest renders NOTHING without `on`; copper renders NOTHING without `owned === true`. Copper stamps are DETAIL-PAGE only                                                                                  |
| `EmptyState`                                 | one Fraunces sentence between hairlines, ≤1 action                                                          | no dashed box, no illustration                                                                                                                                                                            |
| `Slip`                                       | 44px confirmation with a 44px Undo, `tone` `ok · you`                                                       | the SHAPE only — the toast system and the six-second window are the shell's; give it a ≥64px bottom offset under 768 so it never covers a mobile control                                                  |
| `Notice`                                     | quiet bordered notice, `tone` `you · ok · wait`                                                             | `you` is the only alarming variant kita has                                                                                                                                                               |
| `Field`                                      | `<label htmlFor>` + 52px underlined input, copper on focus                                                  | the caller owns `id`, `type`, `inputMode`, `name` and the value                                                                                                                                           |

### Constants

`SERIF` · `SERIF_SECTION` · `TABULAR` · `EYEBROW` · `MICRO_LABEL` ·
`SECTION_H2` · `HAIRLINE` · `CARD` · `FOCUS` · `FIELD` · `PILL_TONE` ·
`PILL_SELECTED` · `PILL_SQUARE` · `INK_HEAD_RULE` · `COPPER_RULE` · `pad2` ·
`MASTHEAD_H1` · `MASTHEAD_SUB` · `NUMERAL_KPI` · `NUMERAL_COUNT` ·
`NUMERAL_ORDINAL` · and the geometry the renders measured: `ROW_H` 44 ·
`HEADER_H` 48 · `SIDEBAR_W` / `RAIL_W` 216 (same value, `RAIL_W` is the v2
name) · `GUTTER` 24 · `COLLAPSE_PX` 1360.

`COPPER_RULE` is the 96×4 masthead graphic (72×4 under 768) and the **only**
sanctioned copper fill in kita. `r19.test.tsx` exempts it **by name** — a
line must contain the identifier `COPPER_RULE` to be exempted — so a copy of
its class string somewhere else is still caught. The declaration has to fit
on ONE physical line or prettier breaks the assignment after `=`, moves
`bg-[var(--bz-copper)]` off the exempted line, and trips the guard on its own
exemption. The render draws a square rule, so v2 dropped v1's `rounded-sm`;
that is what keeps the line inside prettier's 80 columns without a pragma.

### Sticky offsets

`DeskStrip` sticks to `var(--bz-header-height, 48px)`, unchanged from v1.
`HairlineHead`'s default CHANGED in v2: it now also sticks at
`var(--bz-header-height, 48px)` (v1 stuck at `calc(... + 44px)`, i.e. below
the desk strip). The measured fusion render pins the head at the shell
header (52/97 in `fusion/MEASURE.md` §6) with the desk strip scrolling away
above it, so the head takes the header's own offset rather than adding the
strip's height to it. Both still read whatever height the shell ships rather
than pinning their own; the kita product block declares 48px.

### Collapse contract (`HairlineGrid`)

Pass `colsCollapsed` and a caller-supplied, stable `id` together and
`HairlineGrid` emits one scoped `<style>` tag:

```
@media (max-width:{collapseAt}px){
  [data-hgrid="{id}"]{--cols:{colsCollapsed}}
  [data-hgrid="{id}"] [data-collapse]{display:none}
  [data-hgrid="{id}"] [data-collapsed-meta]{display:inline}
}
```

`collapseAt` defaults to `COLLAPSE_PX` (1360). Below that width the grid
narrows to `colsCollapsed`, any cell the caller marked `data-collapse` leaves
the grid, and `CellStack`'s `collapsed` slot (rendered `hidden` by default,
inside `[data-collapsed-meta]`) reappears on the primary cell's secondary
line. Passing `colsCollapsed` WITHOUT `id` emits no style at all — there
would be nothing to scope the selector to, and an un-scoped rule would
collide with every other grid on the page. This needs no hooks, so
`HairlineGrid` stays usable from a server-rendered tree.

### Row activation (`HairlineRow`)

Pass `href` and the whole row becomes activatable: `role="link"`,
`tabIndex={0}`, `data-href={href}`, a pointer cursor, and `onActivate?.(href)`
fires on click, on Enter and on Space (Space also calls `preventDefault()` so
the page does not scroll). Without `href` the row stays a plain, inert div —
no role, no tabIndex. `actions` and `touchAction` each stop propagation on
click and keydown, so a secondary action never also activates the row. This
is presentation only: the row calls back, the PAGE navigates.

### Ownership margin (`NumberedList`, `OrdinalMargin`, `LedgerSection`)

An item's ordinal is copper when the list is `owned` OR the item's own
`tone === "you"`, and otherwise takes the item's own tone (default `wait`):
`item.tone ?? (owned ? "you" : "wait")`. `owned` also draws a 4px copper
BORDER (never a fill) on the `<ol>` itself. `OrdinalMargin` is the same
18px ordinal plus its 1px hairline column, generalized to a ledger row or a
`LedgerSection` head — `n` is always RENDERED, never stored; the caller
derives it from an index.

---

## 3. What these primitives will not do

They hold no state, fetch nothing, own no timer and route nowhere. Sorting,
selection, row activation's navigation, the undo window and every request
stay with the page that owns the data. That is what keeps a restyle a
restyle. `HairlineRow` is the one exception worth naming explicitly: it owns
the activation _event handling_ (click/keydown → `onActivate`) because that
is presentation, not data — but it still never navigates itself.

## 4. Client-side surface

Every component in this module is server-safe EXCEPT `Slip.tsx` (already
`"use client"`, a toast needs to run client-side) and `HairlineGrid.tsx`.
`HairlineRow` — defined in `HairlineGrid.tsx` alongside `HairlineGrid`,
`HairlineHead`, `HairlineBody` and `CellStack` — owns real event handlers
(click/keydown activation, `stopPropagation` on its action cells), and those
closures cannot cross the server/client boundary, so the FILE carries
`"use client"`. The other four exports in that file do not need it
themselves (no state, no hooks, no handlers of their own) and would
otherwise stay server-safe; they are client components only because they
share a file with `HairlineRow`. A future window may split `HairlineRow` out
if that boundary starts to matter for a page's bundle size.
