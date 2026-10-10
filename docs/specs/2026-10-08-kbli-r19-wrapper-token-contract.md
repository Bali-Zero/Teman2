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
  the census walks. §8 (W0c) names their grounds and classes and opens them. Attribute and ARIA
  state variants such as `data-[state=open]:`,
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
  the variant that reads on paper. §8.3 rules on it.
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
| class     | `border-[rgba(212,132,90,0.2)]`                                                         | line #DAD8D1                | rest hairline: copper is reserved for action, hover and focus (declared taste, R19 restraint)                        |
| class     | `border-[rgba(255,255,255,0.06)]`                                                       | line #DAD8D1                | hairline                                                                                                             |
| class     | `border-[rgba(255,255,255,0.07)]`                                                       | line #DAD8D1                | hairline                                                                                                             |
| class     | `border-[var(--border)]`                                                                | line #DAD8D1                | hairline                                                                                                             |
| class     | `border-[var(--kbli-border)]`                                                           | line #DAD8D1                | hairline                                                                                                             |
| class     | `border-[var(--kbli-pma-closed)]/20`                                                    | semantic #8E2F2A            | PMA closed verdict                                                                                                   |
| class     | `border-[var(--kbli-pma-closed)]/30`                                                    | semantic #8E2F2A            | PMA closed verdict                                                                                                   |
| class     | `border-[var(--kbli-pma-open)]/20`                                                      | semantic #2E5E4E            | PMA open verdict                                                                                                     |
| class     | `border-[var(--kbli-pma-open)]/30`                                                      | semantic #2E5E4E            | PMA open verdict                                                                                                     |
| class     | `border-[var(--kbli-pma-restricted)]/20`                                                | semantic #7A5A1E            | PMA restricted / amber highlight                                                                                     |
| class     | `border-accent-sand/20`                                                                 | line #DAD8D1                | rest hairline: copper is reserved for action, hover and focus (declared taste, R19 restraint)                        |
| class     | `border-accent-sand/30`                                                                 | line #DAD8D1                | rest hairline: copper is reserved for action, hover and focus (declared taste, R19 restraint)                        |
| class     | `border-accent-warm/30`                                                                 | line #DAD8D1                | rest hairline: copper is reserved for action, hover and focus (declared taste, R19 restraint)                        |
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
`state-colors-off-contract:` follows `colors-outside-direction-a:` and `state-rows-unseen:`; §7.5 defines both.
The opened-surface lines of §8.4 come last, and the last printed line is `opened-text-below-4.5:`.

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
  #8139's head (`1fc7c5ad29`), and the state rows of §5. That is 81 tokens, 69 painted
  and 12 not painted. 18 of them are new to the contract.
- State rows also define their class for the `read-but-undefined` check.

<!-- states:begin -->

| token                                                                                   | state               | property   | value                       | against          | contrast | reason                                                                                             |
| --------------------------------------------------------------------------------------- | ------------------- | ---------- | --------------------------- | ---------------- | -------- | -------------------------------------------------------------------------------------------------- |
| `focus-visible:ring-2`                                                                  | focus-visible       | ring       | copper #A44B36              | paper #F7F4EE    | 5.26     | keyboard focus ring is copper                                                                      |
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

| candidate                                                                                                      | ruling                          | reason                                                                                                                                                                                                                                                     |
| -------------------------------------------------------------------------------------------------------------- | ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Copper rest borders (`border-[rgba(212,132,90,0.2)]`, `border-accent-sand/20`, `/30`, `border-accent-warm/30`) | CHANGE to line (declared taste) | Not a budget matter: on main at 1440x900 these classes cover at most 0.22% of a screen (0.216% worst, /kbli-explorer, 6 elements) against an 8% budget. Declared taste: copper is reserved for action, hover and focus, the R19 restraint. §5 rows edited. |
| Copper hover and focus borders                                                                                 | KEEP copper                     | One element at a time, 5.26:1 on paper: the action signal.                                                                                                                                                                                                 |
| PMA semantic borders (`border-[var(--kbli-pma-*)]/20`, `/30`)                                                  | KEEP                            | The triad is excluded from the budget (plan 2.4) and each hue is at least 4.5:1 on paper.                                                                                                                                                                  |
| Wash hover (`hover:bg-*` becomes wash)                                                                         | KEEP                            | Wash against ink is 11.17:1, copper text on it 4.53:1. `hover:bg-surface-editorial-elevated` resolves to elevated today and must paint wash.                                                                                                               |
| Explorer search frame (`border-accent-sand/30`, page.tsx line 324)                                             | CHANGE to line (declared taste) | It is the same rest copper border as the first row: one rule, one ruling.                                                                                                                                                                                  |

### 7.4 Selector rule

Wrapper overrides must match `:is(.kbli-r19, .kbli-r19 *)`. A descendant-only selector such as
`.kbli-r19 *` cannot match the wrapper element itself, so `selection:` on the wrapper's own
classes escaped #8139's override. The census still keys a class read through the single-class
subject compound, so `.cls:is(.kbli-r19, .kbli-r19 *)` stays `class cls`.

### 7.5 The census walks states

The census adds a state walk on `desktop/light` and `mobile/system-dark` for each of the five
pages. Hover goes through `page.hover`, keyboard focus through Tab (up to 80 stops), and
selection through a programmatic range. Each token that the table declares is read where its
condition holds: computed `color`, `background-color`, border colour, ring, `scrollbar-color` or
`::selection`. Alpha is dropped for every syntax Chrome computes (rgb, `color(srgb)`, oklab, oklch,
lab, lch): the `/ α` is cut off the computed string before any canvas conversion, which only ever
sees an opaque colour. Tailwind 4 writes `/30` as `color-mix(in oklab, …)`, which computes to
`oklab(L a b / α)`; a canvas round-trip of that drifts (copper at 30% read `#A64C35`). Copper at
30% now reads `#A44B36`, as W1's `slice(0, 7)` does. The
variant is split at the last colon outside brackets, so `[color:var(--x)]` is a utility. A token counts as off contract when the observed hex is not the row's
hex, or when a state-variant colour class has no row. The census prints, after the two W0
lines, `state-rows-unseen: U` (painted rows whose class is in the DOM and was never observed,
named) and then `state-colors-off-contract: N`. On `origin/main` N is the pre-W2 state: it is reported,
not a gate. The exit for W2'' is U equal to 0 and N equal to 0.

## 8. Amendment 2026-10-09: the surfaces a click opens (W0c, W0c', W0d-1, W0d-2)

#8161 (W2'') was gate-blocked for a cause that is not contract fidelity. The wrapper sets
`--color-white` to ink, as §5 says, but the `/kbli` search dropdown kept its unnamed ground
`bg-[#1c1c1f]/95`. Result titles read 1.05:1 and descriptions 2.40:1, on a surface no walk had
opened. §2 left drawers, modals, the sector panel and search results outside the census. This
amendment names every background those surfaces paint, the classes on them and the artwork in
the wrapper, and the census now opens them.

W0c (#8167) was gate-blocked in turn on two counts. The `/kbli` mobile nav drawer was neither
named nor opened, and the ground verdict judged class spellings rather than paint, so a dark
slab under a spelling with no row counted 0. W0c' adds the drawer (§8.5), judges every painted
ground by its computed value (§8.4) and follows the owner's ruling on the explorer logo (§8.3).

W0c' (#8183) was gate-blocked for the same cause, under-match. Its drift pin held only drawers on
the R19 branch, yet `/v2` and `/v2/news` render the non-R19 branch that W2''' edits, so an
ungated paper repaint printed D 0. The W0 census lot was suspended and specified
(`SPEC-W0d-census.md`, mission kit). W0d-1 implements its shared-component matrix (§8.5), and
W0d-2 its ground algorithm, the pixels and the painters (§8.4).

### 8.1 The surfaces table

**Scope, found mechanically.** The scope is every rest background class that §5 and §7 do not
name:

- `bg-*` colour utilities and the `from-`, `via-` and `to-` gradient stops;
- in `components/kbli`, `app/kbli` and `app/kbli-explorer`, plus the files they import that paint
  inside the wrapper: `components/ui/button.tsx`, `components/ui/skeleton.tsx`,
  `components/lead/WhatsAppLeadButton.tsx`, `components/funnel/funnel-nav.ts`,
  `app/v2/_components/MobileNav.tsx` and `lib/kbli*.ts`; tests excluded;
- on `origin/main` and on #8161's head (`51b2407f27`).

`rg` lists them. Chrome resolves each one on a bare element outside any wrapper
(`evidence/2026-10/agent-air-m5-mouth-kbli-r19-w0cp-1009-df574d62/surface_scan.py`).

- `rg` finds 92 rest background classes in the scope; `bg-accent-warm` makes 93. 49 have a §5
  row.
- The other 44 are the rows below: the 35 background rows of #8161's `unmapped-left.tsv`;
  three gradient stops that exist only on `origin/main` (`ZantaraChat.tsx`,
  `ThinkingIndicator.tsx`); `bg-transparent`; `bg-accent-warm`, which only #8161's wrapper
  stylesheet spells; and the four var classes of `components/ui/button.tsx` and `skeleton.tsx`.
- A **dark slab** is a class on whose colour ink reads below 4.5:1 at an alpha of 0.5 or more,
  or a gradient stop of such a colour. 34 classes qualify: 18 have a §5 row and 16 are rows
  below. A class that reads a `--kbli-*` var resolves to main's dark value here, because the
  scan runs outside the wrapper.
- The scan prints `unnamed-grounds: 0` and `unnamed-dark-slabs: 0`. It lists three state-variant
  background classes without a §7 row, the boundary-only classes of §8.6.

**Columns.** `token` is the class at rest; a state variant belongs to §7. `surface` says where
the class paints. `ground` is one of four kinds:

| ground   | what it is                                  | allowed value                                           | text                           |
| -------- | ------------------------------------------- | ------------------------------------------------------- | ------------------------------ |
| `opaque` | a text-bearing ground, painted at alpha 1   | paper, elevated or wash; copper only as the action fill | the roles of §3 that sit on it |
| `scrim`  | the backdrop behind an open dialog or sheet | ink, at any alpha                                       | none                           |
| `mark`   | a dot, caret or handle, painted at alpha 1  | any §3 role                                             | none                           |
| `-`      | the class paints nothing                    | `not painted on this surface`                           | none                           |

The scrim is the only translucency this section allows, because a scrim has to show the page it
dims. For an `opaque` row, `contrast` is the lowest ratio of the listed roles on the value. The
parser recomputes it to two decimals and refuses a row below 4.5:1.

**Rules.**

- A dark slab inside the wrapper is elevated or wash, never ink. Elevated is for a card: a
  dropdown, drawer, modal, sheet or bar. Wash is for a pill or band on a card. This is the
  §7.2 hero-band rule read the other way round.
- A translucent tint under text becomes opaque wash, and the hue lives in the word, as the
  `--kbli-pma-*-bg` rows of §5 already rule.

**Portals.** Three surfaces opened from inside the wrapper render through `Dialog.Portal` into
`<body>`, outside `.kbli-r19`: the sector drawer, the comparison modal and the `/kbli` mobile nav
drawer. **Ruling:** every surface opened from inside the wrapper renders inside `.kbli-r19`, or
carries the wrapper class on its portal content, so the wrapper's tokens reach it. A row here
binds there too. The census counts every opened surface outside the wrapper root
(`opened-outside-wrapper:`, §8.4).

<!-- surfaces:begin -->

| token                              | surface                                                                                                       | ground | value                       | text                                                    | contrast | reason                                                                            |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------- | ------ | --------------------------- | ------------------------------------------------------- | -------- | --------------------------------------------------------------------------------- |
| `bg-[#1c1c1f]/95`                  | /kbli search dropdown                                                                                         | opaque | elevated #FFFCF7            | ink, muted                                              | 6.08     | dark slab: a floating list is a card, so elevated; titles ink, descriptions muted |
| `bg-[#141416]/95`                  | sector drawer panel                                                                                           | opaque | elevated #FFFCF7            | ink, muted, copper, open, restricted, closed            | 5.64     | dark slab: a drawer is a card, so elevated                                        |
| `bg-[#0A0C10]`                     | comparison modal, mobile inspector sheet, inspector related-code cards                                        | opaque | elevated #FFFCF7            | ink, muted, copper, structure, open, restricted, closed | 5.64     | dark slab: modal, sheet and the cards on them are cards, so elevated              |
| `bg-[#0A0C10]/95`                  | explorer compare bar                                                                                          | opaque | elevated #FFFCF7            | ink, copper                                             | 5.64     | dark slab: a sticky bar over the paper page is a card, so elevated                |
| `bg-[#151921]`                     | explorer related-code buttons and risk pills                                                                  | opaque | wash #EAE3D8                | ink, muted, copper                                      | 4.53     | dark slab: a pill on a card is a sunken band, so wash                             |
| `bg-black/50`                      | explorer mobile inspector backdrop                                                                            | scrim  | ink #1D2C3B                 | -                                                       | -        | backdrop: dims the page behind an open sheet; no text sits on it                  |
| `bg-black/70`                      | sector drawer and comparison modal backdrop                                                                   | scrim  | ink #1D2C3B                 | -                                                       | -        | backdrop: dims the page behind an open dialog; no text sits on it                 |
| `bg-black/90`                      | Black Book modal backdrop                                                                                     | scrim  | ink #1D2C3B                 | -                                                       | -        | backdrop: dims the page behind an open dialog; no text sits on it                 |
| `bg-[#dc2626]/10`                  | search dropdown code chip                                                                                     | opaque | wash #EAE3D8                | copper                                                  | 4.53     | red tint becomes wash; the code is copper                                         |
| `bg-emerald-500/10`                | search dropdown verified PMA badge                                                                            | opaque | wash #EAE3D8                | open                                                    | 5.83     | verdict chip: the hue lives in the word                                           |
| `bg-zinc-500/10`                   | search dropdown unverified PMA badge                                                                          | opaque | wash #EAE3D8                | muted                                                   | 4.88     | neutral tint becomes wash                                                         |
| `bg-amber-500/10`                  | search dropdown risk badge, explorer legacy alert (warning)                                                   | opaque | wash #EAE3D8                | ink, restricted                                         | 4.98     | amber tint becomes wash; the hue lives in the word                                |
| `bg-amber-500/[0.08]`              | search dropdown error banner                                                                                  | opaque | wash #EAE3D8                | restricted                                              | 4.98     | amber tint becomes wash; the message is restricted                                |
| `bg-white/[0.02]`                  | search dropdown footer                                                                                        | opaque | wash #EAE3D8                | muted                                                   | 4.88     | footer band of the list: sunken, so wash                                          |
| `bg-red-500/10`                    | explorer legacy alert (critical)                                                                              | opaque | wash #EAE3D8                | ink, closed                                             | 6.36     | red tint becomes wash; the hue lives in the word                                  |
| `bg-amber-500/20`                  | explorer legacy alert icon tile (warning)                                                                     | opaque | wash #EAE3D8                | -                                                       | -        | icon tile: no text on it                                                          |
| `bg-red-500/20`                    | explorer legacy alert icon tile (critical)                                                                    | opaque | wash #EAE3D8                | -                                                       | -        | icon tile: no text on it                                                          |
| `bg-amber-500/5`                   | explorer inspector card (what you need)                                                                       | opaque | wash #EAE3D8                | ink, muted, restricted                                  | 4.88     | tinted card becomes wash                                                          |
| `bg-blue-500/5`                    | explorer inspector card (what it means)                                                                       | opaque | wash #EAE3D8                | ink, muted, structure                                   | 4.88     | tinted card becomes wash                                                          |
| `bg-green-500/5`                   | explorer inspector card (Bali context)                                                                        | opaque | wash #EAE3D8                | ink, muted, open                                        | 4.88     | tinted card becomes wash                                                          |
| `bg-slate-400/10`                  | /kbli/[code] unverified PMA verdict card                                                                      | opaque | wash #EAE3D8                | ink, muted                                              | 4.88     | neutral tint becomes wash                                                         |
| `bg-slate-400/5`                   | /kbli/[code] licensing note                                                                                   | opaque | wash #EAE3D8                | ink, muted                                              | 4.88     | neutral tint becomes wash                                                         |
| `bg-accent-sand/15`                | explorer compare toggle, on                                                                                   | opaque | wash #EAE3D8                | copper                                                  | 4.53     | accent tint becomes wash: no tinted copper slabs                                  |
| `bg-accent-warm/20`                | Zantara chat avatar                                                                                           | opaque | wash #EAE3D8                | -                                                       | -        | avatar disc: an icon, no text                                                     |
| `bg-[var(--kbli-accent)]/15`       | sector strip arrows and active chip                                                                           | opaque | wash #EAE3D8                | ink, copper                                             | 4.53     | accent tint becomes wash: no tinted copper slabs                                  |
| `bg-[var(--kbli-bg-elevated)]`     | /kbli/[code] cards, provenance badge                                                                          | opaque | elevated #FFFCF7            | ink, muted, copper, open, restricted, closed            | 5.64     | reads --kbli-bg-elevated: elevated                                                |
| `bg-[var(--kbli-bg-secondary)]`    | /kbli/[code] sunken bands                                                                                     | opaque | wash #EAE3D8                | ink, muted, copper                                      | 4.53     | reads --kbli-bg-secondary: wash                                                   |
| `bg-accent-sand`                   | explorer action buttons and the compare check                                                                 | opaque | copper #A44B36              | elevated                                                | 5.64     | the one action fill: copper under elevated text, as --r19-cta-ink                 |
| `bg-slate-500`                     | explorer status dot                                                                                           | mark   | muted #58626B               | -                                                       | -        | a dot, no text                                                                    |
| `bg-white/20`                      | explorer sheet drag handle                                                                                    | mark   | line-strong #A8ACA9         | -                                                       | -        | a handle, no text: visible on elevated                                            |
| `bg-accent-warm/60`                | Zantara chat typing dots                                                                                      | mark   | copper #A44B36              | -                                                       | -        | dots, no text                                                                     |
| `from-[#0F1115]`                   | explorer inspector header                                                                                     | -      | not painted on this surface | -                                                       | -        | gradient stop: Direction A paints solid grounds; the header sits on its panel     |
| `to-[#050507]`                     | explorer inspector header                                                                                     | -      | not painted on this surface | -                                                       | -        | gradient stop: Direction A paints solid grounds; the header sits on its panel     |
| `from-[#d4845a]/20`                | Zantara chat bubble                                                                                           | -      | not painted on this surface | -                                                       | -        | gradient stop: Direction A paints solid grounds and solid ink                     |
| `to-[#d4845a]/5`                   | Zantara chat bubble                                                                                           | -      | not painted on this surface | -                                                       | -        | gradient stop: Direction A paints solid grounds and solid ink                     |
| `to-[#C4A473]`                     | explorer thinking indicator                                                                                   | -      | not painted on this surface | -                                                       | -        | gradient stop: Direction A paints solid grounds and solid ink                     |
| `bg-destructive/10`                | route error boundaries                                                                                        | -      | not painted on this surface | -                                                       | -        | no colour named destructive exists: the class paints nothing today                |
| `bg-green-50`                      | TransitionBadge source comment                                                                                | -      | not painted on this surface | -                                                       | -        | named only in a source comment: no element carries it                             |
| `bg-transparent`                   | explorer answer, chat input, outline Button                                                                   | -      | not painted on this surface | -                                                       | -        | transparent: the class paints no ground of its own                                |
| `bg-accent-warm`                   | no element: only inside the escaped selector of `group-hover:bg-accent-warm/15` in #8161's wrapper stylesheet | -      | not painted on this surface | -                                                       | -        | no element carries it                                                             |
| `bg-[var(--accent)]`               | route error boundary Try Again (Button default variant)                                                       | opaque | copper #A44B36              | elevated                                                | 5.64     | the action fill under elevated text, as --r19-cta-ink                             |
| `bg-[var(--error)]`                | Button destructive variant                                                                                    | -      | not painted on this surface | -                                                       | -        | no /kbli* route renders the destructive variant                                   |
| `bg-[var(--background-elevated)]`  | route loading skeleton cards                                                                                  | opaque | elevated #FFFCF7            | ink, muted                                              | 6.08     | a card                                                                            |
| `bg-[var(--background-secondary)]` | route loading skeleton bubbles, Button secondary variant                                                      | opaque | wash #EAE3D8                | ink, muted                                              | 4.88     | a sunken band                                                                     |

<!-- surfaces:end -->

Lowest text pair: 4.53:1, copper on wash: the dropdown code chip, a related-code pill and the
compare toggle.

### 8.2 The classes on those surfaces

The scan also finds the non-background classes that the same surfaces carry unnamed. These
are §5 rows in §5's format, parsed by the same parser between their own markers. The census
reads them together with §5, and a token may appear in only one of the two tables. There are 60
rows:

- 41 classes from #8161's `unmapped-left.tsv`: 17 text colours, 17 borders and 7 shadows;
- `text-muted-foreground`, the explorer error boundary's body text;
- 12 `rule` rows for the `/kbli` mobile nav drawer, which paints through inline styles and its
  own vars rather than classes (§8.5);
- 6 `rule` rows for the explorer PMA badge, which paints through an inline style
  (`getPmaBadgeInline`).

Together, 8.1 and 8.2 name all 76 classes of #8161's `unmapped-left.tsv` and the six classes
the W0c gate found beyond it.

<!-- surface-classes:begin -->

| kind  | token                                                                         | value                       | reason                                                                                               |
| ----- | ----------------------------------------------------------------------------- | --------------------------- | ---------------------------------------------------------------------------------------------------- |
| class | `border-[#dc2626]/20`                                                         | line #DAD8D1                | hairline on an opened surface                                                                        |
| class | `border-[var(--kbli-accent)]/50`                                              | copper #A44B36              | active sector chip: the selection signal                                                             |
| class | `border-[var(--kbli-pma-restricted)]/30`                                      | semantic #7A5A1E            | PMA restricted edge, as /20                                                                          |
| class | `border-accent-sand/40`                                                       | line-strong #A8ACA9         | dashed underline of a tooltip term: visible, never a control boundary                                |
| class | `border-accent-sand`                                                          | copper #A44B36              | selected compare card: the selection signal                                                          |
| class | `border-amber-500/20`                                                         | line #DAD8D1                | hairline on an opened surface                                                                        |
| class | `border-amber-500/30`                                                         | line #DAD8D1                | hairline on an opened surface                                                                        |
| class | `border-blue-500/20`                                                          | line #DAD8D1                | hairline on an opened surface                                                                        |
| class | `border-green-500/20`                                                         | line #DAD8D1                | hairline on an opened surface                                                                        |
| class | `border-l-[#3b82f6]/50`                                                       | structure #233D52           | answer bubble left rule: the second accent                                                           |
| class | `border-l-[#D4B483]`                                                          | copper #A44B36              | selected answer card left rule: the selection signal                                                 |
| class | `border-l-white/10`                                                           | line #DAD8D1                | hairline on an opened surface                                                                        |
| class | `border-red-500/30`                                                           | line #DAD8D1                | hairline on an opened surface                                                                        |
| class | `border-slate-400/25`                                                         | line #DAD8D1                | hairline on an opened surface                                                                        |
| class | `border-slate-400/30`                                                         | line #DAD8D1                | hairline on an opened surface                                                                        |
| class | `border-white/20`                                                             | line #DAD8D1                | hairline on an opened surface                                                                        |
| class | `border-white/[0.10]`                                                         | line #DAD8D1                | hairline on an opened surface                                                                        |
| class | `shadow-[0_0_10px_rgba(212,132,90,0.2)]`                                      | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                            |
| class | `shadow-[0_0_10px_rgba(212,180,131,0.3)]`                                     | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                            |
| class | `shadow-[0_0_20px_rgba(220,38,38,0.08),inset_0_1px_0_rgba(255,255,255,0.06)]` | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                            |
| class | `shadow-[0_0_50px_rgba(212,180,131,0.1)]`                                     | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                            |
| class | `shadow-[0_10px_60px_rgba(0,0,0,0.6),inset_0_1px_0_rgba(255,255,255,0.04)]`   | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                            |
| class | `shadow-[0_16px_48px_rgba(0,0,0,0.5)]`                                        | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                            |
| class | `shadow-[0_4px_24px_rgba(0,0,0,0.3)]`                                         | not painted on this surface | shadow: Direction A is flat; cards separate by a 1px line                                            |
| class | `text-[#777]`                                                                 | muted #58626B               | secondary text: explorer answer descriptions                                                         |
| class | `text-[#BBB]`                                                                 | ink #1D2C3B                 | primary text: comparison modal and explorer answer                                                   |
| class | `text-[#c98a3a]`                                                              | muted #58626B               | truncation note: secondary text                                                                      |
| class | `text-[#dc2626]`                                                              | copper #A44B36              | search dropdown code: the accent colour                                                              |
| class | `text-amber-200`                                                              | ink #1D2C3B                 | legacy alert body (warning): primary text                                                            |
| class | `text-amber-300`                                                              | semantic #7A5A1E            | search error message: the amber word                                                                 |
| class | `text-amber-500`                                                              | semantic #7A5A1E            | legacy alert icon (warning)                                                                          |
| class | `text-blue-400`                                                               | structure #233D52           | inspector card heading (what it means): the second accent                                            |
| class | `text-destructive`                                                            | not painted on this surface | no colour named destructive exists: the class paints nothing today                                   |
| class | `text-emerald-400`                                                            | semantic #2E5E4E            | verified PMA badge, thinking indicator: the open word                                                |
| class | `text-green-400`                                                              | semantic #2E5E4E            | inspector card heading (Bali context)                                                                |
| class | `text-red-200`                                                                | ink #1D2C3B                 | legacy alert body (critical): primary text                                                           |
| class | `text-red-500`                                                                | semantic #8E2F2A            | legacy alert icon and title (critical)                                                               |
| class | `text-silver`                                                                 | not painted on this surface | no colour named silver exists: the text inherits the wrapper ink                                     |
| class | `text-slate-400`                                                              | muted #58626B               | secondary text                                                                                       |
| class | `text-white/70`                                                               | muted #58626B               | secondary text                                                                                       |
| class | `text-zinc-500`                                                               | muted #58626B               | secondary text                                                                                       |
| class | `text-muted-foreground`                                                       | muted #58626B               | explorer route error boundary body text                                                              |
| rule  | `MobileNav paper drawer { background }`                                       | paper #F7F4EE               | reads --nav-bg (section 5 paper) once the drawer renders inside the wrapper                          |
| rule  | `MobileNav paper drawer { color }`                                            | ink #1D2C3B                 | reads --text-primary                                                                                 |
| rule  | `MobileNav paper drawer { border }`                                           | line #DAD8D1                | reads --nav-border                                                                                   |
| rule  | `MobileNav paper menu label { color }`                                        | muted #58626B               | reads --text-tertiary                                                                                |
| rule  | `MobileNav paper item { background }`                                         | wash #EAE3D8                | color-mix(in srgb, var(--accent-funnel) 6%, transparent) today, a copper tint: an opaque sunken band |
| rule  | `MobileNav paper item { border }`                                             | line #DAD8D1                | color-mix(in srgb, var(--accent-funnel) 14%, transparent) today: a hairline                          |
| rule  | `MobileNav paper item { color }`                                              | ink #1D2C3B                 | reads --text-primary                                                                                 |
| rule  | `MobileNav paper CTA { background }`                                          | copper #A44B36              | Get Started reads --accent-funnel: the action fill                                                   |
| rule  | `MobileNav paper CTA { color }`                                               | elevated #FFFCF7            | reads --text-on-accent: elevated on copper, 5.64:1                                                   |
| rule  | `MobileNav paper login { color }`                                             | muted #58626B               | reads --text-secondary                                                                               |
| rule  | `MobileNav paper login { border }`                                            | line #DAD8D1                | reads --border-default                                                                               |
| rule  | `MobileNav paper overlay { background }`                                      | ink #1D2C3B                 | rgba(0,0,0,0.45) today: a scrim is ink at its own alpha, with no text on it                          |
| rule  | `explorer PMA badge inline { background }`                                    | wash #EAE3D8                | getPmaBadgeInline paints rgba(…, 0.12) today: an opaque wash chip, the hue in the word               |
| rule  | `explorer PMA badge inline { border }`                                        | line #DAD8D1                | getPmaBadgeInline paints rgba(…, 0.25) today: a hairline                                             |
| rule  | `explorer PMA badge inline, open { color }`                                   | semantic #2E5E4E            | the open verdict word                                                                                |
| rule  | `explorer PMA badge inline, restricted { color }`                             | semantic #7A5A1E            | the restricted verdict word                                                                          |
| rule  | `explorer PMA badge inline, closed { color }`                                 | semantic #8E2F2A            | the closed verdict word                                                                              |
| rule  | `explorer PMA badge inline, unknown { color }`                                | muted #58626B               | an unverified verdict is secondary text                                                              |

<!-- surface-classes:end -->

### 8.3 Artwork

Raster artwork carries no token (§2). It still paints a ground when its file has no alpha
channel. **Rule:** an image inside the wrapper has a transparent ground, or it is out of scope
for a stated reason. The colour type comes from the PNG header (`IHDR`).

| where                                                                                 | asset today                                                                                                                                                               | ruling                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| explorer sidebar, `app/kbli-explorer/page.tsx` `<img src="/images/logo-zantara.png">` | 1024x1024 PNG, colour type 2 (RGB, **no alpha**): a red 3 and a white om roundel on an opaque black square. The gate saw it as a heavy black square on the paper sidebar. | **Re-cut, keep the artwork** (the owner's ruling, Z-DECISIONI Q11). A new file `/images/logo-zantara-transparent.png` sits next to the old one; the `<img>` points at it. The black field becomes alpha through a background-only matte, a flood fill from the four corners, so the 3 and the om roundel keep their own pixels, the black disc inside the ring included. W2''' proves it: mode RGBA; the four corner pixels at alpha 0; a pixel diff of 0 against the original inside the roundel mask; one render of `/kbli-explorer` desktop/light with the logo on paper. |
| `/kbli` nav, `NavShell logo={<BZLogo variant="full" />}`                              | `/assets/logo/balizero-logo-clean.png`, 512x512 RGBA: the black disc lockup, transparent outside the disc                                                                 | **Keep.** The disc is the lockup itself, not a ground behind other content.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| footer, `BZLogo variant="round"`                                                      | `app/v2/_components/Footer.tsx`                                                                                                                                           | **Out of scope.** It is the shared v2 footer, outside the `/kbli*` fence: changing it changes every route.                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |

### 8.4 The census opens the surfaces

After the state walk, the census runs an opened-surface walk. Each scenario loads its page in
a fresh context and opens the surface with real input. The census waits 2.5 s with transitions
and animations off, then measures. Every context suppresses `setInterval` timers of 2 s or more,
so a rotating placeholder holds its first state and the count does not depend on the moment it
is read. The search and inspect APIs answer from
`scripts/mouth/tests/fixtures/r19_opened_surfaces.json` through Playwright route interception.
The fixture holds placeholder rows and no client data. The walk therefore needs no backend, and
it runs offline and in CI.

| scenario                    | page                                   | opened by                                                                                                                                                                           | walks                                                    |
| --------------------------- | -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| `search-dropdown`           | `/kbli`                                | typing `restaurant` in the hero search                                                                                                                                              | all six states                                           |
| `search-active-row`         | `/kbli`                                | the same query, then ArrowDown                                                                                                                                                      | desktop/light, mobile/system-dark                        |
| `search-error`              | `/kbli`                                | the same query, with the API answering 503                                                                                                                                          | the same two                                             |
| `sector-drawer`             | `/kbli`                                | a click on the first sector card (the intercepted route)                                                                                                                            | the same two                                             |
| `explorer-answer-inspector` | `/kbli-explorer?inspect=56101`         | a seeded answer with two results (`sessionStorage` `kbli-messages`) and the inspect deep link: the answer, the legacy alert, and the inspector as a desktop panel or a mobile sheet | the same two                                             |
| `explorer-compare`          | `/kbli-explorer`                       | the seeded answer, the compare toggle, two results, then "Compare 2 codes"                                                                                                          | the same two                                             |
| `explorer-black-book`       | `/kbli-explorer`                       | "Ask about your codes"                                                                                                                                                              | the same two                                             |
| `explorer-mobile-sidebar`   | `/kbli-explorer`                       | the menu button                                                                                                                                                                     | mobile/system-dark                                       |
| `kbli-mobile-nav`           | `/kbli`                                | the nav's hamburger (`button[aria-label="Open menu"]`)                                                                                                                              | mobile, all three themes                                 |
| `kbli-code-mobile-nav`      | `/kbli/55203`                          | the same                                                                                                                                                                            | mobile, all three themes                                 |
| shared components           | the ten pins of §8.5, outside `/kbli*` | the hamburger for MobileNav; none for NavShell and Footer, read at rest                                                                                                             | mobile/light and mobile/system-dark; NavShell on desktop |

**What is measured (W0d-2).** The ground under every text run is read twice, by the pixels and
by the painters (`SPEC-W0d-census.md` §2).

- **Text runs.** A run is one own text node of a visible element inside a surface root: opacity
  product at least 0.1, not `visibility:hidden`, a box larger than 1px. Its boxes are the node's
  Range client rects, so an icon beside it never pollutes the sample. Each box is sampled at its
  centre and at its four corners, inset by min(2px, 25%).
- **Resolver A, the pixels, decides.** Motion is frozen and the active element blurred. Every
  text inside the roots turns transparent (colour, fill, decoration, caret, shadow). The viewport
  is captured with CDP `Page.captureScreenshot` at device scale 1 and decoded in the page. A
  run's ground is the median of its samples, and a spread over 6 on any channel is non-uniform.
  A run below the fold is scrolled to the centre and captured there. Each position is read once
  two captures 100 ms apart are identical, so a section a script reveals on scroll has
  finished, and each page is read once its network has been idle for 500 ms. The dev server's
  indicator (`nextjs-portal`) is never painted: the census always runs on `next dev`, CI
  included, and the indicator sits over the viewport's bottom-left corner (W0d-2').
- **Resolver B, the painters, names.** `elementsFromPoint` runs with `pointer-events:auto`
  forced, so an overlay that ignores the pointer is still seen. An element outside the run that
  paints above it occludes that point. So does a fixed or sticky element outside the roots that
  paints anything at all, a faint layer or a filter included, such as a floating button's
  blurred glow. A run with even one point under such an overlay is read again once it is
  brought to the middle of the viewport, because a blur reaches past the overlay's box onto
  the points that are left (W0d-2'). Below the run, each element adds its `::after` and
  `::before`, its replaced content (`img`, `video`, `canvas`, `iframe`, `object`, `embed`, a
  painted SVG shape), its background image and its background colour. A layer's alpha is its own
  times every opacity above it. Layers composite down to the first opaque colour, then the
  `html`/`body` canvas, then white. A blend mode, a backdrop filter or a filter makes B
  approximate. The painter a line names is the topmost layer.
- **Agreement.** A and B agree within ±2 per channel. A run on which they do not, while B is
  neither approximate nor over an image, is listed under `ground-resolver-disagree`, so a painter
  B cannot see shows there instead of passing.
- **Grounds.** A run's ground, as A reads it, must be within ±2 per channel of paper, elevated or
  wash. Copper is a ground only for its own action: the painter is or sits inside `a`, `button`
  or `[role=button]`, the run is inside that action, and the painter's box lies within the
  action's box, ±1px. Ink is never a ground on an opened surface (§8.1). Text over an image is
  off contract, named by its cause: the topmost layer is an image, a gradient or replaced
  content, the text is clipped to its background, or A is non-uniform. Each distinct ground,
  painter and cause is one line.
- **Scrims.** A scrim is an element without text that covers at least 95% of the viewport,
  outside the roots, and paints a ground. It must be ink at an alpha below 1.
- **Classes.** Every background class on the surface or its scrim must paint its §8.1 row: the
  row's hex, at alpha 1 for `opaque` and `mark` rows, and nothing for a row that paints
  nothing. A colour class with no §5 or §8.1 row is off contract by its name.
- **Portals.** Each surface root that is neither inside the census's wrapper root nor carries
  `.kbli-r19` is counted.
- **Contrast.** M uses A's ground. The text colour is the computed colour times the opacity
  product, composited over that ground. The floor is 4.5:1 for all text.
- **At rest.** The same resolvers read every text run inside the wrapper on each of the 30 rest
  captures. There, ink is a ground too, but only under elevated or paper text (§7.2's flag and
  hero band).

**Declared deviations from `SPEC-W0d-census.md` §2.** Each was forced by a measurement on
`origin/main`, and each has a test.

- **A pseudo-element is a layer only when its box covers its host**, 90% each way. B cannot tell
  where a smaller one sits: the `/kbli/51101` list bullets (`li::before`) would name a copper
  dot as the ground of the whole item. A smaller pseudo-element that does sit under text still
  shows, because A reads it and disagrees with B.
- **Over an image means the topmost layer.** An image seen only through a translucent colour
  makes B approximate, and A's spread decides whether it shows. An image layer whose alpha
  cannot move a channel by 6 (`body::after`, the page's 1.5% noise texture) is faint: it names
  no ground and never occludes. Taken literally, §2.3's rule put every run on every page over
  an image.
- **The scroll cap is 250 positions, not 8.** The sector drawer holds about 1,700 runs and needs
  39 positions on desktop and 77 on mobile. A walk over the cap is still INCOMPLETE.
- **Rest captures are 30, not 54.** The four routes §1.a adds come with W0d-3.

**Verdict states.** Each walk prints one state:

- `ok`: at least one root, and at least one run measured by A;
- `failed:never-opened (<reason>)`: the page failed to load (`load: …`), the opener threw
  (`opener: …`), the page hydrated its own theme over the forced one (`theme: …`), there were 0
  roots or 0 text runs, or every run was occluded (`0 measurable, N occluded`);
- `failed:over-image-only (N runs)`: the surface opened, but every measured run is over an
  image. Its grounds are still listed under K.

Any failed walk, or any walk over the scroll cap, turns P, K, R and M INCOMPLETE, never 0.
Two gestures keep a loaded runner from failing a walk that would open (W0d-2'). When an opener
throws or leaves no root, the page is loaded and opened once more, because under load a click
can land before hydration: the surface never opens, closes again, or a link navigates away. A forced theme that hydration replaced is forced again
before the page is read, at rest and opened alike; a page that keeps its own fails the walk.

**What it prints.** `page-grounds-off-contract: G` follows `state-colors-off-contract:`. It
lists each distinct ground, painter and cause found at rest, and is INCOMPLETE when a capture
failed or its walk ran over the cap. Then:

1. `opened-surfaces: N ok, F failed`, then one line for each scenario and walk, with its state;
2. `opened-outside-wrapper: P`, one line per surface root outside the wrapper;
3. `opened-grounds-off-contract: K`, one line per distinct off ground, scrim or class;
4. `ground-resolver-disagree: R`, one line per run on which A and B disagree;
5. `shared-touched-unpinned: N` (§8.5);
6. `shared-component-drift: D` (§8.5);
7. last, `opened-text-below-4.5: M`.

**Numbers measured (W0d-2').** These are reported, not a gate. `origin/main` is `0c76eb94ed`
(`apps/mouth` and `packages/core` are unchanged through `c49b7e84ac`). It was walked twice on an
M5, 38 s apart, and the two verdict texts are identical (I11). #8161's head, `51b2407f27`, was
walked for its three search scenarios only. CI walked the same tree on Linux in
`wrapper-census-states`, twice on two runners, and the two verdict texts are identical; its
numbers differ from the M5's by a few lines, because the runner lays the pages out differently
(the #8202 gate traced it to the Linux fonts).

| head                      | `page-grounds-off-contract:` | `opened-surfaces:` | `opened-outside-wrapper:` | `opened-grounds-off-contract:` | `ground-resolver-disagree:` | `shared-touched-unpinned:` | `shared-component-drift:` | `opened-text-below-4.5:` |
| ------------------------- | ---------------------------- | ------------------ | ------------------------- | ------------------------------ | --------------------------- | -------------------------- | ------------------------- | ------------------------ |
| `origin/main`, M5         | 438                          | 25 ok, 0 failed    | 10                        | 140                            | 0                           | 0                          | 0                         | 680                      |
| `origin/main`, CI         | 437                          | 25 ok, 0 failed    | 10                        | 138                            | 0                           | 0                          | 0                         | 677                      |
| #8161's head, search only | not measured                 | 10 ok, 0 failed    | 0                         | 21                             | 0                           | not measured               | not measured              | 108                      |

- W0d-1 printed K 88 and M 398 on `origin/main` from the DOM composite. The pixels read every
  run: a run over an image now lists its ground, and a ground off by a few levels is its own
  line.
- On `origin/main` the dropdown titles are white on `#1C1C1F` (17.0:1), and the red code chips
  read 3.30:1 and 3.26:1. M also counts the sector drawer's faded and zinc text, the explorer's
  dark greys, and the `/kbli` mobile nav drawer's Get Started: 3.66:1 red (light and
  forced-dark) and 4.36:1 blue (system-dark).
- At #8161's head the dropdown titles read 1.04:1 and 1.03:1 on `#282729` and `#28282A`, the
  gate's number, now by the pixels.
- G counts `KBLIConsultationCTA` over its inline gradient on every state of `/kbli/55203`.
- R is 0 on `origin/main`. W0d-2 printed 2, and named the wrong cause (the page texture):
  - both runs were read at the viewport's bottom-left, where two fixed overlays sit: the dev
    server's indicator (`nextjs-portal`) and the floating button's blurred glow (`filter:
blur(6px)`, a box 64px wide that the pixels see and the painter stack did not). They were
    `'News'` in the `/kbli` footer (pixels `#F0F0F1`, painters `#F4F4F5`) and a `❓` chip in the
    sector drawer (pixels `#F5F7F9`, painters `#F8FAFC`);
  - read in the middle of the viewport, both agree with the painters, the texture included.
    The same corner was in the shared pin: the `/news` footer pinned `'News'` on `#E2DED6`,
    where it reads `#EEE9E1`. On #8202, CI read the same `'News'` as `#EFEAE2` and the copyright
    line there as over an image, and printed `shared-component-drift: 8`;
  - W0d-2' hides the indicator and makes a fixed or sticky overlay occlude, so the run is read
    again in the middle of the viewport. G falls by 11 and K by 3 for the same reason.
- R 0 is reachable by construction for W2''': no overlay of the instrument's own runner is ever
  painted, and a page's own fixed overlay never decides a run it covers. A disagreement left in
  W2''' is a ground the painters cannot name, which W2''' fixes in the page.
- P is 10. It counts the sector drawer and the comparison modal twice each, and the mobile nav
  drawer six times, because all three are portals into `<body>`.
- The exit for W2''' is G, F, P, K, R, N, D and M equal to 0.

**Not reached by the walk.** These rows are named in 8.1 and 8.2 and judged when a later walk
reaches them:

- the `/kbli/[code]` variants for codes the census does not open (`bg-slate-400/10`,
  `bg-slate-400/5`);
- the Zantara chat bubbles;
- the thinking indicator;
- the route error and loading boundaries (`components/ui/button.tsx`, `skeleton.tsx`).

### 8.5 The shared components (W0d-1)

`/kbli*` mounts components that also serve routes outside it. A `/kbli*` lot that edits one of
them repaints those routes too. Each component has one or more **branches**, the paint it takes
in a given context. The census pins one route per (component, branch) pair outside `/kbli*`,
taken on `origin/main`, and requires a pin for every pair of every shared file a lot touches.

**The matrix.** Paths are relative to `apps/mouth/src/` unless they start with `packages/`.

| file                                                                                                                                                                                                                          | mounts outside `/kbli*`                                                                                                                                | pair: pinned routes                                                                                                         | `/kbli*` takes                                                 |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `app/v2/_components/MobileNav.tsx`                                                                                                                                                                                            | `/v2`, `/v2/news`, `/visa/*`, BlogNav, `/property/eligibility`, `/tax-calendar`                                                                        | MobileNav non-R19: `/v2`, `/visa/second-home`, `/v2/news`; MobileNav R19: `/tax-calendar`, `/property/eligibility`, `/news` | the non-R19 branch on `origin/main`; the `paper` prop at #8161 |
| `packages/core/components/NavShell.tsx`, `NavShell.module.css`                                                                                                                                                                | `/v2`, `/v2/news`, `/visa/*` (default); `/tax-calendar`, `/property/eligibility`, BlogNav (paper)                                                      | NavShell default: `/v2`; NavShell paper: `/tax-calendar`                                                                    | default                                                        |
| `app/v2/_components/Footer.tsx`                                                                                                                                                                                               | `/v2`, `/v2/news`, the blog layout, the marketing home, `not-found`                                                                                    | Footer editorial: `/v2`; Footer R19 blog: `/news`                                                                           | the wrapper's tokens                                           |
| `packages/core/components/BZLogo.tsx`, `components/lead/WhatsAppLeadButton.tsx`, `packages/core/components/FunnelFrame.tsx`, `components/ui/button.tsx`, `components/ui/skeleton.tsx`, `components/providers/LazyToaster.tsx` | many routes each                                                                                                                                       | none                                                                                                                        | unpinned by construction                                       |
| `components/r19/R19Presentation.module.css`, `components/r19/presentation.ts` (`R19_VARS`)                                                                                                                                    | every R19 surface: the blog layout, `/tax-calendar`, `/property/eligibility`, the marketing home, `not-found`, MobileNav's R19 branch, the Zantara FAB | none                                                                                                                        | unpinned by construction (W0d-2)                               |

`NavShell.module.css` is NavShell's own stylesheet, so it is listed with it. MobileNav's non-R19
branch **with** `paper` renders only on `/kbli*`, so K judges it (§8.4) and D does not. The two
R19 presentation files paint every R19 surface, far beyond the drawer pins, so an edit to either
is unpinned by construction.

**Measured on `origin/main`.** The census reads each branch at run time, on the hydrated surface,
never from the server HTML, because the server markers do not always match the hydrated paint
(the spec found this on `/visa/voa`). MobileNav's branch is the drawer's `data-presentation`;
NavShell's is its `paper` class; Footer has none, and its paint follows the route.

W0d-1 listed the drawer's own ground, composited from the DOM. W0d-2 reads, with the pixels, the
ground under the drawer's `Home` item, which carries the item tint over the drawer:

| route                                             | MobileNav branch | under `Home`, light / system-dark (pixels) | W0d-1, drawer (DOM)   | Get Started ground    |
| ------------------------------------------------- | ---------------- | ------------------------------------------ | --------------------- | --------------------- |
| `/v2`                                             | non-R19          | `#D0C2C2` / `#13213D`                      | `#C0C3C8` / `#0F1B31` | `#FF2D4C` / `#3A6DFF` |
| `/v2/news`                                        | non-R19          | `#DED2D2` / `#101F3C`                      | `#C0C3C8` / `#0F1B31` | `#FF2D4C` / `#3A6DFF` |
| `/visa/second-home`                               | non-R19          | `#DFD3D3` / `#162440`                      | `#FDFCFB` / `#1C273C` | `#FF2D4C` / `#3A6DFF` |
| `/kbli`, `/kbli/55203`                            | non-R19          | `#BFB3B5`, `#C1B6B8` / `#101E3A`           | `#C0C3C8` / `#0F1B31` | `#FF2D4C` / `#3A6DFF` |
| `/tax-calendar`, `/property/eligibility`, `/news` | R19              | `#F2EAE3`                                  | `#F7F4EE`             | `#A44B36`             |

**Which ground is the truth (gate note on #8189).** The pixels. In light the non-R19 drawer
computes `rgba(255, 255, 255, 0.72)` with `backdrop-filter: blur(16px)`; `rgba(14, 26, 48,
0.94)` is its system-dark (editorial) value. W0d-1's `#C4BAC1` under the items composited the
6% item tint and the 0.72 white over the body's navy `#1D273B`. The backdrop, however, blurs the
page behind the drawer, not the body colour. So on `/v2` the pixels read `#C2B6B7` to `#D0C2C2`
under the items, `Business` and `Visa` read non-uniform, and the drawer root reads over-image.
B is approximate there (a backdrop filter), so R does not count the difference. In system-dark
the pixels read `#101E3A` to `#13213D` under the items, against B's `#111F3C` under `Home`.

- NavShell renders the default branch on `/v2` and the paper branch on `/tax-calendar`.
- The Footer reads `#F3F3F4` to `#F4F4F5` (light) and `#172E51` to `#182F52` (system-dark)
  under its text on `/v2`, and `#EDE9E1` at its root on `/news`.
- W0c' said that `/kbli` is the only route on the non-R19 branch. That was **false**: `/v2`,
  `/v2/news` and `/visa/second-home` render it too.

**Ruling.** The §8.2 `MobileNav paper` rows bind the drawer **only** under the `paper` prop, and
the drawer obeys the §8.1 Portal ruling. Every route outside `/kbli*` keeps its pinned paint.

**`shared-component-drift: D`.**

- The pins live in `scripts/mouth/tests/fixtures/r19_shared_component_pins.json`: ten (pair,
  route) pins, two walks each and four for NavShell, 24 walks in all.
- Every pin is walked at mobile/light and mobile/system-dark. NavShell is walked on desktop as
  well. At 390px its bar holds no text of its own (a raster logo, links hidden below `md`, an
  icon trigger), so its mobile pins are **ground-only**: the pixels read the bar's own ground
  at its centre and corners, `#FCFBF9` (light) and `#0F1C34` (system-dark) on `/v2`, and
  `#F7F4EE` on `/tax-calendar`.
- A walk's fingerprint holds:
  - each text pair, as foreground on the ground the pixels read, plus the label;
  - each text over an image, as its own colour and alpha plus the label;
  - the root's own ground, read by the pixels (W0d-2);
  - the branch.
- D counts the entries that appeared or vanished since the pin, plus any walk that is not in
  the pin. An entry whose colours moved by 2 or less per channel is the same entry, §8.4's
  tolerance: a ground the pixels read can move by a level from one walk to the next (W0d-2 saw
  36 such one-level moves in `/news`'s footer between two dev servers of the same tree).
- A pinned walk that is missing or failed turns D INCOMPLETE, never 0.

**`shared-touched-unpinned: N`.**

- The census lists the files the tree changed since its merge base with a base ref: in CI the
  pull request's base (the merge commit's first parent), locally `origin/main`, committed or not.
- It intersects that list with the matrix's file column.
- Every touched file needs a pin for every pair it serves, taken on the branch the pair claims.
  Otherwise the census prints one line naming the file and the pair, and counts it.
- A file with no pair is unpinned by construction, so W2''' must not edit it. A deliberate edit
  first adds its pins in a W0 lot.
- When git cannot diff, N is INCOMPLETE.

**Proof, on a scratch tree of `origin/main` served by its own dev server.** The rows below are
replayed from `scripts/mouth/tests/fixtures/r19_shared_mutants.json` by the test suite. W0d-2
walked them again with the pixel oracle (W0d-1 printed D 72 for mutation A).

| row             | change to `MobileNav.tsx`                                                                      | result                                                          |
| --------------- | ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| I9              | none                                                                                           | D 0                                                             |
| G27, mutation A | `background: isR19 ? "var(--nav-bg)" : "#F7F4EE"`, ungated                                     | D 84, all on `/v2`, `/v2/news` and `/visa/second-home`          |
| G28, mutation B | the item tint `color-mix(… 6% …)` becomes 40%, both branches                                   | D 108, on all six MobileNav pins                                |
| I10             | the drawer painted `#F7F4EE` only under a new `paper` prop, which `app/kbli/layout.tsx` passes | D 0; the `/kbli` drawers now paint `#F7F4EE`, and K judges them |
| G29             | `MobileNav.tsx` touched, with the `/v2` pins removed                                           | `shared-touched-unpinned: 1`, naming MobileNav non-R19          |

### 8.6 Boundary-only classes

The three `hover:` variants of `components/ui/button.tsx` render only inside the route
`error.tsx` boundaries, which no walk opens:

- `hover:bg-[var(--accent-hover)]`;
- `hover:bg-[var(--error)]/90`;
- `hover:bg-[var(--background-elevated)]`.

They have no §7 row, and the scan lists them as the only state-variant background classes
without one. The lot that walks the boundaries adds their §7 rows.

## 9. Amendment 2026-10-10: the census in parts (W0d-3a)

In one CI job the census took 28 min 39 s on its 30 captures (W0d-2'), against a 75-minute
timeout, and W0d-3 grows it to 54 captures and 51 walks. CI therefore runs it in parts, side by
side. Every count it prints is unchanged.

**The one list.** `scenarios()` lists every scenario of a full run in the order the run takes
them, each with the one part that runs it:

| part       | scenarios                                                            | count |
| ---------- | -------------------------------------------------------------------- | ----- |
| `rest`     | the 30 captures (5 pages in 6 states) and the 10 state walks of §7.5 | 40    |
| `kbli`     | the opened-surface walks of §8.4 on `/kbli` and `/kbli/55203`        | 18    |
| `explorer` | the opened-surface walks of §8.4 on `/kbli-explorer`                 | 7     |
| `shared`   | the shared-component walks of §8.5                                   | 24    |

`--part P` runs the scenarios of P and nothing else. With no `--part`, the census runs the whole
list in one job, as before.

**The aggregate.** Each part dumps what it walked (`--json`). `--replay` over the dumps,
concatenated in any order, folds the parts in the order of the table. A token that two parts
read folds as one run folds it. Every entry then goes back to where a full run takes it, and the
census is judged as one.

**What it prints.** The first line is `scenarios-off-manifest: S`. S counts:

- each scenario no part reported, done or failed (`missing:`);
- each scenario reported twice (`twice:`);
- each scenario that is not on the list (`unexpected:`).

Each is named on its own line. A missing scenario is entered as failed, whether it is a
capture, a state walk, an opened walk or a shared walk. Every count it feeds then reads
INCOMPLETE, never 0, and so does S.

A live part answers for its own scenarios. A replay answers for the whole list, whatever it
holds. A dump from before the parts has no list, and its replay prints no S line.

**In CI.**

- `wrapper-census-part (<part>)` runs one job per part, with fail-fast off and a 40-minute
  timeout each. Each job prints `phase-seconds:` for its part on stderr, never in the verdict.
- `wrapper-census-states` keeps its name. It downloads the dumps and replays them. It then asserts
  these five lines exactly:
  - `scenarios-off-manifest: 0`;
  - `captures: 30 ok, 0 failed`;
  - `opened-surfaces: 25 ok, 0 failed`;
  - `shared-touched-unpinned: 0`;
  - `shared-component-drift: 0`.
- The aggregate also fails when any part job did not succeed. The browser guilt and innocence
  tests run in the `explorer` job, after its census.
- The aggregate runs after a failed part, and reads that part's scenarios as missing.
- A dispatch with `parts` set to `["full"]` runs the whole census in one job. That is the
  reference the proof compares against.

**The proof.** On the same commit, the aggregate's verdict text is byte-identical to the verdict
of the single-job full run. Offline, a test cuts the full fixture into the four parts' dumps,
concatenates them in another order and replays them. The result is the same text as the full
dump's replay, and that text is the earlier verdict under its first line.
