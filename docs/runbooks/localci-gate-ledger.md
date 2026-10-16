# Runbook — the gate-verdict ledger (LocalCI B25-prime)

Spec: `docs/specs/localci-sovereign-2026-10-07.md` section 2b.2. A gate verdict is trusted by LocalCI only if it is a line of the Pro
ledger `~/.nuzantara-pilots/local-ci-gate/verdicts.jsonl` (directory 0700, file 0600, owner = the merger's user).

- **Gates run candidate code isolated.** A gate session that executes a PR's code (tests, scripts, workflow text) does it in a container
  or a throwaway worktree with no ssh agent, no `gh` credentials and no Pro access in its environment; the publisher
  `scripts/harness_fable_gate.py` runs from `origin/main`, never from the candidate's checkout.
- **Who can write the ledger (spec residual R2).** Anything that executes as the Pro user: any `ssh pro` session (implementer sessions
  included, they hold the same key), every service of the Pro user behind cloudflared or Funnel. `via` records the ssh client HOST
  address, not a session or a person. The control is the isolation above; the optional hardening is D2, an ssh key dedicated to gate
  appends with a forced `gate-append` command.
- **Publish.** `python3 scripts/harness_fable_gate.py --verdict PASS --sha <40-hex> [--pr <n>] --gate-session <name>`. `--pr` is optional:
  a gate usually posts before its PR exists, and the entry then carries `pr: null` (never a guess). The script first runs a read-only
  preflight on Pro (the wrapper has the mode, the mirror has `gate_ledger.py`; neither is executed, because an old wrapper treats ANY
  argv as a tick), then appends over `ssh pro` through the wrapper's `gate-append` (one base64 argv), then posts the GitHub status. A
  missing deploy step is printed by name and nothing is posted; a failed append posts nothing; re-running is safe (the append is
  idempotent against the head's newest entry). A verdict that follows an earlier failure of the same head needs `--supersede "<reason>"`.
- **Check.** `ssh pro 'tail -n1 ~/.nuzantara-pilots/local-ci-gate/verdicts.jsonl'` shows the head, the verdict and `via`;
  `gate_ledger.py verify` (run on Pro from a checkout of `origin/main`) exits 0 on a good ledger and names the first bad line otherwise.
- **Repair.** A torn or invalid line makes every head read false. `gate_ledger.py quarantine --line N` moves that one line to
  `verdicts.quarantine.jsonl` (it refuses a line that validates; a torn tail stays torn). Wrong mode or owner: `chmod 600`; a lost
  file is restored from Pro's restic repository once step 5 below is done (M5 `~/Backups` holds that repository, not a copy of the ledger).

## Deploy (the shipping session, on Pro, in this order, right after the merge)

Until steps 1 and 2 are done every publisher fails closed with the missing step named; nothing wrong is posted.

1. Install the wrapper pair: `cp scripts/localci/localci_merger_tick.sh ~/.nuzantara-cron/localci_merger_tick.sh.new && mv -f ~/.nuzantara-cron/localci_merger_tick.sh.new ~/.nuzantara-cron/localci_merger_tick.sh`, then `cmp` it with `git show origin/main:scripts/localci/localci_merger_tick.sh`.
2. Fetch the code into the mirror now (a tick would only do it at its next start, 26 minutes on average, 100 or more at worst):
   `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 git -C ~/.nuzantara-pilots/local-ci/merger/repo.git fetch --no-tags --quiet origin +refs/heads/main:refs/merger/wrapper`.
3. Probe: `git -C ~/.nuzantara-pilots/local-ci/merger/repo.git cat-file -e refs/merger/wrapper:scripts/localci/gate_ledger.py && echo present`.
4. Dry run against a temp ledger: `GATE_LEDGER=$(mktemp -d)/v.jsonl bash ~/.nuzantara-cron/localci_merger_tick.sh gate-append <base64 of a throwaway entry>` prints a digest; remove the temp dir. Never point it at the real path.
5. Backups: add `$HOME/.nuzantara-pilots/local-ci-gate` to `CANDIDATES` in `~/scripts/restic-backup-pro.sh` on Pro (the Pro to M5 restic job does not cover `~/.nuzantara-pilots` today).
