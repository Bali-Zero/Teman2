---
date: 2026-08-24
domain: operations
client_case: none
sources:
  - apps/admin-dashboard-local/lib/garuda-preview-adapter.ts (read in full this session)
  - apps/backend-rag/backend/services/garuda_flow/intake.py, nationality_eligibility.py, internal_preview_cli.py (read this session)
  - apps/backend-rag/backend/tests/services/garuda_flow/test_preview_adapter_parity.py (read + executed this session)
  - apps/admin-dashboard-local/__tests__/garuda-preview-process-integration.test.ts (read + executed this session)
  - apps/mouth/src/app/visa/voa/route.ts (read this session)
  - .github/workflows/tests.yml lines 1580-1755 (read this session)
  - gh pr view / gh pr diff on #4784, #4787, #4796, #4802 (GitHub API, this session)
  - live pytest run of the RC 0→1→0 desync proof, in a scratch worktree of #4802's branch (this session)
  - live vitest run of the full admin-dashboard-local suite (this session)
  - live pytest run of the full garuda_flow + garuda_voa Python suite (this session)
---

# GARUDA VOA — the defects were in the joint

> S14 set out to bring the GARUDA VOA engine to production-complete. Four defects were fixed.
> Two of the four were never in the engine — they were in the JOINT between the engine and its
> only consumer, and a fully green Python suite (202 tests, RC 0, verified live this session)
> could not see either one, because the contract's other half is TypeScript in an app the CI
> matrix does not run. They surfaced because someone walked the consumer-map by hand before
> arming, not because any gate caught them.

## 0. The joint, anatomically

`apps/admin-dashboard-local` is the **only** consumer of the GARUDA VOA engine's preview
payload. It is a staff-only workbench, deliberately not deployed anywhere — no Vercel config,
no Fly config, `next.config.mjs` refuses to start without `LOCAL_ONLY=1`, every start command
binds to `127.0.0.1:3100`. The public route that used to serve VOA is a deliberate tombstone:
`apps/mouth/src/app/visa/voa/route.ts` returns a plain 404 with `x-robots-tag: noindex,
nofollow` and the comment `/** Retired public URL. GARUDA remains an owner-only internal
tool. */`, confirmed by reading the file live this session. Being local-only is a sovereignty
choice (Legge 6) about where the *app* runs, not a statement about whether its *test suite*
needs to run in CI — the two are independent, and §4 below is about the second one.

The engine talks to that workbench through one file: `apps/admin-dashboard-local/lib/
garuda-preview-adapter.ts` (490 lines). It spawns the Python CLI
(`backend.services.garuda_flow.internal_preview_cli`) as a child process, parses its stdout as
JSON, and validates the shape before trusting it. The validator is `hasExactKeys` (line 204):

```ts
function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const actual = Object.keys(value);
  return (
    actual.length === expected.length &&
    actual.every((key) => expected.includes(key))
  );
}
```

`actual.length === expected.length` is the load-bearing clause: it requires an **exact** key
count, not a subset. Add one field on the Python side without updating the TypeScript
allowlist and every preview breaks — `parseObject`/`hasExactKeys` reject the payload,
`invalidEngineResponse()` throws `GarudaPreviewAdapterError("preview_unavailable", ...)`, and
every staff member sees the same opaque failure regardless of which request triggered it.

The adapter carries nine hand-maintained mirrors of Python constants, none of them generated:

| TS constant | line | mirrors |
|---|---|---|
| `OFFICIAL_PRICE_KEYS` | 11 | `pricing.py::_ISSUANCE_PRICE_KEY` / `_EXTENSION_PRICE_KEY` |
| `CHECKPOINT_LABELS` | 15 | `constants.py::PILOT_INTAKE_THRESHOLD_DAYS` / `INTERNAL_ESCALATION_DAYS` / `FINAL_CHECK_DAYS` |
| `DECLINE_CODES` | 16 | `eligibility.py::DeclineCode` enum |
| `BASE_WARNINGS` | 36 | `internal_preview_cli.py::_BASE_WARNINGS` |
| `ESTIMATED_EXPIRY_WARNING` | 41 | same module, single string |
| `EXTENSION_WARNING` | 43 | same module, single string |
| `CALENDAR_WARNING` | 45 | same module, single string |
| `PRICE_WARNING` | 47 | same module, single string |
| `SUCCESS_KEYS` | 49 | `InternalPreviewResponse` Pydantic field order |

Every one of these nine is checked, and only these nine, by `test_preview_adapter_parity.py` —
see §3.

## 1. Four defects, two surfaces

| # | Surface | PR | State (verified this session) | What broke |
|---|---|---|---|---|
| 1 | Engine | [#4784](https://github.com/Bali-Zero/Teman2/pull/4784) | **MERGED** 2026-08-24T08:36:42Z | Unavailable official price silently dropped instead of surfaced |
| 2 | Engine | [#4787](https://github.com/Bali-Zero/Teman2/pull/4787) | **MERGED** 2026-08-24T09:10:00Z | An arrival too far out for any eVOA issued today to still cover was accepted |
| 3 | **Joint** | [#4796](https://github.com/Bali-Zero/Teman2/pull/4796) | **MERGED** 2026-08-24T09:49:47Z | The nine mirrors above had no guard pinning them to their Python originals |
| 4 | **Joint** | [#4802](https://github.com/Bali-Zero/Teman2/pull/4802) | **OPEN**, mergeable, all required checks green at last look — not yet merged | A base warning told staff the engine skips a check it now performs |

### 1.1 Defect 1 — a dropped signal, engine

`pricing.py::price_for_case` already documented its `(None, None)` return as deliberate
fail-safe output: callers must ask staff to confirm rather than invent a price. The producer
was correct. `build_internal_preview` was the bug — it passed `price_idr=None` straight into
the response with no status field, no warning, nothing appended to `warnings`. A catalogue
lookup failure rendered as a plain `ACCEPT` with a blank price and no sign anything had gone
wrong. The fix mirrors a pattern the same function already used twenty lines below for the
operating calendar: a typed `price_status` alongside a `price_warning`, same shape as
`calendar_status` / `calendar_warning`. The PR's own verification line reads "190 tests
green, RC=0" — that count has since grown to 202 (§3), most of it from defects 3 and 4's own
work, confirmed by a fresh `--collect-only` run this session.

This is also the fix that would have taken the workbench down through `hasExactKeys`, had
#4796 not landed first: `price_status`/`price_warning` are two of the nine keys `SUCCESS_KEYS`
now enumerates, and adding them to `InternalPreviewResponse` without a matching TypeScript
edit is exactly the failure mode `hasExactKeys` exists to catch — or, before #4796, exists to
cause silently.

### 1.2 Defect 2 — a suppressed computation, engine

The GARUDA charter's own truth-sheet already recorded both the rule and the gap: B1's eVOA is
"berlaku 90 hari sejak diterbitkan" (usable for 90 days from issuance), and a truth-sheet line
flagged "nessun campo `issuance_date` — la finestra d'uso 90 giorni non è validabile. OPEN."
The only bound in code was a 365-day malformed-input guard — a sanity check, not a regulatory
one. Measured in the PR: `today + 90` lands on 2026-11-22 while the operating calendar's
`COVERAGE_END` is 2026-12-31, leaving a five-week band where the engine cleanly `ACCEPT`ed an
arrival no eVOA issued *today* could still cover.

The fix adds `_issuance_usability_window_verdict` (`intake.py:244`) alongside the existing
`_issuance_submission_verdict` (`intake.py:217`), both gated to issuance-only and both anchored
on `today` — conservative by construction, since an eVOA for this request cannot be issued
before today, so its 90-day window cannot start earlier either. The detail worth recording
precisely, because the PR body states it as a correction to an earlier draft: **an earlier
version ran the usability gate first and short-circuited the submission-window computation
when it fired**, leaving `submit_by_date` at `None` — and `internal_preview_cli` derives
`calendar_status` from exactly that value. The result was an engine that declined correctly
but explained itself with a **false** warning ("the operating calendar does not cover this
entry date") for a date the calendar covered perfectly well. The shipped fix runs both gates
unconditionally and lets both codes accumulate when both genuinely fire — the lesson isn't "run
A before B", it's that **one gate's short-circuit must never suppress a computation the
response still depends on**, however unrelated the two look at the call site.

### 1.3 Defect 3 — the guard, joint

`test_preview_adapter_parity.py` is a Python test that reads
`garuda-preview-adapter.ts` as a text file (`_repo_root()` walks up from `__file__` to find
`.git`, no dependency on pytest's cwd) and regex-parses each of the nine constants back into
Python values, then asserts equality against the real Python originals: `DECLINE_CODES` against
the `DeclineCode` enum, `SUCCESS_KEYS` against `InternalPreviewResponse.model_fields` **in
order**, `BASE_WARNINGS` **in order**, the four single-string warnings against actual engine
output exercised end-to-end (issuance, extension, an uncovered-calendar case, and a
price-lookup failure forced via `unittest.mock.patch`), `OFFICIAL_PRICE_KEYS` against the
pricing module's key constants, and `CHECKPOINT_LABELS` against the three checkpoint-day
constants. Six test functions, nine constants, merged 2026-08-24T09:49:47Z.

### 1.4 Defect 4 — the warning that outlived the fact it described, joint, still open

`BASE_WARNINGS[1]` reads, on `origin/main` as of this session: *"Nationality and entry-point
eligibility are not yet checked against an authoritative dataset and require manual
verification."* That stopped being half-true on 2026-08-23, when `nationality_eligibility.py`
landed: 97 ISO-3 codes from **Kepmenkumham RI No. M.HH-02.GR.01.06/2024**, cross-verified by
two independent retrieval methods with zero divergence, wired at `intake.py:295` —
`nationality_entry_eligible=is_voa_eligible_nationality(request.nationality)`. The engine
performs precisely the check the warning tells staff it does not perform.

The entry-point half was never actually a "no dataset yet" situation, and #4802's own PR body
makes the more careful claim: `VoaIntakeRequest` has nine fields (`case_type`, `nationality`,
`entry_date`, `passport_expiry_date`, `purpose`, `travellers`, `self_pay`,
`voa_expiry_date`, `extension_already_used` — counted directly from the dataclass this
session) and none of them is an entry point. There is no missing dataset; there is no *input*
to check against one. #4802's replacement text says each half as it actually is: *"The
nationality code is checked against the decree-sourced VOA list; this pre-screen does not
collect an entry point, so staff must confirm entry-point eligibility."* The mirror travels in
the same commit — `internal_preview_cli.py::_BASE_WARNINGS[1]`, the adapter's `BASE_WARNINGS[1]`,
and the adapter's own test expectation — because a one-sided edit is exactly the failure mode
of §0.

**#4802 was OPEN, not merged, when this document was written** (`mergeable: MERGEABLE`, not
draft, every required check green except `CodeQL Analysis (python)` still `IN_PROGRESS`; one
non-required advisory job — `Visa Oracle fullstack smoke` — red on an unrelated surface). Its
own check-run list, pulled live this session, contains **zero** entries named for
`admin-dashboard-local` — not even though this exact PR edits that app's adapter and one of
its 13 test files. That is not a hypothetical illustration of §4's finding; it is this PR
proving it about itself, live, on the surface it is trying to fix.

## 2. The measurement that matters most: the guard proven on a real desync

Confirming the parity test's assertion mechanics is one thing; confirming it actually catches
drift is another. This session reproduced the whole cycle directly, in a scratch git worktree
of #4802's branch, never touching the working PR:

1. **Baseline — all three mirrors aligned** (the branch as authored): `pytest
   test_preview_adapter_parity.py` → **RC 0**, 6 passed.
2. **Desync the TypeScript side only** — restored the *old* warning string in
   `garuda-preview-adapter.ts`, leaving the Python source and the adapter's own test file
   untouched: → **RC 1**. The failure lands exactly where it should:
   `test_base_warnings_match_engine_in_order`, `AssertionError: assert [...] == [...]`, diffing
   at index 1, the old string on one side and #4802's replacement on the other.
3. **Restore** the file to the PR's version: → **RC 0** again, and `git diff --stat` against
   the branch came back empty — the worktree was left exactly as found.

The proof reproduced cleanly on the first attempt, no retries. This is the difference between
"a test exists that could theoretically catch this" and "this test was pointed at a real
desync and rang."

## 3. The gate that exists and does not run

`apps/admin-dashboard-local` ships 13 vitest files. This session ran the suite live: **130
tests, 13 files, 834ms, all green.** Among them, `garuda-preview-process-integration.test.ts`
spawns the *real* Python child process — not a mock — through a synthetic repo root, plants a
`.env` file loaded with sentinel secrets (`JWT_SECRET_KEY`, `API_KEYS`, `DATABASE_URL`) in a
location the adapter is supposed to refuse to trust, and asserts the spawned interpreter
never sees them. It is exactly the class of defect §1's warning text used to describe as
unverified — proven, not asserted.

None of those 13 files, 130 tests, or that specific integration test run in CI.
`grep -rln "admin-dashboard-local" .github/workflows/` returns nothing. The Frontend Tests
matrix in `tests.yml` has a leg literally named `admin-dashboard` (line 1597) — a **different**,
publicly-deployed app under `apps/admin-dashboard`, not `apps/admin-dashboard-local`. #4802's
own required-check list (§1.4) confirms which leg actually ran: `Frontend Tests (Next.js)
(admin-dashboard, false)`, green, unrelated to the app the PR edits.

This is not the first time. Two prior instances of exactly this shape are documented in
`tests.yml`'s own comments, adjacent to each other, both citing the same superscar by name:

> *"WS4 governance: `packages/core` … shipped 33 test files / 123 tests that NO workflow ever
> executed … Built, never armed (cicatrix-superscar #2)"* — `tests.yml:1689-1695`

> *"wa-mirror's vitest suite had NEVER run in CI — 8 test files, 0 gates … Built, never armed
> (cicatrix-superscar #2), and W108's lesson is that the defect only surfaces once the test
> runs on EVERY PR."* — `tests.yml:1715-1721`

`admin-dashboard-local` is the **third** instance of the same class, in the same file, and the
organism's own comments are the record of having named and cured the first two. Both cures
share a shape worth noting for whoever fixes the third: neither became a new job or a new
matrix entry. Branch protection pins required contexts by name (W69 — required checks
disarmed), so a new name is born unrequired and stays that way until someone edits repo
settings by hand. Both were instead attached as a *step* of an already-required leg
(`Frontend Tests (Next.js) (mouth, true)`). The same move is available here: `admin-dashboard`
is already required, so `admin-dashboard-local`'s `npx vitest --run` can be a step on it
without inventing a check nobody will remember to make required.

## 4. What this means, beyond the narrative

**A green suite proves less than it appears to.** The Python suite tested the engine
completely and correctly — 202 tests, RC 0, defects 1 and 2 both caught and fixed with real
before/after tables in their PR bodies. It still could not see either joint defect, for a
structural reason that has nothing to do with test quality: the contract has two halves, and
one half lives in a different language, in a different app, under a test runner the CI matrix
never invokes for that app. A 100%-passing suite on one side of a language boundary says
nothing about the other side. This is not specific to GARUDA or to TypeScript/Python — it is
the general shape of any contract enforced by convention across a process or language
boundary rather than by a single generated source of truth, and it recurs precisely because
each side's own tests look, and are, completely healthy.

**Nine hand-maintained mirrors is the actual disease; the parity test treats a symptom.** The
parity test is real, it is well-built, and §2 proved it fires on a genuine desync — but it
catches drift *after* someone writes it, on the next CI run (assuming §3's gap closes),
never before. The honest question is whether the contract should be generated from one
source instead of mirrored by hand nine times over. The case for it: it would make the
disease structurally impossible rather than merely detected — no PR could ever introduce the
desync in the first place, because there would be nothing to keep in sync. The honest cost:
`hasExactKeys`, the four single-string warnings, and the six-constant list are not a
mechanical 1:1 translation — `SUCCESS_KEYS` needs Pydantic field order, `DECLINE_CODES` needs
the enum's string values, `CHECKPOINT_LABELS` needs three separately-named day constants
interpolated into `D-{n}` strings, and none of that generation logic currently exists for a
Python-to-TypeScript boundary in this codebase. Building and trusting a codegen step is real,
non-trivial work, and — this is the part worth stating plainly rather than assuming away — a
generated contract still would not have caught defect 4. Defect 4 was not a shape mismatch; it
was a **true-when-written, false-when-read string** that stayed syntactically valid the entire
time. No parity check, generated or hand-written, catches a warning that is still the right
*type* but the wrong *content* once the world it describes changes underneath it. That failure
mode needs its own answer, and this document does not have one to offer.

**Cicatrix #2's specific cruelty here.** The organism did not fail to notice this class of
defect. It named it, wrote the antidote, and applied that antidote successfully — twice, in
the same file, with comments that say so in as many words. And it still shipped a third
instance. The likely mechanism is visible in the fix's own shape: because each fix was
"attach one more step to an existing required leg" rather than "add a rule that new frontend
apps must register their own CI step," curing packages/core and wa-mirror closed those two
specific gaps without closing the *category*. There is no lint, no template, no
`git commit -m "feat: new app"` hook that asks "does this app have a test suite, and if so, is
it wired into `tests.yml`?" The antidote fixed two symptoms in the same organ without
touching what let a third symptom grow.

**What is still uncovered.** The parity test (§1.3) covers contract *drift* — nine constants,
checked for exact equality against their Python originals. It does not, and by design cannot,
cover what `garuda-preview-process-integration.test.ts` uniquely proves: that the spawned
Python child process cannot read the backend's `.env` or inherit unrelated application
secrets. That is a live-process boundary check, not a static comparison, and it exists in
exactly one of the 130 untested-in-CI tests. Overstating the parity test's coverage would be
its own small version of defect 4 — a claim that stays true in one dimension while going
false in another. And as of this writing, defect 4's actual fix is not live: #4802 is open,
green, and unmerged, so the mis-worded warning it corrects is still what a staff member reads
on `origin/main` today.

## 5. Open items

- Wire `admin-dashboard-local`'s vitest suite (13 files, 130 tests) as a step on the already-
  required `admin-dashboard` matrix leg, mirroring how packages/core and wa-mirror were
  attached — not a new job, not a new required-context name.
- Merge #4802 (open, green, mergeable at last check).
- No design decision reached here on generated-vs-mirrored contract, per §4 above — only the
  cost/benefit stated. That choice is out of this document's scope.
