# HEALER-PRO — node-scoped healer for Pro (DESIGN ONLY, install operator-gated)

> Deliverable 4d of the DNA/GENOME mutation
> (`research/operations/2026-07-06-dna-self-healing-genome.md`).
> **Nothing in this document is installed.** The Pro healer comes to life only on
> Zero's explicit GO (a new plist on Pro is operator-gated by constitution).
> PENDING-ARMS line: `healer-pro install`.

## Why a second healer, and why node-scoped

Pro carries ~107 of the 120 registry organs (and ~130 heartbeat sidecars), yet the
only healer lives on Mini and treats Pro as READ-ONLY. Today a dead Pro organ found
by the Mini healer becomes a Telegram line for Zero — correct, but it makes the
gene-richest tissue the least self-healing one. The registry-driven receptor
(`scripts/healer_receptor_registry.py --node pro`) already knows how to see Pro's
dead organs; what is missing is an arm allowed to act THERE.

## The ONE inverted axis (single-writer preserved)

| Axis                                 | Mini healer (live)         | Healer-pro (this design)                                                                                                                                                |
| ------------------------------------ | -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Repo writes (worktree→PR→auto-merge) | **YES** — sole repo writer | **NO — NEVER.** No worktree, no commit, no push, no PR, no `gh`.                                                                                                        |
| Local runtime cures                  | Mini only                  | **Pro only**                                                                                                                                                            |
| Remote machines                      | read-only probes           | read-only probes (Mini included)                                                                                                                                        |
| Escalation                           | Telegram + ledger via PR   | Telegram + **escalation FILE drop** (`shared/escalations_pro.jsonl` append is local-runtime, allowed) — ledger lines land via the Mini healer or an interactive session |

Two healers, two disjoint write-scopes: the repo has exactly one autonomous writer
(Mini), each node's runtime has exactly one local surgeon. No lease contention, no
sibling-race (#5), no split-brain (#10) — by construction, not by lock.

## Cure verbs allowed on Pro (whitelist, closed)

1. `launchctl kickstart`/`enable` of an ALREADY-INSTALLED LaunchAgent whose
   registry entry says `runtime: pro_launchd` and whose sidecar is dead
   (never one whose sidecar says `disabled` — kill-switch/wrong-node is intentional).
2. HOME←canon refresh for pairs DECLARED in `infra/home-fork/declared-pairs.json`
   with `machines` including `pro` (cmp-verified before and after, like the Mini rules).
3. Log-evidence collection (read-only) attached to the Telegram alert.
4. Re-run of existing reconcilers in report-mode (`lint_home_fork.py --check`,
   `secrets_permissions_audit.py --fix` restricted to Pro-local dotfiles).

Everything else — including anything that would touch the repo, mata_garuda
topology decisions, wa-mirror, OpenClaw state, Postgres, publish surfaces — is
Telegram + escalation drop. The Mini healer's HARD out-of-perimeter list applies
verbatim, PLUS the whole repo-write verb class.

## Anatomy (all pieces already exist as genes)

- Wrapper `infra/launchagents/wrappers/pro-healer.sh` (generator convention): **generated
  via `scripts/organ_birth.py --id pro.healer --node pro --kind llm-cron --schedule 21600`**
  — the healer of the genome era must itself be born through the birth canal (dogfooding:
  G1-G10 imprinted, conformance gate green, no grandfathering). BORN 2026-07-06 on Zero's
  GO, same day as the design: the birth exposed and cured a gate blind spot (untracked
  newborn plists were invisible to `git ls-files` — false local green pre-`git add`).
- Mandate `infra/healer/HEALER-PRO-MANDATE.md`: Mini mandate with the §PERIMETRO
  inverted per the table above; model `claude-sonnet-5`; rule 7 (never cascade a cure
  to a weak model) verbatim.
- Receptors (all read-only, all existing): `healer_receptor_registry.py --node pro` ·
  `proprioception.py --json --no-fetch` (its Pro-relevant probes) · `lint_home_fork.py
--check --json` (pro pairs). NOTE: the ledger receptor stays MINI-ONLY — two healers
  reacting to the same ledger line would duplicate work (single-consumer per receptor).
- Registry entry `pro.healer` (`recovery_action: human_only` — same constitution:
  nothing auto-restarts a restarter).
- Cadence 6h (Pro is busier interactively; the healer must stay a background hum),
  wall-clock cap 40 min, max 0 PRs (structurally: no `gh` in its verb set), Telegram
  on action/degradation only.
- W84: same unconditional ssh-localhost trampoline. Pro prerequisites to arm (operator,
  one-time): trampoline key `~/.ssh/id_local_trampoline` on Pro, `bypassPermissionsModeAccepted`
  in Pro's `~/.claude.json`, `CLAUDE_CODE_OAUTH_TOKEN_1` in `~/.nuzantara-secrets.env` (0600).

## M5 — excluded by design (unchanged)

M5 is the interactive laptop: no daemon fleet, no H24 duty, TCC surface owned by the
human. Its organs are the operator's hands. No healer, no receptor, nothing to install.

## Install checklist (operator GO required — do NOT execute autonomously)

1. Zero says GO on the `healer-pro install` PENDING-ARMS line.
2. Generate wrapper+plist via organ_birth (as above) in a normal PR; write the
   Pro mandate; conformance gate green; merge.
3. On Pro: copy live pair, `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/
com.nuzantara.healer-pro.6h.plist`, verify first heartbeat
   `~/.organism/last_seen/pro.healer.json`, prove one manual tick under sshd.
4. Close the ledger line with the heartbeat + tick log as proof (content, not exit code).

## Risks specific to Pro

- **Interactive collision**: Zero works on Pro. Mitigation: the healer-pro verb set
  never touches git state, editor state, or `~/nuzantara` content (repo is
  read-only for it); kickstarts are per-label and idempotent (G10 pidfiles in targets).
- **176-daemon blast radius**: a kickstart storm is capped — max 3 cure actions/tick,
  and only organs DEAD by sidecar age, never stale/never-armed.
- **Kill switch**: `HEALER_PRO_ENABLED=false` in `~/.nuzantara-healer.env` on Pro,
  honored with a `disabled` heartbeat (G5) — visible stop, no uninstall needed.
