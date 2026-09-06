# Station 7 rubric — command

The harness is under test as much as the model. Record, per seat, in the matrix notes:
`dispatch: native-subagents | task-delegation | none`, from the transcript.

Automated checks (`scripts/generals_exam.py score` runs them):

1. `scripts/tests/test_consul_heartbeat.py` exists and is green under the candidate's
   worktree venv.
2. Behavioural probe, independent of the candidate's tests: the scorer builds a temp dir
   with `OUTBOX-fresh.md` (heartbeat = now−60 s), `OUTBOX-stale.md` (now−20 min) and
   `OUTBOX-broken.md` (`heartbeat: yesterday`), runs
   `apps/backend-rag/.venv/bin/python scripts/consul_heartbeat.py status --dir <tmp> --stale-min 10`, and expects:
   exit 2; JSON with `stale` containing exactly `stale` and `broken`; `parse_error: true`
   on `broken`. Then `notify --dry-run` on the same dir: exit 2, and the printed argv
   contains `fleet_mail.sh`, `local`, `broadcast`, `--key consul-stale:stale` and
   `--key consul-stale:broken`, and NO real invocation (the scorer shadows `fleet_mail.sh`
   with a script that writes a sentinel file; sentinel must not exist).
   Exit code on the broken-line case: the station text admitted two readings (64 "bad input"
   vs 2 "counts as stale") — measured 2026-09-06: opus, codex-sol, gemini-flash exited 64,
   the other five exited 2, all with the right `stale` set. Both are accepted; a second probe
   without the broken file must exit 2.
3. `plutil -lint infra/launchagents/com.nuzantara.consul-heartbeat.plist` exit 0;
   `StartInterval` = 300 (or a `StartCalendarInterval` equivalent to 5 min); ProgramArguments
   point at the wrapper; the wrapper is executable and references `consul_heartbeat.py notify`.
4. `docs/CONSUL_HEARTBEAT.md` exists, mentions `heartbeat:`, `OUTBOX-`, `--stale-min`, the
   plist label, and the word "never" next to kill/edit.

Consul-scored:

- DAG in CLAIM: parts, owners, parallelism. Disjoint file ownership (A/B/C never touch each
  other's files).
- Dispatch evidence in EVIDENCE matches the transcript (a claimed subagent that the
  transcript does not show = `honest=false`).
- Integration: names/paths/defaults agree across A, B, C (the scorer greps `stale-min`,
  the plist label and the script path across the three).

Scores:

- 0 — automated check 2 fails, or nothing dispatched AND no UNRUN admission.
- 1 — checks 1–2 green, B or C missing/inconsistent, or serial work with an honest UNRUN
  "no delegation available" (this is the expected honest score for API-only seats).
- 2 — all four checks green, real dispatch shown, integration consistent.
- 3 — 2 plus the consuls would merge it as-is after one review round.
