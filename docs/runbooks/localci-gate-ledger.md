# Runbook — the gate-verdict ledger (LocalCI B25-prime)

Spec: `docs/specs/localci-sovereign-2026-10-07.md` section 2b.2. A gate verdict is trusted by LocalCI only if it is a line of the Pro
ledger `~/.nuzantara-pilots/local-ci-gate/verdicts.jsonl` (directory 0700, file 0600, owner = the merger's user).

- **Gates run candidate code isolated.** A gate session that executes a PR's code (tests, scripts, workflow text) does it in a container
  or a throwaway worktree with no ssh agent, no `gh` credentials and no Pro access in its environment; the publisher
  `scripts/harness_fable_gate.py` runs from `origin/main`, never from the candidate's checkout. Whatever runs as the Pro user can write
  the ledger (spec residual R2), so the isolation is the control.
- **Publish.** `python3 scripts/harness_fable_gate.py --verdict PASS --sha <40-hex> --pr <n> --gate-session <name>`: the ledger line is
  appended over `ssh pro` first (the tick wrapper's `gate-append`, one base64 argv), then the GitHub status is posted. A failed append
  posts nothing; re-running is safe (the append is idempotent against the head's newest entry). A verdict that follows an earlier
  failure of the same head needs `--supersede "<reason>"`.
- **Check.** `ssh pro 'tail -n1 ~/.nuzantara-pilots/local-ci-gate/verdicts.jsonl'` shows the head, the verdict and `via`;
  `gate_ledger.py verify` (run on Pro from a checkout of `origin/main`) exits 0 on a good ledger and names the first bad line otherwise.
- **Repair.** A torn or invalid line makes every head read false. `gate_ledger.py quarantine --line N` moves that one line to
  `verdicts.quarantine.jsonl` (it refuses a line that validates). Wrong mode or owner: `chmod 600` or restore from M5 `~/Backups`.
- **Deploy.** The wrapper is a declared pair: copy `scripts/localci/localci_merger_tick.sh` to `~/.nuzantara-cron/localci_merger_tick.sh` on
  Pro. `gate-append` runs the `gate_ledger.py` of the mirror's `refs/merger/wrapper`, so it works once a tick has fetched the merge.
