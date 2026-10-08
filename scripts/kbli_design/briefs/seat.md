# KBLI Navigator — sealed design contest, round 1 (one shot)

You are one design seat. You answer ALONE: no other seat sees your work before it is measured. No
tools, no browsing, no file reads — everything you need is in this message. Answer once.

## The objective (the owner's words, translated)

Take the KBLI Navigator app's UI/UX to the highest global level WITHOUT touching any content —
every string, verdict, cap, citation and Bali reason stays byte-identical to the canonical dataset —
and refuse flatness and boring monotony in a way that can be counted.

## The app

- macOS app: 1,559 KBLI 2025 codes, the PMA verdict, the Bali overlay, licensing per scale, a
  dossier, a chat. Two variants from one codebase (INTERNAL and BKPM; BKPM = the same screens
  minus Media). You design the six screens below; they map 1:1 onto the app's baseline renders.
- The six screens in NAVIGATION ORDER (adjacency is measured in this order): search-results,
  registry-table, detail-card, dossier, sheet-ledger, chat.
- The measured "before" is the diagnosis at the end of this message: 17 contrast pairs below
  4.5:1 (15 are white risk-tier chips, day worse than night), a textual contradiction on blocked
  codes ("Open · 100%" under a red HEADS-UP banner), 21 unreachable content truncations, and a
  registry an earlier review called "a wall of plates".

## The visual language (inputs, not suggestions)

- Bali Zero R19, Direction A: paper #F7F4EE, elevated #FFFCF7, wash #EAE3D8; ink slate #1D2C3B,
  muted #58626B; structure #233D52; copper #A44B36 (the one action accent); lines #DAD8D1 and
  #A8ACA9. Type: Fraunces 450 for display (clamp(48px, 5vw, 68px)) + Manrope 400 15px/1.75 for
  text. Google Fonts is the only external host allowed.
- "Anima Indonesiana", the app's decorative register: gold-amber national register; padi and kapas
  only as a LINEAR motif, never as a shield or crest; a moment, never a wallpaper.
- Night: derive the night palette from the same family yourself; every pair still meets 4.5:1.

## Content is frozen

The content pack below is the ONLY source of KBLI facts. Every pack string you show is PASTED, never
retyped, and sits alone in an element carrying `data-pack="<key>"` whose rendered text is EXACTLY
that string: no CSS text-transform, no ellipsis, no added or removed character, no line break
inside (a string that itself contains a newline gets `white-space: pre-wrap`). Keys are the dotted
paths under `codes` in the pack: `55203.en.title`, `51101.verdict`, `56101.cap`,
`55203.en.heads_up.0`, `51101.id.rows.3.risk`, and so on. Labels you write yourself ("Max foreign",
"Licensing per scale") are fine; a KBLI fact that is not in the pack must not appear at all.
Across your six screens show, for each of 55203, 51101 and 56101, at least: `verdict`, `cap`,
`basis`, `en.title`, `id.title`, `en.bali_reason`, `en.heads_up.0`, `en.heads_up.1`, and for every
licensing row N its `en.rows.N.scale.0`, `en.rows.N.risk` and `en.rows.N.term`. Registry rows come
from the pack's other codes (their `en.title`, `verdict`, `cap`).

## The criteria, measured by a probe on your rendered DOM (C1–C10)

- C1 One peak per screen: exactly one element with `data-peak`; its box is at most 25% of the
  1440×900 viewport.
- C2 Composition variety: at least 3 distinct layout families across the 6 screens, and no two
  ADJACENT screens (navigation order) on the same column grid.
- C3 Type scale in use: at least 4 distinct font sizes painted on every screen; Fraunces at 48px or
  more on detail-card and dossier.
- C4 Editorial moment: exactly one element with `data-editorial` per screen (a specimen number, a
  pull-quote of the basis citation, a map or mark, a decorated empty state) — never two.
- C5 Accent budget: copper and gold at most 8% of the painted area of each screen. The PMA triad
  (the TERBUKA / TERBATAS / TERTUTUP colours) is excluded: mark those chips with `data-pma`.
- C6 Rhythm: at least 3 distinct vertical spacing steps per screen; no wall of equal plates.
- C7 Contrast: every text/background pair at least 4.5:1, day AND night, risk-tier chips included,
  and no horizontal scroll. Text sitting on a background image (gradients included) cannot be
  measured and counts as a failure.
- C8 Density: registry-table shows at least 12 rows inside 1440×900 at default size, with the
  verdict column visible.
- C9 Content frozen: every `data-pack` element's rendered text equals the pack, byte for byte.
- C10 Law: no Garuda emblem (UU 24/2009 Art. 57), no "Indonesia Emas 2045" logo, no government
  lockup; padi and kapas linear only.

## What you return — this exact shape, nothing before the first line

The first line is `VERDICT: <your thesis, named in at most 8 words>`. Then twelve files, each as:

```
=== FILE: <name> ===
<content>
=== END FILE ===
```

All twelve names are required: `search-results-day.html`, `registry-table-day.html`,
`detail-card-day.html`, `dossier-day.html`, `sheet-ledger-day.html`, `chat-day.html`,
`detail-card-night.html`, `registry-table-night.html`, `thesis.md`, `derivability.md`,
`self-report.md`, `motion.md`.

- Each HTML file: one self-contained file that declares `<meta charset="utf-8">`, inline CSS,
  assets as `data:` URIs, Google Fonts the only external request, complete without JavaScript, designed for exactly 1440×900 with no
  horizontal scroll.
- `thesis.md`: at most 300 words — the one idea, named, and what it refuses.
- `derivability.md`: a table `rule | input it is computed from` (e.g. `ground L 94% | paper
#F7F4EE`). A rule that cannot name its input is a fad: leave it out.
- `self-report.md`: your own measurement of each screen against C1–C10.
- `motion.md`: at most 10 lines — which transitions exist, their durations, and the
  `prefers-reduced-motion` fallback.
