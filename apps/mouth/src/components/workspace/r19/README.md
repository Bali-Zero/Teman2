# R19 "SIAP" primitives — the kita workspace contract

Shipped by **SAETTA-R19K window K1 (PR-K1b)** against the frozen concept in
`R19-KITA-20260914/concept/`. Windows K2–K5 **import from here and do not
re-invent**. If a page needs a shape this module does not have, add it here in
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

**On a fill** — `--bz-on-warm`

**Shadow** — `--bz-shadow-card` (one per page, on the slip)

`--state-danger` resolves to copper on kita and every dangerous state carries a
WORD. **There is no red in this module.** `--bz-neon-purple` resolves to slate.

### Laws this module encodes

1. **Copper is a person, not a status.** It means *you are the next actor*,
   derived from the viewer and the record together, never from a raw status
   string. Where ownership is not derivable, use `wait`.
2. **Copper is never a fill.** It is text, an outline, a numeral, a pip or a
   3px rule. The only filled pills are `tone="ink"` and the `selected` filter.
3. **Colour never travels alone.** Every tone carries a word.
4. **Fraunces never touches a label, a cell or a button.** It is mastheads,
   numerals and the empty-state sentence.

---

## 2. The primitives

| Export | Shape | Notes |
|---|---|---|
| `Masthead` | copper 56×3 rule · eyebrow · Fraunces h1 · subtitle · `right` slot | the copper rule lives here, which is why a page never drops it |
| `Eyebrow` | 10px/650/.14em uppercase | |
| `StatePill` | `tone` of `ok · ours · you · wait · ink`, `label` | inert `<span>` with a dot by default; pass `pressed` and it becomes `<button aria-pressed>` with a slate fill and a leading ✓ |
| `DeskStrip` | 44px sticky bar: Fraunces `count` · `FILTER` group · `right` | filters are a `role="group"`; put `SearchBox`, view toggles and the primary action in `right` |
| `HairlineGrid` | sets `--cols` | wrap `HairlineHead` + `HairlineBody` |
| `HairlineHead` | sticky column heads, **sibling** of the body | so a virtualized scroller can take the body later |
| `HairlineRow` | 44px row, `actions` on hover/focus, `touchAction` always-on for `hover:none` | hover is the wrong gate on a tablet |
| `CellStack` | primary + secondary inside one cell | truncates; give long values a `title` |
| `NumberedList` / `Numeral` | 01/02/03 in Fraunces, tone `wait · you · done` | numbering is presentational; the caller supplies the order |
| `Stamp` | rotated forest outline, `Reviewed · Bali Zero · date` | render it **only** where a real review timestamp exists |
| `EmptyState` | one Fraunces sentence between hairlines, ≤1 action | no dashed box, no illustration |
| `Slip` | 44px confirmation with a 44px Undo, `tone` `ok · you` | the SHAPE only — the toast system and the six-second window are the shell's |
| `Notice` | quiet bordered notice, `tone` `you · ok · wait` | `you` is the only alarming variant kita has |
| `Field` | `<label htmlFor>` + 52px underlined input, copper on focus | the caller owns `id`, `type`, `inputMode`, `name` and the value |

### Constants

`SERIF` · `SERIF_SECTION` · `TABULAR` · `EYEBROW` · `MICRO_LABEL` ·
`SECTION_H2` · `HAIRLINE` · `CARD` · `FOCUS` · `FIELD` · `PILL_TONE` ·
`PILL_SELECTED` · `COPPER_RULE` · `pad2` · and the geometry the renders
measured: `ROW_H` 44 · `HEADER_H` 48 · `SIDEBAR_W` 216 · `GUTTER` 24 ·
`COLLAPSE_PX` 1360.

`COPPER_RULE` is the 56×3 masthead graphic and the **only** sanctioned copper
fill in kita. `r19.test.tsx` exempts it **by name**, so a copy of its class
string somewhere else is still caught.

### Sticky offsets

`DeskStrip` and `HairlineHead` stick to `var(--bz-header-height, 48px)`, so
they follow whatever height the shell ships rather than pinning their own. The
kita product block currently declares 64px; **K1c** brings it to the concept's
48px, and these primitives move with it without an edit.

---

## 3. What these primitives will not do

They hold no state, fetch nothing, own no timer and route nowhere. Sorting,
selection, row activation, the undo window and every request stay with the page
that owns the data. That is what keeps a restyle a restyle.
