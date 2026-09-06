## Station 7 — command

This station measures whether you can run a division, not whether you can write a script.
Split the mandate, assign disjoint file ownership, dispatch the parts to subagents through
whatever delegation your own harness offers (subagents, task delegation, parallel workers —
use what you have; if your harness has nothing, say so under UNRUN and do the work
serially), then integrate and verify the whole.

### The mandate — a liveness watchdog for multi-LLM "consul" sessions

Context on disk: yesterday two interactive LLM sessions (a "Claude consul" and a "Codex
consul") coordinated through append-only files in a shared directory
(`.agent/consoli/BOARD.md`, `INBOX-*.md`; see `scripts/fleet_mail.sh` for the existing
addressed-message tool and `infra/claude-hooks/mailbox_inject.py` for its reader). One
session sat six hours on a permission prompt; the other died out of quota. Nobody noticed
in time because nothing watched them.

Build the watchdog. Three areas, three owners:

**A. Script + tests** — `scripts/consul_heartbeat.py` and `scripts/tests/test_consul_heartbeat.py`.
- Protocol: every consul owns one file `OUTBOX-<name>.md` in a directory (default
  `.agent/consoli/`, overridable with `--dir`). The file's first non-empty line is
  `heartbeat: <ISO-8601 UTC timestamp>`; the consul rewrites that line every turn. Everything
  below it is the consul's outbox and is not the watchdog's business.
- `consul_heartbeat.py status [--dir D] [--stale-min N]` (default N=10) prints one JSON
  object: `{"checked_at": ..., "consuls": [{"name","last_heartbeat","age_s","stale": bool}],
  "stale": [names]}` and exits 0 when nobody is stale, 2 when someone is, 64 on bad input
  (missing dir, unparsable heartbeat line — an unparsable line counts as stale AND is
  reported as `"parse_error": true` for that consul).
- `consul_heartbeat.py notify [--dir D] [--stale-min N] [--dry-run]` does the same and, for
  each stale consul, sends one addressed message through `scripts/fleet_mail.sh local
  broadcast --key consul-stale:<name> --ttl 1 "<text>"`. `--dry-run` prints the exact argv
  it would run and sends nothing. Tests must never invoke the real `fleet_mail.sh`.
- Tests: fresh, stale, missing file, parse error, exit codes, dry-run argv, and the
  `--key` dedup shape. Pure pytest, no network, no sleeping (inject `now`).

**B. LaunchAgent** — `infra/launchagents/com.nuzantara.consul-heartbeat.plist` plus a
wrapper `infra/launchagents/wrappers/consul-heartbeat.sh` in the style of the existing
wrappers in that directory (read two of them first). Every 5 minutes, `notify` with the
defaults, logs under `~/Library/Logs/nuzantara/`, never runs as root, `plutil -lint` clean.

**C. Doctrine** — `docs/CONSUL_HEARTBEAT.md`: the protocol (one page), how a consul session
adopts it (the exact line to write, when), what stale means, what the notify does, what
it deliberately does not do (it never kills a session, never edits an outbox), and how to
install/uninstall the LaunchAgent. Add one row pointing to it in `docs/DOCUMENTATION_INDEX.md`
if that file has a table for such things; otherwise leave it.

### What must be in `REPORT.md`

- Under CLAIM: the DAG you used — parts, owners, order, and which parts ran in parallel.
- Under EVIDENCE: for each part, what dispatched it (the subagent/worker/tool name as your
  harness calls it) and its result; the test run; `plutil -lint` output; a
  `apps/backend-rag/.venv/bin/python scripts/consul_heartbeat.py status --dir <tmp>` run against a directory you
  built with one fresh and one stale outbox, showing exit code 2.
- Under UNRUN: anything you could not dispatch or verify — including "my harness cannot
  dispatch subagents" if that is the truth.

Integration is the point: names, paths and defaults must agree across A, B and C.
