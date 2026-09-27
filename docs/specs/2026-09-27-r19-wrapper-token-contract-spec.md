# R19 paper wrapper — token contract for the funnel waves (R1-R6)

Status: PROPOSED 2026-09-27. Spec only, no code in this PR. Consumers: the v2 wrapper lane, then the four
wave rebases (kbli, oracle, studio, voa) that share the local "R19 Direction A" foundation `8cb6914f80`.

Why: PR #7508 (kbli, first wave) took three REWORK rounds on ONE cause and was suspended under Builder
Contract §1 ("three reds for the SAME cause … write the spec"). The paper wrapper (`.r19-direction-a` +
`.kbli-paper`, inline `R19_DIRECTION_A_VARS` spreading main's `R19_VARS` from
`apps/mouth/src/components/r19/presentation.ts`) re-themes a dark-default app only partially. Each round
cured one instance and the next gate found the next one:

| Round | Head         | Finding (`gate-7508.md`)                             | Mechanism                                                                           |
| ----- | ------------ | ---------------------------------------------------- | ----------------------------------------------------------------------------------- |
| 1     | `c7b1088309` | B1 menu toggle white on paper, 1.10:1                | `MobileNav` branches on `useR19()`, false under the wrapper; painted `#ffffff`      |
| 2     | `0e1f773419` | B3 `--foreground` dropped: 19 new texts at 1.08-1.15 | read under the wrapper, not declared on it: keeps the `:root` dark `#ececec`        |
| 3     | `94b588cda1` | B4 TrustBand labels 1.07:1, footer tagline 1.21:1    | `--color-text-secondary` resolved at `:root`; `.brand-tagline` is `#fff` in globals |

One CSS fact explains all three. A custom property inherits its COMPUTED value, and a `var()` inside a
custom property resolves on the element that declares it. mouth declares dark values and dark-resolving
aliases at `:root` (`packages/core/tokens/semantic.css`, `apps/mouth/src/app/globals.css`, and Tailwind v4
`@theme` in `packages/core/tailwind/theme.css`, emitted at `:root`). A token the wrapper does not re-declare
keeps what `:root` computed. The round-3 guard could not see this: it scanned only `app/kbli/**`,
`components/kbli/**` and `MobileNav.tsx`, exempted `--kbli-*` by prefix, and skipped CSS, `packages/core`
and global classes.

## Definitions

- **Wave W**: one funnel conversion. **Wrapper**: the ONE element of W carrying the paper var map inline
  plus its scope classes (`r19-direction-a`, and a wave layer such as `kbli-paper`).
- **SURFACE(W)**: every non-test `.ts/.tsx/.css` file reachable from W's route directory through static
  imports, literal `import()` and CSS `@import`, resolving `@/`, relative paths, and `@balizero/core` named
  exports through the `packages/core/index.ts` barrel. Plus every global class rule (`globals.css` and its
  `@import`s) whose classes all appear in a string literal in SURFACE(W).
- **READS(W)**: every `var(--x)` in SURFACE(W) outside `:root`/`html`/`:host`/`@theme` rules, plus
  `--color-<name>` for every Tailwind utility (`text-`, `bg-`, `border-`, `ring-` …) whose `--color-<name>`
  is declared at `:root`/`@theme`. `var(--b)` used only as the fallback of a `var(--a, …)` with `--a`
  wrapper-defined is not a read.
- **WRAPPER_DEFINED(W)**: keys of the inline map (following `...spread`s) plus custom properties declared
  in a rule whose selector is exactly one wrapper class. `:root`, `@theme`, ancestors, descendants and
  `var()` fallbacks do not count.

## R1 — the wrapper token contract

- **R1.1 Closed set.** CONTRACT(W) = READS(W) − NON_COLOUR − INVARIANTS(W), and CONTRACT(W) ⊆
  WRAPPER_DEFINED(W). NON_COLOUR is one exact name regex (`--space-*`, `--font*`, `--text-(xs|sm|base|lg|Nxl)`,
  `--leading-*`, `--tracking-*`, `--radius*`, `--r19-radius-*`, `--public-header-height`, `--z-*`,
  `--duration-*`, `--ease-*`, `--tw-*`) and SHALL match no colour token. No prefix exemption: `--kbli-*`
  passes because `.kbli-paper` declares it on the wrapper, not because of its name.
- **R1.2 Invariants.** A colour token MAY stay off the wrapper only if the wave's INVARIANTS list names it
  with a reason, it is declared at `:root` as a literal, and no theme, attribute or class rule re-declares
  it. kbli needs three: `--accent-whatsapp-ink` (`semantic.css`), `--color-green-50`, `--color-green-500`
  (`primitives.css`). An entry failing any condition is itself a violation.
- **R1.3 Literal vs `var()`.** On the wrapper, a value equal to an `R19_VARS` value SHALL be
  `var(--that-key)`. A literal is allowed only when no `R19_VARS` key carries the value (hover `#843719`,
  `--r19-control-border`, the `--kbli-*` risk and PMA hues). A `var()` declared ON the wrapper resolves
  against the wrapper's own values; the alias trap exists only for aliases declared at `:root` or on an
  ancestor, so the `r19Vars.ts` comment calling `--foreground: var(--text-primary)` a trap SHALL be
  corrected. The rule binds the wave layer too.
  - Guilt at `94b588cda1`: `.kbli-paper` declares 60 literals. 22 equal an `R19_VARS` value, and six keep
    the pre-unification values B2 removed only from `r19Vars.ts`: `#58626b` ×4 (`--foreground-secondary`,
    `--foreground-muted`, `--kbli-text-secondary`, `--kbli-text-muted`) and `#a8aca9` ×2
    (`--border-hover`, `--kbli-border-hover`), where main has `#435464` and `#a7a69f`.
  - Innocence: the same block with those literals written as `var(--<R19 key>)` reports 0.
- **R1.4 Portals.** Custom properties inherit through the DOM, not the React tree. Portal content opened
  from SURFACE(W) (Radix `Dialog.Portal`, `createPortal`) SHALL carry the wrapper on its own root, as main
  does for its drawer. At `94b588cda1` the kbli sector offcanvas does. The `MobileNav` drawer opens dark,
  as on production today (not a census failure); v2 themes it or lists it as a named exception.
- **R1.5 Descendant re-scope.** A rule outside the wrapper that re-declares a contract token on a
  descendant SHALL be neutralised by a wrapper-scoped rule written in `var()`. `[data-funnel="kbli"]` in
  `semantic.css` sets `--accent-funnel: #eab308` and `--text-on-accent: #1a1208`. The existing neutraliser
  `.kbli-paper [data-funnel="kbli"]` restates `#a44b36`/`#ffffff`; per R1.3 these become
  `var(--r19-copper)` and `var(--r19-cta-ink)`.

## R2 — main's R19 global class rules are reached, never copied

- **R2.1** Every class X with a rule `.root :global(.X …)` in
  `apps/mouth/src/components/r19/R19Presentation.module.css` that appears in SURFACE(W) SHALL be styled
  under the wrapper by THAT module. Recommended: each such selector gains a second scope
  (`.root :global(.X), .chrome :global(.X)`), `presentation.ts` exports the hashed class as
  `R19_CHROME_CLASS`, and the wrapper applies it. Alternative: the wrapper applies the module's `.root`,
  which also brings main's editorial layout and `font-synthesis-weight: none` on h1-h3, so it needs its
  own visual check. `<R19Presentation>` does NOT work: `isR19Route("/kbli")` is false. Copying the
  declarations into a funnel stylesheet is forbidden.
  - Guilt at `94b588cda1`: `.brand-tagline` (v2 `Footer`) is unreached, which is B4's tagline.
  - Innocence: a wrapper importing `R19_CHROME_CLASS` reports 0.
- **R2.2** A component in SURFACE(W) branching on `useR19()` renders its NON-R19 branch under the wrapper.
  That branch SHALL paint only contract tokens, with a literal allowed only as a `var()` fallback (the B1
  cure's `--nav-icon-*`). `MobileNav` is the only such file in kbli's surface.

## R3 — the guard runs over the real rendered surface

- **R3.1** The v2 lane SHALL ship a vitest guard in `apps/mouth` computing SURFACE, READS and
  WRAPPER_DEFINED as defined above for every wave in one table. It fails on any CONTRACT member outside
  WRAPPER_DEFINED (R1.1), any bad invariant (R1.2), any wrapper literal equal to an `R19_VARS` value
  (R1.3), and any unreached R2.1 class. The reference probe at the end of this file is normative: when the
  vitest and the probe disagree on a tree, the probe holds until this spec is amended.
- **R3.2 Guilt**, measured with the probe on 2026-09-27:
  - `94b588cda1` reports `--color-text-secondary` and `--surface-subtle`, the two B4 tokens, both first
    read by `packages/core/components/TrustBand.tsx`. It also reports the latent `--error` (destructive
    variant of `components/ui/button.tsx`, reached through kbli's `error.tsx` pages), `.brand-tagline` and
    22 copied literals, and exits 1.
  - `0e1f773419` additionally reports `--foreground`, which is B3.
  - Deleting `--nav-icon-color` from a cured tree reports it, which is B1's token.
- **R3.3 Innocence.** A cured copy of `94b588cda1` exits 0: it adds `--color-text-secondary`,
  `--surface-subtle` and `--error` to the map, imports `R19_CHROME_CLASS` and rewrites the 22 literals. On
  the head the non-colour exemptions are exactly `--font-size-2xl`, `--public-header-height` and
  `--space-3/4/6`. Among the `R19_VARS` keys NON_COLOUR matches only `--font-sans` and `--font-serif`, and
  it matches no `--foreground*`, `--color-*`, `--surface-*`, `--bz-*`, `--nav-*` or
  `--text-(primary|secondary|on-accent)` name; the vitest SHALL pin that.
- **R3.4 Limits.** R3 sees token reads, not literal colours. B1's original `#ffffff` would have passed it,
  as would Tailwind palette utilities (`text-white`) and class names built at runtime. R4 owns those. A
  green R3 is necessary, not sufficient.

Run the probe from this file. After R6 the `--wrapper` is the single helper for every wave:

````bash
awk '/^```python r19-wrapper-probe$/{f=1;next} /^```$/{f=0} f' \
  docs/specs/2026-09-27-r19-wrapper-token-contract-spec.md > /tmp/r19_wrapper_probe.py
python3 /tmp/r19_wrapper_probe.py --root <tree> --route apps/mouth/src/app/kbli \
  --wrapper apps/mouth/src/app/kbli/layout.tsx --wrapper-class r19-direction-a --wrapper-class kbli-paper \
  --invariant=--accent-whatsapp-ink --invariant=--color-green-50 --invariant=--color-green-500
````

| Wave   | `--route` under `apps/mouth/src/app/` | Wrapper today (wave branch)   | Wrapper classes                                   |
| ------ | ------------------------------------- | ----------------------------- | ------------------------------------------------- |
| kbli   | `kbli`                                | `kbli/layout.tsx`             | `r19-direction-a`, `kbli-paper`                   |
| oracle | `(visa-oracle)/visa-oracle`           | `_components/OracleShell.tsx` | `r19-direction-a`, `oracle-root`                  |
| studio | `visa/second-home/studio`             | `StudioApp.tsx`               | `r19-direction-a`, `bz-shs-studio`, `bz-shs-room` |
| voa    | `visa/voa`                            | `visa/voa/layout.tsx`         | `r19-direction-a`                                 |

## R4 — contrast census is the acceptance

- **R4.1 Routes**, at 1440 and 390 px, on the candidate and on `https://balizero.com` as reference.
  kbli: `/kbli`, `/kbli/56101`, `/kbli/47111`, `/kbli/68111`, `/kbli/sectors`, `/kbli/sectors/I`,
  `/kbli/builder`, `/kbli/decoder`, and the sector panel opened from `/kbli`. oracle: `/visa-oracle`,
  `/visa-oracle/privacy`, `/visa-oracle/unlock`. studio: `/visa/second-home/studio`. voa: `/visa/voa`,
  `/visa/voa/auth/continue`, `/visa/voa/<hash>`, `/visa/voa/checkout/<resultId>`,
  `/visa/voa/upload/<resultId>`, `/visa/voa/orders/<orderId>` and its `/return`. Dynamic ids SHALL be
  synthetic (not-found/expired state or a shipped fixture), never a real client's (Builder Contract §4).
- **R4.2 Method.** Visible text = elements with a non-empty direct text node, a non-empty client rect, and
  no `visibility: hidden` or zero effective opacity. Every computed colour (`oklch()`, `lab()`,
  `color-mix()` included) is normalised to sRGB by painting it on a 1×1 canvas and reading the pixel. Text
  alpha is composited over the effective background, found by compositing ancestor `background-color`s
  until opaque; a `background-image` on that walk moves the element to a reported, uncounted
  "image-backed" list. Thresholds: WCAG 2.x AA 4.5:1, or 3:1 for text ≥24 px or ≥18.66 px bold; named
  non-text controls (the menu toggle) ≥3:1 (SC 1.4.11).
- **R4.3 Method innocence, first, every session.** Rounds 1-2 parsed `oklch(...)` backgrounds as rgb
  numbers, invented "PMA unverified 1.43" and filed the real B4 as "pre-existing". The census SHALL start
  with a self-test: `oklch(0.984 0.003 247.858)` → `[248,250,252]`; `rgba(255,255,255,.68)` over
  `#F7F4EE` → ≈1.07:1; a planted `<span style="color:oklch(1 0 0)">` on paper counted as a failure, then
  removed. A census whose self-test fails reports nothing.
- **R4.4 Acceptance.** new_failures(W) = elements below AA on the candidate whose text key (tag + trimmed
  text) is not below AA on the reference, over all routes and viewports. It SHALL be 0. Remaining
  failures are listed as pre-existing on production, with both ratios.

## R5 — evidence and `Bites:` for a wave PR

- **R5.1** Pack and body carry, at the FINAL head: the probe's summary line with exit 0, the R4 self-test
  result, and new_failures = 0 per route × viewport. If the head's own preview was CANCELED by the Ignored
  Build Step (evidence-only commit), the census runs on the latest READY deployment whose `apps/` and
  `packages/` tree hashes equal the head's, and the pack says so.
- **R5.2** `Bites:` consumer = visitors of W's funnel routes. The observation is post-promote, because
  mouth merges land staged and go live only on `vercel promote`: the R4 census on
  `https://balizero.com/<W routes>` at 1440 and 390 px reports new_failures = 0 against the production
  baseline captured BEFORE promote in the same session, naming the three rounds' elements (menu toggle
  ≥3:1, Licensing overview row, TrustBand labels, footer tagline) or W's equivalents. A pre-merge test
  count is supporting evidence, never the observation.

## R6 — one wrapper implementation, one rebase order

- **R6.1 One implementation.** After the v2 lane, a single helper under `apps/mouth/src/lib/theme/`
  applies the paper wrapper (classes + map) for route wrappers and portals (R1.4); besides the map's own
  module it is the only non-test file referencing the map. At `94b588cda1` there are two application
  sites (`kbli/layout.tsx`, `KBLISectorOffcanvas.tsx`). Studio restates a map key inline
  (`--border-strong`, `StudioApp.tsx:772`) and reads map values at import time into a
  `body:has(.bz-shs-room)` rule (`:147-148`), which would inject a `var()` outside the wrapper once an
  aliased key is read. Both are per-wave copies and forbidden.
- **R6.2 Drop, do not rebase, the foundation.** oracle, studio and voa still carry `lib/theme/`
  byte-identical to `8cb6914f80` (pre-unification values, `r19Fonts.ts`, `lib/theme/fonts/`). Each rebase
  starts from a fresh `origin/main` and cherry-picks only the wave's own commits.
- **R6.3 Order, serialized.** (1) this spec; (2) the v2 wrapper lane: unified map, helper,
  `R19_CHROME_CLASS`, the R3 vitest with the wave table, no route converted; (3) kbli, superseding #7508,
  which closes unmerged; (4) oracle; (5) studio; (6) voa. A wave opens only after the previous one is
  merged AND promoted, since R4's reference is production. Reordering 4-6 is the lead's call; parallel
  is not allowed, because every wave edits the guard's wave table.

## D-notes — out of scope, and why

- **D1 Font weight synthesis.** Main's `-latin` subsets are static (Fraunces 500, Manrope 400), so 600-750
  are synthesized: the gate counted 87 elements on `/kbli` and 79 on production `/news`. It is #7448's
  font decision on main's editorial routes, needs new binaries, and has no contrast effect. The inert
  SOFT/WONK `font-variation-settings` in `r19-direction-a.css` may go in v2; it is not a contract rule.
- **D2 `-latin` vs variable `-home` subsets** is a bytes-versus-weights trade-off on main; this contract is
  about colour tokens.
- **D3 `--font-size-2xl`** is undefined everywhere (primitives define `--text-2xl`); TrustBand already
  falls back on production. Non-colour, and it belongs to `packages/core`.
- **D4 The name "Direction A"** collides with main's "R19" in name only; the values are unified.

## Acceptance, by command

| Rule  | Command                                                                       | Required at a wave head             |
| ----- | ----------------------------------------------------------------------------- | ----------------------------------- |
| R1-R3 | the probe with the wave's row                                                 | exit 0, all four counts 0           |
| R4    | census self-test, then candidate and production census                        | self-test PASS, new_failures 0      |
| R5    | the PR body's `Bites:` line                                                   | post-promote census, named elements |
| R6.1  | `git grep -l <map name> -- apps/mouth/src ':!*.test.*'`                       | the map module and the helper only  |
| R6.2  | `git ls-tree -r --name-only HEAD apps/mouth/src/lib/theme` filtered for fonts | no `r19Fonts.ts`, no `fonts/`       |

## Reference probe (normative for R3)

```python r19-wrapper-probe
import argparse, pathlib, re, sys
ap = argparse.ArgumentParser()
ap.add_argument("--root", required=True)
ap.add_argument("--route", required=True)
ap.add_argument("--wrapper", required=True)
ap.add_argument("--wrapper-class", action="append", required=True)
ap.add_argument("--invariant", action="append", default=[])
a = ap.parse_args()
R = pathlib.Path(a.root).resolve(); SRC = R / "apps/mouth/src"; CORE = R / "packages/core"
NONCOLOUR = re.compile(r"^--(space|font|text-(xs|sm|base|lg|\d*xl)$|leading|tracking|radius|r19-radius|public-header-height|z-|duration|ease|tw-)")
TW = r"(?<![\w-])(?:[\w-]+:)*(?:text|bg|border(?:-[trblxy])?|ring|fill|stroke|from|via|to|outline|decoration|divide|placeholder|caret|accent)-({})(?:/[\d.]+)?(?![\w-])"
ROOTSEL = {":root", "html", ":host", "@theme", "@theme inline"}
def rd(p): return re.sub(r"/\*[\s\S]*?\*/", "", p.read_text(encoding="utf-8"))
def rules(css):
    out, stack, buf = [], [["", ""]], ""
    for ch in css:
        if ch == "{":
            head, _, sel = buf.rpartition(";"); stack[-1][1] += head + ";"; stack.append([sel.strip(), ""]); buf = ""
        elif ch == "}" and len(stack) > 1:
            sel, body = stack.pop(); out.append(({x.strip() for x in sel.split(",")}, body + buf)); buf = ""
        else: buf += ch
    return out
def isroot(sels): return bool(sels) and sels <= ROOTSEL
def decls(body): return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+)", body))
def res(spec, frm):
    if spec.startswith("@/"): b = SRC / spec[2:]
    elif spec.startswith("@balizero/core/"): b = CORE / spec[15:]
    elif spec.startswith("."): b = frm.parent / spec
    else: return None
    for e in ("", ".tsx", ".ts", ".css", "/index.tsx", "/index.ts"):
        if (p := pathlib.Path(str(b) + e)).is_file(): return p.resolve()
IMP = re.compile(r"(?:import|export)\s+(type\s+)?(?:([\w*{}\s,]+?)\s+from\s+)?[\"']([^\"']+)[\"']|import\(\s*[\"']([^\"']+)[\"']|@import\s+(?:url\()?[\"']([^\"']+)[\"']")
def closure(todo, barrel):
    seen = set()
    while todo:
        f = todo.pop()
        if f in seen or ".test." in f.name: continue
        seen.add(f)
        for tonly, names, spec, dyn, cssi in IMP.findall(rd(f)):
            spec = spec or dyn or cssi
            if tonly: continue
            if spec == "@balizero/core":
                todo += [barrel[n] for n in (x.strip().split(" as ")[0] for x in re.sub(r"[{}]", "", names).split(",")) if n in barrel]
            elif (p := res(spec, f)): todo.append(p)
    return seen
barrel = {n.strip().split(" as ")[-1]: res(s, CORE / "index.ts") for ns, s in re.findall(r"export\s*\{([^}]*)\}\s*from\s*[\"']([^\"']+)", rd(CORE / "index.ts")) for n in ns.split(",") if n.strip() and not n.strip().startswith("type ")}
seen = closure([p.resolve() for p in (R / a.route).rglob("*") if p.suffix in (".ts", ".tsx", ".css")], barrel)
GLOBAL = closure([SRC / "app/globals.css"], {})
wf = (R / a.wrapper).resolve(); wsrc = rd(wf)
def objkeys(name, frm):
    for f in [frm] + [p for s in re.findall(r"from\s+[\"']([^\"']+)", rd(frm)) if (p := res(s, frm))]:
        if (m := re.search(r"export const " + name + r"\s*=\s*\{([\s\S]*?)\n\}", rd(f))):
            ks = set(re.findall(r"\"(--[\w-]+)\"\s*:", m.group(1)))
            for sp in re.findall(r"\.\.\.(\w+)", m.group(1)): ks |= objkeys(sp, f)
            return ks
    return set()
m = re.search(r"style=\{(\w+)\}", wsrc) or sys.exit("R3-NO-WRAPPER-MAP: --wrapper applies no style={IDENT}")
D = objkeys(m.group(1), wf)
wsel = {"." + c for c in a.wrapper_class}
tsx = "\n".join(rd(f) for f in seen if f.suffix != ".css")
used = lambda c: re.search(r"[\"'`][^\"'`]*(?<![\w-])" + re.escape(c) + r"(?![\w-])", tsx)
R19HEX = {v.lower() for v in re.findall(r"\"(#[0-9A-Fa-f]{6})\"", rd(SRC / "components/r19/presentation.ts"))}
ROOT, LOCAL, THEMED, extra, COPIED = {}, set(), set(), [], set()
for f in GLOBAL | {s for s in seen if s.suffix == ".css"}:
    for sels, body in rules(rd(f)):
        if sels & wsel:
            D |= set(decls(body)); COPIED |= {(k, v.strip()) for k, v in decls(body).items() if v.strip().lower() in R19HEX}
        elif isroot(sels): ROOT.update(decls(body))
        else:
            (LOCAL if f in seen else THEMED).update(decls(body))
            if f in GLOBAL and f not in seen and all(used(c) for s in sels for c in re.findall(r"\.([\w-]+)", s)) and any(re.findall(r"\.([\w-]+)", s) for s in sels): extra.append((f, body))
for f in seen:
    if f.suffix != ".css": LOCAL |= set(re.findall(r"[\"'](--[\w-]+)[\"']\s*:", rd(f)))
twre = re.compile(TW.format("|".join(map(re.escape, sorted((k[8:] for k in ROOT if k.startswith("--color-")), key=len, reverse=True)))))
reads = {}
for f, src in [(f, rd(f)) for f in sorted(seen)] + extra:
    if f.suffix == ".css" and f in seen: src = "".join(b for s, b in rules(src) if not isroot(s))
    cond = {i for o, i in re.findall(r"var\(\s*(--[\w-]+)\s*,\s*var\(\s*(--[\w-]+)", src) if o in D}
    got = (set(re.findall(r"var\(\s*(--[\w-]+)", src)) - cond) | ({"--color-" + m for m in twre.findall(src)} if f.suffix != ".css" else set())
    for t in got: reads.setdefault(t, f.relative_to(R))
bad_inv = [t for t in a.invariant if t not in ROOT or "var(" in ROOT[t] or t in THEMED or t in D]
U = {t: f for t, f in reads.items() if t not in D and not NONCOLOUR.match(t) and t not in a.invariant and not (t in LOCAL and t not in ROOT and t not in THEMED)}
G = set(re.findall(r"\.root\s+:global\(\.([\w-]+)", rd(SRC / "components/r19/R19Presentation.module.css")))
V2 = [] if re.search(r"R19Presentation\.module\.css|R19_CHROME_CLASS", wsrc) else sorted(c for c in G if used(c))
print(f"surface_files={len(seen)} global_class_rules={len(extra)} wrapper_defined={len(D)} reads={len(reads)}")
for t in sorted(U): print(f"R3-UNDEFINED {t} root_default={'yes' if t in ROOT else 'no'} first_reader={U[t]}")
for c in V2: print(f"R2-UNREACHED .{c}")
for t in bad_inv: print(f"R3-BAD-INVARIANT {t}")
for k, v in sorted(COPIED): print(f"R1.3-COPIED-LITERAL {k}: {v}")
print(f"undefined_colour_tokens={len(U)} unreached_r19_class_rules={len(V2)} bad_invariants={len(bad_inv)} copied_literals={len(COPIED)}")
raise SystemExit(1 if U or V2 or bad_inv or COPIED else 0)
```
