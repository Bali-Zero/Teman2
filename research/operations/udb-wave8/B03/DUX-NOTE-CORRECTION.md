# DUX-NOTE-CORRECTION — B03 (the single permitted correction)

Everything below was observed by the Dux on Mini in this worktree on 2026-10-15. State only what these
observations prove. Edit only files under `research/operations/udb-wave8/B03/`.

## Observed test results (pre-commit diagnostic run, receipts in `dux-requests/RECEIPTS.json` + `.out`)
- DUX-REQ-B03-10 (unittest): FAILED, exit 1, "Ran 0 tests": `setUpClass` raised `PinVerificationError`
  (SHA-256 mismatch for `.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json`: pinned `94fe3190…`,
  on disk `e8a35c24…`). Raised in `verify_pins` via `build_census_rows`.
- DUX-REQ-B03-11 (adapter run): FAILED, exit 1, same `PinVerificationError`. No artifact was produced.
- DUX-REQ-B03-12 (index join): OK, exit 0: `matched_index_nodes: 10292 of 10299` — the index `source_id`
  is `sha256(path)[:24]` of `git ls-files` paths.
- DUX-REQ-B03-13 (cross-host LaunchAgents/crontab hashing): NOT admitted, deferred. Remove it from the
  requests or mark it DEFERRED; do not claim anything from it.

## Observed on-disk sha256 (Dux `shasum -a 256`, the only valid pin values)
| path | sha256 |
|---|---|
| `.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json` | `e8a35c2404520884f58c7d2801e647c743b86cf69707591f1a1c828bab97722e` |
| `.agent-receipts/udb-wave8-inputs/ASTRA-ADVICE.md` | `72f349f285bc681013b67ad1d25cdad54d3d4478080dc1f5e7e0512dd9e1fdb8` |
| `.agent-receipts/udb-wave8-inputs/FINAL-BLUE-GATE.json` | `b9d284e1dba9e87ad340cbd4076061e7a35a93fdf8bc1c910340e6099d711856` |
| `.agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json` | `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d` |
| `.agent-receipts/udb-wave8-inputs/REPORT.md` | `d289fb8660a6bd634cb7785fef3a8c0b47ceefe82463d134c4bbf66dc0563e9a` |
| `.agent-receipts/udb-wave8-inputs/STATE.json` | `caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4` |
| `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` | `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118` |
| `.agent-receipts/udb-wave8-inputs/research-lines.csv` | `1b3d1f31df997500975311d3f49cbd3a50346c2fa7d27f45ff808c7203654c10` |
| `.agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json` | `91e6bac9c91181a2b3aa3f6cd1dc6585671c18ce90cb887444229a1a17a084e7` |
| `.agent-receipts/udb-wave8-inputs-dux/prior/census-20261012-0454/source-index-enhanced.json` | `9f90a66733d63b9183ad21beeca6b84b78db0b243e41aeb9a1d7bc5ab89363cd` |
| `.agent-receipts/udb-wave8-inputs-dux/prior/census-20261012-0454/jobs-pro.json` | `4f7bf4e90c1aad7f47ca04cd80ca8fe304cf2affae56bbc68fca080185986703` |
| `.agent-receipts/udb-wave8-inputs-dux/prior/census-20261012-0454/jobs-mini.json` | `99bff7025a5cfecd5b4413c8f9b19e921f884b6f80890a9e3fffc7342c2306e2` |
| `.agent-receipts/udb-wave8-inputs-dux/prior/census-20261012-0454/jobs-M5.json` | `b53d5b487c7da69e732e4bd31a57a422f655871b11b738f9ef136f3f596c7198` |
| `.agent-receipts/udb-wave8-inputs-dux/prior/advance-20261014-0535/GITHUB-WORKFLOW-METADATA.json` | `115e40a4d82a89b11301ef17b7820ecf4ee94e0f51f4e8a3e94ad91fbb729a29` |

`INPUT-MANIFEST.json` top-level keys are `files` and `scope` (there is no `inputs` key); its `files` map
agrees with the on-disk sha256 of all 7 frozen inputs (Dux-checked).

## The correction (one pass, inside the B03 report dir)
1. Replace all pins with the values above; read the manifest key `files`, never `inputs`.
2. Pin the 5 supplementary priors; fail closed if one is missing or mismatched.
3. Remove the `or bool(canonical_id)` tautology in the duplicate pre-image check.
4. Repository-static rows use `evidence_timestamp` `2026-10-15T07:06:22Z` plus `STATIC_SOURCE_ONLY` in
   `unknowns` (CONTRACT-CONVENTIONS); `03:28:00Z` is not an evidence time.
5. The LEAD-DELTA row uses store_id `unknown:unknown:unknown` plus `STORE_ID_PROPOSED:pg:mini:local`
   (and a specific token) in `unknowns`; B04 has not catalogued `pg:mini:local`.
6. RESULT.json: exactly the 7 required keys, `block_closed: false`; tests `PENDING_DUX_EXECUTION`; no
   count, pin or "verified"/"enforced" claim that no Dux execution produced.
7. PR_BODY.md: branch `agent/mini-pro2/db/udb-b03-census`; pins as above; a `Bites:` line whose
   observation is the Dux re-run of DUX-REQ-B03-10/11 (not yet observed — say so).
8. Keep DUX-REQ-B03-10/11/12 as the post-correction requests (the Dux re-runs them with `-I -B`).
9. Do not touch RUN-*/SESSION*.json; the Dux preserves them outside the commit.
