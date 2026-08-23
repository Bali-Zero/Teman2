---
date: 2026-08-23
domain: visa
client_case: none — internal engineering/governance artifact for the Visa Oracle ENFORCE-GATE
adversarial_review: codex
sources:
  - apps/backend-rag/backend/services/visa_engine/evaluate_path.py
  - apps/backend-rag/backend/services/visa_engine/enums.py
  - apps/backend-rag/backend/services/visa_engine/bundle.py (validate_activation, verify_rule_pack)
  - apps/backend-rag/backend/scripts/visa_engine/activate_pack.py
  - apps/backend-rag/backend/scripts/visa_engine/replace_activation_set.py
  - apps/backend-rag/backend/scripts/visa_engine/sign_pack.py
  - apps/backend-rag/backend/db/migrations_v2/250_visa_engine_core.sql
  - apps/backend-rag/backend/db/migrations_v2/251_visa_activation_writer.sql
  - apps/backend-rag/backend/db/migrations_v2/253_visa_activation_writer_hardening.sql
  - apps/backend-rag/backend/db/migrations_v2/267_visa_replace_activation_set.sql
  - apps/backend-rag/backend/tests/services/visa_engine/test_evaluate_endpoint.py
  - apps/backend-rag/backend/tests/services/visa_engine/test_activation_writer.py
  - apps/backend-rag/backend/tests/services/visa_engine/test_repository.py (_builders, _trust_store_for)
  - apps/backend-rag/backend/tests/scripts/visa_engine/test_activate_pack.py
  - apps/backend-rag/backend/tests/scripts/visa_engine/test_replace_activation_set.py
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/runtime-mode.ts
---

# Visa Oracle kill-switch — rollback proof (2026-08-23)

**Mandate**: produce a current, independently reproducible rollback proof for the two Visa
Oracle kill switches named in the ENFORCE-GATE (`.agents/skills/visaoracle/SKILL.md`), without
touching production in any way. Worktree: `.worktrees/backend-rag-visaoracle-killswitch-proof-0823`
(created via `scripts/agent_start.py --lane backend-rag --task-id visaoracle-killswitch-proof-0823`),
branched from `origin/main` at `868b62322df0be7fddd9cf48ebdb1c01f50b7f8d` (2026-08-23 05:01:35 UTC).

**Provenance (corrected 2026-08-23, second pass)**: the first version of this file, written before
it was committed, said "No commit, no push" — true at the time of writing, false the instant it
landed as part of a commit, and it was never updated after that happened. This is now
**PR #4616** (`agent/air-m5/backend-rag/visaoracle-killswitch-proof-0823` → `main`), containing this
file and its two companion scripts. Do not read a specific commit SHA off this paragraph — a value
hardcoded here would go stale on the very next amendment to this same file, which is exactly the
class of self-referential-evidence mistake the first version made. Run `git log --oneline -1 --
research/visa/2026-08-23-killswitch-rollback-proof.md` (or `gh pr view 4616 --json headRefOid`) for
the current head SHA of this branch.

**Safety**: every command below ran either with zero DB access (unit tests, `--dry-run` CLI
invocations) or against a disposable local/ephemeral Postgres database that this session created
and that pytest-xdist tears down automatically. Nothing in this report touched
`nuzantara-postgres` (Fly), `fly ssh`, Fly secrets, or `VISA_ENGINE_EVALUATE_MODE` on the deployed
app. The engine's live mode was never read or queried remotely — everything here is local-code and
local-DB evidence.

## Summary verdict

**There are two genuinely distinct kill switches, confirmed by reading the code, not assumed from
the task description.** Both mechanisms were driven end-to-end today, through the real production
code path (not a mock), against a local Postgres 17.10 instance (M5's `brew` Postgres — see
**Known limitation** below for the version delta against CI's `postgres:15`).

1. **The MODE switch** (`VISA_ENGINE_EVALUATE_MODE`, the **backend** resolver) is a **fail-safe,
   read-fresh-per-call** three-state gate (`OFF|SHADOW|ENFORCE`) that determines whether an
   evaluate response is authoritative. **PROVEN LOCALLY, both directions, same facts, same pack.**
   The frontend has a separate, differently-behaved resolver — see §1.1's scope note — not covered
   by this claim and not proven safe by this proof.
2. **The PACK rollback** (`activate_pack.py` / `replace_activation_set.py` / the
   `visa_replace_activation_set`/`visa_activate_rule_pack` SQL functions) is a
   **strictly-forward, hash-chained, append-only ledger with a triple-redundant anti-rollback
   gate** (Python pre-check, SQL trigger, and — for the multi-segment path — the SQL function's own
   explicit chain-walk). **A pack can never be reactivated at a lower-or-equal sequence number by
   the intended executor role**, with the trigger enabled at its normal operating condition (see
   §2.1's precisely-scoped consequence — the first version of this claim was an unscoped absolute
   that did not hold). The system's actual "rollback" mechanism is: re-sign the desired content as
   a NEW pack at the next sequence number, chained from the true current head, and activate that.
   **PROVEN LOCALLY, both the guilt case (naive reactivation rejected) and the innocence case
   (legitimate content-restore succeeds, exactly one open activation, no temporal gap), at three
   levels: the DB/repository layer, the actual `activate_pack.py` CLI subprocess, AND — the part
   added after adversarial review — the restored pack driven through the real, unmocked evaluate
   path (`verify_rule_pack` → `build_compiled_pack` → `evaluate_with_trace`), reproducing the
   original pack's actual DECISION on fixed facts, not merely a matching ledger row.**

---

## 1. The MODE switch — `VISA_ENGINE_EVALUATE_MODE`

### 1.1 What the code does (read, not assumed)

`resolve_evaluate_mode()` (`evaluate_path.py:212-219`):

```python
def resolve_evaluate_mode() -> EngineMode:
    """Resolve the public authority lever; unknown values fail closed to OFF."""
    raw = os.environ.get(EVALUATE_MODE_ENV, EngineMode.OFF.value).strip().upper()
    try:
        return EngineMode(raw)
    except ValueError:
        return EngineMode.OFF
```

- **Accepted values**: `OFF`, `SHADOW`, `ENFORCE` (`EngineMode` enum, `enums.py:109-118`).
- **Unset, empty, or any invalid string** (case-insensitive, whitespace-trimmed) **fails closed to
  `OFF`** — the most restrictive state, never to `ENFORCE`. This is not incidental: the `except
ValueError: return EngineMode.OFF` is the only fallback path in the function.
- **Read fresh on every call, never cached at import time** (module docstring `evaluate_path.py:161-165`
  and confirmed by reading the call site: `resolve_evaluate_mode()` is invoked at the top of
  `run_evaluation()`, `evaluate_path.py:1454`, on every request). This means flipping the switch
  takes effect on the very next request **within the same running process** — no code redeploy, no
  process restart is required by the code itself. **Operationally**, on Fly.io the value is
  delivered as a secret; `fly secrets set` triggers a machine restart to propagate a changed
  secret into a running machine's environment, so the practical mechanism an operator uses is
  "secret set → automatic restart" (seconds, not a `fly deploy`), not a genuine hot-reload of a
  live process's env — but the CODE itself imposes no redeploy requirement, and does not cache the
  old value.
- **Response-mode mapping** (`resolve_response_mode()`, `evaluate_path.py:233-243`): `ENFORCE` →
  `"ENGINE"` (authoritative); `OFF` and `SHADOW` both → `"CURATED"` (never authoritative).
- **Scope of this claim — the BACKEND resolver only.** Everything above describes
  `evaluate_path.resolve_evaluate_mode()`. The frontend has a **separate, unrelated** resolver,
  `resolveVisaOracleMode()` (`apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/runtime-mode.ts:21-32`),
  and it does **not** fail closed the same way: on unset/invalid `NEXT_PUBLIC_VISA_ORACLE_MODE`
  outside a `NODE_ENV=test` build, it returns `"ENGINE"`, not a safe default (`runtime-mode.ts:32`:
  `return nodeEnvironment === "test" ? "PREVIEW" : "ENGINE";`). This was flagged by an adversarial
  review (§ below) and is real — read here, not inferred. It is not, on its own, an authority
  bypass: `"ENGINE"` only tells the mouth app which UI/adapter code path to render, and that
  adapter still requires a genuine `"mode": "ENGINE"` **envelope from the backend** (the field this
  section proves the backend fails closed on) before it will show anything as authoritative — the
  frontend resolver choosing `"ENGINE"` cannot manufacture an authoritative decision the backend
  never sent. But it is a real asymmetry worth naming plainly: the two kill-switch halves fail in
  OPPOSITE directions on a misconfigured/unset env var, and only one of them is proven safe by the
  reasoning in this section.
- **OFF short-circuits before any I/O**: `run_evaluation()` checks `engine_mode is EngineMode.OFF`
  and returns `build_temp_unavailable_body(..., code="EVALUATE_SURFACE_DISABLED", ...)`
  **immediately**, before the retention-policy check, before pack binding, before any DB access
  (`evaluate_path.py:1455-1460`). Verified empirically below with a DB-pool sentinel that raises on
  ANY attribute access.
- **ENFORCE fails closed on a persistence failure**: if the durable decision write fails, ENFORCE
  degrades to `TEMPORARILY_UNAVAILABLE` (`code="DECISION_PERSISTENCE_UNAVAILABLE"`) rather than
  returning an authoritative verdict that was never actually recorded (`evaluate_path.py:1610-1618`).
  SHADOW, by contrast, is best-effort — its response stays `CURATED` regardless, because it was
  never claiming authority.

### 1.2 Mechanism verified unchanged since the last live drill

`git log` on `evaluate_path.py` shows exactly 3 commits ever, and only one since the 2026-08-08
production kill-switch drill recorded in `.agents/skills/visaoracle/CURRENT_STATE.md`/LIVE STATE
(`fix(visa): align offline replay with public policy path`, `0fae2a64c`, 2026-08-14): that diff
touches replay/policy-adapter code, **not** the mode resolver — `git show 0fae2a64c -- evaluate_path.py
| grep -i "mode|EVALUATE_MODE|resolve_evaluate"` returns zero hits. The mechanism the 2026-08-08
drill exercised in production (`SHADOW→OFF` verified `EVALUATE_SURFACE_DISABLED` in ~1.5 min,
`OFF→SHADOW` restored in ~1 min) is, at the code level, identical to what is running today.

### 1.3 Reproduced locally, driving the real code path

Companion script: `research/visa/2026-08-23-killswitch-mode-proof.py`. It reuses this repo's own
test fixtures (`_patch_engine_chain`, `_facts_with_purposes`, `_UntouchedPool` from
`test_evaluate_endpoint.py`) rather than inventing a new harness — the same technique the suite's
own `test_enforce_mode_is_engine_after_durable_persistence` uses, extended to compare **all three**
mode values against **identical applicant facts and the identical gold TEST pack**, in one Python
process, one call after another (proving the "read fresh, no import-time cache" claim empirically,
not just by reading the docstring).

**Command** (run from `apps/backend-rag`, venv activated):
```
PYTHONPATH=. python /path/to/research/visa/2026-08-23-killswitch-mode-proof.py
```

**Observed output** (2026-08-23, this session, exit 0 — every `assert` in the script held):
```
env VISA_ENGINE_EVALUATE_MODE    resolved  response.mode  decision.state           outage.code                  persisted_rows  persisted_engine_mode
None                             OFF       CURATED        TEMPORARILY_UNAVAILABLE  EVALUATE_SURFACE_DISABLED    0               None
OFF                              OFF       CURATED        TEMPORARILY_UNAVAILABLE  EVALUATE_SURFACE_DISABLED    0               None
BOGUS                            OFF       CURATED        TEMPORARILY_UNAVAILABLE  EVALUATE_SURFACE_DISABLED    0               None
SHADOW                           SHADOW    CURATED        HUMAN_REVIEW_REQUIRED    None                         1               SHADOW
ENFORCE                          ENFORCE   ENGINE         HUMAN_REVIEW_REQUIRED    None                         1               ENFORCE

PROOF HOLDS: identical facts -> identical decision_state ('HUMAN_REVIEW_REQUIRED') under SHADOW
and ENFORCE, but only ENFORCE's response.mode is authoritative ('ENGINE' vs 'CURATED'). OFF /
unset / invalid all fail SAFE to a non-authoritative, zero-persistence TEMPORARILY_UNAVAILABLE
response.
```

This is the concrete claim the ENFORCE-GATE asks for: **with the switch in the safe position
(SHADOW), the exact same request that reaches a real, non-abstaining decision
(`HUMAN_REVIEW_REQUIRED`, not `TEMPORARILY_UNAVAILABLE`) does NOT get an authoritative verdict — the
response is labeled `CURATED` and the caller cannot treat it as legal authority. With the switch in
the other position (ENFORCE), the identical facts against the identical pack produce the identical
`decision_state`, but now labeled `"mode": "ENGINE"` — authoritative.** OFF/unset/invalid all
collapse to the safest possible behavior: no decision computed at all, zero DB writes (proven by
`_UntouchedPool`, a sentinel object that raises `AssertionError` on any attribute access — the OFF
path never even reaches the pool).

I also independently re-ran the three most relevant **existing, already-reviewed** tests fresh
(not cited from memory):

```
cd apps/backend-rag && source .venv/bin/activate
export TEST_DATABASE_URL="postgresql://nuzantara@localhost:5432/nuzantara_test"
PYTHONPATH=. python -m pytest backend/tests/services/visa_engine/test_evaluate_endpoint.py \
  -k "TestResolveEvaluateShadowEnabled or TestResolveResponseMode or \
      test_off_mode_is_temp_and_persists_nothing or \
      test_enforce_mode_is_engine_after_durable_persistence" -q
```
→ **13 passed** (these don't touch the DB — `object()`/`_UntouchedPool()` sentinels only).

### 1.4 What I could NOT re-verify (owner-gated, scripted)

I did not, and per the hard safety constraint must not, flip `VISA_ENGINE_EVALUATE_MODE` on the
deployed Fly app myself. The last time this exact drill ran in production was 2026-08-08 (see
LIVE STATE) and the mechanism is unchanged (§1.2). If Zero wants a **fresh live re-drill** (not
required by this proof, since the code-level mechanism is verified and unchanged, but available if
wanted), the exact commands are:

```
# 1. Confirm current mode
fly ssh console -a nuzantara-rag -C 'printenv VISA_ENGINE_EVALUATE_MODE'   # expect SHADOW

# 2. Flip to OFF, watch it apply (secrets set triggers an automatic restart)
fly secrets set VISA_ENGINE_EVALUATE_MODE=OFF -a nuzantara-rag
# then poll: a POST to /api/visa-oracle/evaluate should return
# decision.state=TEMPORARILY_UNAVAILABLE, decision.outage.code=EVALUATE_SURFACE_DISABLED

# 3. Flip back
fly secrets set VISA_ENGINE_EVALUATE_MODE=SHADOW -a nuzantara-rag
# then poll: the same POST should return a real decision.state again, "mode":"CURATED"
```
Expected output constituting proof: outage code exactly `EVALUATE_SURFACE_DISABLED` within ~2 min
of step 2, and a real (non-outage) decision within ~2 min of step 3 — matching the 2026-08-08
timings.

---

## 2. The PACK rollback — `activate_pack.py` / `replace_activation_set.py`

### 2.1 The mechanism (read from code + migrations, not assumed)

**`activate_pack.py`** is the single-pack ceremony tool: verify signature → `validate_activation`
(Python-side anti-rollback pre-gate, operator supplies `--current-sequence`/`--current-payload-sha256`
as a courtesy fail-fast) → insert the immutable pack row → activate via
`VisaEngineRepository.activate_rule_pack`, which calls the `SECURITY DEFINER` SQL function
`public.visa_activate_rule_pack(uuid, text, text)` (migration 251).

**`replace_activation_set.py`** is the multi-segment ceremony tool (needed when a legal-period
correction must replace several currently-open segments atomically, migration 267's own header) —
same verify → chain-validate → insert → activate shape, but calling
`public.visa_replace_activation_set(uuid[], text, text)`.

**The anti-rollback gate exists at THREE independent layers**, and I read and then empirically
re-triggered all three:

1. **Python pre-gate**, `bundle.validate_activation()` (`bundle.py:914-994`): rejects
   `payload.sequence <= current_sequence`, and rejects a broken `previous_payload_sha256` chain
   (candidate's declared previous hash must equal the current head's actual `payload_sha256`
   exactly). This runs BEFORE any DB connection is opened — it is a pure function over values the
   caller already holds (which, for `activate_pack.py`, are **operator-supplied CLI args**, not
   DB-queried — a courtesy check, not the source of truth).

2. **SQL trigger**, `reject_visa_activation_insert()` / `visa_activation_insert_guard`. **Citation
   correction**: the trigger function was originally *created* by migration 250
   (`250_visa_engine_core.sql:380-440`), but its LIVE, currently-installed body is the one
   `CREATE OR REPLACE FUNCTION public.reject_visa_activation_insert()` in migration
   **253** (`253_visa_activation_writer_hardening.sql:260`, further replaced once more at
   `:721` in the same file) — 253 is the authoritative-current definition; 250 only defines the
   pre-hardening ancestor of it. This proof cites 253. The runtime behavior is what §2.2's tests
   (`test_activation_writer.py::test_trigger_resolves_to_hardened_public_function`) actually
   exercise: it fires on every INSERT into `visa_ruleset_activations`, **independently re-derives
   the true current head** via a query over the live table's own current-highest-sequence row — it
   does **not** trust anything the Python layer or the CLI operator claimed. Rejects
   `pack.sequence <= head.seq` (message: `"visa activation rollback rejected: pack sequence % <=
prior activated sequence %"`) and a broken hash chain (`"visa activation hash chain broken"`).
   **This is the real enforcement layer** — a lying/stale `--current-sequence` CLI argument cannot
   get a rollback past this trigger.

3. **The `visa_replace_activation_set` function itself** (migration 267, multi-segment path) does
   its OWN explicit forward chain-walk (`267_visa_replace_activation_set.sql:150-180`) in addition
   to relying on the same insert trigger — belt-and-suspenders for the batch case.

**Consequence, precisely scoped** (narrowed 2026-08-23 after adversarial review — the first version
of this sentence claimed an unscoped absolute that does not hold): **there is no code path
available to the intended executor role — with the trigger enabled and normal
`session_replication_role=origin`, the operating condition for any real production connection —
that can reactivate a pack at a sequence number less than or equal to the current head.** That
scoping is load-bearing, not decorative: an ordinary (non-`ENABLE ALWAYS`) Postgres trigger, this
one included, is bypassable either by `SET session_replication_role=replica` for the session, or by
a role with `ALTER TABLE` privilege directly disabling it. This proof's own test suite demonstrates
the second form is *practicable*, not merely theoretical:
`test_repository.py:1316` runs `ALTER TABLE visa_ruleset_activations DISABLE TRIGGER
visa_activation_insert_guard` to build a controlled pre-condition for an unrelated fixture (a
legal-period CHECK-constraint test) — proof that a role holding table-owner privilege can silence
this exact trigger. What makes this safe in practice, and the actual claim this proof supports: the
production executor role (`activate_pack.py`'s `_assert_production_separation`, §2.2's
`test_ownership_and_grant_boundary_real_roles` family) is deliberately granted only `EXECUTE` on
the activation functions, never table ownership, `ALTER TABLE`, or superuser privileges — it has no
ability to disable the trigger or change `session_replication_role` in the first place. So the
practical guarantee holds for the role that actually runs in production, not because the trigger is
architecturally unbypassable in the abstract — a genuinely different (and narrower, correct) claim
than the original absolute. This is enforced at the SQL layer independent of the Python layer, so
it cannot be bypassed by a buggy or malicious CLI argument using the intended executor's own
privileges. **"Rollback" in this system therefore does not mean "go back" — it means "author a NEW
pack, at the next sequence number, whose content restores the desired prior behavior, chained
forward from the true current head, and activate that."** This is exactly the pattern the
2026-08-08 Cameroon/Guinea Calling Visa correction used in production (LIVE STATE: "re-signed
identical content as seq 3... retroactive").

### 2.2 Reproduced locally — DB/repository layer (guilt + innocence + no-gap bookkeeping)

Ran the existing, already-reviewed local-Postgres integration suites fresh, against an
**ephemeral, pytest-xdist-cloned throwaway database** (never the shared `nuzantara_test`/
`nuzantara_dev` DB the test files' own docstrings warn against — the `-n 1` flag triggers
`backend/tests/conftest.py`'s per-worker DB clone-and-teardown, confirmed by reading that
conftest's module-level xdist-isolation block):

```
cd apps/backend-rag && source .venv/bin/activate
export TEST_DATABASE_URL="postgresql://test@localhost:5432/nuzantara_test"   # local role;
                                                                              # 'nuzantara' role
                                                                              # doesn't exist on
                                                                              # this machine, see
                                                                              # Known limitation
PYTHONPATH=. python -m pytest backend/tests/services/visa_engine/test_activation_writer.py -n 1 -q
PYTHONPATH=. python -m pytest backend/tests/scripts/visa_engine/test_replace_activation_set.py -n 1 -q
PYTHONPATH=. python -m pytest backend/tests/scripts/visa_engine/test_activate_pack.py -n 1 -q
```
**Results**: `test_activation_writer.py` — **44 passed, 1 skipped** (the skip is
`visa_activation_executor role absent — operator provisioning not yet run`, an expected/documented
scaffold skip on a machine with no operator-provisioned executor role, not a failure of anything
under test). `test_replace_activation_set.py` — **11 passed**. `test_activate_pack.py` — **18
passed**. Among these, already covering guilt+innocence for BOTH kill-switch mechanisms with real
Postgres roles (not mocks):

- `test_activate_sequence_rollback_via_function_raises` — activates pack seq 1, then seq 2, then
  attempts to reactivate seq 1 → `asyncpg.exceptions.RaiseError, match="rollback rejected"`; asserts
  seq 2's activation is untouched (still open) afterward — the whole failed call rolled back
  atomically.
- `test_activate_hash_chain_break_via_function_raises` — a higher-sequence pack with the WRONG
  `previous_payload_sha256` is rejected with `match="hash chain broken"`.
- `test_activation_periods_adjacent` — proves the closed-prior's `system_period` upper bound equals
  the new activation's lower bound EXACTLY (same `clock_timestamp()` read), and exactly one open
  activation exists.
- `test_ownership_and_grant_boundary_real_roles` — creates REAL, distinct Postgres roles locally
  and proves the production writer/activation privilege-separation boundary
  `activate_pack.py`'s `_assert_production_separation` depends on (owner vs serving vs executor
  capability shape) — this is the mechanism behind "production refuses a combined login."
- `test_production_separation_accepts_exact_capabilities` /
  `test_production_activation_rejects_one_combined_database_login` /
  `..._rejects_one_login_using_two_set_roles` / `..._rejects_superuser` (`test_activate_pack.py`) —
  direct unit coverage of `_assert_production_separation`'s guilt and innocence cases.

**My own targeted scenario — SECOND VERSION (2026-08-23, this is the corrected proof; see
Adversarial review for what was wrong with the first).** The first version of this scenario used
`test_repository.py`'s `_pack_hash()` helper — its own docstring says plainly "NOT a real SHA-256
digest" — and a fabricated random-UUID `signature` field, and only ever called
`repo.load_active_rule_pack()` (a DB read) to check the "restore." It never called
`verify_rule_pack`, `build_compiled_pack`, or the actual evaluator. That proved the ledger accepts
and orders rows correctly; it did **not** prove a restored pack is cryptographically verifiable,
compiles, or produces the same applicant-facing decisions as the original — exactly the gap a real
adversarial review exists to catch, and did.

Companion file (same file path as before, content replaced):
`research/visa/2026-08-23-killswitch-pack-rollback-proof-test.py` — a temporary pytest test written
into `apps/backend-rag/backend/tests/services/visa_engine/`, run, then removed from the tests
directory; the copy in `research/visa/` is the permanent record. This version signs three **real**
Ed25519-signed, real-JCS-hashed envelopes over the actual checked-in evaluatable TEST pack
(`rulepack-test-c1-tourism.source.json`: one product, C1 Tourist Visit Visa; a HARD_FILTER
excluding `overstay_days > 60`; an ELIGIBILITY rule supporting TOURISM stays `<= 30` days) — using
this exact test suite's own established real-signing idiom
(`_builders.ephemeral_ed25519_keypair` + `_builders.sign_rule_pack_envelope`, already exercised
end-to-end by `test_repository.py::_insert_activate_load_verify`, that file's own P0-1/P1-8 proof —
no new mechanism invented) — and drives the FULL production evaluate path
(`evaluate_path.run_evaluation`) against fixed facts, **unmocked** from `_resolve_active_pack_binding`
through `verify_rule_pack` → `build_compiled_pack` → `evaluate_with_trace` →
`apply_public_policy_adapters`, asserting the restored pack reproduces the original's **decision**
on identical facts — not that a ledger row landed.

Two things are deliberately mocked, both orthogonal to pack correctness and disclosed in the
script's own module docstring rather than silently patched: `active_retention_policy_available`
(stubbed `True` — the real gate lives behind a Zero retention-policy record this proof's migration
set does not provision; it decides whether to PERSIST a decision, never what the decision IS), and
`_save_evaluate_decision` (stubbed no-op — its target table, `visa_decisions`, is created by a
migration outside this proof's applied set 250/251/253/254/267; the function only writes an audit
row of an already-computed decision, it never reads or influences one). Pricing-catalog acquisition
is untouched: `run_evaluation` already catches any exception from `get_pricing_service()` and
degrades to `UnavailablePricingCatalog()` — that real degrade path runs here, not a test double.

The scenario:

1. **Pack A** (sequence 1, the real checked-in payload, unmodified rules): sign for real, insert,
   activate. Drive `run_evaluation()` against fixed facts (TOURISM, `stay_days=20`,
   `overstay_days=10`) → real decision: `state=SUPPORTED_CANDIDATES`, `candidates=[C1]`.
2. **Pack B** — the "bad deploy": content-identical to A except the HARD_FILTER threshold is
   tightened from 60 days to 5 (`payload["rules"][0]["when"]["value"] = 5`), sequence 2, chained
   from A's REAL payload hash. Sign, insert, activate — A closes exactly when B opens (adjacent, no
   gap, asserted against the DB). Drive `run_evaluation()` again, SAME facts → real decision: `C1`
   is genuinely EXCLUDED (`overstay_days=10 > 5`), `state != SUPPORTED_CANDIDATES` — **the bad
   deploy demonstrably changes the applicant-facing outcome, through the real evaluator, not just
   in the abstract.**
3. **GUILT**: attempt to reactivate pack A verbatim while B is head (sequence 1 ≤ 2) →
   `asyncpg.exceptions.RaiseError, match="rollback rejected"`. B's activation verified untouched
   afterward (still open, `open_count == 1`).
4. **INNOCENCE — the legitimate rollback**: sign pack C — same `products`/`rules` content as A,
   byte-identical (asserted directly: `payload_c["rules"] == payload_a["rules"]` and
   `["products"] == ["products"]`) — sequence 3, chained from **B's** REAL payload hash (the true
   current head, not A's stale one). Insert, activate → succeeds. B's `system_period` closes
   exactly when C's opens (no gap); exactly ONE open activation; that row is C.
5. **The proof this file exists for**: drive `run_evaluation()` a third time, SAME fixed facts,
   with C now active — real decision: `state=SUPPORTED_CANDIDATES`, `candidates=[C1]`, **identical
   `reason_codes` and `product_version_id`** to pack A's original decision. The restored pack does
   not merely satisfy the ledger — it reproduces the real applicant-facing outcome, through the
   unmocked evaluator, exactly.

**Command and result** (run 2026-08-23, this session, local ephemeral Postgres 17.10,
pytest-xdist-cloned, real Ed25519 keys generated fresh in-process — never touching any real signing
key):
```
cd apps/backend-rag && source .venv/bin/activate
export TEST_DATABASE_URL="postgresql://test@localhost:5432/nuzantara_test"
PYTHONPATH=. python -m pytest \
  backend/tests/services/visa_engine/test_zzz_killswitch_rollback_proof.py -n 1 -v -rA
```
```
PASSED backend/tests/services/visa_engine/test_zzz_killswitch_rollback_proof.py::test_emergency_rollback_ceremony_reproduces_real_decisions
```
Captured stdout (real UUIDs and real SHA-256 hex digests from this run — not illustrative):
```
DECISION-REPRODUCTION PROOF HOLDS: pack_a=6cb46f47-fc57-429b-9956-ca9ebc36395a
pack_b=973f2425-c4b5-4211-8e38-4f4a102e4eaa pack_c=f962da81-fd4b-4540-9497-91e35f065879
activation_a=cf542919-609e-4aff-bf72-1a386f7fdb4d activation_b=50d581a0-86c0-45b9-93ab-ca624b3a8c44
activation_c=6b14a0a8-11d8-460b-a396-286b0e920cba
payload_sha256(A)=8fc7c71a6b18ff52261c13f484bea2028687c0ce9b72f249dc251fe054ec2d32
payload_sha256(B)=e960ba9cd6e3cab8e1510247641a82a3a49fa143823b00f29bb89ef6118e135c
payload_sha256(C)=dad82b8fdda13a25c6db746dc01dbb12b738d5871f9463cb1648d394400842ca -- real
Ed25519-signed pack A, driven through the real unmocked evaluate path, produced
state=SUPPORTED_CANDIDATES candidates=[C1]; real bad-deploy pack B (HARD_FILTER 60d->5d, same
facts) genuinely EXCLUDED C1; naive reactivation of A was rejected while B was head; re-signed
content-identical pack C (chained from B's real hash) was accepted and, driven through the same
real evaluate path, reproduced A's exact decision: SUPPORTED_CANDIDATES=[C1] with identical
reason_codes and product_version_id.
```
Captured log (the guilt step's real DB error, unaltered):
```
ERROR VisaEngineRepository:base_repository.py:50 fetchrow failed: visa activation rollback
rejected: pack sequence 1 <= prior activated sequence 2 | query=SELECT
public.visa_activate_rule_pack($1, $2, $3) AS activation_id
```

**One thing this proof does NOT cover, stated plainly rather than silently left out**: the
checked-in TEST source payload ships without a `freshness_policy` on its source record, and
`compile_pack`'s `EXTENSION_POLICY_STATUS_REQUIRED` gate only fires for sequence≥2 products. Both
are real, documented behaviors of this system (the freshness gate is the same mechanism behind
prod SHADOW's stale-abstain history in this skill's own LIVE STATE log) that would otherwise make
every one of packs A/B/C abstain into `HUMAN_REVIEW_REQUIRED`/`NEEDS_INPUT` regardless of the
rollback mechanism being tested. The script adds a generous (1-year) `freshness_policy` and a
`VERIFIED` `extension_policy.status` to every pack's payload uniformly (A/B/C alike) — a deliberate
simplification, disclosed in the script's own docstring, that isolates the pack-rollback mechanism
under test from these two unrelated gates rather than silently working around them.

### 2.3 Reproduced locally — the actual `activate_pack.py` CLI subprocess

Beyond the repository-layer proof above, I also invoked the **real CLI entry point** (not just the
functions it calls) as a subprocess, against the repo's own checked-in signed TEST rule pack
(`apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-test-c1-tourism.signed.json`,
kid `key-2026-07-test-1`, sequence 1, environment TEST), using the TEST trust-store public key
already checked into `fullstack_smoke.py` (`hPwtyP1ekdj_n-BK4M97dyWnRxW1RJ-uGcnVsX5buHM`). Both
invocations below are **dry-run** (`--yes` omitted) — the code returns before opening any DB
connection in this mode (verified by reading `activate_pack.py:307-318` — the `writer_database_url`
lookup happens strictly after the dry-run early-return), so **zero DB access, local or remote,
occurred** in either command.

**Innocence (bootstrap, `--current-sequence 0`)**:
```
export VISA_ENGINE_TRUST_STORE_KEYS_JSON='[{"kid":"key-2026-07-test-1","public_key":"hPwtyP1ekdj_n-BK4M97dyWnRxW1RJ-uGcnVsX5buHM","environment":"TEST","valid_from":"2026-07-19T00:00:00Z","valid_to":null,"revoked_at":null}]'
PYTHONPATH=. python -m backend.scripts.visa_engine.activate_pack \
  backend/services/visa_engine/contracts/packs/rulepack-test-c1-tourism.signed.json \
  --actor operator.killswitch-proof --reason dry-run-verify-only --current-sequence 0
```
```
INFO backend.services.visa_engine.bundle: verified rule pack 8a57d996-c7f2-5abc-9c31-4128a29ed848 sequence=1 kid=key-2026-07-test-1
INFO visa_engine.activate_pack: verified against trust store: kid=key-2026-07-test-1
INFO visa_engine.activate_pack: anti-rollback pre-gate passed
INFO visa_engine.activate_pack: dry_run=true would_insert_and_activate=true rule_pack_id=8a57d996-c7f2-5abc-9c31-4128a29ed848 sequence=1 environment=TEST payload_sha256=ffefeb62d53350fbfc196123cbb3c3676e641ac738f2677de6c1032a8e7cd164 actor=operator.killswitch-proof reason=dry-run-verify-only
```
Exit 0.

**Guilt (claim sequence 1 is already active, try to "reactivate" the same sequence-1 pack)**:
```
PYTHONPATH=. python -m backend.scripts.visa_engine.activate_pack \
  backend/services/visa_engine/contracts/packs/rulepack-test-c1-tourism.signed.json \
  --actor operator.killswitch-proof --reason guilt-check-cli-level --current-sequence 1
```
```
INFO backend.services.visa_engine.bundle: verified rule pack 8a57d996-c7f2-5abc-9c31-4128a29ed848 sequence=1 kid=key-2026-07-test-1
INFO visa_engine.activate_pack: verified against trust store: kid=key-2026-07-test-1
Traceback (most recent call last):
  ...
  File ".../backend/scripts/visa_engine/activate_pack.py", line 293, in run
    validate_activation(
  File ".../backend/services/visa_engine/bundle.py", line 967, in validate_activation
    raise RulePackVerificationError(
backend.services.visa_engine.errors.RulePackVerificationError: candidate sequence 1 is not greater than the current sequence 1
```
Exit 1.

This confirms the real, operator-facing CLI — not just its internals — rejects a naive rollback and
accepts a legitimate forward-chained activation, using genuine Ed25519 signature verification
against a real checked-in pack.

### 2.4 What I could NOT re-verify (owner-gated, scripted)

I did not exercise `activate_pack.py --yes` (real DB write) against the **PRODUCTION** database, its
real two-role separation (`VISA_ENGINE_PACK_WRITER_DATABASE_URL` / `VISA_ENGINE_ACTIVATION_DATABASE_URL`
pointed at the actual `nuzantara-postgres` roles), or the full opt-in browser-to-Postgres smoke
(`backend/scripts/visa_engine/fullstack_smoke.py`, `VISA_ORACLE_FULLSTACK=1`) — the latter is
available in-repo but spins up Next.js + Playwright, which is out of scope for a kill-switch proof
and was not needed once the repository-layer and CLI-subprocess proofs above held. If Zero wants an
actual production emergency-rollback rehearsal (not required to close this ENFORCE-GATE item, since
the mechanism is now proven end-to-end on a real signed pack and real Postgres triggers, only the
specific prod credentials/roles are untested here), the scripted command is:

```
VISA_ENGINE_PACK_WRITER_DATABASE_URL=<prod pack-writer DSN> \
VISA_ENGINE_ACTIVATION_DATABASE_URL=<prod activation-executor DSN> \
PYTHONPATH=. python -m backend.scripts.visa_engine.activate_pack \
  <path to a freshly re-signed, higher-sequence pack whose previous_payload_sha256 chains from
   the CURRENT prod head — never a stale/old signed bundle> \
  --actor operator.<name> --reason <opaque-token> \
  --current-sequence <current prod head sequence> \
  --current-payload-sha256 <current prod head payload_sha256 hex> \
  --yes
```
Expected output constituting proof: `activated rule_pack_id=... activation_id=...` on success; a
`FAIL`/`RaiseError` containing `rollback rejected` or `hash chain broken` if the target pack or the
supplied `--current-*` values are wrong. This is `operator[secret]`/`operator[credential]`
territory (real prod DSNs) and not something this session should or can obtain — surfaced, not
executed.

---

## 3. Known limitation — Postgres version delta

Local Postgres was `17.10` (Homebrew, M5's existing dev instance — `postgresql@17` LaunchAgent,
already running before this session started). CI's visa_engine integration jobs run
`postgres:15` (confirmed: `.github/workflows/tests.yml:501,1385`,
`scripts-tests-sweep.yml:97`, `intel-router-tests.yml:30`, `fly-deploy.yml:36`). No Docker was
available in this environment to spin up a matching `postgres:15` container (`docker` not found).

I judge this delta **low-risk to the conclusions above**, for a stated reason, now confirmed rather
than merely argued: the repository's own code is explicitly version-aware where it matters —
`_supported_table_privileges()` in both `activate_pack.py` and `replace_activation_set.py` branches
on `server_version_num >= 170000` to add the PG17-only `MAINTAIN` privilege to its checked set,
direct evidence the authors already accounted for the 15-vs-17 boundary at exactly the layer this
proof exercises (privilege introspection). The anti-rollback SQL itself (triggers, `tstzrange`,
`EXCLUDE USING gist`, `SECURITY DEFINER` functions) uses no PG16/17-only syntax found while reading
migrations 250/251/253/254/267 in full. This report's own adversarial review (Codex gpt-5.6-sol
xhigh, see below) was specifically briefed to try to find a PG15/17 divergence risk in this
mechanism and reported none, having checked the same primitives — triggers,
`session_replication_role`, `pg_advisory_xact_lock`, ranges/`range_agg`, `SECURITY DEFINER`/
search_path/privileges — against both versions' documented behavior. That is a genuine
independently-checked non-finding, not merely this report's own author reasoning about its own
work — the environment delta is disclosed, and the conclusion above it stands on two independent
passes, not one. The one thing that would raise this from "checked twice, no divergence found" to
"measured directly" is still what it was: `TEST_DATABASE_URL` pointed at a `postgres:15` Docker
container (`docker run -p 5433:5432 -e POSTGRES_PASSWORD=test -e POSTGRES_USER=test
public.ecr.aws/docker/library/postgres:15`), same commands as §2.2 — available if Zero wants it,
not required to close this ENFORCE-GATE item.

Separately: the local role `nuzantara` (CI's default) does not exist on this M5 Postgres instance
(only `balizero` and `test`, both superuser) — I used `test` throughout, which is a benign
substitution (both are local superusers on a throwaway/xdist-cloned DB) but is a deviation worth
naming plainly rather than silently.

## Adversarial review

**This section describes an actual cross-family review that happened, not a self-review label
attached after the fact.** After the first version of this report was committed and opened as
PR #4616, a real adversarial refutation was run against it: **Codex gpt-5.6-sol at `xhigh` effort**,
briefed to attack six specific axes — (1) does the PACK-rollback proof actually verify a restored
pack cryptographically and functionally, or only its ledger bookkeeping; (2) is the "no code path
anywhere" claim actually unscoped/false; (3) is the MODE-switch claim actually product-wide or only
backend; (4) are the migration citations current; (5) does the report's own provenance stay true
after landing; (6) is there a real PG15/17 semantic divergence risk in the primitives used. The
verdict was **DO-NOT-SHIP**, with six findings, two of them severity P1 (one of those effectively
FATAL to the report's central pack-rollback claim as originally written). All six were real; none
were rejected; every fix below is a substantive change, not a wording patch:

- **P1 (FATAL) — the pack-rollback proof only proved ledger bookkeeping.** The original
  `test_zzz_killswitch_rollback_proof.py` built its "restored" pack C using
  `test_repository.py`'s `_pack_hash()` (a documented non-real placeholder — 32 identical bytes,
  its own docstring says so) and a random-UUID `signature`, then checked only
  `repo.load_active_rule_pack()` — a DB read. It never called `verify_rule_pack`,
  `build_compiled_pack`, or the real evaluator, so it never actually proved a restored pack is
  cryptographically verifiable, compiles, or reproduces the original's decisions. **Fixed**: the
  proof now signs real Ed25519 envelopes over the real evaluatable TEST pack and drives
  `evaluate_path.run_evaluation()` unmocked end to end, asserting real decision equality between
  the original and the restored pack, and a real decision DIFFERENCE for the intervening bad
  deploy — see the rewritten §2.2 above, run and observed this session, real SHAs and UUIDs
  included.
- **P1 — the ENFORCE-GATE LIVE STATE entry overclaimed before the above was true.** Flagged and
  held: the LIVE STATE entry in `.agents/skills/visaoracle/SKILL.md` and the ENFORCE-GATE bullet
  were not touched again until the real proof above existed and passed. See that file's own
  history for the corrected wording.
- **P2 — the MODE-switch claim was stated as a product-wide invariant when it is backend-only.**
  The frontend's `resolveVisaOracleMode()` fails OPEN to `"ENGINE"` on unset/invalid outside a test
  build — read directly at `runtime-mode.ts:21-32`, confirmed real, not a false alarm. **Fixed**:
  §1.1 and the summary verdict now scope the claim to the backend resolver and name the frontend
  asymmetry explicitly, including why it is not (currently) exploitable on its own.
- **P2 — the "no code path anywhere" pack-rollback claim was an unscoped absolute, plus a citation
  pointing at a superseded migration.** `session_replication_role=replica` or a table-owning role
  can bypass an ordinary trigger; this report's own test suite (`test_repository.py:1316`) proves
  the direct-disable form is practicable. Migration 250 only created the trigger function's
  original body; migration 253 replaced it twice and is the live definition. **Fixed**: §2.1 now
  scopes the claim to the intended executor role under normal trigger/replication conditions, cites
  253 as authoritative, and states the privilege-separation reason the scoped claim still holds
  operationally.
- **P3 — the report's own provenance paragraph was self-contradicting once committed.** "No commit,
  no push" was true when written, false the instant the file landed in a commit, and was never
  updated. **Fixed**: the mandate section now points at PR #4616 and the branch name instead of a
  self-referential SHA, with an explicit note not to hardcode a commit hash that a future amendment
  to this same file would immediately stale out.
- **P3 (non-finding, independently confirmed) — no real PG15/17 semantic divergence.** Codex was
  specifically asked to find one and checked the actual primitives (triggers,
  `session_replication_role`, `pg_advisory_xact_lock`, ranges/`range_agg`, `SECURITY
DEFINER`/search_path/privileges) against both versions' documented behavior. None found — §3 above
  now states this as a confirmed, doubly-checked conclusion rather than a hedge.

**What survived intact, stated plainly rather than only listing what broke**: the MODE-switch
*backend* mechanism and its proof (§1) were attacked on exactly the axes that would matter — unset/
empty/invalid/casing/whitespace handling, whether anything reaches `ENFORCE` unintentionally, and
whether OFF genuinely touches zero I/O — and held without a single required change; the CLI-
subprocess proof in §2.3 (real signature verification, real checked-in signed artifact, dry-run
zero DB access) was reviewed and not challenged. Both are exactly as strong as originally
described. The reviewer's own framing, worth repeating rather than softening: the MODE half of this
work survived a serious attack intact because it had actually been done properly; the PACK half's
first version had not been, and this rewrite is the actual fix, not a rebuttal of the finding.

Two independent verification passes now stand behind this report: this session's own re-execution
of every command in it, and Codex's adversarial pass against the resulting artifact. Neither
alone would carry the weight both carry together — generator≠grader (CLAUDE.md §6): the same
session that produced the first flawed proof could not be the one to certify it correct, and did
not; a genuinely independent review, on fresh context, found what self-review had missed.

This file and its two companion scripts (`2026-08-23-killswitch-mode-proof.py`,
`2026-08-23-killswitch-pack-rollback-proof-test.py`) are committed as part of PR #4616 — see the
provenance note at the top of this report for how to find the current head SHA rather than reading
a stale one off this paragraph.

