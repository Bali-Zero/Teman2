---
date: 2026-08-29
domain: operations
plan: beyond-sota-craft-wave
lane: "L11 — Product, UX & visual design craft"
source_report: research/operations/2026-08-28-beyond-sota-product-ux-visual-design.md (PR #5177 branch)
status: SPEC-FINAL
---

# L11 — Product, UX & visual design craft

## Mission

Cure the "verify at the surface I control, and call it the experience" belief (report §8).
Falsifying number: **0 of 6** measured 2026-08-28 production defects (dream ejection, chat false
bounce, visa-clock overstay, magic-link dead end, `/prime` Maps key, `/exclusive` ambiguity) were
caught by the existing **53 Playwright specs** across 158 routes — those run against a local build
with mocked auth and assert on elements, not on where an anonymous visitor ends up in production.
Report §2 scores 5 of 6 as mechanically catchable by a journey-grade probe. Separately, R0 counted
**six coexisting design systems**; this session verified ≥3 live palettes serving public/app
surfaces with raw hex literals, while a fully-computed WCAG token contract (Merah Putih, R4) sits
unshipped in a research doc. This lane arms the vantage-point fix (journey sentinels) and starts
the token-SSOT + critic-conformance cures, in that priority order.

## Ground to load (orchestrator first reads)

- `discovery_five_measured_defects_on_public_surfaces_2026_08_28.md` [memory, exists] — the six
  defects and their journey-catchability scoring; re-read before building anything.
- Merge commits already curing part of this list, verified this session: `d6556a75b` (auth gates
  decide on server session state, not localStorage, 14 sites, #5181), `fcf3bf7e5` (regression
  guard for that split-brain, #5189), `10ba83473` (visa-clock overstay fix, #5170) — **REPLAY the
  6 defect fixtures against CURRENT prod first** and drop already-cured classes before PR-1.
- `apps/mouth/e2e/` [exists, 53 spec files verified, subdirs incl. `smoke/`, `chat/`, `auth/`,
  `a11y/`] — `apps/mouth/e2e/production/` is **[proposed, verified absent]**, new directory.
  `apps/mouth/e2e/a11y/workspace-a11y.spec.ts` [exists] is pattern reference only.
- `apps/mouth/src/app/visa/clock/[hash]/page.tsx`, `apps/mouth/src/app/portal/magic-link/page.tsx`
  - `magic/page.tsx`, `apps/mouth/src/app/dream/` [all exist] — the journey surfaces PR-1 targets.
- `apps/mouth/src/lib/api/auth/auth.api.ts` [exists, `isAuthenticated()` defined here] — 14
  referencing files verified this session; PR #5181 already migrated the cited sites — verify
  current count before re-opening this as unfixed.
- `research/design/2026-08-27-r4-identity-merah-putih-token-spec.md` [exists] — Merah Putih token
  contract PR-2 transcribes; computed contrast ratios live here, not asserted.
- `apps/mouth/src/app/globals.css` [exists] — current copper/dark palette (`--bz-accent`), one of
  ≥3 live palettes; PR-2 does NOT touch this file (no migration in wave 2).
- `.claude/skills/bali-zero-brand/tokens.json` [exists] — IG-carousel token system, a DIFFERENT
  store from the new `apps/mouth` DTCG SSOT PR-2 creates — do not conflate them.
- `.claude/agents/wr2-critic.md` [exists] — the critic PR-3 benchmarks; `cicatrix-scars.md` W99
  entry (line 717, "6/9 slides... critic PASS") [exists, verified] — seed PR-3's corpus with it.
- `infra/guard-conformance/registry.json` + `check_guard_conformance.py` +
  `.github/workflows/guard-conformance.yml` [all exist] — guilt+innocence discipline (family #3)
  PR-3 extends to design gates; study its sentinel-pattern trigger (no top-level `paths:` filter).
- `.github/workflows/lighthouse.yml` + `apps/mouth/.lighthouserc.json` [exist] — a11y ERROR gate
  reference, not modified here. L07's spec owns the VOA anonymous-buyer journey — no duplicate.

## PR-1: feat(journeys): production journey sentinels wave 1 — dream, clock, magic-link

**Files**: `apps/mouth/e2e/production/*.spec.ts` [proposed, new dir]; `scripts/journey_sentinel.sh` [proposed]; plist under `infra/launchagents/` [proposed, `com.nuzantara.*` naming]
**Gear**: 2
**Build**:

- Before writing specs: replay all 6 defect fixtures against CURRENT prod (post-#5181/#5189/#5170)
  — drop any class already cured from this wave; keep it as a permanent regression guard anyway
  (guilt+innocence needs both states).
- Each spec runs against PRODUCTION (`playwright.prodlike.config.ts` pattern), anonymous context,
  real typing where the defect involved autosave/debounce, asserts (a) final URL, (b) zero console
  errors of named classes (`ExpiredKeyMapError`, 4xx on public XHR), (c) content truthfulness for
  state-driven pages (an overstay payload must NOT render "Valid until").
- dream: assert typing one character never lands on `login?expired=true&reason=token_expired`.
- clock: assert an overstay-date payload renders an overstay branch, never "Valid until"/"0 days".
- magic-link: assert the email-link journey reaches the funnel's first page, not a dead end.
- `scripts/journey_sentinel.sh` runs the suite on cron (Pro/Mini), routes failures through the
  existing Telegram gateway under the existing P0 budget — no new alert channel.
- Include a seeded-failure self-test route that MUST fail on demand, verified per run (family #2:
  a sentinel that greens while dead is worse than none).
  **Acceptance**: Guilt — on a scratch branch, revert the cure commits (#5181/#5189/#5170), then run
  the suite → red, naming the correct defect class. Innocence — run against current prod → suite green.
  Self-test — the seeded-failure route fails on demand every run (not just once).
  **Seats**: implementer = Sonnet 5; refuter = Kimi K3 (journey-test PR, no prod-flag surface); final gate = orchestrator (Opus 5 xhigh).
  **Arming / prove-live**: armed when the cron wrapper is loaded on its machine (`launchctl print`

* real log content, not exit 0) AND at least one real Telegram alert has been produced by the
  seeded self-test this session.
  **Conflicts / order**: does NOT include the VOA anonymous-buyer journey (L07 owns it). Must not
  re-flag any defect class PR #5181/#5189/#5170 already closed — verify via replay before building.

### PR-1 ACCEPTANCE CORRECTION (2026-08-29, Squad P) — the supplied guilt fixture is not executable

PR-1's Acceptance reads:

> Guilt — on a scratch branch, revert the cure commits (#5181/#5189/#5170), then run the suite ->
> red, naming the correct defect class.

**Executed at gate time, and it does not work.** Reverting `10ba83473`'s change to
`apps/mouth/src/app/visa/clock/[hash]/page.tsx` locally and running that sentinel gives:

```
[1/1] ... an overstay payload on /visa/clock/[hash] renders the overstay branch, never 'Valid until'
  1 passed (4.3s)
```

Green, with the cure reverted. That is **not** a defect in the sentinel. All three cures live in
`apps/mouth/src/**`, which is compiled and deployed to Vercel, and these specs drive
`https://balizero.com`. Reverting local source cannot change what production serves; satisfying
this fixture literally would mean deploying reverted code to production.

**Why the wrong fixture is worse than no fixture here:** an author who runs it and sees green has
three readings available — "the cure is still live" (true, but nothing was tested), "the sentinel
is broken" (false), "guilt passed" (false) — and nothing in the spec disambiguates them. A guilt
fixture whose green is uninformative trains its reader to stop looking.

**What a PRODUCTION sentinel's guilt fixture must be instead** (all three shipped in PR-1):

1. **Synthesize the defect at the NETWORK layer**, never in source. The visa-clock spec intercepts
   the page's two API calls with a synthetic overstay payload — #5170 was a client-side `Math.max`
   bug, so the deployed bundle that regressed is still the thing exercised.
2. **Mutate the SENTINEL and require red.** Measured: self-test neutered -> `CRITICAL
selftest-malfunction`; a spec file moved out of the directory -> exit 8 naming it; a spec skipped
   -> `[SKIPPED - never actually ran]` in `real_failures`; `baseURL` pointed at localhost -> exit 7
   refusal.
3. **Keep at least one sentinel pointed at a defect that is genuinely live**, so the suite is not
   composed entirely of things that cannot currently fail. Today that is `/prime`
   (`ExpiredKeyMapError`, needs-ruling item 1) — and it is the only one detecting anything.

The Innocence and Self-test halves of PR-1's acceptance are unaffected and were both satisfied.

## PR-2: feat(design-tokens): Merah Putih DTCG source + contrast tripwire

**Files**: `design/tokens/merah-putih.tokens.json` [proposed — no existing tokens dir at repo root
for `apps/mouth`; distinct from the brand-cortex carousel `tokens.json`]; `scripts/check_token_contrast.py` [proposed]; CI job [proposed]
**Gear**: 2
**Build**:

- Transcribe `research/design/2026-08-27-r4-identity-merah-putih-token-spec.md` §3 into DTCG
  2025.10 shape (`$value`/`$type`/`$description` = provenance: R4 ruling/ratio/PR number).
- `scripts/check_token_contrast.py` RECOMPUTES every contrast ratio the file claims (e.g.
  `border-input #7a8093` → 3.64:1) — must fail if a `$value` is edited to a failing hex.
- **NO surface migration in this PR** — `globals.css` and the raw hex in `(marketing)/page.tsx`,
  `PersonaDoors.tsx`, `layout.tsx` stay untouched; SSOT + tripwire only, migration is a later PR.
- Add a DO-NOT-EDIT-BY-HAND header anticipating a future generator (family #9 two-writers risk).
  **Acceptance**: Guilt — edit a `$value` to a hex failing its declared ratio → CI red, naming the
  token. Innocence — CI green on the spec as authored (ratios recompute within tolerance).
  **Seats**: implementer = Sonnet 5; refuter = Kimi K3 (static token file, no prod-flag surface);
  final gate = orchestrator (Opus 5 xhigh).
  **Arming / prove-live**: armed when the CI job actually runs on a PR touching the token file
  (confirm via a real PR diff, not just presence of the job definition).
  **Conflicts / order**: independent of PR-1/PR-3; must land before any future migration PR.

### PR-2 FIELD REPORT (2026-08-29, Squad P) — the tripwire's model is under-specified

PR-2 shipped as [#5240] and the SSOT half is sound. The TRIPWIRE half needs one more PR, and this
section is the missing spec detail that PR needs — written here, per the craft-wave depth-1 rule,
instead of being patched in a second correction round on the same surface.

**What two blind cross-family rounds found.** Kimi K3 found that a token could be silenced by
emptying its own claims list; that was cured with a required-claims floor over 16 duty-chosen
paths. Codex GPT-5.6 sol (xhigh, blind, no context about Kimi's round) then found SEVEN more ways
to make the script print `OK` while the identity it guards is broken. **All seven were reproduced
against the shipped token file** by the gating seat before being accepted:

| #   | escape                                                         | measured                                                                                                      |
| --- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| 1   | `"$value"` on the `color` GROUP silences the entire tree       | prints `OK — 0 claim(s) … all 16 required-claims-floor path(s) carry >=1 claim` (false in that state), exit 0 |
| 2   | `duty: "decorative"` on a `color.text.*` token skips the floor | ink at the page ground's own hex, 1.0:1 → exit 0                                                              |
| 3   | the floor comparison rounds before comparing                   | true 4.4951 published as `4.50` clears a 4.5 floor                                                            |
| 4   | claim IDENTITY is unpinned, only the count                     | delete a real pairing + duplicate another → count still 28, exit 0                                            |
| 5   | `against` accepts a frozen hex literal                         | freeze `{color.ground.carta}`, then move that ground to `#000000` → exit 0, every pairing stale               |
| 6   | a bare `NaN` ratio bypasses drift                              | `nan > tolerance` is False → exit 0                                                                           |
| 7   | `REQUIRED_CLAIM_PATHS` is a frozen list of today's names       | a NEW `color.text.*` token with no claim is invisible → exit 0                                                |

**The root cause is single and structural**: _the script validates the claims the file VOLUNTEERS,
and never derives from the token tree which claims MUST exist and what each must be measured
against._ Every row above is that sentence wearing a different hat, which is why patching them
one at a time would have been the wrong shape of fix.

**What the follow-up PR must change (this is the spec, not a wish list):**

1. **Derive the required claim set from the TREE, not from a frozen list.** Any token under a
   category that carries a WCAG duty (`color.text.*`, `color.state.state-*`, and whatever the
   duty table names next) requires at least one claim, discovered by walking — so a token added
   tomorrow is covered without anyone remembering to edit a constant.
2. **A group carrying `$value` must not terminate the walk for its descendants**, and a run that
   collects ZERO claims must be a FAILURE, never an `OK`. Zero claims is the signature of a
   silenced file, not of a clean one.
3. **`against` must be an ALIAS**, never a literal. A claim's whole purpose is to bind a
   foreground to a background TOKEN; a frozen hex severs that binding invisibly.
4. **Compare the raw ratio to the floor**, and reconcile that with the drift check's 2dp
   tolerance deliberately — the two currently disagree, and the disagreement is what lets a
   sub-threshold ratio through. WCAG does not permit rounding up to the threshold.
5. **Reject non-finite ratios at parse time** (`json.loads(..., parse_constant=)` or an
   `isfinite` gate), and reject a `duty` that is not legal for the token's category — the duty
   string is currently an unrestricted floor off-switch.
6. **Pin claim IDENTITY, not just the count** — the set of `(token, against)` pairs, so a
   deletion cannot be hidden behind a duplicate.

**Until that lands, the standing instruction is in the script's own docstring and must be honoured
by whoever wires the CI job**: do NOT promote `check_token_contrast.py` to a blocking or required
check. A gate that cannot fail is worse than no gate, because it is believed — the exact defect
class (superscar #2) the script was written to defend against. The blocking-job request in the
squad ledger (HANDOFF H3) carries the same blocker.

**What a green from the current script DOES still prove**, and why it is worth keeping meanwhile:
for a claim that is present and honestly shaped, the ratio really is recomputed from the raw hex
and really is compared to its duty's floor. Both directions were re-measured at gate time —
drifting one hex fails naming every affected claim; emptying a required token's list fails naming
the token.

## PR-3: feat(wr2): critic conformance corpus + font structural probe

**Files**: fixtures dir [proposed], runner [proposed], CI job [proposed]
**Gear**: 2
**Build**:

- Build a labeled corpus from what exists: the brand-cortex past-carousel archive, the W99 failing
  slides (6/9 system-font renders, `cicatrix-scars.md:717`), any R6 blind-panel outputs on disk —
  re-render from archived source where possible, never trust a remembered verdict as a label
  (family #6).
- The WR2 critic (`.claude/agents/wr2-critic.md`) must, in CI: (a) FAIL known-bad (W99-class)
  artifacts, (b) PASS known-good ones, (c) route font/identity checks through a structural probe
  (`document.fonts.check` or equivalent) instead of vision — vision alone cannot judge font
  identity (W99: critic PASS on system-font slides).
- **The source report supplies NO acceptance test for this PR — a recorded defect.** This spec
  supplies one below; do not ship without it passing for real.
- Wire the CI job as blocking, not `continue-on-error` (W108). Introduce it NON-required in
  branch protection — promoting to REQUIRED is an operator/Zero ruleset action, not
  self-authorized here (see Needs-ruling); the workflow-file diff for promotion is handed to
  Squad W per the battle plan.
  **Acceptance** (falsifiable, guilt+innocence, written because the report did not supply one):
  Guilt — feed the W99-class known-bad fixture to the critic in CI → must return FAIL, else red.
  Innocence — feed a known-good fixture → must return PASS, else red. Both run every invocation.
  **Seats**: implementer = Sonnet 5; refuter = Codex GPT-5.6 sol (xhigh) — this PR's acceptance test
  was authored from scratch, raising the bar for verifying fixture labels are real re-renders, not
  remembered verdicts; final gate = orchestrator (Opus 5 xhigh).
  **Arming / prove-live**: armed when the CI job is blocking (not advisory) AND both fixtures have
  actually run red/green in a real CI run this session, not local execution alone. Required-check
  promotion is a separate, later operator/Zero action and is not part of this PR's arming.

> **MEASURED 2026-08-29 by squad P — the kill criterion FIRES, and the probe mechanism this PR
> names is insufficient. Read this before attempting PR-3.**
>
> **Corpus**: `~/.claude/skills/bali-zero-brand/_carousels-by-session/` contains exactly **one**
> session (`c5a-konten-kreator-2026-05-26`): 13 PNG, 12 HTML, 9 JSON. It does carry a genuine
> good/bad pair (`_archive-parallel-pre-verify/brief-parallel-errato.json` vs
> `slides-v2-post-verify-gate.json`, alongside `CRITIC-GATE.md`/`VERIFY-GATE.md`) — but those labels
> are about CONTENT correctness, not the font-identity dimension W99 concerns. **The W99 failing
> slides are not on disk anywhere in the tree**, and no R6 blind-panel output exists. 13 < 20 and the
> available labels are for the wrong dimension, so the kill criterion applies as written.
>
> **The probe mechanism**: this PR's build step says to route font/identity checks through
> `document.fonts.check` "or equivalent". Measured against production:
>
> ```
> https://balizero.com/visa/clock
>   loaded FontFace families: inter, inter Fallback, cormorant, cormorant Fallback,
>                             montserrat, montserrat Fallback
>   document.fonts.check(): Montserrat=true Inter=true "Cormorant Garamond"=true "IBM Plex Mono"=true
> ```
>
> **`IBM Plex Mono` answers `true` while being absent from the loaded set entirely.**
> `document.fonts.check()` answers "can this family be used?" — a system or fallback resolution
> satisfies it. It does NOT prove a webfont loaded, so a W99 cure built on it would pass on exactly
> the system-font renders W99 is about: the defect's own shape, one level up.
>
> A sound probe must instead (a) enumerate the `FontFace` set and require each brand family with
> `status === "loaded"`, and (b) assert the COMPUTED `font-family` of a rendered element resolves to
> the brand face. Never `check()` alone.
>
> **Also note** the fold-in target is not buildable until PR-1 merges: `playwright.production.config.ts`
> arrives with it, so a branch cut from `main` has no harness to fold into.

**Conflicts / order**: if the corpus can't reach 20 labeled artifacts (report's kill criterion),
fold this PR's scope into PR-1's sentinel probes instead of an under-powered conformance job.

## Needs-ruling carried (Zero only — this spec does NOT decide these)

1. **`/prime` Google Maps key expired** — `operator[GUI]`, Google console; the map IS the page's
   product, no code path fixes a credential.
2. **`/dream` public or gated?** — the #5181/#5189 cure removed the ejection bug, not the
   ambiguity of whether the page should require auth at all.
3. **`/exclusive` two-line body + streaming video** — intended minimalism or unfinished? Unowned;
   PR-1 treats this as PARTIAL/not-sentinel-worthy until ruled.
4. **Adopting Merah Putih as the production identity** — PR-2 ships the token SSOT as a
   research-backed artifact, but shipping it AS the production identity (vs. team-controlled
   default per R6) is a business decision (report's adversarial review, objection #2, accepted).
5. **VOA dark-state page**: is a bare 404 body the right dark state for the flagship product page
   if anything external links it? Already flagged to Zero in the 5-defects memory.
6. **`/visa/match` investor >500M → E33G ("remote worker") domain misroute** — owner Zero per
   `MEMORY_VISA_ORACLE.md:87`; carried per report §7, not in this lane's 3 PRs.
7. **Experimentation infra (GrowthBook + CUPED) and any A/B on real prospective clients** — needs
   consent-copy ruling (Law 2); wave 3 in the report, carried for completeness only.
8. **PR-3's required-check promotion** — an operator/Zero ruleset action, not self-authorized by
   this PR; PR-3 ships the job blocking-but-non-required, the promotion diff goes to Squad W.

## Suspend & ledger rules

- Rule 8: a PR red for the SAME cause three times (gate/lint/refuter, same surface) gets no
  fourth round — SUSPEND with one PENDING-ARMS line naming the cause, branch left alive, move on.
- Fix-of-a-fix stops at depth 1: a wrong correction means the surface is under-specified — write
  the spec or escalate to Needs-ruling, never open a third corrective PR.
- Every built-not-armed step gets one PENDING-ARMS row (e.g. "PR-1 merged, cron not installed on
  Pro/Mini"), closed only when `launchctl print` + real log/Telegram content confirm the arm.
- PR-3 has no report-supplied acceptance test; if this spec's supplied test cannot be made to pass
  for real, PR-3 SUSPENDS rather than ship an unfalsifiable gate.

## Out of scope

- The VOA anonymous-buyer journey and its dead-man — owned entirely by L07, do not duplicate.
- Migrating `globals.css` or marketing-page raw hex onto the new token SSOT — PR-2 is SSOT +
  tripwire only; migration is a separate future PR.
- GrowthBook/CUPED experimentation infra (report R5) — wave 3, needs-ruling item 7, not this lane.
- The journey-gate for NEW public routes (report R6) — separate PR, not one of this lane's 3.
- Fixing `/prime`'s Maps key, ruling `/dream`'s public/gated status, or `/exclusive`'s content —
  `operator[GUI]` or Zero rulings, not session-executable.

---

## Spec-back (2026-08-29, Squad P) — the sentinel's output cannot tell you whether two failures on one journey are one condition or two

**This section began as a claimed defect in the alert fingerprinting. That claim was REFUTED before
merge, and it is kept here as the finding — because the trap it describes is one a future reader of
this organ's log will fall into exactly as I did.**

### The retracted claim, stated so nobody re-derives it

`/prime` failed with two different messages across runs — `GOOGLE MAPS KEY DEFECT
(ExpiredKeyMapError)` and `window.google.maps never loaded — the Maps SDK script itself failed
(404 / CSP / DNS)` — producing two different fingerprints (`b28513a7`, `0753d92d`) and therefore two
Telegram dedup keys. I read that as ONE defect surfacing through whichever assertion tripped first,
and concluded the fingerprinting defeated its own dedup.

**Wrong, and the file that settles it is `apps/mouth/e2e/production/prime-maps.spec.ts` itself**,
whose header records the empirical measurement:

> Google's JS bootstrap loads and defines `window.google.maps` **regardless of key validity**; key
> validation happens against the backend … So these three checks alone do NOT discriminate today's
> defect from a healthy map — they are useful for a DIFFERENT class of break (404 / blocked script /
> DNS failure / CSP — cases where the SDK never loads at all)

Under the expired key the SDK **does** load. A run where it never loaded is therefore a DIFFERENT
condition, not the same one in disguise — so two fingerprints is **correct behaviour**, and the
alert log confirms it worked: `0753d92d` paged once as a new condition while `b28513a7` followed its
own dedup ladder normally.

### The evidence that settles it, and the mechanism that produces the flutter

Two measurements a second refuter (Kimi K3) asked for and I then took myself, both decisive:

1. **In the `00:19` run — the only genuine cron occurrence of the `never loaded` presentation — the
   string `ExpiredKeyMapError` appears NOWHERE.** The bootstrap did not execute at all. Under the
   expired key it does execute and logs that error, so this is a different condition co-occurring
   with the known credential defect, not the credential defect in disguise. (That run also took
   58.3s against ~27s typical — consistent with a slow or failed fetch of the SDK.)
2. **The fingerprint is taken from the RETRY, never the first attempt.** `spec_error_summary()`
   iterates `for r in reversed(t.get("results") or [])`, and the production Playwright config sets
   `retries: 1`. So with two attempts, the dedup identity is decided by the second — the flakiest
   single observation available. At `22:54` attempt 1 showed the key error and the retry showed
   `never loaded`, in the same minute: that proves the OBSERVATION is non-deterministic, and the
   `reversed()` choice makes the dedup key inherit that non-determinism wholesale.

And the alerting behaved correctly throughout, which is the strongest argument that there is no bug
here to fix: reading the log's own `tg[p0 …]` lines, across those runs exactly **one** fresh page
occurred (`00:19`, a new key on first appearance); `22:57` and `01:20` flip-backs were `deduped` by
the dominant key's own window, and `22:54` never alerted at all because that run exited at the
missing-spec-file branch — it was one of my mutation runs.

**Requirement this replaces the retracted one with**: before anyone changes the fingerprinting,
_determine cause identity first_ — and the means is already in the log: check whether the
`never loaded` runs contain the key error string. They do not. Any future proposal to merge two
presentations into one dedup identity must clear that bar first, or it will re-mute a genuine
404 / CSP / DNS event, which is the bug the fingerprint was added to prevent.

### Two things a future reader should take from that, and they are the real spec content

1. **The log alone cannot answer "same condition or different?"** Nothing in the heartbeat, the
   alert, or the verdict JSON carries the fact that settles it. The answer lived in a source
   comment. **Read the detector's own documentation before reasoning about what its output means** —
   for this spec that means the header block, which explicitly states which checks discriminate
   which fault class and which do not.
2. **Your own runs are in the log.** Of 12 verdicts, only **3** were production cron ticks
   (`launchctl … runs = 3`, spaced ~1h); the other nine were hand-runs and mutation fixtures from
   development sessions, and one carried `missing_files: ["dream.spec.ts"]` — an exit-8 guilt
   fixture. Any RATE computed over that log is arithmetic over a polluted denominator. The tells are
   `missing_files` and second-level clustering. A **universal** claim ("never leaked") survives this;
   a **rate** claim does not.

### What IS a real defect, measured and unrefuted: the heartbeat note reads as its own opposite

The published note quotes the failing Playwright test's TITLE, and titles are conventionally phrased
as the DESIRED property. A RED organ therefore publishes, verbatim:

```
1 real journey failure(s): ;/prime Google Maps key is valid (currently RED     see file header, ...)
```

Three separate problems, and only `status=degraded` keeps the organ honest:

- the note leads with a string asserting the thing that is false;
- the `error_summary` that would state the failure plainly **already exists and is used in the
  Telegram alert**, and the heartbeat discards it;
- a separator (`;`) is used as a prefix.

A narrower correction, since an earlier draft of this section over-claimed it: the author DID
anticipate the first problem and appended `(currently RED — see file header)` to the title, and
`scripts/lib/heartbeat.sh` byte-strips non-ASCII to spaces (deliberately — provably-valid JSON in
any locale, its own comment declares the cost), so the em dash becomes whitespace. **The mitigating
WORDS survive**; only the visual break is lost. The mitigation is damaged, not destroyed — but a
note that needs a parenthetical to stop it meaning the opposite is still the wrong shape.

**Requirement**: the note must state a FAILURE unambiguously even when every title is phrased as the
desired property, carry the `error_summary` the alert already has, separate rather than prefix, stay
ASCII, and degrade legibly when several failures must share the budget.

**Blocker for any change here**: `scripts/journey_sentinel.sh` has **no shell corpus at all** —
verified, its only test is the Playwright self-test spec, which tests detection rather than the
wrapper. A change to it is untestable by construction until one exists, so a fix must bring the
first one, including a scar-pin that goes red if the fix is reverted.

### The general rule, worth carrying past this lane

A machine-readable signal must never be phrased so that a human skimming it reads the opposite of
its own status field, and must not rely on a non-ASCII character to carry meaning through a writer
that is contractually ASCII-only.
