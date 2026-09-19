• ---
  seat: kimi/kimi-k3
  objective_sha256: 325ad09ef4863087b0f9b7be5428c91cf54ee0b9c0924f5e68361429909766e6
  facts_cited: [F4, F5, F6, F7, F8, F9, F10, F11, F12, F14, F15, C1, C2, C3, C4, C5, C6, C7, C9, C10]
  assumptions: 4
  ---

  ASSUMPTION 1: §5's "TP1 and kimi are live" is stale against §2's own measurement: every TP1 row is HTTP 429 quota-exhausted (F7's weekly bucket drained), while kimi's TIMEOUT carries a real version banner — slow, not dead (F8: the probe covers 1 of 16 seats). I plan with **kimi live, TP1 dead**.
  ASSUMPTION 2: the mandate-owning BLUE shipper is a Claude-on-OAuth session, quota-dead until 09:00 Asia/Makassar; everything before that is preparation (C4).
  ASSUMPTION 3: the interview AST is a DAG where each question is answered at most once per walk; the enumerator dedupes by decision-relevant fact vector, making the space finite and countable by machine.
  ASSUMPTION 4: synthetic personas only for live runs (C2) — already the brief's rule.

  ## Formation
  | role | seat | why (F ref) | substitute if dead (F8) |
  |---|---|---|---|
  | Coach / designer / builder-prep | kimi-k3 (this seat) | long-context audit + design (F12) | claude post-09:00 reset |
  | Bound prover + enumeration tooling | kimi-k3 | 1M ctx over AST + census + generator (F12) | claude Sonnet unit post-reset |
  | Grader / refuter of every build | fresh Opus 5 xhigh | different family (F4, F6, C5, C6) | none — wait for 09:00, never same-family (F4) |
  | Ground-truth check of named conditions vs regs | nlm | ground-truth verifier, never synthesizer (F12) | owner reads the reg text |
  | Grunt replays (census reruns) | jules | 3/day, cheap (F8) | skip — kimi runs pytest locally |
  | Shipper (merge, arm, deploy, prove) | mandate BLUE session | C4 | none |
  | Signing hands, Vercel promote, Q1, consents | owner (Zero) | §3 | none |
  | NOT USED | TP1 (all 7 rows 429), codex/agy (timeout), codex-spark (400-dead, F8), ollama (not installed) | F7, F8 | — |

  ## Tactics
  | stage | seat(s) | in-script or window | parallel/serial | round cap | exit command | hands to next stage |
  |---|---|---|---|---|---|---|
  | S0 Bound | kimi | in-script | first, alone | 1 | enumerator dry-run prints path count + per-node fan-out to `research/operations/2026-09-19-visa-oracle-enumeration/bound.txt` | bound number + fan-out table on disk |
  | S1 G1 engine | kimi | worktree `.worktrees/visa-oracle-g1/` (C10) | serial after S0 | 2 | `pytest apps/backend-rag/backend/tests/services/visa_engine/ -k census` green with seq-23 pins: FUNNEL HUMAN_REVIEW_REQUIRED == criminal-disclosure walks only; per-flag table all zeros | fold_pack_seq23 + guilt tests + diff on disk |
  | S1b Review copy | kimi | same worktree, separate PR | parallel with S1 | 1 | `OutcomeSheet.test.tsx`/`engine-adapter.test.ts` green, generic sentence deleted | EN/ID copy + tests on disk |
  | S2 nlm check | nlm | window | parallel with S1 | 1 | nlm answer file confirms each named condition cites its reg | verification note on disk |
  | S3 Sign seq-23 | owner | human window | serial after S1 | 1 | `observe_visa_seq23_signed.py`-style observer reads seq-23 as highest signed pack | signed bundle hash on disk |
  | S4 G3 tree UI | kimi | worktree `visa-oracle-g3/` | starts at S1 schema freeze, parallel with S3 | 2 | 19 e2e specs green locally; atlas.css shows 4 distinct outcome colours | UI diff + screenshots (synthetic persona) on disk |
  | S5 G2 enumeration harness | kimi | in-script | parallel from S0 | 2 | runner prints walk count == S0 bound, hits live engine URL | runner + report skeleton on disk |
  | S6 Gate | fresh Opus 5 xhigh, outside chain (C5) | window, post-09:00 | serial | 1 | gate verdict file on disk | VERDICT + diff readback (F11) |
  | S7 Ship+fix loop | BLUE session | window | serial | depth-1 per cause (C7) | each PR merged, `Bites:` observation live; backend deploys on merge (F15) | PR list on disk |
  | S8 Prove-live | owner promote + BLUE observe | human + window | last | 1 | promoted Vercel URL + deployment id in the enumeration report; zero reds | G2 report complete |

  Fix-directly-inside-the-contract: the S5/S8 runner writes each red to a cause-classified ledger row; one cause = one ≤400-line PR (C3), auto-merge armed at open, gate per batch at S6 cadence — never skipped, never rerun-before-why (C7). Three reds same cause suspends the loop and escalates to the owner.

  ## Termination
  Two counters in `.worktrees/visa-oracle-g*/ROUNDS.json`: `fix_depth_by_cause` (hard stop at 1, C7) and `reds_by_cause_class` (hard stop at 3 → suspend). The BLUE Dux reads the file before opening any new round; no round launches without the read. A fourth round is impossible because the runner refuses to open a PR when either counter is at cap — the block is in the script, not in anyone's judgement.

  ## Evidence between stages
  Files on disk, never journals (F11, F14): S0 publishes `bound.txt`; S1 publishes the fold script, the diff, the pytest log, and the per-flag table printed by `test_every_disclosure_flag_reports_the_walks_it_rewrites`; S3 publishes the signed bundle's sha256; S4 publishes screenshots + e2e log against a synthetic persona; S6's gate reads disk directly, never the builder's claim (C6); S8's report names the live URLs, deployment identifiers, walk count vs bound, zero reds, and the fixing PRs. Every handoff is a path the receiver re-verifies.

  ## Never
  - Never a same-family grader — 7/8 false-clean (F4, C6).
  - Never ship, merge, arm, or promote from this kimi seat (C4); never a paid Anthropic route (C1).
  - Never rerun a red before its cause is named; never fix-of-a-fix past depth 1 (C7).
  - Never leave a non-criminal hold silent or the generic fallback sentence alive; never collapse the four outcome colours; never transplant R19's Second Home fork (brief §1).
  - Never fan out un-pinned `agent()` lanes (F10, C8); never TP1 one-shot storms — the bucket is dead (F7, §2).
  - Never real applicant data in any artefact; synthetic personas only (C2).

  ## First move
  The S0 enumerator dry-run (≤100 lines): load `rulepack-prod-022.signed.json` AST, walk every root-to-leaf path with each question answered once, dedupe by the fact tuple the claim_ledger actually consumes, print total walks, per-question fan-out, and the multiplicative bound. · Bites: G2 enumeration report · observation: `bound.txt` on disk shows walk count == enumerated count and the bound formula reproduces it from the fan-out table.

  ## Cost
  kimi: ~8–10 long-context calls (bound, G1 build, copy, G3 build, harness, 2 fix rounds reserve). jules: ≤3 grunt replays. nlm: 1–2 verification queries. TP1/codex/agy: 0. Anthropic windows: 2, both after the 09:00 reset — one fresh Opus 5 xhigh gate (C5), one BLUE ship window. Owner windows: 1 signing, 1 Vercel promote, 1 Q1 decision. Expected wall-clock: S0–S5 today (~6 h, S1/S3/S4 overlapped), gate+ship+prove tomorrow morning — the critical path is the quota reset and the owner's signing hands, not the build.

