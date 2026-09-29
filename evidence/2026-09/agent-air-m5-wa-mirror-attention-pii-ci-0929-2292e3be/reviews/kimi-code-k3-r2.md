• VERDICT: REWORK — driven by finding 1 (the R1-5 fix is incomplete: pytest honors config/conftest locations the relevance regex does not cover, so the corpus can still be neutered on a run=false green).

## Findings

**1. (MED) Relevance regex only pins ROOT-level pytest config — pytest also honors inifiles/conftest in `scripts/` and `scripts/tests/`.**
Concrete line: the `grep -zqE` pattern — anchored alternatives `conftest\.py|pytest\.ini|pyproject\.toml|setup\.cfg|tox\.ini` match only at repo root, and `scripts/tests/conftest\.py` is the only nested path covered.
Pytest determines rootdir/inifile by walking UP from the common ancestor of the args (`scripts/tests/test_wa_attention_*.py`): the FIRST `pytest.ini` / `[tool.pytest.ini_options]` pyproject / `[pytest]` tox.ini / `[tool:pytest]` setup.cfg found in `scripts/tests/`, then `scripts/`, then root wins. Conftests load from rootdir down through `scripts/conftest.py` and `scripts/tests/conftest.py`. So a PR adding `scripts/tests/pytest.ini` (e.g. `python_functions = nothing_matches`) or `scripts/conftest.py` (a `pytest_collection_modifyitems` deselect) matches NONE of the regex alternatives → `run=false` → sentinel success → check green with the corpus disarmed. The junit/must_run gate never executes because it only runs when `run=true`. This is exactly the R1-5 evasion class, one directory level down. Fix: extend the regex to `(^|/)(conftest\.py|pytest\.ini|pyproject\.toml|setup\.cfg|tox\.ini)$` (or at minimum cover `scripts/` and `scripts/tests/`), or pin pytest with `-c` to a known config and add `--confcutdir`/`--rootdir` so only intended files are honored.

**2. (LOW) junit `testcase/@name` includes parametrization brackets.** The `must_run` set does exact-match against `c.get("name")`; pytest emits `test_foo[pg16]` style names for parametrized tests. If any of the four named real-PG tests is parametrized, the gate is permanently red (fail-closed, so availability not soundness — but it would block every PR). Test files not shown, so unverifiable; suggest matching on `name.split("[")[0]`.

**3. (LOW) Artifacts left in workspace, no failure forensics.** `changed.z` and `junit.xml` are written to the workspace and never cleaned or uploaded. On a red run the junit is exactly what an operator needs; add `actions/upload-artifact` with `if: failure()`. Cosmetic.

**4. (LOW) `edited` trigger scope.** `edited` fires on title/body edits, not just base retargets — a few extra no-op runs per PR (relevance step exits green in seconds, so cost is negligible). No loop risk: the workflow never edits PRs. Acceptable as-is.

**5. (LOW) PG version selection.** `find ... | sort -V | tail -1` picks the NEWEST `/usr/lib/postgresql/*/bin` on the image, not necessarily 16. If the runner image ever ships two versions, the suite may run against an unexpected server. Suite's version tolerance not shown. Consider hardcoding `16` or asserting `"$pgbin" == /usr/lib/postgresql/16/bin`.

## Round-1 dispositions

- **R1-1 RESOLVED.** Diff is captured to `changed.z` in its own `set -euo pipefail`-checked command; no pipe, no SIGPIPE. Improvement beyond the ask: a git failure now fails the STEP (job red, fail-closed) rather than silently selecting `run=false`. `-z`, `--no-renames`, `core.quotepath=off` all present.
- **R1-2 RESOLVED.** `--no-renames` present; a rename-away reports the old path (and your local proof confirms run=true).
- **R1-3 RESOLVED.** `-o addopts=""` (overrides ini addopts), `-o xfail_strict=true`, `--strict-markers`, `PYTEST_ADDOPTS: ""` at step env (empty string parses to zero extra args — semantics are correct), junit gate fails on ANY `<skipped>` element (xfail is recorded as skipped; xpass under strict mode is a failure and exits pytest nonzero before the Python check — both paths red), and absence of the 4 named real-PG testcases catches deselects. Python check runs only after pytest succeeds, so a pytest crash → red via `set -e`. All fail-closed.
- **R1-4 RESOLVED.** `[^/]*` present.
- **R1-5 NOT RESOLVED (partial).** Root `conftest.py`/`pytest.ini`/`pyproject.toml`/`setup.cfg`/`tox.ini` and `scripts/tests/conftest.py` are covered, but `scripts/conftest.py`, `scripts/tests/pytest.ini`, `scripts/pytest.ini` and other ancestor-level inifiles pytest actually honors are not — see finding 1.
- **R1-6 RESOLVED.** `ready_for_review` and `edited` added; comment documents the retarget rationale.

## New-defect hunt results (checked, clean)

- **Heredoc/YAML indentation:** OK. The heredoc body and the `PY` terminator sit at the same indentation as the other `run:` block lines, so after YAML strips the block's common leading indent, `PY` lands at column 0 — valid for `<<'PY'` (no `<<-` needed), and the Python is all top-level statements so zero indentation is fine.
- **`grep -zqE` anchoring:** OK. With GNU grep `-z`, NUL is the record delimiter and `^`/`$` anchor to record boundaries; alternation + anchors are correctly parenthesized. No-match exit 1 is inside `if` so pipefail is not triggered.
- **merge_group handling:** OK. Non-PR path forces `run=true` (full corpus in the queue — matches the stated intent), `cancel-in-progress` correctly disabled for merge_group, concurrency group falls back to `github.ref`.
- **PATH propagation:** OK. The PG step writes `$GITHUB_PATH` and the pytest step runs after it; if `find` yields nothing, `"$pgbin/initdb"` → exit 127 → step red (fail-closed, not a silent skip).
- **Partial clone:** OK. `filter: blob:none` still fetches commits+trees; `--name-only` diff needs no blobs (and promisor lazy-fetch would cover it anyway). `fetch-depth: 0` gives the merge-base for `base...HEAD`.

Re-submit with the finding-1 regex fix (one line) and this is an ACCEPT.
