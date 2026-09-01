---
name: design
description: "Design corner — the shared brain for every Bali Zero visual surface (front page, GARUDA VOA, Visa Oracle, brand pages). Load BEFORE designing, judging or measuring any page, or when Zero says /design, 'la home', 'il rendering', 'la pagina'. Holds: the derivability doctrine (a rule that cannot name its input is a fad), the calibrated probes, the 2026-09-01 front page and how to rebuild it, and the standing rule that a mechanical gate can tell you a page is well-built but never that it is TRUE."
---

# /design — the visual-surface corner

> Created 2026-09-01 on Zero's order at the close of the front-page rebuild
> ("salva tutto in un nuovo corner /design che casomai vai a unire cn altre
> skill/corner"). This is HOT CONTEXT for any session touching a Bali Zero
> visual surface. **§1 LIVE STATE is only useful while it is true — update it
> when it changes.**

## 0. What this corner is, and the north star

Bali Zero sells a service that is easy to fake and expensive to get wrong: a
foreigner's permission to live in Indonesia. Every visual surface therefore has
one job before it has any other — **be recognisably the work of people who know
the answer.** The corpus's own documented failure mode is a page that is
"technically correct and emotionally flat"; the failure mode we shipped and had
to undo on 2026-09-01 is its sibling, a page that spends itself insisting it is
legitimate.

**THE NORTH STAR: the product's promise, delivered before anything is claimed.**
On a visa surface that means an answer in ten seconds. Knowing the answer is the
only trust signal a copycat cannot reproduce — a website is an afternoon's work,
knowing which permit someone needs is not. Proof of legitimacy is a line and a
row of real faces, never a section, never six.

**The unit of quality here is a MEASUREMENT, not an opinion** (SYMBIOSIS Law 7).
Everything in `strumenti/` exists so a design claim can be falsified. But see
§3: the measurements bound how well a page is BUILT and say nothing about
whether it is TRUE.

## 1. LIVE STATE (2026-09-01)

| thing                                                                      | where                                                                     | state                                                                                                                                 |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **Front page v2.1**                                                        | artifact `9f30f3b6-72c4-4a87-9e23-17c16581815c`                           | published, private. Source of truth = `prima-pagina/home.tpl.html` HERE                                                               |
| **Nine rendered states**                                                   | artifact `9f1fcdcd-a398-47df-a6ca-66940f572622`                           | published, private                                                                                                                    |
| **Design dossier** (110KB synthesis, 12 lane reports, 53+ gates, 11 knobs) | `~/Desktop/Design-Dossier-2026-08-31/`                                    | ⚠️ NOT in git, 29MB, and `~/Desktop` is TCC-denied in readdir — a glob there returns empty WITHOUT error. Read files by explicit path |
| **5-LLM blind contest** ("la prima pagina")                                | `~/Desktop/Design-Dossier-2026-08-31/concorso-la-prima-pagina/arena.html` | 🔴 **OPEN — awaiting Zero's blind vote.** `mapping.json` is sealed: NEVER put the seat↔letter mapping in prose before the vote        |
| Calibrated probes                                                          | `strumenti/` HERE                                                         | armed; controls pass                                                                                                                  |
| Front-page build chain                                                     | `prima-pagina/` HERE                                                      | proven end-to-end from a clean dir on 2026-09-01                                                                                      |

**Open, and they are Zero's, not a session's:**

- **Registry numbers + street address** — the footer carries a dashed placeholder.
  Nothing invented; needs the real NIB / entity / tax-licence numbers.
- **The August filing count** (`47 KITAS / 9 PT PMA`) is a SHAPE, not a measurement.
  Replace with the real CRM figure or delete the clause. Its methodology line
  (counted on submission, not approval; as-of date) is correct and must survive.
- **`since 2019` vs `since 2020`** contradict each other across `apps/mouth`
  (10 vs 14 occurrences), and `lib/trust-figures.ts` contradicts `app/layout.tsx`.
- **Five live `#1` claims** in `(marketing)/page.tsx` and `layout.tsx` — blocklist class.
- The 5-LLM contest vote.

## 2. The doctrine, in four rules

**R1 — Derivability (Test A).** A rule that cannot name the input it is computed
from is a fad, not a principle. "Ground L 18–20%" is derivable; "use a dark
theme" is not. Every knob in `§5.1` of the dossier names its input.

**R2 — Falsifiability (Test B).** For every claim on a page, name the external
record that would falsify it. **Your own server renders decoration; a registrar
renders evidence.** This is why the footer links `oss.go.id`, `ahu.go.id` and
`sikop.kemenkeu.go.id` instead of showing a badge, and why the Google rating is
a link to the live profile with the date it was read.

**R3 — One peak per viewport.** Intensity is a budget. On the front page the
peak is the photograph; everything after it is quiet on purpose.

**R4 — Proof is a line, not a section.** See §0. The 2026-09-01 rebuild moved
proof from six of eight sections to one line plus six faces, and gave the space
to a photograph and a working answer.

## 3. Blood-bought rules (each one cost a real defect)

1. **A mechanical gate cannot be wrong about a regulation.** Twelve green gates
   sat on a widget that named the wrong visa code with confident specificity.
   Any surface that ANSWERS needs a cross-family refuter pointed at its facts —
   it is the only instrument aimed there. Ground truth for visas:
   `research/visa/2026-07-24-w2-factbase-*.md`, re-read on the turn you use it.
2. **A broken `<img>` passes every layout gate** — it still has a box, an alt
   string, a contrast ratio and a tap target. Six gates × six states plus six
   defect classes all reported clean on a page whose seven images were dead.
   `verify_images.py` exists for this, and it carries a deliberate guilt control.
3. **Your local render is not the published page.** The artifact wrapper injects
   `[hidden]{display:none!important}`; a local file without it lets
   `.opts{display:flex}` beat the `hidden` attribute. `home.tpl.html` now
   declares the host's rules itself. Whenever the host adds CSS to your document,
   declare it or you are measuring a different page.
4. **`loading="lazy"` on a data: URI defers nothing** (there is no request) but
   leaves cards outside a horizontal scroller undecoded. Pure downside.
5. **A copy blocklist over-matches on negations.** "We do **not** guarantee
   outcomes" fires a `guarantee` guard. The side that moves is the GUARD, never
   the honest sentence — narrow to a positive claim, then re-prove innocence AND
   guilt (cicatrix family #3).
6. **The brand mark is not a letter.** Setting it as the "B" of BALI reads
   "3ALI ZERO" at 26px. The staff cards put the mark BESIDE the wordmark; follow
   the brand rather than inventing a lockup for it.
7. **A colour mixed toward white or black outlives its ground** — on dark,
   lightening raises contrast; on paper it lowers it. Pin the token, not a
   `color-mix` string. (See memory `discovery_a_colour_mixed_toward_white_...`.)
8. **Prices come from PricingTool only** (CLAUDE.md golden rule #11), and the
   stores disagree: `practice_types.base_price` diverges from the sheet on
   `B1 - VOA` (750k vs 790k). A mockup shows no price.
9. **Client PII never reaches a mockup.** The one clean-consent image class is
   `apps/mouth/public/static/team/*.jpg` — staff cards, carrying their own name
   and role. The immigration-queue photograph in the same tree shows ~15–20
   identifiable strangers and must NOT be published.

## 4. What is here

```
strumenti/                 the calibrated probes — all read the RENDERED DOM
  measure.py    <file>     6 states (mobile/desktop × light/system-dark/forced-dark):
                           27-pair contrast, horizontal overflow, 44px tap targets,
                           external requests, no-JS text, derived palette/type metrics
  defects.py    <root>     six classes a human had to notice once: dead-control,
                           duplicate-string, heading-order, double-announce,
                           struck-copy, clipped-sentence. Needs <root>/*/ui.html and
                           <root>/../calib -> controlli-di-calibrazione
  occlusion.py             overlap/occlusion pass
  regression.py            before/after comparison
  judge.py                 rubric scoring
  controlli-di-calibrazione/   the innocence + guilt controls. A run whose
                           innocence is NOISY or whose guilt is SILENT proves nothing

prima-pagina/              the 2026-09-01 front page, rebuildable from repo sources
  home.tpl.html            THE SOURCE. Tokens __LOGO__ __HERO__ __SURYA__ ... substituted at build
  assets.py                re-encodes mark + hero + 6 staff cards from apps/mouth/public
  build.py                 template + assets.json -> home.html
  render.py                9 states incl. two answered-widget shots and two diagnostics
  shrink.py / gallery.py   PNG -> JPEG, then the 9-state gallery page
  verify_images.py         every <img> actually decoded (guilt-controlled)
  verify_copy.py           drives all 7 widget branches + runs the claim blocklist
```

Nothing images-shaped is copied into this corner on purpose: the staff photos
stay in `apps/mouth/public/static/team/` and are re-encoded on demand. A second
copy is a second thing to keep in sync and a second place they can leak from.

## 5. How to rebuild the front page (proven 2026-09-01, clean dir)

```bash
C=<repo>/.agents/skills/design ; T=<scratch>/proof ; R=<repo-root>
V=<repo-root>/apps/backend-rag/.venv/bin/python      # Pillow lives here, not in system python
mkdir -p "$T"
"$V" "$C/prima-pagina/assets.py" "$R" "$T"           # -> assets.json  (~159 KB inline)
python3   "$C/prima-pagina/build.py"  "$T"           # -> home.html    (~241 KB)
python3   "$C/prima-pagina/verify_images.py" "$T/home.html"   # must say 8/8
python3   "$C/prima-pagina/verify_copy.py"   "$T/home.html"   # 7 branches + blocklist
mkdir -p "$T/probe/home" && cp "$T/home.html" "$T/probe/home/ui.html"
ln -sfn "$C/strumenti/controlli-di-calibrazione" "$T/calib"
python3   "$C/strumenti/measure.py" "$T/home.html"
python3   "$C/strumenti/defects.py" "$T/probe"       # must say "probe trusted"
python3   "$C/prima-pagina/render.py" "$T/home.html" "$T/shots"
```

The headless Chromium path is resolved per-machine (`CHROME_HEADLESS` env, else
the newest `~/Library/Caches/ms-playwright/chromium_headless_shell-*`) — M5's
home is `/Users/balizero`, Pro/Mini's is `/Users/nuzantara`, so a hardcoded path
is a probe that dies silently on the other machine.

**Read a probe's verdict only after reading its controls.** `defects.py` prints
them first for exactly this reason.

## 6. Conventions

- **Artifact commentary in Italian, UI copy in English.** Never mixed in one artifact.
- The study is a STUDY: no product code, no deploy, feature flags stay OFF.
  Output is research, doctrine and mockups.
- No external assets in an artifact beyond the CSP allowlist — inline everything
  as data URIs. Google Fonts is the one stylesheet host that loads.
- Publish updates to the SAME artifact URL (pass `url`); a new file path claims
  a new artifact and orphans the link Zero already has.

## 7. Merge candidates (Zero, 2026-09-01: "casomai vai a unire cn altre skill/corner")

This corner deliberately does NOT duplicate what already exists. If it is ever
consolidated, these are the neighbours and the seam:

| corner / skill                                      | overlap                                                                                                             | seam                                                                                                                                                                              |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `bali-zero-brand` (user skill, `~/.agents/skills/`) | palette, type, voice, forbidden phrases; surfaces `carousel-ig`, `internal-print-a4`, `web-mouth`, `email-template` | **It owns the brand tokens; this corner owns the measurement and the web-page doctrine.** A merge should fold §2–§3 in as a `web-front` surface and leave `tokens.json` sovereign |
| `wr2`                                               | the `carousel-ig` surface and its critic rubric                                                                     | wr2's critic judges slides; `strumenti/` judges pages. Same discipline (guilt+innocence), different DOM                                                                           |
| `visaoracle`                                        | the front page's widget answers ITS domain                                                                          | visaoracle owns the RulePack and the ENFORCE gate; this corner must never assert a verdict — the widget says "orientation, not a determination" and links out                     |
| `modus`                                             | Gear 3 governs a redesign of this size                                                                              | no overlap to merge; modus is the loop, this is the terrain                                                                                                                       |
