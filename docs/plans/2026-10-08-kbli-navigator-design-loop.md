# KBLI Navigator — design loop: `/kbli*` onto R19, the app to world-class UI/UX

> Written on M5, 2026-10-08. Every number below comes from a command run on disk in the
> writing session, never from a report. Zero's mandate, verbatim (translated): **(1) the
> website — make it coherent in design and palette with R19; (2) the single app — confirm it
> is the most up-to-date one, then study with the other LLMs a design that takes the UI/UX to
> the highest global level without touching the contents, avoiding flatness and boring
> monotony.** Two tracks, two different shapes of work: W is a CONTRACT, A is a CONTEST.
>
> This document is the loop. It builds nothing. Track W produces a token contract + a guard
> and rebases an existing branch; Track A produces a `/dynamic-workflow` brief whose R1 is a
> sealed design contest judged blind by Zero.

---

## 0. Measured state (2026-10-08)

### 0.1 Website `/kbli*` (apps/mouth)

| fact                                                                                                                    | measure                                                                                                                                                                                                                                                                                                   |
| ----------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R19 marker on the KBLI surface                                                                                          | `data-presentation="r19"` on **0** files under `src/app/kbli` + `src/app/kbli-explorer` (2 files repo-wide carry it)                                                                                                                                                                                      |
| KBLI theme                                                                                                              | **dark-default**, 17 `--kbli-*` tokens in `globals.css` (`bg-base/card/elevated/input/primary/secondary/surface` + hovers, `border`, `ink`, `text-primary/secondary/muted`, `accent`, `accent-hover`) plus `--kbli-pma-restricted(-bg)` read by `kbli/[code]/page.tsx:424-425`                            |
| R19 tokens already in mouth                                                                                             | `globals.css`: `--r19-ink` ×15, `--r19-wash` ×8, `--r19-line` ×8, `--r19-surface` ×6, `--r19-muted` ×5, `--r19-line-strong` ×3, `--r19-paper` ×1, `--r19-copper` ×1; `src/lib/theme/rumahVars.ts` 18 refs, `merahPutihDayVars.ts` 0                                                                       |
| R19 language (Direction A, measured on the branch — `research/design/2026-09-11-r19-design-reuse-map-apps-mouth.md` §1) | paper `#F7F4EE`, elevated `#FFFCF7`, wash `#EAE3D8`; ink slate `#1D2C3B`, muted `#58626B`; structure `#233D52`; copper `#A44B36`; lines `#DAD8D1` / `#A8ACA9`; **Fraunces** 450 (display `clamp(48px,5vw,68px)`) + **Manrope** 400 15px/1.75                                                              |
| The wave that already exists                                                                                            | branch `agent/air-m5/mouth/ux-kbli-r19-0927` on origin (13-commit `ux-kbli-0926` rebased on `#7448`) — **PR #7508 CLOSED/SUSPENDED 2026-09-27**, three reds for ONE cause                                                                                                                                 |
| The cause, verbatim from the suspension                                                                                 | _"the R19 paper wrapper re-themes a dark-default app only partially, so every shared component or global class rule that reads a token the wrapper does not set keeps its dark-theme colour (TrustBand labels 1.07:1, footer tagline 1.21:1 on every /kbli surface)"_                                     |
| The prescribed next step, verbatim                                                                                      | _"a spec for the R19 wrapper token contract (every token read inside the wrapper is defined by the wrapper; a mechanical guard over the REAL rendered surface incl. packages/core + global class rules; a contrast census as acceptance), then this wave and the oracle/studio/voa waves rebase onto it"_ |
| Surface size                                                                                                            | 1,559 `/kbli/<code>` pages + `/kbli` index + `/kbli-explorer` (the AI-inspect surface, reads `inspect_kbli`)                                                                                                                                                                                              |

Builder Contract rule 1 binds: three reds for the same cause → no fourth round; a fix-of-a-fix
stops at depth 1; **the surface is under-specified, so write the spec.** Track W is that spec.

### 0.2 The single app — WHICH one is current (confirmed)

| candidate                                                                                                                                                                       | state                                                                                                                                                                                                                                                                                                                             | verdict                |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| **macOS native app** `KBLI Navigator - INTERNAL.app` (+ `BKPM` variant, one codebase) — repo **`~/kbli-navigator-app`** (moved from `~/Desktop/logo/`; still **no git remote**) | last commit `e15a920` 2026-10-07 (restore of design diagnostics); dataset re-anchored `3fa3e9b` 2026-09-25 to canonical **`c29d6e6aea7a4fdb`** — sha256 identical on repo `Resources/`, on the installed M5 bundle, and on `origin/main:data/source_documents/KBLI_2025_FINAL_CLEAN.json` today; installed on M5 and Pro Desktops | **this is the one**    |
| `apps/kbli-navigator` (Next.js, knowledge.balizero.com)                                                                                                                         | SSO-gated, `/kbli-navigator/*` 308 → `/kbli/*`, no deploy workflow; last three commits are dataset-sync side effects (2026-09-24)                                                                                                                                                                                                 | dormant — not in scope |

Already on disk in the app repo, to be REUSED not re-derived:

- `docs/LOOP-2026-09-17-fable-astra.md` — the previous loop; its §1 bans carry over unchanged:
  **max 2 review rounds per surface**, evidence ≤ code lines, no delivery gate on n=8, a dead
  seat is declared in one line and never replaced by a promoted reserve, no fix-of-a-fix past
  depth 1.
- `docs/design/diagnosis-2026-09-17.md` + `contrast-2026-09-17.json` (74 pairs, **17 fail**
  <4.5:1 — 15 are the literal `.white` risk-tier chips at `KBLIRegistryView.swift:1541/:1708`,
  **day worse than night** 2.06–2.62:1), `truncation-2026-09-17.json` (25 hits, 21 unreachable
  content caps), `states-2026-09-17.json`; C1 = the textual contradiction "Open · 100% / MAX
  FOREIGN" under the red HEADS-UP banner, measured on both PNGs.
- `docs/design/baseline-2026-09-17/` — **24 renders** = 6 screens (`chat`, `detail-card`,
  `dossier`, `registry-table`, `search-results`, `sheet-ledger`) × day/night × en/id +
  `manifest.json`, produced by `Sources/Snapshot.swift` (`KBLINavigator --snapshot <mode> out.png`,
  modes `detail`, `dossier:`, `registry:`, `rich:`, `empty:<noSelection|noResults|mediaEmpty|chat>`).
- Views (10): `RootView`, `SearchListView`, `KBLIRegistryView` + `KBLIRegistryTable`,
  `KBLIDetailView` + `KBLIDetailRichView`, `KBLIDossierView`, `RegistryVerdictSheet`, `ChatView`,
  `MediaView`; decor layer `D4Decor.swift` ("Anima Indonesiana", 2026-08-11, doctrine in
  `research/design/2026-08-11-kbli-navigator-indonesian-soul.md`: gold-amber national register,
  padi/kapas as linear motif never as a shield, **no Garuda emblem — UU 24/2009 Art. 57**).

---

## 1. Track W — `/kbli*` on R19: a contract, a guard, a census, then the rebase

Not a redesign. The design already exists (Direction A) and the wave already exists (#7508's
branch). What is missing is the thing the suspension named. Four lots, each ≤ ~400 net lines,
serial, each with its own `Bites:`.

| lot               | deliverable                                                                                                                                                                                                                                                                                                                                                                                                 | exit (a command, not an opinion)                                                                                                                                                                                                                                      |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **W0 contract**   | `docs/specs/<date>-kbli-r19-wrapper-token-contract.md`: the full list of tokens READ inside the `/kbli*` wrapper (every `--kbli-*`, every `--r19-*`, every Tailwind colour class, every `packages/core` component and global class rule that paints there), each mapped to ONE R19 Direction-A value or declared "not painted on this surface". No token may be read and undefined.                         | a script (`scripts/mouth/r19_wrapper_token_census.py`, read-only) walks the rendered DOM of `/kbli`, `/kbli/55203`, `/kbli/51101`, `/kbli/56101`, `/kbli-explorer` in the 6 states of `.claude/skills/design/strumenti/measure.py` and prints `read-but-undefined: 0` |
| **W1 guard**      | the census above armed as a test in `apps/mouth` (Playwright, local `next dev --webpack` — Vercel previews sit behind SSO), plus a **palette census**: every computed `color`/`background-color`/`border-color` on those pages ∈ the Direction-A set (+ the PMA verdict triad, which keeps its semantic hues at ≥4.5:1 on paper). Guilt control: a fixture that paints one `--kbli-bg-base` dark must fail. | `npm test -- r19-wrapper` green, with the guilt fixture red                                                                                                                                                                                                           |
| **W2 rebase**     | `agent/air-m5/mouth/ux-kbli-r19-0927` rebased onto W0+W1; token reads that the contract declares are rewritten, nothing else. Diff is not lost (suspension comment).                                                                                                                                                                                                                                        | `measure.py` 27-pair contrast ≥ 4.5:1 on all 6 states × 5 pages; `defects.py` "probe trusted"; `data-presentation="r19"` present on the 3 route files                                                                                                                 |
| **W3 prove-live** | merge → Vercel lands **STAGED** → `vercel promote <dpl>` (memory: merge ≠ live on mouth) → Playwright on `balizero.com`                                                                                                                                                                                                                                                                                     | `balizero.com/api/health .commit` = the merge SHA; the two 2026-09-27 reds re-measured: TrustBand labels and footer tagline ≥ 4.5:1                                                                                                                                   |

Seats: implementer **Sonnet 5**; refuter **Codex GPT-5.6-sol** (xhigh, read-only) on W0 only —
its one question is _"name a token read inside the wrapper that the contract does not define"_
(an UNDER-match hunt, superscar #3); final on-disk gate **Opus 5.5** xhigh. Human: none — the
session owns review → merge → arm → promote → prove-live. The oracle/studio/voa waves rebase
onto W0+W1 afterwards and are NOT in this loop.

`Bites:` per lot = the exit command above, run on the branch head, output pasted. W3's `Bites:`
is the live measurement, never the merge.

---

## 2. Track A — the app: a sealed multi-LLM design contest, content frozen

### 2.1 Shape

`/dynamic-workflow` with the objective in `docs/plans/2026-10-08-kbli-navigator-design-loop.objective.md`
(PII-free by construction — the brief builder's redactor refuses otherwise). Its R1 is the
contest; R2 is one cross-family refutation of the facts each mockup renders; synthesis by a
fresh **Opus 5.5** window; **Zero picks blind** (sealed `mapping.json`, as in the 2026-09-01
front-page contest — never put seat↔letter in prose before the vote).

```bash
# brief (bytes identical for every seat; arsenal probed at build time, never hardcoded)
python3 scripts/dynamic_workflow.py brief --slug kbli-nav-design \
  --objective-file docs/plans/2026-10-08-kbli-navigator-design-loop.objective.md \
  --colour BLUE --kit ~/BATTAGLIA-$(date +%Y%m%d)/DYNAMIC-WORKFLOW-kbli-nav-design
python3 scripts/dynamic_workflow.py check --kit ~/BATTAGLIA-$(date +%Y%m%d)/DYNAMIC-WORKFLOW-kbli-nav-design
```

Seat rule (from the 2026-09-17 loop, unchanged): a seat that the probe reports dead is declared
in one line in the kit and not replaced. **Quorum = 3 live FAMILIES**; below that the round is
postponed, not run with reserves. At the time of writing the probe says Kimi, Qwen 3.8 Max and
GLM 5.2 are `QUOTA_DEAD` — the brief re-measures at build time; this line is stale by construction.

### 2.2 What every coach receives (the content pack, built by the convener once)

- the 24 baseline PNGs + `manifest.json` — the "before";
- `diagnosis-2026-09-17.md` — the measured defects (17 contrast fails, C1, truncation class);
- the R19 Direction-A tokens and type (§0.1) — the shared Bali Zero language;
- the Anima Indonesiana doctrine (§0.2) — what the decorative layer may and may not do;
- **three frozen codes** with their exact rendered strings extracted from the canonical at
  `c29d6e6aea7a4fdb`: `55203` (villa — blocked in Bali, open nationally: the C1 case), `51101`
  (TERBATAS 49%, located, Lampiran III entry #31), `56101` (restaurant — TERBUKA, the
  highest-traffic question). Title, verdict triad, cap, basis citation, Bali overlay status +
  reason, per-scale licensing rows, the HEADS-UP sentence. **Byte-identical, en + id.**

### 2.3 What every coach returns (R1, sealed, one shot)

1. **Design thesis** ≤ 300 words — the one idea, named; what it refuses.
2. **Six screens as single-file HTML mockups** (inline CSS, data-URI assets, Google Fonts the
   only external host — the design corner's artifact rules), 1440×900, day; plus `detail-card`
   and `registry-table` in night. Screens = the six baseline modes, so before/after are
   comparable 1:1. The three frozen codes populate them; the content pack strings are pasted,
   never retyped.
3. **Derivability table** (R1 of `/design`): every rule the mockups follow names the input it
   is computed from (e.g. "ground L 94% from paper `#F7F4EE`", "accent area ≤ 8% from the
   one-peak budget"). A rule that cannot name its input is a fad and is struck.
4. **Anti-monotony self-report** against §2.4, measured on the coach's own mockups.
5. **Motion spec** ≤ 10 lines: which transitions exist, durations, and the `reduce-motion` fallback.

### 2.4 "Senza piattume": the anti-flatness criteria, each one measurable

Flatness has a shape and the shape can be counted. A mockup set passes only if ALL hold:

| criterion                                | measure                                                                                                                                                                                                | why it is derivable                                      |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------- |
| **One peak per viewport** (`/design` R3) | each screen names its peak element; its area ≤ 25% of the viewport; no second element within 70% of its visual weight                                                                                  | intensity is a budget                                    |
| **Composition variety**                  | ≥ 3 distinct layout families across the 6 screens (e.g. split-pane, ledger/table, dossier/editorial, conversational); **no two adjacent screens in the navigation order share the same grid template** | monotony = the same grid six times                       |
| **Type scale in use**                    | ≥ 4 distinct steps actually painted on every screen; the display step (Fraunces ≥ 48px) appears on `detail-card` and `dossier`                                                                         | a scale that exists but is not used is flat              |
| **Editorial moment**                     | exactly one per screen: a specimen number (the cap, the 1945→2045 arc), a pull-quote (the basis citation), a map/mark, or a decorated empty state — never two                                          | the Anima Indonesiana layer is a moment, not a wallpaper |
| **Accent budget**                        | copper/gold ≤ 8% of painted area per screen; the PMA triad keeps its semantic hues and is excluded from the budget                                                                                     | one accent read as "the action", not as a theme          |
| **Rhythm**                               | vertical spacing uses ≥ 3 distinct steps of one scale per screen; a page of equal plates ("wall of plates", C5 of the 06-24 review) fails                                                              | spacing is rhythm; equal spacing is none                 |
| **Contrast**                             | every (fg,bg) pair ≥ 4.5:1 day AND night; the 15 `.white` chip pairs of the diagnosis must be ≥ 4.5:1 in the proposal                                                                                  | the 2026-09-17 census is the baseline to beat            |
| **Density**                              | `registry-table` shows ≥ 12 rows at default text size without losing the verdict column; Dynamic Type at the largest size still shows ≥ 6                                                              | a navigator is a ledger first                            |
| **Content frozen**                       | the text of the 3 codes extracted from the mockup DOM == content pack, byte-identical, en + id. **Guilt control:** a mockup that changes one verdict word is rejected by the probe                     | Zero's constraint: contents untouched                    |
| **Law**                                  | no Garuda emblem, no "Indonesia Emas 2045" logo, no government lockup; padi/kapas only as a linear motif                                                                                               | UU 24/2009 Art. 57; the 2026-08-11 doctrine              |

The convener measures 1–9 with a probe (`strumenti/measure.py` for contrast/overflow/tap +
a ≤ 150-line `anti_flatness.py` that reads the mockup DOM for peak area, grid templates per
screen, painted type sizes, accent area, spacing steps, and the content byte-diff). **Read the
probe's controls before its verdict**: an innocence set (the 24 baselines must FAIL variety and
PASS content) and a guilt set (a baseline with one verdict word changed must FAIL content).

### 2.5 R2 → synthesis → build

- **R2 (one round, cross-family):** Codex GPT-5.6-sol refutes the FACTS each mockup renders
  (the three codes against the canonical) and the derivability tables — never the taste.
  Blood-bought rule from `/design` §3.1: a mechanical gate tells you a page is well-built,
  never that it is TRUE; the refuter is the only instrument aimed at truth.
- **Arena:** `arena.html` with the mockup sets as letters, `mapping.json` sealed; Zero votes.
  Zero may vote a hybrid ("A's registry, C's dossier") — the synthesis window records it.
- **Synthesis (fresh Opus 5.5, outside the contribution chain):** the pick → a SwiftUI
  implementation spec for the app repo: `Theme.swift` token changes, per-View layout changes,
  `D4Decor` moments per screen, motion. ≤ 400 lines of spec; the spec names, per View, the
  baseline PNG it changes and the snapshot command that proves it.
- **Build (Sonnet 5, app repo `~/kbli-navigator-app`, build on Pro — M5 has no Xcode):** one
  commit per View; the repo has no remote, so a commit is a complete action and the proof is
  the re-rendered 6×2×2 snapshot set under `docs/design/baseline-<date>/` plus the re-run
  `Tools/contrast/measure_contrast.py` → 0 fails. **Max 2 review rounds per View**; the third
  becomes a phase of the next loop. Both variants (`--variant internal|bkpm`) rebuilt, BKPM
  verified at 0 balizero.com links in Resources, fleet re-installed (M5, Pro, Mini when reachable),
  `deploy/check-fleet.sh` exit 0.

### 2.6 What stays with Zero (Legge 5)

1. **Palette family of the app.** ASSUMPTION in the brief: the app adopts the R19 Direction-A
   family (paper/slate/copper, Fraunces/Manrope) so the two products read as one, with the
   Anima Indonesiana gold-amber layer as the decorative register. Zero may rule the app keeps
   its own "Proposta" palette instead — then §2.4 still applies, with that palette as input.
2. **BKPM variant in scope.** ASSUMPTION: yes — same screens minus Media articles; the contest
   does not design BKPM-only surfaces.
3. **The blind vote**, and whether this mission is BLUE or ORANGE (default BLUE).

---

## 3. Sequencing

```
W0 contract ──▶ W1 guard ──▶ W2 rebase ──▶ W3 prove-live        (serial, session-owned)
A brief ──▶ R1 sealed ──▶ probes ──▶ R2 refute ──▶ arena ──▶ Zero votes ──▶ synthesis ──▶ build
```

W and A are independent and run in parallel — W touches `apps/mouth` only, A touches the app
repo only; neither writes the canonical dataset. A's build starts only after Zero's vote;
A's brief and R1 can start today.

## 4. Non-goals, stated so nobody re-opens them

- No change to any KBLI fact, verdict, cap, basis or Bali overlay — on either track. The
  content-frozen probe (§2.4 row 9) is the guard, the canonical stays untouched.
- No resurrection of `apps/kbli-navigator` (dormant) or `apps/website` (archived R19 candidate).
- No new delivery gate on the P2b benchmark (n=8) — the 2026-09-17 loop retired that.
- No fourth round on #7508's branch before W0+W1 exist.
