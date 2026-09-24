# JEV repository context selector pilot — Phase 0 ledger

**Mandate:** `jev-context-selector-pilot-20260925`

**Mission:** BLUE, Gear 2, external builder prepare-only

**Phase boundary:** Phase 1 evaluation or workflow integration remains unauthorized
until an explicit owner GO. No push, PR open, merge, arm, deploy, publish or client send
is part of this ledger.

## Frozen inputs

| Input | SHA-256 | Observation |
| --- | --- | --- |
| `research/operations/2026-09-24-jev-coding-optimization-audit.md` | `34cfaf707de5012fdab524c5dfb56a1a85b86e33a105465653e23c6859eac584` | Matches the Phase 0 contract. |
| `research/operations/2026-09-24-jev-coding-live-probe.json` | `04027fb75ebb96c12fde5e85253fbe57d12c6b57ad67e5116bfc438df365f544` | Matches the Phase 0 contract. |
| `research/operations/fixtures/jev-context-selector-eval-v1.json` | `52dfe533a3c09900edb1c680f8f996349f0761957ebfdd9a06c8e478424e4f02` | 36 unique synthetic repository tasks across eight required strata; all labelled paths are Git-tracked. |
| `research/operations/2026-09-24-jev-context-selector-phase0-metrics.json` | `397ddc9fc39c67748373778b53f3413fd3fb54f94d7b29c52cdb2e492ad40759` | Ten post-review-fix rows: five arm B and five cold arm C runs. |

The frozen repository revision for the fixture and live dry run is
`92526ca8394ba746cd318a72f1ef2256e177b406`.

## Implementation observations

- `scripts/typesafe_client.py` preserves the answers-only `ask()` API and adds explicit
  attempted/received/schema/abstention/failure/model/usage/latency/attempt telemetry.
  A shared monotonic deadline and HTTP-attempt budget govern semantic calls. The
  open-plus-read operation is wall-clock bounded, late responses are discarded, and
  invalid JSON/schema responses are not retried.
- `scripts/lint_paid_llm_entity.py` keeps the incumbent `grep OR JEV` composition and
  reports attempted, response, schema-valid, abstained, failed and judged counts
  separately.
- `scripts/codex_task_usage.py` uses native incremental `token_usage_record.usage`, an
  explicit root session and `root_turn_id`, explicit descendant links, response-id
  deduplication and unknown-not-zero aggregation. Malformed lines, non-object records
  or non-object token payloads in an included stream make the aggregate explicitly
  incomplete and all token totals unknown.
- `scripts/jev_context_selector.py` accepts only safe regular Git-tracked repository
  files, makes applicable `AGENTS.md` and quoted-symbol definitions unconditional,
  uses entity boundaries for explicit paths, and records index/worktree provenance.
  Fixture selection material is the canonical id-plus-task record only. The exact
  cache accepts successful non-empty schema-valid selections only, never source,
  response bodies, abstentions or transient failures. C visibly falls back to B.
- The selector is an explicit CLI/helper only. No hook, default workflow, daemon or
  production integration was installed.

## RED to GREEN record

The initial focused command was:

```text
PYTHONPATH=scripts /Users/balizero/.local/share/mise/installs/python/3.11/bin/python3 -m pytest -q scripts/tests/test_typesafe_client_telemetry.py scripts/tests/test_codex_task_usage.py scripts/tests/test_jev_context_selector.py
```

After correcting an initial test-path collection error, the contract run was RED with
`2 failed, 12 passed`: unavailable telemetry and malformed-envelope failure semantics
did not yet match the frozen contract. The implementation then reached GREEN. The
final acceptance run, including symlink guilt, nested-`AGENTS.md`, safe-cache,
semantic omission, strict wall deadline, fixture isolation, symbol protection,
path punctuation and incomplete-rollout cases, reports `222 passed`.

## Five-task repository-only dry run

The live run used fixture tasks `JCS-001`, `JCS-024`, `JCS-028`, `JCS-029` and
`JCS-033`, arm B then arm C serially, a 6,000 estimated-token packet budget, a
1.5-second semantic deadline, two shared HTTP attempts and a cold cache.

Arm C made exactly five authorized repository-only TypeSafe calls after fixture
isolation. All five produced readable, schema-valid responses in one HTTP attempt;
there were no endpoint abstentions or failures and no cache hits. Four selections were
non-empty. `JCS-033` returned usable all-false answers, so the selector visibly fell
back to B with reason `abstention`. Vendor-reported usage was 38,110 input and 4,155
output tokens. Observed semantic latency was 1,039.307 ms minimum, 1,086.901 ms median
and 1,255.622 ms maximum. Aggregate packet estimates were 29,490 tokens for B and
12,598 for C, a diagnostic delta of -57.28%.

No coding outcome was measured. The order was not randomized, packet counts are byte
estimates rather than Codex receipts, no live cache-hit run occurred, and one fallback
in five calls does not estimate a production fallback rate. Therefore these observations
prove plumbing and fail-safe behavior only and do not authorize Phase 1.

The later path-boundary and mandatory-symbol-excerpt fixes do not change the semantic
request material for these five tasks. A local arm-B replay compared selection-input
bytes/band, candidate count, selected count and packet estimate against the metrics
artifact for all five tasks and returned `all_match=true` with no mismatches. No
additional TypeSafe call was made.

## Native Codex usage snapshots

The builder segment is rooted at session
`01a0d339-18b0-70c3-b6d9-06bad42ff648`, turn
`01a0d339-1921-7311-876b-a7b6c94a2c04`: 55 receipts, 167,057 uncached input,
6,339,840 cached input, 56,507 output and 18,266 reasoning-output tokens.

The completion-audit segment is rooted at session
`01a0d32e-5a4f-7752-9656-d2587eb0fea3`, turn
`01a0d341-d616-7d23-b9b2-516493eae7f6`: 64 receipts, 99,596 uncached input,
5,349,120 cached input, 36,538 output and 18,586 reasoning-output tokens at the
pre-review snapshot.

Both snapshots have zero missing-field receipts and zero duplicate receipts. The context
bridge continuation does not carry a native `parent_thread_id`, so the two independent
root segments are reported separately; this ledger does not invent a cross-session
aggregate.

Exact accounting commands:

```text
python3 scripts/codex_task_usage.py --root-session-id 01a0d339-18b0-70c3-b6d9-06bad42ff648 --root-turn-id 01a0d339-1921-7311-876b-a7b6c94a2c04
python3 scripts/codex_task_usage.py --root-session-id 01a0d32e-5a4f-7752-9656-d2587eb0fea3 --root-turn-id 01a0d341-d616-7d23-b9b2-516493eae7f6
```

## Verification commands

The final candidate is checked with these exact local commands:

```text
PYTHONPATH=scripts /Users/balizero/.local/share/mise/installs/python/3.11/bin/python3 -m pytest -q scripts/tests/test_typesafe_client_telemetry.py scripts/tests/test_codex_task_usage.py scripts/tests/test_jev_context_selector.py scripts/test_lint_paid_llm_entity.py scripts/tests/test_typesafe_client_pin.py scripts/tests/test_vendor_authorization_fence.py
/Users/balizero/.local/bin/ruff check scripts/typesafe_client.py scripts/lint_paid_llm_entity.py scripts/codex_task_usage.py scripts/jev_context_selector.py scripts/tests/test_typesafe_client_telemetry.py scripts/tests/test_codex_task_usage.py scripts/tests/test_jev_context_selector.py
/Users/balizero/.local/share/mise/installs/python/3.11/bin/python3 -m compileall -q scripts/typesafe_client.py scripts/lint_paid_llm_entity.py scripts/codex_task_usage.py scripts/jev_context_selector.py
jq -e '.selector_policy_version == "jev-context-selector-phase0-v2" and (.rows | length == 10) and (.aggregates.arm_c.schema_valid == 5) and (.aggregates.arm_c.fallback == 1)' research/operations/2026-09-24-jev-context-selector-phase0-metrics.json
git diff --cached --check
```

The verification result and independent review disposition are recorded below after the
candidate fingerprint is frozen.

## Independent BLUE review

Fresh Claude OAuth Opus 5.5 xhigh review session
`3c8203b1-7b49-451c-9324-5f9af358d445` returned `FAIL` before the fixes above. It found
two high, three medium and three low defects: all-false fallback naming, quoted-symbol
coverage beyond the content-hit cap, fixture-label packet leakage, failure caching,
silent malformed-rollout records, path-substring overmatch, non-wall-clock read timeout,
and ambiguous index/worktree provenance. Each finding now has a focused regression test
or explicit provenance field. A fresh post-fix BLUE re-review remains required before
the candidate can be handed off.

Fresh scoped re-review session `ea168a95-9bb9-47c7-8aec-3c662ede3832` (model
`claude-opus-5-5`, first-party OAuth, xhigh, read-only sandbox) returned `FAIL` with two
medium and two low findings. A complete path followed by sentence punctuation or
prefixed with `./` was not treated as explicit, and a deeply located quoted-symbol
definition could be protected while its line was absent from the bounded excerpt. The
contract now specifies both cases; focused regressions cover punctuation/`./`, a
definition after more than 12 generic definition hits, TS definition forms, and an
included-rollout read error. A direct local replay also proves fixture task `JCS-006`
protects `scripts/ci/required_context_map.py` for reason `explicit_path`. A fresh final
BLUE review of the corrected staged candidate remains required.

Fresh final review session `d41b230d-57d5-4d25-bf9e-6e2adeeb2ff2` (model
`claude-opus-5-5`, first-party OAuth, xhigh, read-only sandbox) returned `FAIL`.
Path punctuation and leading `./` were accepted, but the quoted-symbol hard stop still
failed: multiline `^\s*` may start a definition match on preceding blank lines, so a
window derived from `match.start()` can omit the actual definition while treating the
symbol as found. The regression used TypeScript interface lines that did not exercise
the generic-hit cap, so it did not detect that gap. The review also recorded low-severity
follow-ups for invalid-UTF-8 rollout lines, less common TypeScript declarations and the
wording of source-hash provenance.

This is the third RED for the same quoted-symbol protected-evidence cause: the initial
candidate-cap miss, the first excerpt omission, and the remaining multiline-offset
omission. Builder Contract rule 1 therefore suspends the candidate instead of allowing
a fourth fix round. A future, newly specified mandate must define and test line indexing
from the captured identifier (`match.start(1)`), horizontal-only leading whitespace,
newline semantics and a genuine post-cap definition before implementation resumes.

## Stop decision

`SUSPENDED`: local verification is green, but independent BLUE acceptance is red on
missed protected evidence, an explicit hard stop in the Phase 0 contract. No commit,
push, PR open, merge, arm, deploy or Phase 1 work is authorized from this candidate.

## Owner-authorized repair mandate

The owner subsequently issued an explicit `continua` instruction. That authorization
opens the narrow repair mandate `jev-context-selector-pilot-repair-20260925`, frozen in
`docs/specs/2026-09-24-jev-context-selector-pilot-repair.md`. It authorizes only the
captured-identifier/horizontal-whitespace protected-symbol repair and the unusable Noul
answer abstention repair, plus their tests, verification and fresh independent BLUE
review. The Phase 1 boundary and every shipping prohibition remain unchanged.

The focused repair command first returned `2 failed`: the protected definition line
was absent from `excerpt_lines`, and `{"q":{}}` reported `abstained=false`. After the
two scoped fixes, the same command returned `2 passed`. No TypeSafe network call or
metrics regeneration occurred.

Repair status: focused GREEN; full verification and fresh independent BLUE review
pending on the final staged candidate.

### Repair verification and review

The staged repair tree `c2235fe35c204f465a17ba4a606dc49c06856410`
received a successful context-bridge verification receipt with fingerprint
`8b1a889a04cf55ddd34afaba34f0a002441ad321ba5657e2a0fbec82b73f6aa5`.
All seven commands exited zero: the full Phase 0 acceptance suite, Ruff,
compileall, the metrics-shape assertion, the four frozen SHA-256 assertions,
`git diff --cached --check`, and the unstaged-diff check.

The fresh independent BLUE Codex re-review of that tree returned `PASS` with no
findings. It reproduced the post-cap protected definition at line 26 in both the
manifest and packet, reproduced the empty requested Noul entry as
`schema_valid=true`, `abstained=true`, `fallback=true`, `failure=null`, and
confirmed that frozen metrics and GROUND inputs were unchanged.

Repair status: `PREPARED / PASS`. Phase 0 is ready for Dux/gate handoff. Phase 1
remains unauthorized, and this external builder still has no authority to push,
open a PR, merge, arm, deploy, publish or send client-facing material.
