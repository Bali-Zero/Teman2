# `/kbli*` — the R19 wrapper token contract (W0)

> Mission `kbli-nav-design-loop/W0`, plan `docs/plans/2026-10-08-kbli-navigator-design-loop.md` §1.
> Every number below was measured on M5, 2026-10-08, on a local `next dev --webpack` of this branch.

**The rule: no token may be read inside the wrapper and left undefined by the wrapper.**

## 1. Why this exists

PR #7508 was suspended after three reds with one cause: the R19 paper wrapper re-themed a
dark-default app only partially. Every shared component or global class rule that reads a
token the wrapper does not set kept its dark colour. The census below finds both measured reds
by name: TrustBand labels read `--color-text-secondary`, and the footer tagline paints through
the global class `brand-tagline`.

The trap behind most of them is the alias. Tailwind's `@theme` block declares
`--color-text-secondary: var(--text-secondary)` on `:root`, and a custom property resolves its
`var()` where it is declared. A wrapper that redefines `--text-secondary` therefore leaves
`--color-text-secondary` dark. So the census lists the alias AND its target. It also reports
where each one resolves today, as `defined-above-wrapper`.

## 2. What the census reads

`scripts/mouth/r19_wrapper_token_census.py` (in-page half: its `PROBE_JS` string) opens
`/kbli`, `/kbli/55203`, `/kbli/51101`, `/kbli/56101` and `/kbli-explorer` in the six states of
`.claude/skills/design/strumenti/measure.py` (mobile 390×844 and desktop 1440×900, each light,
system-dark and forced-dark).

- **Wrapper root.** The first of: `[data-presentation="r19"]`, `.r19-direction-a`, the
  `KBLILayout` div carrying `--font-montserrat`, the parent of `#kbli-explorer-jsonld`.
- **A read.** Every `var(--x)`, fallbacks included, in a declaration that paints an element in
  the wrapper. The property families are those of `apps/mouth/src/test/r19-colour-guard.ts`
  (`COLOUR_BEARING`) minus geometry, plus `color`, `font-family` and `font-weight`, because
  Direction A fixes one weight per face. A `filter` counts
  only when it resolves to a `drop-shadow()`. Declarations come from every stylesheet rule the
  element matches, adopted sheets included, with nesting, `@media`, `@supports` and `@layer`
  handled. Inline `style` and SVG `fill`/`stroke`/`stop-color` attributes count too.
- **Chains.** Each token is followed to the element that declares it, and that declaration's
  own `var()` reads count too. Tailwind's `--tw-*` plumbing is followed but never listed. The
  class that sets it is listed instead, such as a gradient stop or a ring colour.
- **States a pointer makes.** `:hover`, `:focus*`, `:active` and pseudo-elements are matched with
  the pseudo stripped, so a hover colour is a read. `::placeholder` is tested on inputs only.
- **The wrapper's inheritance.** The wrapper also reads what it inherits and does not paint
  itself: `body { color }` and the body backdrop.
- **Kinds.** `var` is a custom property. `class` is a class token whose own rule paints the
  element, a Tailwind utility or a single-class global rule. `rule` is any other matched
  selector, keyed `selector { family }`. `component` is a `packages/core` component that owns the
  painting element in React's dev fiber, keyed `Name { family }`.

Limits, declared:

- Drawers, modals and the sector panel paint only after a click, so they are not in the DOM
  the census walks. Attribute and ARIA state variants such as `data-[state=open]:`,
  `:checked` and `:disabled` are matched only as rendered. W1 adds those states.
- `forced-colors` and `prefers-contrast` media are not among the six states.
- Portals outside the wrapper are not inside it, `sonner` toasts included.
- A literal colour is not a token. It shows up in `colors-outside-direction-a`, which in W0
  counts distinct computed `color`, `background-color` and `border-color` values whose RGB is
  outside §3, alpha ignored.
- A static scan of the source files behind these pages finds colour class tokens that no
  capture rendered: search results, modals, error pages and other verdicts. They are outside
  this contract by construction. W1's added states will surface them.
- `BZLogo` is a `next/image` PNG. Raster artwork carries no token, so it has no row. W2 picks
  the variant that reads on paper.
- Geometry tokens are out of scope: radius, space and size. The type scale counts as
  geometry: `font-size`, `line-height` and `letter-spacing`.

## 3. Values

| role        | hex       | on paper | use                                   |
| ----------- | --------- | -------- | ------------------------------------- |
| paper       | `#F7F4EE` | 1.00     | page ground                           |
| elevated    | `#FFFCF7` | 1.07     | cards, inputs, ink-on-copper          |
| wash        | `#EAE3D8` | 1.16     | sunken bands, hover fills, footer     |
| ink         | `#1D2C3B` | 12.96    | primary text                          |
| muted       | `#58626B` | 5.67     | secondary text (4.88 on wash)         |
| structure   | `#233D52` | 10.28    | Zantara / second accent               |
| copper      | `#A44B36` | 5.26     | the one action colour (4.53 on wash)  |
| line        | `#DAD8D1` | 1.30     | hairlines, decorative only            |
| line-strong | `#A8ACA9` | 2.09     | hover rules, never a control boundary |

The PMA verdict triad keeps its semantic hues:

| verdict    | hex       | on paper | on elevated | on wash |
| ---------- | --------- | -------- | ----------- | ------- |
| open       | `#2E5E4E` | 6.77     | 7.26        | 5.83    |
| restricted | `#7A5A1E` | 5.78     | 6.20        | 4.98    |
| closed     | `#8E2F2A` | 7.39     | 7.92        | 6.36    |

Type has two values: Fraunces 450 for display, and Manrope 400 at 15px/1.75 for everything else.

Main's `R19_VARS` in `apps/mouth/src/components/r19/presentation.ts` diverges on four tokens:

- `--text-secondary` is `#435464` there and muted `#58626B` here.
- `--border-strong` is `#A7A69F` there and line-strong `#A8ACA9` here.
- `--r19-cta-ink` is `#FFFFFF` there and elevated `#FFFCF7` here.
- `--footer-bg` is `#EEE9E1` there and wash `#EAE3D8` here.

W2 either defines the contract value on the wrapper or amends the row in its own PR. The census
reads this table, so the guard follows the amendment.

## 4. Format

The parser in the census script pins this format, and its test refuses a mutated table rather
than reading it as empty.

- The block sits between the two `contract:` markers. Its header is exactly
  `kind | token | value | reason`, with four cells per row.
- `kind` is one of `var`, `class`, `rule` or `component`.
- `value` takes one of four shapes. `<role> #HEX` must match §3 exactly. `semantic #HEX` must be
  one of the three triad hues. `type Fraunces 450 display` and `type Manrope 400 15px/1.75`
  name the two faces. `not painted on this surface` needs a reason.
- A row whose note says "not read on main today" is vocabulary the wrapper defines for W2. It
  covers the `--r19-*` set, `R19_VARS`, and the `--kbli-*` tokens no page reads yet.

## 5. The contract

<!-- contract:begin -->

| kind      | token                                                                                   | value                       | reason                                                                                                               |
| --------- | --------------------------------------------------------------------------------------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| var       | `--accent-funnel`                                                                       | copper #A44B36              | the one action / accent colour                                                                                       |
| var       | `--accent-funnel-text`                                                                  | copper #A44B36              | the one action / accent colour; not read on main today                                                               |
| var       | `--accent-sand`                                                                         | copper #A44B36              | the one action / accent colour                                                                                       |
| var       | `--accent-warm`                                                                         | copper #A44B36              | the one action / accent colour                                                                                       |
| var       | `--accent-whatsapp-ink`                                                                 | elevated #FFFCF7            | ink on copper / on the CTA: 5.64:1 (R19_VARS has #FFFFFF; Direction A has no pure white)                             |
| var       | `--accent-zantara`                                                                      | structure #233D52           | Zantara / second accent                                                                                              |
| var       | `--background`                                                                          | paper #F7F4EE               | page ground                                                                                                          |
| var       | `--border`                                                                              | line #DAD8D1                | hairline                                                                                                             |
| var       | `--border-default`                                                                      | line #DAD8D1                | hairline                                                                                                             |
| var       | `--border-strong`                                                                       | line-strong #A8ACA9         | hover / emphasis rule                                                                                                |
| var       | `--border-subtle`                                                                       | line #DAD8D1                | hairline                                                                                                             |
| var       | `--color-accent-sand`                                                                   | copper #A44B36              | the one action / accent colour                                                                                       |
| var       | `--color-accent-warm`                                                                   | copper #A44B36              | the one action / accent colour                                                                                       |
| var       | `--color-amber-400`                                                                     | semantic #7A5A1E            | medium-high risk / merged mapping / amber highlight share the restricted hue                                         |
| var       | `--color-black`                                                                         | wash #EAE3D8                | dark-default black = a deeper ground; on paper the deeper ground is wash                                             |
| var       | `--color-border-subtle`                                                                 | line #DAD8D1                | hairline                                                                                                             |
| var       | `--color-green-500`                                                                     | semantic #2E5E4E            | low risk / new mapping / live dot share the open hue                                                                 |
| var       | `--color-purple-500`                                                                    | structure #233D52           | Zantara / second accent                                                                                              |
| var       | `--color-red-500`                                                                       | copper #A44B36              | brand red on CTA borders becomes the action colour                                                                   |
| var       | `--color-slate-200`                                                                     | line #DAD8D1                | hairline                                                                                                             |
| var       | `--color-slate-50`                                                                      | wash #EAE3D8                | dark-default black = a deeper ground; on paper the deeper ground is wash                                             |
| var       | `--color-slate-500`                                                                     | muted #58626B               | grey text on dark becomes secondary text                                                                             |
| var       | `--color-surface-deep`                                                                  | wash #EAE3D8                | sunken band / hover fill                                                                                             |
| var       | `--color-surface-editorial-elevated`                                                    | elevated #FFFCF7            | card / panel / input ground                                                                                          |
| var       | `--color-text-secondary`                                                                | muted #58626B               | secondary text: 5.67:1 on paper, 4.88:1 on wash (R19_VARS carries #435464)                                           |
| var       | `--color-white`                                                                         | ink #1D2C3B                 | dark-default white is the foreground: on paper it is ink, white/alpha overlays become ink/alpha tints                |
| var       | `--color-zinc-100`                                                                      | ink #1D2C3B                 | near-white text on dark becomes primary text                                                                         |
| var       | `--color-zinc-300`                                                                      | ink #1D2C3B                 | near-white text on dark becomes primary text                                                                         |
| var       | `--color-zinc-400`                                                                      | muted #58626B               | grey text on dark becomes secondary text                                                                             |
| var       | `--color-zinc-500`                                                                      | muted #58626B               | grey text on dark becomes secondary text                                                                             |
| var       | `--cta-primary-bg`                                                                      | copper #A44B36              | the one action / accent colour; not read on main today                                                               |
| var       | `--drop-shadow-lg`                                                                      | not painted on this surface | drop-shadow filter: Direction A is flat                                                                              |
| var       | `--drop-shadow-md`                                                                      | not painted on this surface | drop-shadow filter: Direction A is flat                                                                              |
| var       | `--drop-shadow-sm`                                                                      | not painted on this surface | drop-shadow filter: Direction A is flat                                                                              |
| var       | `--font-mono`                                                                           | type Manrope 400 15px/1.75  | Direction A sets no mono face: KBLI codes print in Manrope tabular-nums                                              |
| var       | `--font-montserrat`                                                                     | type Manrope 400 15px/1.75  | body face                                                                                                            |
| var       | `--font-sans`                                                                           | type Manrope 400 15px/1.75  | body face                                                                                                            |
| var       | `--font-serif`                                                                          | type Fraunces 450 display   | display face                                                                                                         |
| var       | `--font-weight-black`                                                                   | type Fraunces 450 display   | display weight: Fraunces carries one, 450                                                                            |
| var       | `--font-weight-bold`                                                                    | type Manrope 400 15px/1.75  | body weight: Manrope carries one, 400; emphasis is ink, not weight                                                   |
| var       | `--font-weight-extrabold`                                                               | type Fraunces 450 display   | display weight: Fraunces carries one, 450                                                                            |
| var       | `--font-weight-light`                                                                   | type Manrope 400 15px/1.75  | body weight: Manrope carries one, 400; emphasis is ink, not weight                                                   |
| var       | `--font-weight-medium`                                                                  | type Manrope 400 15px/1.75  | body weight: Manrope carries one, 400; emphasis is ink, not weight                                                   |
| var       | `--font-weight-semibold`                                                                | type Manrope 400 15px/1.75  | body weight: Manrope carries one, 400; emphasis is ink, not weight                                                   |
| var       | `--footer-bg`                                                                           | wash #EAE3D8                | footer ground (R19_VARS carries #EEE9E1, outside Direction A)                                                        |
| var       | `--footer-border`                                                                       | line #DAD8D1                | hairline                                                                                                             |
| var       | `--footer-icon-color`                                                                   | muted #58626B               | footer social icon ink; undefined in every stylesheet today (fallback rgba white 0.72 paints)                        |
| var       | `--foreground`                                                                          | ink #1D2C3B                 | primary text                                                                                                         |
| var       | `--foreground-muted`                                                                    | muted #58626B               | secondary text: 5.67:1 on paper, 4.88:1 on wash (R19_VARS carries #435464)                                           |
| var       | `--foreground-secondary`                                                                | muted #58626B               | secondary text: 5.67:1 on paper, 4.88:1 on wash (R19_VARS carries #435464)                                           |
| var       | `--kbli-accent`                                                                         | copper #A44B36              | the one action / accent colour                                                                                       |
| var       | `--kbli-accent-glow`                                                                    | not painted on this surface | glow: Direction A is flat, the wrapper defines it transparent/none; not read on main today                           |
| var       | `--kbli-accent-hover`                                                                   | copper #A44B36              | hover keeps the hue; it shifts by underline/opacity; not read on main today                                          |
| var       | `--kbli-accent-muted`                                                                   | wash #EAE3D8                | accent tint becomes wash: no tinted copper slabs; not read on main today                                             |
| var       | `--kbli-accent-subtle`                                                                  | wash #EAE3D8                | accent tint becomes wash: no tinted copper slabs; not read on main today                                             |
| var       | `--kbli-accent2`                                                                        | structure #233D52           | Zantara / second accent                                                                                              |
| var       | `--kbli-accent2-glow`                                                                   | not painted on this surface | glow: Direction A is flat, the wrapper defines it transparent/none; not read on main today                           |
| var       | `--kbli-amber`                                                                          | semantic #7A5A1E            | medium-high risk / merged mapping / amber highlight share the restricted hue                                         |
| var       | `--kbli-amber-glow`                                                                     | not painted on this surface | glow: Direction A is flat, the wrapper defines it transparent/none; not read on main today                           |
| var       | `--kbli-bg-base`                                                                        | paper #F7F4EE               | page ground                                                                                                          |
| var       | `--kbli-bg-card`                                                                        | elevated #FFFCF7            | card / panel / input ground; not read on main today                                                                  |
| var       | `--kbli-bg-card-hover`                                                                  | wash #EAE3D8                | sunken band / hover fill; not read on main today                                                                     |
| var       | `--kbli-bg-elevated`                                                                    | elevated #FFFCF7            | card / panel / input ground                                                                                          |
| var       | `--kbli-bg-input`                                                                       | elevated #FFFCF7            | card / panel / input ground; not read on main today                                                                  |
| var       | `--kbli-bg-primary`                                                                     | paper #F7F4EE               | page ground; not read on main today                                                                                  |
| var       | `--kbli-bg-secondary`                                                                   | wash #EAE3D8                | sunken band / hover fill; not read on main today                                                                     |
| var       | `--kbli-bg-surface`                                                                     | elevated #FFFCF7            | card / panel / input ground                                                                                          |
| var       | `--kbli-bg-surface-hover`                                                               | wash #EAE3D8                | sunken band / hover fill; not read on main today                                                                     |
| var       | `--kbli-border`                                                                         | line #DAD8D1                | hairline                                                                                                             |
| var       | `--kbli-border-accent`                                                                  | line-strong #A8ACA9         | hover / emphasis rule; not read on main today                                                                        |
| var       | `--kbli-border-hover`                                                                   | line-strong #A8ACA9         | hover / emphasis rule; not read on main today                                                                        |
| var       | `--kbli-ink`                                                                            | ink #1D2C3B                 | hero band ground on /kbli; text on it must be paper or elevated                                                      |
| var       | `--kbli-map-merged`                                                                     | semantic #7A5A1E            | medium-high risk / merged mapping / amber highlight share the restricted hue; not read on main today                 |
| var       | `--kbli-map-new`                                                                        | semantic #2E5E4E            | low risk / new mapping / live dot share the open hue; not read on main today                                         |
| var       | `--kbli-map-renamed`                                                                    | structure #233D52           | medium-low risk and renamed mapping: slate, not a fourth hue; not read on main today                                 |
| var       | `--kbli-map-unchanged`                                                                  | muted #58626B               | grey text on dark becomes secondary text; not read on main today                                                     |
| var       | `--kbli-pma-closed`                                                                     | semantic #8E2F2A            | PMA closed verdict: 7.39:1 on paper                                                                                  |
| var       | `--kbli-pma-closed-bg`                                                                  | elevated #FFFCF7            | verdict chip ground: the hue lives in the word, not in a tinted slab                                                 |
| var       | `--kbli-pma-open`                                                                       | semantic #2E5E4E            | PMA open verdict: 6.77:1 on paper                                                                                    |
| var       | `--kbli-pma-open-bg`                                                                    | elevated #FFFCF7            | verdict chip ground: the hue lives in the word, not in a tinted slab                                                 |
| var       | `--kbli-pma-restricted`                                                                 | semantic #7A5A1E            | PMA restricted verdict: 5.78:1 on paper                                                                              |
| var       | `--kbli-pma-restricted-bg`                                                              | elevated #FFFCF7            | verdict chip ground: the hue lives in the word, not in a tinted slab                                                 |
| var       | `--kbli-risk-high`                                                                      | semantic #8E2F2A            | high risk shares the closed hue; not read on main today                                                              |
| var       | `--kbli-risk-low`                                                                       | semantic #2E5E4E            | low risk / new mapping / live dot share the open hue                                                                 |
| var       | `--kbli-risk-medium-high`                                                               | semantic #7A5A1E            | medium-high risk / merged mapping / amber highlight share the restricted hue                                         |
| var       | `--kbli-risk-medium-low`                                                                | structure #233D52           | medium-low risk and renamed mapping: slate, not a fourth hue                                                         |
| var       | `--kbli-shadow-card`                                                                    | line #DAD8D1                | card edge is a 1px line, not a shadow; not read on main today                                                        |
| var       | `--kbli-shadow-card-hover`                                                              | line-strong #A8ACA9         | hover / emphasis rule; not read on main today                                                                        |
| var       | `--kbli-shadow-glow`                                                                    | not painted on this surface | glow: Direction A is flat, the wrapper defines it transparent/none; not read on main today                           |
| var       | `--kbli-text-muted`                                                                     | muted #58626B               | secondary text: 5.67:1 on paper, 4.88:1 on wash (R19_VARS carries #435464)                                           |
| var       | `--kbli-text-primary`                                                                   | ink #1D2C3B                 | primary text                                                                                                         |
| var       | `--kbli-text-secondary`                                                                 | muted #58626B               | secondary text: 5.67:1 on paper, 4.88:1 on wash (R19_VARS carries #435464)                                           |
| var       | `--kbli-zantara`                                                                        | structure #233D52           | Zantara / second accent; not read on main today                                                                      |
| var       | `--kbli-zantara-bg`                                                                     | wash #EAE3D8                | accent tint becomes wash: no tinted copper slabs; not read on main today                                             |
| var       | `--kbli-zantara-glow`                                                                   | not painted on this surface | glow: Direction A is flat, the wrapper defines it transparent/none; not read on main today                           |
| var       | `--nav-bg`                                                                              | paper #F7F4EE               | nav ground: opaque paper, no glass                                                                                   |
| var       | `--nav-border`                                                                          | line #DAD8D1                | hairline                                                                                                             |
| var       | `--r19-active-bg`                                                                       | wash #EAE3D8                | sunken band / hover fill; not read on main today                                                                     |
| var       | `--r19-active-border`                                                                   | line-strong #A8ACA9         | hover / emphasis rule; not read on main today                                                                        |
| var       | `--r19-control-border`                                                                  | muted #58626B               | control boundary needs >=3:1 (WCAG 1.4.11); line-strong is 2.09:1, muted is 5.67:1; not read on main today           |
| var       | `--r19-copper`                                                                          | copper #A44B36              | the one action / accent colour; not read on main today                                                               |
| var       | `--r19-copper-hover`                                                                    | copper #A44B36              | hover keeps the hue; it shifts by underline/opacity; not read on main today                                          |
| var       | `--r19-cta-ink`                                                                         | elevated #FFFCF7            | ink on copper / on the CTA: 5.64:1 (R19_VARS has #FFFFFF; Direction A has no pure white); not read on main today     |
| var       | `--r19-focus`                                                                           | copper #A44B36              | focus ring (R19: 2px copper); not read on main today                                                                 |
| var       | `--r19-ink`                                                                             | ink #1D2C3B                 | primary text; not read on main today                                                                                 |
| var       | `--r19-ink-muted`                                                                       | muted #58626B               | secondary text: 5.67:1 on paper, 4.88:1 on wash (R19_VARS carries #435464); not read on main today                   |
| var       | `--r19-line`                                                                            | line #DAD8D1                | hairline; not read on main today                                                                                     |
| var       | `--r19-line-strong`                                                                     | line-strong #A8ACA9         | hover / emphasis rule; not read on main today                                                                        |
| var       | `--r19-muted`                                                                           | muted #58626B               | secondary text: 5.67:1 on paper, 4.88:1 on wash (R19_VARS carries #435464); not read on main today                   |
| var       | `--r19-paper`                                                                           | paper #F7F4EE               | page ground; not read on main today                                                                                  |
| var       | `--r19-shadow-header`                                                                   | not painted on this surface | header shadow: the paper nav separates by its line border; not read on main today                                    |
| var       | `--r19-slate`                                                                           | structure #233D52           | Zantara / second accent; not read on main today                                                                      |
| var       | `--r19-structure`                                                                       | structure #233D52           | Zantara / second accent; not read on main today                                                                      |
| var       | `--r19-surface`                                                                         | elevated #FFFCF7            | card / panel / input ground; not read on main today                                                                  |
| var       | `--r19-wash`                                                                            | wash #EAE3D8                | sunken band / hover fill; not read on main today                                                                     |
| var       | `--surface-base`                                                                        | paper #F7F4EE               | page ground                                                                                                          |
| var       | `--surface-deep`                                                                        | wash #EAE3D8                | sunken band / hover fill                                                                                             |
| var       | `--surface-editorial-elevated`                                                          | elevated #FFFCF7            | card / panel / input ground                                                                                          |
| var       | `--surface-elevated`                                                                    | elevated #FFFCF7            | card / panel / input ground; not read on main today                                                                  |
| var       | `--surface-overlay`                                                                     | paper #F7F4EE               | nav ground: opaque paper, no glass                                                                                   |
| var       | `--surface-raised`                                                                      | elevated #FFFCF7            | card / panel / input ground; not read on main today                                                                  |
| var       | `--surface-subtle`                                                                      | wash #EAE3D8                | TrustBand ground; undefined in every stylesheet today (reads nowhere, paints nothing)                                |
| var       | `--text-on-accent`                                                                      | elevated #FFFCF7            | ink on copper / on the CTA: 5.64:1 (R19_VARS has #FFFFFF; Direction A has no pure white)                             |
| var       | `--text-primary`                                                                        | ink #1D2C3B                 | primary text                                                                                                         |
| var       | `--text-secondary`                                                                      | muted #58626B               | secondary text: 5.67:1 on paper, 4.88:1 on wash (R19_VARS carries #435464)                                           |
| var       | `--text-tertiary`                                                                       | muted #58626B               | secondary text: 5.67:1 on paper, 4.88:1 on wash (R19_VARS carries #435464)                                           |
| class     | `bg-[#050507]`                                                                          | paper #F7F4EE               | page ground                                                                                                          |
| class     | `bg-[#080A0E]`                                                                          | paper #F7F4EE               | page ground                                                                                                          |
| class     | `bg-[#0A0C10]/90`                                                                       | paper #F7F4EE               | page ground                                                                                                          |
| class     | `bg-[#1c1c1e]/60`                                                                       | elevated #FFFCF7            | card / glass panel ground                                                                                            |
| class     | `bg-[#2A3241]/10`                                                                       | not painted on this surface | ambient glow blob: dropped                                                                                           |
| class     | `bg-[#3b82f6]/10`                                                                       | not painted on this surface | ambient glow blob: dropped                                                                                           |
| class     | `bg-[rgba(255,255,255,0.02)]`                                                           | elevated #FFFCF7            | card / glass panel ground                                                                                            |
| class     | `bg-[rgba(255,255,255,0.03)]`                                                           | elevated #FFFCF7            | card / glass panel ground                                                                                            |
| class     | `bg-[var(--background)]`                                                                | paper #F7F4EE               | page ground                                                                                                          |
| class     | `bg-[var(--kbli-accent)]/40`                                                            | copper #A44B36              | accent / action colour                                                                                               |
| class     | `bg-[var(--kbli-bg-surface)]`                                                           | elevated #FFFCF7            | card / glass panel ground                                                                                            |
| class     | `bg-[var(--kbli-ink)]`                                                                  | ink #1D2C3B                 | hero band / sticky bar ground (reads --kbli-ink)                                                                     |
| class     | `bg-[var(--kbli-ink)]/80`                                                               | ink #1D2C3B                 | hero band / sticky bar ground (reads --kbli-ink)                                                                     |
| class     | `bg-[var(--kbli-pma-closed-bg)]`                                                        | elevated #FFFCF7            | verdict chip ground: the hue lives in the word                                                                       |
| class     | `bg-[var(--kbli-pma-open-bg)]`                                                          | elevated #FFFCF7            | verdict chip ground: the hue lives in the word                                                                       |
| class     | `bg-[var(--kbli-pma-restricted-bg)]`                                                    | elevated #FFFCF7            | verdict chip ground: the hue lives in the word                                                                       |
| class     | `bg-accent-sand/10`                                                                     | wash #EAE3D8                | accent tint becomes wash: no tinted copper slabs                                                                     |
| class     | `bg-accent-sand/5`                                                                      | wash #EAE3D8                | accent tint becomes wash: no tinted copper slabs                                                                     |
| class     | `bg-accent-warm/10`                                                                     | wash #EAE3D8                | accent tint becomes wash: no tinted copper slabs                                                                     |
| class     | `bg-black/20`                                                                           | wash #EAE3D8                | sunken / hover fill                                                                                                  |
| class     | `bg-black/60`                                                                           | wash #EAE3D8                | sunken / hover fill                                                                                                  |
| class     | `bg-gradient-to-br`                                                                     | not painted on this surface | gradient: Direction A paints solid grounds and solid ink                                                             |
| class     | `bg-gradient-to-r`                                                                      | not painted on this surface | gradient: Direction A paints solid grounds and solid ink                                                             |
| class     | `bg-gradient-to-tr`                                                                     | not painted on this surface | gradient: Direction A paints solid grounds and solid ink                                                             |
| class     | `bg-green-500`                                                                          | semantic #2E5E4E            | live dot                                                                                                             |
| class     | `bg-linear-to-br`                                                                       | not painted on this surface | gradient: Direction A paints solid grounds and solid ink                                                             |
| class     | `bg-linear-to-r`                                                                        | not painted on this surface | gradient: Direction A paints solid grounds and solid ink                                                             |
| class     | `bg-slate-50`                                                                           | wash #EAE3D8                | sunken / hover fill                                                                                                  |
| class     | `bg-surface-deep`                                                                       | wash #EAE3D8                | sunken / hover fill                                                                                                  |
| class     | `bg-surface-deep/40`                                                                    | wash #EAE3D8                | sunken / hover fill                                                                                                  |
| class     | `bg-surface-deep/60`                                                                    | wash #EAE3D8                | sunken / hover fill                                                                                                  |
| class     | `bg-surface-deep/80`                                                                    | wash #EAE3D8                | sunken / hover fill                                                                                                  |
| class     | `bg-surface-editorial-elevated`                                                         | elevated #FFFCF7            | card / glass panel ground                                                                                            |
| class     | `bg-white`                                                                              | ink #1D2C3B                 | progress fill: solid foreground                                                                                      |
| class     | `bg-white/2`                                                                            | elevated #FFFCF7            | card / glass panel ground                                                                                            |
| class     | `bg-white/5`                                                                            | elevated #FFFCF7            | card / glass panel ground                                                                                            |
| class     | `bg-white/[0.03]`                                                                       | elevated #FFFCF7            | card / glass panel ground                                                                                            |
| class     | `bg-white/[0.04]`                                                                       | elevated #FFFCF7            | card / glass panel ground                                                                                            |
| class     | `bg-white/[0.06]`                                                                       | elevated #FFFCF7            | card / glass panel ground                                                                                            |
| class     | `bg-white/[0.08]`                                                                       | elevated #FFFCF7            | card / glass panel ground                                                                                            |
| class     | `bg-white/[0.10]`                                                                       | elevated #FFFCF7            | card / glass panel ground                                                                                            |
| class     | `border-[#1c1c1e]`                                                                      | line #DAD8D1                | hairline                                                                                                             |
| class     | `border-[color:var(--border-strong)]`                                                   | line-strong #A8ACA9         | hover / focus edge                                                                                                   |
| class     | `border-[rgba(212,132,90,0.2)]`                                                         | line #DAD8D1                | rest hairline: copper borders on every card and chip break the 8% accent budget (plan 2.4)                           |
| class     | `border-[rgba(255,255,255,0.06)]`                                                       | line #DAD8D1                | hairline                                                                                                             |
| class     | `border-[rgba(255,255,255,0.07)]`                                                       | line #DAD8D1                | hairline                                                                                                             |
| class     | `border-[var(--border)]`                                                                | line #DAD8D1                | hairline                                                                                                             |
| class     | `border-[var(--kbli-border)]`                                                           | line #DAD8D1                | hairline                                                                                                             |
| class     | `border-[var(--kbli-pma-closed)]/20`                                                    | semantic #8E2F2A            | PMA closed verdict                                                                                                   |
| class     | `border-[var(--kbli-pma-closed)]/30`                                                    | semantic #8E2F2A            | PMA closed verdict                                                                                                   |
| class     | `border-[var(--kbli-pma-open)]/20`                                                      | semantic #2E5E4E            | PMA open verdict                                                                                                     |
| class     | `border-[var(--kbli-pma-open)]/30`                                                      | semantic #2E5E4E            | PMA open verdict                                                                                                     |
| class     | `border-[var(--kbli-pma-restricted)]/20`                                                | semantic #7A5A1E            | PMA restricted / amber highlight                                                                                     |
| class     | `border-accent-sand/20`                                                                 | line #DAD8D1                | rest hairline: copper borders on every card and chip break the 8% accent budget (plan 2.4)                           |
| class     | `border-accent-sand/30`                                                                 | line #DAD8D1                | rest hairline: copper borders on every card and chip break the 8% accent budget (plan 2.4)                           |
| class     | `border-accent-warm/30`                                                                 | line #DAD8D1                | rest hairline: copper borders on every card and chip break the 8% accent budget (plan 2.4)                           |
| class     | `border-slate-200`                                                                      | line #DAD8D1                | hairline                                                                                                             |
| class     | `border-white/10`                                                                       | line #DAD8D1                | hairline                                                                                                             |
| class     | `border-white/5`                                                                        | line #DAD8D1                | hairline                                                                                                             |
| class     | `border-white/[0.05]`                                                                   | line #DAD8D1                | hairline                                                                                                             |
| class     | `border-white/[0.06]`                                                                   | line #DAD8D1                | hairline                                                                                                             |
| class     | `border-white/[0.08]`                                                                   | line #DAD8D1                | hairline                                                                                                             |
| class     | `border-white/[0.14]`                                                                   | line-strong #A8ACA9         | hover / focus edge                                                                                                   |
| class     | `border-white/[0.1]`                                                                    | line-strong #A8ACA9         | hover / focus edge                                                                                                   |
| class     | `brand-tagline`                                                                         | ink #1D2C3B                 | footer tagline: #fff + text-shadow today = the 1.21:1 red of #7508; the R19Presentation shell already paints it ink. |
| class     | `drop-shadow-[0_0_8px_rgba(212,180,131,0.2)]`                                           | not painted on this surface | drop-shadow filter: Direction A is flat                                                                              |
| class     | `drop-shadow-lg`                                                                        | not painted on this surface | drop-shadow filter: Direction A is flat                                                                              |
| class     | `drop-shadow-md`                                                                        | not painted on this surface | drop-shadow filter: Direction A is flat                                                                              |
| class     | `drop-shadow-sm`                                                                        | not painted on this surface | drop-shadow filter: Direction A is flat                                                                              |
| class     | `filter`                                                                                | not painted on this surface | drop-shadow filter: Direction A is flat                                                                              |
| class     | `focus-within:bg-[#1c1c1e]`                                                             | wash #EAE3D8                | hover / focus fill                                                                                                   |
| class     | `focus-within:border-accent-warm/40`                                                    | copper #A44B36              | accent / action colour                                                                                               |
| class     | `focus-within:shadow-[0_0_20px_rgba(212,132,90,0.15)]`                                  | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `focus:border-accent-sand/30`                                                           | copper #A44B36              | accent / action colour                                                                                               |
| class     | `focus:border-white/[0.15]`                                                             | muted #58626B               | DEFECT W0: a focus border is a control boundary; line-strong was 2.09:1, muted is 5.67:1                             |
| class     | `focus:ring-1`                                                                          | copper #A44B36              | focus ring colour (R19: copper)                                                                                      |
| class     | `focus:ring-2`                                                                          | copper #A44B36              | focus ring colour (R19: copper)                                                                                      |
| class     | `focus:ring-[#D4B483]/30`                                                               | copper #A44B36              | focus ring colour (R19: copper)                                                                                      |
| class     | `focus:ring-[#dc2626]`                                                                  | copper #A44B36              | focus ring colour (R19: copper)                                                                                      |
| class     | `font-black`                                                                            | type Fraunces 450 display   | display weight on the h1: Fraunces carries one, 450                                                                  |
| class     | `font-bold`                                                                             | type Manrope 400 15px/1.75  | body weight: Manrope carries one, 400; emphasis is ink, not weight                                                   |
| class     | `font-extrabold`                                                                        | type Fraunces 450 display   | display weight on the h1: Fraunces carries one, 450                                                                  |
| class     | `font-light`                                                                            | type Manrope 400 15px/1.75  | body weight: Manrope carries one, 400; emphasis is ink, not weight                                                   |
| class     | `font-medium`                                                                           | type Manrope 400 15px/1.75  | body weight: Manrope carries one, 400; emphasis is ink, not weight                                                   |
| class     | `font-mono`                                                                             | type Manrope 400 15px/1.75  | Direction A sets no mono face: Manrope tabular-nums                                                                  |
| class     | `font-sans`                                                                             | type Manrope 400 15px/1.75  | body face                                                                                                            |
| class     | `font-semibold`                                                                         | type Manrope 400 15px/1.75  | body weight: Manrope carries one, 400; emphasis is ink, not weight                                                   |
| class     | `font-serif`                                                                            | type Fraunces 450 display   | display face                                                                                                         |
| class     | `from-[#D4B483]`                                                                        | not painted on this surface | gradient stop: Direction A paints solid grounds and solid ink                                                        |
| class     | `from-[#D4B483]/20`                                                                     | not painted on this surface | gradient stop: Direction A paints solid grounds and solid ink                                                        |
| class     | `from-[#D4B483]/40`                                                                     | not painted on this surface | gradient stop: Direction A paints solid grounds and solid ink                                                        |
| class     | `from-[#d4845a]`                                                                        | not painted on this surface | gradient stop: Direction A paints solid grounds and solid ink                                                        |
| class     | `from-white`                                                                            | not painted on this surface | gradient stop: Direction A paints solid grounds and solid ink                                                        |
| class     | `group-focus-visible:bg-[color-mix(in_srgb,var(--accent-zantara)_10%,transparent)]`     | wash #EAE3D8                | hover / focus fill                                                                                                   |
| class     | `group-focus-visible:border-[color:var(--accent-zantara)]`                              | structure #233D52           | Zantara accent                                                                                                       |
| class     | `group-focus-visible:text-[color:var(--accent-zantara)]`                                | structure #233D52           | Zantara accent                                                                                                       |
| class     | `group-focus-within:text-zinc-300`                                                      | ink #1D2C3B                 | primary text                                                                                                         |
| class     | `group-hover:bg-[color-mix(in_srgb,var(--accent-zantara)_10%,transparent)]`             | wash #EAE3D8                | hover / focus fill                                                                                                   |
| class     | `group-hover:bg-accent-warm/15`                                                         | wash #EAE3D8                | hover / focus fill                                                                                                   |
| class     | `group-hover:border-[color:var(--accent-zantara)]`                                      | structure #233D52           | Zantara accent                                                                                                       |
| class     | `group-hover:border-accent-warm/40`                                                     | copper #A44B36              | accent / action colour                                                                                               |
| class     | `group-hover:shadow-[0_0_25px_rgba(212,132,90,0.2),inset_0_1px_0_rgba(212,132,90,0.1)]` | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `group-hover:text-[#CCC]`                                                               | ink #1D2C3B                 | primary text                                                                                                         |
| class     | `group-hover:text-[color:var(--accent-zantara)]`                                        | structure #233D52           | Zantara accent                                                                                                       |
| class     | `group-hover:text-[var(--kbli-accent)]`                                                 | copper #A44B36              | accent / action colour                                                                                               |
| class     | `group-hover:text-accent-sand`                                                          | copper #A44B36              | accent / action colour                                                                                               |
| class     | `group-hover:text-accent-warm`                                                          | copper #A44B36              | accent / action colour                                                                                               |
| class     | `group-hover:text-white`                                                                | ink #1D2C3B                 | primary text                                                                                                         |
| class     | `group-hover:text-zinc-300`                                                             | ink #1D2C3B                 | primary text                                                                                                         |
| class     | `hover:bg-[#151921]`                                                                    | wash #EAE3D8                | hover / focus fill                                                                                                   |
| class     | `hover:bg-[#D01033]/90`                                                                 | copper #A44B36              | accent / action colour                                                                                               |
| class     | `hover:bg-[rgba(255,255,255,0.06)]`                                                     | wash #EAE3D8                | hover / focus fill                                                                                                   |
| class     | `hover:bg-accent-warm/10`                                                               | wash #EAE3D8                | hover / focus fill                                                                                                   |
| class     | `hover:bg-surface-editorial-elevated`                                                   | wash #EAE3D8                | hover / focus fill                                                                                                   |
| class     | `hover:bg-white/5`                                                                      | wash #EAE3D8                | hover / focus fill                                                                                                   |
| class     | `hover:bg-white/[0.05]`                                                                 | wash #EAE3D8                | hover / focus fill                                                                                                   |
| class     | `hover:bg-white/[0.06]`                                                                 | wash #EAE3D8                | hover / focus fill                                                                                                   |
| class     | `hover:bg-white/[0.07]`                                                                 | wash #EAE3D8                | hover / focus fill                                                                                                   |
| class     | `hover:border-[#D01033]/60`                                                             | copper #A44B36              | accent / action colour                                                                                               |
| class     | `hover:border-[rgba(255,255,255,0.12)]`                                                 | line-strong #A8ACA9         | hover / focus edge                                                                                                   |
| class     | `hover:border-[var(--kbli-accent)]/40`                                                  | copper #A44B36              | accent / action colour                                                                                               |
| class     | `hover:border-accent-sand`                                                              | copper #A44B36              | accent / action colour                                                                                               |
| class     | `hover:border-accent-sand/30`                                                           | copper #A44B36              | accent / action colour                                                                                               |
| class     | `hover:border-accent-sand/40`                                                           | copper #A44B36              | accent / action colour                                                                                               |
| class     | `hover:border-accent-warm/40`                                                           | copper #A44B36              | accent / action colour                                                                                               |
| class     | `hover:border-red-500/30`                                                               | copper #A44B36              | accent / action colour                                                                                               |
| class     | `hover:border-white/[0.1]`                                                              | line-strong #A8ACA9         | hover / focus edge                                                                                                   |
| class     | `hover:shadow-[0_0_15px_rgba(212,132,90,0.2)]`                                          | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `hover:shadow-[0_0_15px_rgba(212,132,90,0.4)]`                                          | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `hover:shadow-[0_0_20px_rgba(220,38,38,0.08),inset_0_1px_0_rgba(255,255,255,0.06)]`     | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `hover:shadow-[0_0_40px_rgba(208,16,51,0.3)]`                                           | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `hover:shadow-[0_8px_32px_rgba(0,0,0,0.35),inset_0_1px_0_rgba(255,255,255,0.06)]`       | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `hover:shadow-[0_8px_32px_rgba(212,132,90,0.1)]`                                        | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `hover:shadow-[0_8px_32px_rgba(220,38,38,0.15)]`                                        | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `hover:shadow-[0_8px_40px_rgba(212,132,90,0.15),inset_0_1px_0_rgba(255,255,255,0.06)]`  | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `hover:shadow-xl`                                                                       | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `hover:text-[var(--foreground-secondary)]`                                              | muted #58626B               | secondary text                                                                                                       |
| class     | `hover:text-[var(--kbli-accent)]`                                                       | copper #A44B36              | accent / action colour                                                                                               |
| class     | `hover:text-accent-warm`                                                                | copper #A44B36              | accent / action colour                                                                                               |
| class     | `hover:text-white`                                                                      | ink #1D2C3B                 | primary text                                                                                                         |
| class     | `kbli-flag-title`                                                                       | elevated #FFFCF7            | DEFECT W0: ink on the ink hero band was 1.00:1; solid elevated Fraunces is 13.91:1 on it                             |
| class     | `placeholder-[#444]`                                                                    | muted #58626B               | placeholder                                                                                                          |
| class     | `placeholder-zinc-400`                                                                  | muted #58626B               | placeholder                                                                                                          |
| class     | `placeholder-zinc-500`                                                                  | muted #58626B               | placeholder                                                                                                          |
| class     | `scrollbar-thumb-white/10`                                                              | line #DAD8D1                | scrollbar thumb                                                                                                      |
| class     | `scrollbar-track-transparent`                                                           | not painted on this surface | transparent track                                                                                                    |
| class     | `selection:bg-accent-sand/30`                                                           | wash #EAE3D8                | selection highlight                                                                                                  |
| class     | `selection:text-accent-sand`                                                            | ink #1D2C3B                 | selected text                                                                                                        |
| class     | `shadow-2xl`                                                                            | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `shadow-[-5px_0_30px_rgba(0,0,0,0.2)]`                                                  | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `shadow-[0_0_15px_rgba(212,132,90,0.2)]`                                                | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `shadow-[0_10px_40px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.03)]`             | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `shadow-[0_4px_20px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.04)]`              | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `shadow-[0_4px_20px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.06)]`              | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `shadow-[0_4px_24px_rgba(0,0,0,0.25),inset_0_1px_0_rgba(255,255,255,0.04)]`             | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `shadow-[0_4px_24px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.04)]`              | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `shadow-[0_8px_32px_rgba(0,0,0,0.4)]`                                                   | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `shadow-[5px_0_30px_rgba(0,0,0,0.3)]`                                                   | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]`                                         | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_2px_8px_rgba(0,0,0,0.2)]`               | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]`                                         | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `shadow-inner`                                                                          | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `shadow-md`                                                                             | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `shadow-sm`                                                                             | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                                            |
| class     | `text-[#050507]`                                                                        | ink #1D2C3B                 | dark text on a light chip                                                                                            |
| class     | `text-[#333]`                                                                           | muted #58626B               | secondary text                                                                                                       |
| class     | `text-[#444]`                                                                           | muted #58626B               | secondary text                                                                                                       |
| class     | `text-[#555]`                                                                           | muted #58626B               | secondary text                                                                                                       |
| class     | `text-[#666]`                                                                           | muted #58626B               | secondary text                                                                                                       |
| class     | `text-[#888]`                                                                           | muted #58626B               | secondary text                                                                                                       |
| class     | `text-[#999]`                                                                           | muted #58626B               | secondary text                                                                                                       |
| class     | `text-[#CCC]`                                                                           | ink #1D2C3B                 | primary text                                                                                                         |
| class     | `text-[#F0F0F0]`                                                                        | ink #1D2C3B                 | primary text                                                                                                         |
| class     | `text-[color:var(--footer-icon-color,rgba(255,255,255,0.72))]`                          | muted #58626B               | secondary text                                                                                                       |
| class     | `text-[var(--accent-whatsapp-ink)]`                                                     | elevated #FFFCF7            | CTA ink on copper                                                                                                    |
| class     | `text-[var(--foreground)]`                                                              | ink #1D2C3B                 | primary text                                                                                                         |
| class     | `text-[var(--foreground-muted)]`                                                        | muted #58626B               | secondary text                                                                                                       |
| class     | `text-[var(--foreground-secondary)]`                                                    | muted #58626B               | secondary text                                                                                                       |
| class     | `text-[var(--kbli-accent)]`                                                             | copper #A44B36              | accent / action colour                                                                                               |
| class     | `text-[var(--kbli-amber)]`                                                              | semantic #7A5A1E            | PMA restricted / amber highlight                                                                                     |
| class     | `text-[var(--kbli-pma-closed)]`                                                         | semantic #8E2F2A            | PMA closed verdict                                                                                                   |
| class     | `text-[var(--kbli-pma-open)]`                                                           | semantic #2E5E4E            | PMA open verdict                                                                                                     |
| class     | `text-[var(--kbli-pma-restricted)]`                                                     | semantic #7A5A1E            | PMA restricted / amber highlight                                                                                     |
| class     | `text-[var(--kbli-text-muted)]`                                                         | muted #58626B               | secondary text                                                                                                       |
| class     | `text-[var(--kbli-text-primary)]`                                                       | ink #1D2C3B                 | primary text                                                                                                         |
| class     | `text-accent-sand`                                                                      | copper #A44B36              | accent / action colour                                                                                               |
| class     | `text-accent-warm`                                                                      | copper #A44B36              | accent / action colour                                                                                               |
| class     | `text-amber-400`                                                                        | semantic #7A5A1E            | PMA restricted / amber highlight                                                                                     |
| class     | `text-slate-500`                                                                        | muted #58626B               | secondary text                                                                                                       |
| class     | `text-white`                                                                            | ink #1D2C3B                 | primary text                                                                                                         |
| class     | `text-white/40`                                                                         | muted #58626B               | secondary text                                                                                                       |
| class     | `text-white/50`                                                                         | muted #58626B               | secondary text                                                                                                       |
| class     | `text-white/60`                                                                         | muted #58626B               | secondary text                                                                                                       |
| class     | `text-white/80`                                                                         | ink #1D2C3B                 | primary text                                                                                                         |
| class     | `text-white/90`                                                                         | ink #1D2C3B                 | primary text                                                                                                         |
| class     | `text-zinc-100`                                                                         | ink #1D2C3B                 | primary text                                                                                                         |
| class     | `text-zinc-300`                                                                         | ink #1D2C3B                 | primary text                                                                                                         |
| class     | `text-zinc-400`                                                                         | muted #58626B               | secondary text                                                                                                       |
| class     | `to-[#0A0C10]`                                                                          | not painted on this surface | gradient stop: Direction A paints solid grounds and solid ink                                                        |
| class     | `to-[#3b82f6]`                                                                          | not painted on this surface | gradient stop: Direction A paints solid grounds and solid ink                                                        |
| class     | `to-[#8C7350]`                                                                          | not painted on this surface | gradient stop: Direction A paints solid grounds and solid ink                                                        |
| class     | `to-[#b36a46]`                                                                          | not painted on this surface | gradient stop: Direction A paints solid grounds and solid ink                                                        |
| class     | `to-transparent`                                                                        | not painted on this surface | gradient stop: Direction A paints solid grounds and solid ink                                                        |
| class     | `to-white/70`                                                                           | not painted on this surface | gradient stop: Direction A paints solid grounds and solid ink                                                        |
| class     | `via-[#D4B483]/10`                                                                      | not painted on this surface | gradient stop: Direction A paints solid grounds and solid ink                                                        |
| class     | `via-[#a855f7]`                                                                         | not painted on this surface | gradient stop: Direction A paints solid grounds and solid ink                                                        |
| rule      | `.kbli-prose p { color }`                                                               | muted #58626B               | editorial body copy                                                                                                  |
| rule      | `.kbli-prose ul li strong { color }`                                                    | ink #1D2C3B                 | emphasis in a bullet                                                                                                 |
| rule      | `.kbli-prose ul li strong { font }`                                                     | type Manrope 400 15px/1.75  | font-weight 600 today: emphasis is ink, not weight                                                                   |
| rule      | `.kbli-prose ul li { background }`                                                      | elevated #FFFCF7            | bullet card row                                                                                                      |
| rule      | `.kbli-prose ul li { color }`                                                           | muted #58626B               | bullet copy                                                                                                          |
| rule      | `.kbli-prose ul li::before { background }`                                              | copper #A44B36              | bullet tick                                                                                                          |
| rule      | `.selection\:bg-accent-sand\/30 ::selection { background }`                             | wash #EAE3D8                | selection highlight inside the explorer                                                                              |
| rule      | `.selection\:text-accent-sand ::selection { color }`                                    | ink #1D2C3B                 | selected text inside the explorer                                                                                    |
| rule      | `::placeholder { color }`                                                               | muted #58626B               | preflight placeholder: 50% currentColor today                                                                        |
| rule      | `[data-theme="editorial"] :is(h1, h2, h3) { font }`                                     | type Fraunces 450 display   | display face                                                                                                         |
| rule      | `body { background }`                                                                   | paper #F7F4EE               | inherited backdrop: the wrapper paints its own paper                                                                 |
| rule      | `body { color }`                                                                        | ink #1D2C3B                 | inherited ink: the wrapper sets its own color                                                                        |
| rule      | `body::before { background }`                                                           | not painted on this surface | fixed radial-gradient haze behind the page: the wrapper's opaque paper covers it                                     |
| rule      | `strong { font }`                                                                       | type Manrope 400 15px/1.75  | preflight bolder: emphasis is ink, not weight                                                                        |
| component | `CTAHandoff { background }`                                                             | paper #F7F4EE               | sticky handoff bar: reads --surface-base                                                                             |
| component | `CTAHandoff { border }`                                                                 | line #DAD8D1                | top rule: reads --color-border-subtle                                                                                |
| component | `NavShell { background }`                                                               | paper #F7F4EE               | nav ground: reads --nav-bg                                                                                           |
| component | `NavShell { border }`                                                                   | line #DAD8D1                | nav bottom rule: reads --nav-border                                                                                  |
| component | `NavShell { color }`                                                                    | muted #58626B               | nav links: read --text-tertiary                                                                                      |
| component | `NavShell { font }`                                                                     | type Manrope 400 15px/1.75  | nav links: font-medium today                                                                                         |
| component | `NavShell { shadow }`                                                                   | not painted on this surface | nav glass shadow: flat paper nav                                                                                     |
| component | `TrustBand { background }`                                                              | wash #EAE3D8                | reads --surface-subtle                                                                                               |
| component | `TrustBand { border }`                                                                  | line #DAD8D1                | reads --color-border-subtle                                                                                          |
| component | `TrustBand { color }`                                                                   | muted #58626B               | labels read --color-text-secondary: the 1.07:1 red of #7508                                                          |
| component | `TrustBand { font }`                                                                    | type Fraunces 450 display   | rating figures in strong: display numerals                                                                           |

<!-- contract:end -->

## 6. Exit

```
python3 scripts/mouth/r19_wrapper_token_census.py --json /tmp/census.json   # starts and kills its own dev server
python3 scripts/mouth/r19_wrapper_token_census.py --replay scripts/mouth/tests/fixtures/r19_wrapper_census.jsonl
```

The verdict is the printed `read-but-undefined:` line, never the exit code.
The state line is the third printed line; §7.5 defines it.

## 7. Amendment 2026-10-09: the state contract (W0b)

W0 described what the wrapper paints at rest. Two successors (#8118, #8139) were gate-blocked
because that left every hover, focus and selection colour unjudged. This amendment states them.
The §5 table keeps its format. Six of its rows are corrected below.

### 7.1 The state table

The block between `states:begin` and `states:end` has seven columns. `token` is the class as it
appears in the DOM. `state` is the variant that applies it. `property` is `color`, `background`,
`border`, `ring`, `shadow` or `scrollbar`. `value` is `<role> #HEX` exactly as in §3, or
`not painted on this surface` with a reason. `against` is the surface the pair is judged on, and
`contrast` is the ratio of the two, recomputed by the parser to two decimals.

- A `color` row is judged against the darkest surface it can sit on, the wash.
- A `background` row is judged against the text that sits on it: ink on the wash, elevated on copper.
- Floors: 4.5:1 for `color` and `background`; 3:1 for a `ring` and for a `focus` border, because
  that is a control boundary (WCAG 1.4.11). A `hover` border is decorative and has no floor.
- The table is the union of three sources: every state-variant colour class in the `/kbli*`
  sources on `origin/main` (components/kbli, app/kbli, app/kbli-explorer), the same set on
  #8139's head (`1fc7c5ad29`), and the state rows of §5. That is 80 tokens, 68 painted
  and 12 not painted. 17 of them are new to the contract.
- State rows also define their class for the `read-but-undefined` check.

<!-- states:begin -->

| token                                                                                   | state               | property   | value                       | against          | contrast | reason                                                                                             |
| --------------------------------------------------------------------------------------- | ------------------- | ---------- | --------------------------- | ---------------- | -------- | -------------------------------------------------------------------------------------------------- |
| `focus-visible:ring-[var(--kbli-accent)]`                                               | focus-visible       | ring       | copper #A44B36              | paper #F7F4EE    | 5.26     | keyboard focus ring: copper 2px                                                                    |
| `focus-within:bg-[#1c1c1e]`                                                             | focus-within        | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover and selection fills are the wash: no tinted slabs                                            |
| `focus-within:border-accent-warm/40`                                                    | focus-within        | border     | copper #A44B36              | paper #F7F4EE    | 5.26     | hover and focus rule keeps the action hue                                                          |
| `focus-within:shadow-[0_0_20px_rgba(212,132,90,0.15)]`                                  | focus-within        | shadow     | not painted on this surface | -                | -        | glow and elevation are not painted: Direction A has no coloured shadow                             |
| `focus:border-accent-sand/30`                                                           | focus               | border     | copper #A44B36              | paper #F7F4EE    | 5.26     | hover and focus rule keeps the action hue                                                          |
| `focus:border-white/[0.15]`                                                             | focus               | border     | muted #58626B               | paper #F7F4EE    | 5.67     | focus border is a control boundary: line-strong is 2.09:1, muted is 5.67:1 (WCAG 1.4.11 needs 3:1) |
| `focus:ring-1`                                                                          | focus               | ring       | copper #A44B36              | paper #F7F4EE    | 5.26     | keyboard focus ring is copper                                                                      |
| `focus:ring-2`                                                                          | focus               | ring       | copper #A44B36              | paper #F7F4EE    | 5.26     | keyboard focus ring is copper                                                                      |
| `focus:ring-[#D4B483]/30`                                                               | focus               | ring       | copper #A44B36              | paper #F7F4EE    | 5.26     | keyboard focus ring is copper                                                                      |
| `focus:ring-[#dc2626]`                                                                  | focus               | ring       | copper #A44B36              | paper #F7F4EE    | 5.26     | keyboard focus ring is copper                                                                      |
| `group-focus-visible:bg-[color-mix(in_srgb,var(--accent-zantara)_10%,transparent)]`     | group-focus-visible | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover and selection fills are the wash: no tinted slabs                                            |
| `group-focus-visible:border-[color:var(--accent-zantara)]`                              | group-focus-visible | border     | structure #233D52           | paper #F7F4EE    | 10.28    | Zantara second accent                                                                              |
| `group-focus-visible:text-[color:var(--accent-zantara)]`                                | group-focus-visible | color      | structure #233D52           | wash #EAE3D8     | 8.86     | Zantara second accent                                                                              |
| `group-focus-within:text-zinc-300`                                                      | group-focus-within  | color      | ink #1D2C3B                 | wash #EAE3D8     | 11.17    | emphasis goes up to ink                                                                            |
| `group-hover:bg-[color-mix(in_srgb,var(--accent-zantara)_10%,transparent)]`             | group-hover         | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover and selection fills are the wash: no tinted slabs                                            |
| `group-hover:bg-accent-warm/15`                                                         | group-hover         | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover and selection fills are the wash: no tinted slabs                                            |
| `group-hover:border-[color:var(--accent-zantara)]`                                      | group-hover         | border     | structure #233D52           | paper #F7F4EE    | 10.28    | Zantara second accent                                                                              |
| `group-hover:border-accent-warm/40`                                                     | group-hover         | border     | copper #A44B36              | paper #F7F4EE    | 5.26     | hover and focus rule keeps the action hue                                                          |
| `group-hover:shadow-[0_0_25px_rgba(212,132,90,0.2),inset_0_1px_0_rgba(212,132,90,0.1)]` | group-hover         | shadow     | not painted on this surface | -                | -        | glow and elevation are not painted: Direction A has no coloured shadow                             |
| `group-hover:text-[#CCC]`                                                               | group-hover         | color      | ink #1D2C3B                 | wash #EAE3D8     | 11.17    | emphasis goes up to ink                                                                            |
| `group-hover:text-[color:var(--accent-zantara)]`                                        | group-hover         | color      | structure #233D52           | wash #EAE3D8     | 8.86     | Zantara second accent                                                                              |
| `group-hover:text-[var(--kbli-accent)]`                                                 | group-hover         | color      | copper #A44B36              | wash #EAE3D8     | 4.53     | action hue holds on hover                                                                          |
| `group-hover:text-accent-sand`                                                          | group-hover         | color      | copper #A44B36              | wash #EAE3D8     | 4.53     | action hue holds on hover                                                                          |
| `group-hover:text-accent-warm`                                                          | group-hover         | color      | copper #A44B36              | wash #EAE3D8     | 4.53     | action hue holds on hover                                                                          |
| `group-hover:text-white`                                                                | group-hover         | color      | ink #1D2C3B                 | wash #EAE3D8     | 11.17    | emphasis goes up to ink                                                                            |
| `group-hover:text-zinc-300`                                                             | group-hover         | color      | ink #1D2C3B                 | wash #EAE3D8     | 11.17    | emphasis goes up to ink                                                                            |
| `hover:bg-[#151921]`                                                                    | hover               | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover and selection fills are the wash: no tinted slabs                                            |
| `hover:bg-[#252932]`                                                                    | hover               | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | dark modal button hover becomes the wash fill                                                      |
| `hover:bg-[#C4A473]`                                                                    | hover               | background | copper #A44B36              | elevated #FFFCF7 | 5.64     | primary CTA hover keeps the action hue                                                             |
| `hover:bg-[#D01033]/90`                                                                 | hover               | background | copper #A44B36              | elevated #FFFCF7 | 5.64     | primary action fill; its text is elevated                                                          |
| `hover:bg-[rgba(255,255,255,0.06)]`                                                     | hover               | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover and selection fills are the wash: no tinted slabs                                            |
| `hover:bg-[var(--kbli-accent)]/20`                                                      | hover               | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | accent tint becomes wash                                                                           |
| `hover:bg-accent-sand/10`                                                               | hover               | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | accent tint becomes wash                                                                           |
| `hover:bg-accent-warm/10`                                                               | hover               | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover and selection fills are the wash: no tinted slabs                                            |
| `hover:bg-surface-editorial-elevated`                                                   | hover               | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover and selection fills are the wash: no tinted slabs                                            |
| `hover:bg-white/5`                                                                      | hover               | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover and selection fills are the wash: no tinted slabs                                            |
| `hover:bg-white/[0.04]`                                                                 | hover               | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover fill                                                                                         |
| `hover:bg-white/[0.05]`                                                                 | hover               | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover and selection fills are the wash: no tinted slabs                                            |
| `hover:bg-white/[0.06]`                                                                 | hover               | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover and selection fills are the wash: no tinted slabs                                            |
| `hover:bg-white/[0.07]`                                                                 | hover               | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover and selection fills are the wash: no tinted slabs                                            |
| `hover:bg-white/[0.08]`                                                                 | hover               | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover fill                                                                                         |
| `hover:bg-white/[0.10]`                                                                 | hover               | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover fill                                                                                         |
| `hover:border-[#D01033]/60`                                                             | hover               | border     | copper #A44B36              | paper #F7F4EE    | 5.26     | hover and focus rule keeps the action hue                                                          |
| `hover:border-[rgba(255,255,255,0.12)]`                                                 | hover               | border     | line-strong #A8ACA9         | paper #F7F4EE    | 2.09     | hover rule, decorative                                                                             |
| `hover:border-[var(--kbli-accent)]/40`                                                  | hover               | border     | copper #A44B36              | paper #F7F4EE    | 5.26     | hover and focus rule keeps the action hue                                                          |
| `hover:border-[var(--kbli-accent)]/60`                                                  | hover               | border     | copper #A44B36              | paper #F7F4EE    | 5.26     | hover rule keeps the action hue                                                                    |
| `hover:border-accent-sand`                                                              | hover               | border     | copper #A44B36              | paper #F7F4EE    | 5.26     | hover and focus rule keeps the action hue                                                          |
| `hover:border-accent-sand/20`                                                           | hover               | border     | copper #A44B36              | paper #F7F4EE    | 5.26     | hover rule keeps the action hue                                                                    |
| `hover:border-accent-sand/30`                                                           | hover               | border     | copper #A44B36              | paper #F7F4EE    | 5.26     | hover and focus rule keeps the action hue                                                          |
| `hover:border-accent-sand/40`                                                           | hover               | border     | copper #A44B36              | paper #F7F4EE    | 5.26     | hover and focus rule keeps the action hue                                                          |
| `hover:border-accent-warm/40`                                                           | hover               | border     | copper #A44B36              | paper #F7F4EE    | 5.26     | hover and focus rule keeps the action hue                                                          |
| `hover:border-red-500/30`                                                               | hover               | border     | copper #A44B36              | paper #F7F4EE    | 5.26     | hover and focus rule keeps the action hue                                                          |
| `hover:border-white/[0.1]`                                                              | hover               | border     | line-strong #A8ACA9         | paper #F7F4EE    | 2.09     | hover rule, decorative                                                                             |
| `hover:shadow-[0_0_15px_rgba(212,132,90,0.2)]`                                          | hover               | shadow     | not painted on this surface | -                | -        | glow and elevation are not painted: Direction A has no coloured shadow                             |
| `hover:shadow-[0_0_15px_rgba(212,132,90,0.4)]`                                          | hover               | shadow     | not painted on this surface | -                | -        | glow and elevation are not painted: Direction A has no coloured shadow                             |
| `hover:shadow-[0_0_20px_rgba(220,38,38,0.08),inset_0_1px_0_rgba(255,255,255,0.06)]`     | hover               | shadow     | not painted on this surface | -                | -        | glow and elevation are not painted: Direction A has no coloured shadow                             |
| `hover:shadow-[0_0_40px_rgba(208,16,51,0.3)]`                                           | hover               | shadow     | not painted on this surface | -                | -        | glow and elevation are not painted: Direction A has no coloured shadow                             |
| `hover:shadow-[0_8px_32px_rgba(0,0,0,0.35),inset_0_1px_0_rgba(255,255,255,0.06)]`       | hover               | shadow     | not painted on this surface | -                | -        | glow and elevation are not painted: Direction A has no coloured shadow                             |
| `hover:shadow-[0_8px_32px_rgba(212,132,90,0.1)]`                                        | hover               | shadow     | not painted on this surface | -                | -        | glow and elevation are not painted: Direction A has no coloured shadow                             |
| `hover:shadow-[0_8px_32px_rgba(220,38,38,0.15)]`                                        | hover               | shadow     | not painted on this surface | -                | -        | glow and elevation are not painted: Direction A has no coloured shadow                             |
| `hover:shadow-[0_8px_40px_rgba(212,132,90,0.15),inset_0_1px_0_rgba(255,255,255,0.06)]`  | hover               | shadow     | not painted on this surface | -                | -        | glow and elevation are not painted: Direction A has no coloured shadow                             |
| `hover:shadow-xl`                                                                       | hover               | shadow     | not painted on this surface | -                | -        | glow and elevation are not painted: Direction A has no coloured shadow                             |
| `hover:text-[#888]`                                                                     | hover               | color      | ink #1D2C3B                 | wash #EAE3D8     | 11.17    | emphasis up on hover: ink on paper                                                                 |
| `hover:text-[var(--foreground-secondary)]`                                              | hover               | color      | muted #58626B               | wash #EAE3D8     | 4.88     | secondary text stays muted                                                                         |
| `hover:text-[var(--kbli-accent)]`                                                       | hover               | color      | copper #A44B36              | wash #EAE3D8     | 4.53     | action hue holds on hover                                                                          |
| `hover:text-[var(--kbli-accent-hover)]`                                                 | hover               | color      | copper #A44B36              | wash #EAE3D8     | 4.53     | hover keeps the hue                                                                                |
| `hover:text-accent-sand`                                                                | hover               | color      | copper #A44B36              | wash #EAE3D8     | 4.53     | hover keeps the hue                                                                                |
| `hover:text-accent-warm`                                                                | hover               | color      | copper #A44B36              | wash #EAE3D8     | 4.53     | action hue holds on hover                                                                          |
| `hover:text-white`                                                                      | hover               | color      | ink #1D2C3B                 | wash #EAE3D8     | 11.17    | emphasis goes up to ink                                                                            |
| `hover:text-zinc-300`                                                                   | hover               | color      | ink #1D2C3B                 | wash #EAE3D8     | 11.17    | emphasis up on hover: ink on paper                                                                 |
| `placeholder-[#444]`                                                                    | placeholder         | color      | muted #58626B               | wash #EAE3D8     | 4.88     | secondary text stays muted                                                                         |
| `placeholder-zinc-400`                                                                  | placeholder         | color      | muted #58626B               | wash #EAE3D8     | 4.88     | secondary text stays muted                                                                         |
| `placeholder-zinc-500`                                                                  | placeholder         | color      | muted #58626B               | wash #EAE3D8     | 4.88     | secondary text stays muted                                                                         |
| `prose-a:text-accent-warm`                                                              | prose-a             | color      | copper #A44B36              | wash #EAE3D8     | 4.53     | link inside a chat answer                                                                          |
| `prose-p:text-zinc-300`                                                                 | prose-p             | color      | ink #1D2C3B                 | wash #EAE3D8     | 11.17    | paragraph inside a chat answer                                                                     |
| `prose-strong:text-white`                                                               | prose-strong        | color      | ink #1D2C3B                 | wash #EAE3D8     | 11.17    | emphasis inside a chat answer                                                                      |
| `scrollbar-thumb-white/10`                                                              | scrollbar           | scrollbar  | line #DAD8D1                | paper #F7F4EE    | 1.30     | decorative thumb                                                                                   |
| `scrollbar-track-transparent`                                                           | scrollbar           | scrollbar  | not painted on this surface | -                | -        | transparent track paints nothing                                                                   |
| `selection:bg-accent-sand/30`                                                           | selection           | background | wash #EAE3D8                | ink #1D2C3B      | 11.17    | hover and selection fills are the wash: no tinted slabs                                            |
| `selection:text-accent-sand`                                                            | selection           | color      | ink #1D2C3B                 | wash #EAE3D8     | 11.17    | emphasis goes up to ink                                                                            |

<!-- states:end -->

Lowest painted pairs: `color` and `background` rows 4.53:1, `ring` and focus borders 5.26:1. No row is below its floor.

### 7.2 Defect corrections

Every §5 value was computed against the surface its reason declares, and every state row against
its `against` cell. Two pairs failed.

| row                         | was         | now      | pair                                                                    |
| --------------------------- | ----------- | -------- | ----------------------------------------------------------------------- |
| `kbli-flag-title`           | ink         | elevated | ink on the ink hero band was 1.00:1; elevated on it is 13.91:1          |
| `focus:border-white/[0.15]` | line-strong | muted    | a focus border is a control boundary: 2.09:1 fails 3:1, muted is 5.67:1 |

Hero band text rule: text on a `--kbli-ink` ground is paper or elevated, never ink, muted or copper.

### 7.3 Rulings on the amendment candidates

| candidate                                                                                                      | ruling         | reason                                                                                                                                       |
| -------------------------------------------------------------------------------------------------------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Copper rest borders (`border-[rgba(212,132,90,0.2)]`, `border-accent-sand/20`, `/30`, `border-accent-warm/30`) | CHANGE to line | A copper hairline on every card, chip and avatar adds up against the 8% budget (plan 2.4). §5 rows edited.                                   |
| Copper hover and focus borders                                                                                 | KEEP copper    | One element at a time, 5.26:1 on paper: the action signal, inside the budget.                                                                |
| PMA semantic borders (`border-[var(--kbli-pma-*)]/20`, `/30`)                                                  | KEEP           | The triad is excluded from the budget (plan 2.4) and each hue is at least 4.5:1 on paper.                                                    |
| Wash hover (`hover:bg-*` becomes wash)                                                                         | KEEP           | Wash against ink is 11.17:1, copper text on it 4.53:1. `hover:bg-surface-editorial-elevated` resolves to elevated today and must paint wash. |
| Explorer search frame (`border-accent-sand/30`, page.tsx line 324)                                             | CHANGE to line | It is the same rest copper border as the first row: one rule, one ruling.                                                                    |

### 7.4 Selector rule

Wrapper overrides must match `:is(.kbli-r19, .kbli-r19 *)`. A descendant-only selector such as
`.kbli-r19 *` cannot match the wrapper element itself, so `selection:` on the wrapper's own
classes escaped #8139's override. The census still keys a class read through the single-class
subject compound, so `.cls:is(.kbli-r19, .kbli-r19 *)` stays `class cls`.

### 7.5 The census walks states

The census adds a state walk on `desktop/light` and `mobile/system-dark` for each of the five
pages. Hover goes through `page.hover`, keyboard focus through Tab (up to 80 stops), and
selection through a programmatic range. Each token that the table declares is read where its
condition holds: computed `color`, `background-color`, border colour, ring or `::selection`,
alpha dropped as in W1. A token counts as off contract when the observed hex is not the row's
hex, or when a state-variant colour class has no row. The census prints, after the two W0
lines, `state-colors-off-contract: N`. On `origin/main` N is the pre-W2 state: it is reported,
not a gate. The gate for W2'' is N equal to 0.
