# Visa Oracle weekly re-attestation organ

Organ `pro.visa_reattestation`, label `com.nuzantara.visa-reattestation`, runner
`scripts/visa_reattestation_organ.py`. It turns the portal re-attestation, a human mandate
that failed twice (scar W141: 2026-08-30 and 2026-10-01), into a scheduled organ.

## What it does and what it never does

Every Monday it reads the 18 `OFFICIAL_PORTAL` pages, has a Claude judge compare them with
what the active pack assumes, folds an UNSIGNED candidate pack (seq N+1) from that ledger
and opens a PR. It never signs, never activates and never arms auto-merge. Signing needs
the production key on M5 and activation needs the ceremony in
`visa-engine-key-ceremony.md` ("Signing + activation note"). Those stay session acts.

## Schedule

`StartCalendarInterval` Weekday 1, 02:00, Pro local time (WITA, UTC+8), so Sunday 18:00 UTC.
No `KeepAlive` (scar #7). Why Monday 02:00:

- The freshness window is 32 days, so one weekly run leaves three or four retries before
  a boundary, and the T-7 alert starts a week out.
- 02:00 WITA is off-peak for the portals and lands the PR and alerts before the owner's
  working day. A failure on Monday leaves the whole week to cure it.
- `expected_hb_seconds` is 1209600 (2 weeks), so one missed Monday is a warning, not noise.

## One run, in order

1. Fetch `origin/main` and find the anchor: the highest signed PRODUCTION pack and the
   `.source.json` next to it. The boundary is the earliest `OFFICIAL_PORTAL`
   `verified_at + max_age_seconds`.
2. Create an own worktree under `~/.local/state/nuzantara/visa-reattestation/` on branch
   `organ/visa-reattest/<anchor-seq>-<date>`, or on the branch of an open organ PR for the
   same anchor. The runner refuses a checkout whose `.git` is a directory (the shared one).
3. `portal_read_receipt.py --all` into `research/visa/<date>-organ-reattest-seq<N+1>/`.
4. `portal_judge.py --all --judge claude --reader organ-<model>-<yyyymmdd>`. The judge
   goes through `claude-cascade.sh --claude-only`. Exit 1 means at least one `unsure`.
5. On judge exit 0, `fold_pack_generic` writes `rulepack-prod-0<N+1>.source.json` INSIDE the ledger
   dir, never into `contracts/packs/`, so human lanes and the CI tests that read the highest
   source pack never see an unreviewed candidate.
6. Commit the ledger, the candidate and an attestation note. Push. Open a PR titled
   `chore(visa-engine): organ re-attestation ledger <date> — candidate seq-<N+1> (unsigned)`,
   or push a new commit to the open one. No auto-merge.
7. Any failure: HIGH row on `shared/escalations_pro.jsonl`, Telegram p0 in the
   `visa-freshness` family, state file records the stage, exit non-zero.
8. T-7: when the boundary is at most 7 days away and a candidate exists (just folded, an
   open organ PR, or an unsigned source on main), alert "pack ready to sign" on every run
   until a newer signed pack exists.

## Flags

| Flag                                              | Effect                                                                                    |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `--dry-run`                                       | Print the plan as JSON. No fetch, no git write, no PR, no alert, no state.                |
| `--offline`                                       | No network read, no `gh`, no Telegram. Needs `--ledger-dir`.                              |
| `--judge fake`                                    | Rehearsal judge. The reader becomes `fake-organ-<date>`; fold gets `--allow-fake-reader`. |
| `--skip-judge`                                    | Use judgements already in the ledger. Fails if there are none.                            |
| `--ledger-dir DIR`                                | Existing ledger, copied into the worktree instead of reading portals.                     |
| `--repo`, `--state-dir`, `--board`, `--code-root` | Paths, so a rehearsal never touches the live ones.                                        |
| `--now`                                           | Test-only clock override.                                                                 |

`--offline` skips portals, `gh`, Telegram and the board, but git still talks to the origin of
`--repo` (a temp origin in the rehearsal). Rehearsal on any machine, no writes outside the temp dirs:
`python3 scripts/ci/observe_visa_reattest_organ.py`.

## Install on Pro (a session act)

Sequence: merge #8069 (the judge) → sign and activate seq-26 → install the plist → kickstart
→ the first ledger and PR are the Bites proof → then weekly. Installing earlier makes the run
fail at the judge stage with a board row naming #8069.

1. Copy the wrapper to `~/scripts/pro-visa-reattestation.sh` and the plist to
   `~/Library/LaunchAgents/` (both are declared pairs in `infra/home-fork/declared-pairs.json`).
2. `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.visa-reattestation.plist`.
3. Prove it is armed, not just present (scar #2): `launchctl kickstart` once, then read
   `~/.organism/last_seen/pro.visa_reattestation.json`. The first PR it opens is the proof.
4. Kill switch: `PRO_VISA_REATTESTATION_ENABLED=false` in the wrapper environment.

## Signing the candidate (the session that gets the PR)

Review the attestation note and the judge verdicts, read the `changed` pages yourself (the
fold needs a `disposition.json` entry for each), sign on M5, activate per the ceremony, then
merge. First `git mv` the candidate from the ledger dir to
`contracts/packs/rulepack-prod-0<N+1>.source.json`; the signed twin goes next to it. The organ's note carries `adversarial_review: pending-session`: the signing session
runs the adversarial review and updates that field.

## Known limits

- The judge inherits the cascade order: seats 1-5 first, seat 6 (Team) only when they are
  exhausted. That is the canon, so the wrapper is unchanged.
- Two organ PRs for the same anchor never coexist. A weekly run adds a commit and refreshes
  the stamp. A merged ledger whose candidate is not yet in `packs/` is picked up as the existing candidate.
- If the portals changed, the judge exits 0 only when every page is `same` or `changed`;
  the fold then refuses `changed` pages without a disposition, and that run fails loudly.
