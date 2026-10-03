**REWORK**

1. **MED — Relevance still misses pytest configuration and ancestor fixtures.**  
   Concrete line: the regex beginning `'^(scripts/wa-mirror-attention-telegram\.py|…'`.

   It includes `conftest.py` and `scripts/tests/conftest.py`, but omits **`scripts/conftest.py`**, which can affect these tests. It also omits configuration files under `scripts/` and `scripts/tests/` that pytest can discover. A PR adding such a file can change collection or execution while receiving sentinel success.

   Include ancestor `conftest.py` paths and pytest configuration paths at those directory levels. Whether those files currently exist is **not shown**; additions must also trigger the gate.

2. **LOW — Required-test presence uses names without suite identity.**  
   Concrete line: `names = {c.get("name") for c in cases}`.

   Another collected testcase with the same name can satisfy a missing real-PG test’s requirement. Check `(classname, name)` pairs using the expected real-PG suite identity. Actual declarations and their JUnit identities are **not shown**; parametrized tests also normally have parameter suffixes in their names, so the four literal expectations need to match the actual report.

Round-1 disposition:

| Item | Status           | Assessment                                                                                                              |
| ---- | ---------------- | ----------------------------------------------------------------------------------------------------------------------- |
| R1-1 | **RESOLVED**     | Standalone `git diff` under `set -e` fails the step on git errors; no SIGPIPE-producing pipeline.                       |
| R1-2 | **RESOLVED**     | `--no-renames` exposes both removed and added paths.                                                                    |
| R1-3 | **RESOLVED**     | Structured skip detection and four-name presence enforcement replace terminal parsing. Identity limitation noted above. |
| R1-4 | **RESOLVED**     | `[^/]*` matches the shell glob’s zero-or-more behavior.                                                                 |
| R1-5 | **NOT RESOLVED** | Missing ancestor fixture and nested configuration paths.                                                                |
| R1-6 | **RESOLVED**     | Both requested event types are included.                                                                                |

Other checks: YAML block indentation correctly preserves the Python body and unindented heredoc terminator. `PYTEST_ADDOPTS: ""` supplies an empty environment value. GNU `grep -z` anchors operate per NUL-delimited record. `edited` adds runs for unrelated PR metadata edits, but this workflow contains no action that creates an edit loop. `changed.z` and `junit.xml` remain in the workspace; no resulting defect is demonstrated here. The no-path-filter PR/merge-group sentinel structure is sound.
