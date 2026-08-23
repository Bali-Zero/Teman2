---
date: 2026-08-23
domain: visa
client_case: none — internal engineering/governance artifact for the Visa Oracle ENFORCE-GATE
sources:
  - apps/backend-rag/backend/services/visa_engine/evaluate_path.py (HEAD 868b62322)
  - apps/backend-rag/backend/services/visa_engine/enums.py
  - apps/backend-rag/backend/services/visa_engine/bundle.py (validate_activation)
  - apps/backend-rag/backend/scripts/visa_engine/activate_pack.py
  - apps/backend-rag/backend/scripts/visa_engine/replace_activation_set.py
  - apps/backend-rag/backend/db/migrations_v2/250_visa_engine_core.sql
  - apps/backend-rag/backend/db/migrations_v2/251_visa_activation_writer.sql
  - apps/backend-rag/backend/db/migrations_v2/267_visa_replace_activation_set.sql
  - apps/backend-rag/backend/tests/services/visa_engine/test_evaluate_endpoint.py
  - apps/backend-rag/backend/tests/services/visa_engine/test_activation_writer.py
  - apps/backend-rag/backend/tests/scripts/visa_engine/test_activate_pack.py
  - apps/backend-rag/backend/tests/scripts/visa_engine/test_replace_activation_set.py
---

# Visa Oracle kill-switch — rollback proof (2026-08-23)

**Mandate**: produce a current, independently reproducible rollback proof for the two Visa
Oracle kill switches named in the ENFORCE-GATE (`.agents/skills/visaoracle/SKILL.md`), without
touching production in any way. Worktree: `.worktrees/backend-rag-visaoracle-killswitch-proof-0823`
(created via `scripts/agent_start.py --lane backend-rag --task-id visaoracle-killswitch-proof-0823`),
HEAD `868b62322df0be7fddd9cf48ebdb1c01f50b7f8d` (2026-08-23 05:01:35 UTC). No commit, no push, no
PR opened per instruction — this file and its two companion scripts (below) are uncommitted in
the worktree.

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

1. **The MODE switch** (`VISA_ENGINE_EVALUATE_MODE`) is a **fail-safe, read-fresh-per-call**
   three-state gate (`OFF|SHADOW|ENFORCE`) that determines whether an evaluate response is
   authoritative. **PROVEN LOCALLY, both directions, same facts, same pack.**
2. **The PACK rollback** (`activate_pack.py` / `replace_activation_set.py` / the
   `visa_replace_activation_set`/`visa_activate_rule_pack` SQL functions) is a
   **strictly-forward, hash-chained, append-only ledger with a triple-redundant anti-rollback
   gate** (Python pre-check, SQL trigger, and — for the multi-segment path — the SQL function's own
   explicit chain-walk). **A pack can never be reactivated at a lower-or-equal sequence number, by
   design, at every layer.** The system's actual "rollback" mechanism is: re-sign the desired
   content as a NEW pack at the next sequence number, chained from the true current head, and
   activate that. **PROVEN LOCALLY, both the guilt case (naive reactivation rejected) and the
   innocence case (legitimate content-restore succeeds, exactly one open activation, no temporal
   gap), at two levels: the DB/repository layer AND the actual `activate_pack.py` CLI subprocess.**

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

2. **SQL trigger**, `reject_visa_activation_insert()` / `visa_activation_insert_guard`
   (migration 250, `250_visa_engine_core.sql:380-440`): fires on every INSERT into
   `visa_ruleset_activations`, **independently re-derives the true current head** via `SELECT
p.sequence, p.payload_sha256 ... ORDER BY p.sequence DESC LIMIT 1` over the live table — it does
   **not** trust anything the Python layer or the CLI operator claimed. Rejects `pack.sequence <=
head.seq` (message: `"visa activation rollback rejected: pack sequence % <= prior activated
sequence %"`) and a broken hash chain (`"visa activation hash chain broken"`). **This is the real
   enforcement layer** — a lying/stale `--current-sequence` CLI argument cannot get a rollback past
   this trigger.

3. **The `visa_replace_activation_set` function itself** (migration 267, multi-segment path) does
   its OWN explicit forward chain-walk (`267_visa_replace_activation_set.sql:150-180`) in addition
   to relying on the same insert trigger — belt-and-suspenders for the batch case.

**Consequence, stated plainly: there is no code path anywhere in this system that can reactivate a
pack at a sequence number less than or equal to the current head.** This is enforced at the SQL
layer independent of the Python layer, so it cannot be bypassed by a buggy or malicious CLI
argument. **"Rollback" in this system therefore does not mean "go back" — it means "author a NEW
pack, at the next sequence number, whose content restores the desired prior behavior, chained
forward from the true current head, and activate that."** This is exactly the pattern the
2026-08-08 Cameroon/Guinea Calling Visa correction used in production (LIVE STATE:
"re-signed identical content as seq 3... retroactive").

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

**My own targeted scenario** (companion file:
`research/visa/2026-08-23-killswitch-pack-rollback-proof-test.py`, a temporary pytest test —
written into `apps/backend-rag/backend/tests/services/visa_engine/`, run, then removed from the
tests directory; the copy in `research/visa/` is the permanent record). It builds the exact
"emergency rollback ceremony" end to end, reusing this directory's own `repo`/`visa_schema`
fixtures and `test_repository.py`'s pure builder helpers (no new mechanism invented):

1. Activate pack A (sequence 1, content `"RULES_V1_GOOD"`).
2. Activate pack B (sequence 2, content `"RULES_V2_BAD"`, chained from A's hash) — A closes exactly
   when B opens (adjacent, no gap).
3. **GUILT**: attempt to reactivate pack A verbatim (sequence 1 ≤ head sequence 2) → **rejected**.
   B's activation is verified untouched afterward.
4. **INNOCENCE — the legitimate rollback**: insert pack C (sequence 3, content
   `"RULES_V1_GOOD"` — i.e., the SAME rules as pack A — chained from **B's** hash, the true current
   head) and activate it → **succeeds**.
5. Verify: B's `system_period` closes exactly when C's opens (no gap); exactly ONE row has an open
   `system_period`; that row is C; `load_active_rule_pack()` (the real engine read path) resolves
   to C's payload, whose content equals pack A's original content, at `sequence=3` — **the ledger
   never moved backward, but the applicant-facing ruleset was genuinely restored.**

**Command and result**:
```
PYTHONPATH=. python -m pytest \
  backend/tests/services/visa_engine/test_zzz_killswitch_rollback_proof.py -n 1 -v -rA
```
```
PASSED backend/tests/services/visa_engine/test_zzz_killswitch_rollback_proof.py::test_emergency_rollback_ceremony_end_to_end
```
Captured stdout:
```
ROLLBACK CEREMONY PROOF HOLDS: activation_a=ffe6d186-e7f9-4472-83f5-335a9821fa30
activation_b=07580d94-40c3-4f8f-8c32-3cfecfa00458 activation_c=b157d56e-8f13-4d3f-b733-f85408d99fe2
-- naive reactivation of pack A (seq 1) was rejected while B (seq 2) was head; re-signing A's
CONTENT as pack C (seq 3, chained from B's hash) was accepted; final state: exactly 1 open
activation (C), B/C system_period adjacent with no gap, engine reads sequence 3 whose payload
content equals the original sequence-1 ruleset.
```
Captured log (the guilt step's real DB error, unaltered):
```
ERROR VisaEngineRepository:base_repository.py:50 fetchrow failed: visa activation rollback
rejected: pack sequence 1 <= prior activated sequence 2 | query=SELECT
public.visa_activate_rule_pack($1, $2, $3) AS activation_id
```

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

I judge this delta **low-risk to the conclusions above**, not zero-risk, for a stated reason: the
repository's own code is explicitly version-aware where it matters —
`_supported_table_privileges()` in both `activate_pack.py` and `replace_activation_set.py` branches
on `server_version_num >= 170000` to add the PG17-only `MAINTAIN` privilege to its checked set,
which is direct evidence the authors already accounted for the 15-vs-17 boundary at exactly the
layer this proof exercises (privilege introspection). The anti-rollback SQL itself (triggers,
`tstzrange`, `EXCLUDE USING gist`, `SECURITY DEFINER` functions) uses no PG16/17-only syntax I
found while reading migrations 250/251/253/254/267 in full. I did not independently confirm this on
a real `postgres:15` instance — that would be the one thing worth re-running if Zero wants
maximum rigor before flipping any doctrine on the strength of this proof; concretely: `TEST_DATABASE_URL`
pointed at a `postgres:15` Docker container (`docker run -p 5433:5432 -e POSTGRES_PASSWORD=test -e
POSTGRES_USER=test public.ecr.aws/docker/library/postgres:15`), same three `pytest -n 1` commands
in §2.2.

Separately: the local role `nuzantara` (CI's default) does not exist on this M5 Postgres instance
(only `balizero` and `test`, both superuser) — I used `test` throughout, which is a benign
substitution (both are local superusers on a throwaway/xdist-cloned DB) but is a deviation worth
naming plainly rather than silently.

## Adversarial review

Self-reviewed against the two failure modes most relevant to this kind of proof: (a) did I actually
drive the real code path, or a stand-in for it? — for the MODE switch, `run_evaluation()` and
`resolve_evaluate_mode()`/`resolve_response_mode()` are called directly and unmocked; only the
DB/pack-verify/pack-compile I/O boundary is stubbed to a deterministic gold pack (the same
technique the suite's own reviewed tests use), and OFF is proven to touch zero I/O via a
hard-failing sentinel, not merely asserted. For the PACK rollback, the guilt/innocence proof runs
against a real Postgres instance with the real migrated triggers and the real
`SECURITY DEFINER` function — not a mock — and the CLI-subprocess proof in §2.3 adds real Ed25519
signature verification on a real checked-in signed artifact. (b) did I claim anything about
production I didn't verify? — §1.4 and §2.4 name exactly what was not re-verified live and hand
over exact, safe, non-destructive commands rather than asserting the mechanism "should" work in
production; the only production claim made (that the code-level MODE mechanism is unchanged since
the 2026-08-08 live drill) is backed by a `git log`/`git show` diff check, not inference.

No PR opened, no commit made, per instruction. This file and its two companions
(`2026-08-23-killswitch-mode-proof.py`, `2026-08-23-killswitch-pack-rollback-proof-test.py`) are
currently uncommitted in the worktree.

