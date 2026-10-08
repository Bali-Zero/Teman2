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
4. Fingerprint first. Every record whose fresh visible-text fingerprint equals the one of the
   baseline ledger's saved text gets a `none` judgement written by the organ itself
   (`judge: "fingerprint"`, no model). Then
   `portal_judge.py --ids <the rest> --judge claude --reader organ-<model>-<yyyymmdd>`
   (`--all` when nothing matched; skipped when every page matched). The judge goes through
   `claude-cascade.sh --claude-only`. Exit 1 means at least one `unsure`.
5. On judge exit 0, `fold_pack_generic --baseline-ledger-dir <baseline>` writes `rulepack-prod-0<N+1>.source.json` INSIDE the ledger
   dir, never into `contracts/packs/`, so human lanes and the CI tests that read the highest
   source pack never see an unreviewed candidate.
6. Commit the ledger, the candidate and an attestation note. Push. Open a PR titled
   `chore(visa-engine): organ re-attestation ledger <date> — candidate seq-<N+1> (unsigned)`,
   or push a new commit to the open one. No auto-merge.
7. Any failure: HIGH row on `shared/escalations_pro.jsonl`, Telegram p0 in the
   `visa-freshness` family, state file records the stage, exit non-zero. The row and the
   Telegram text end with `Ledger kept at <path>` (see "Where the ledger of a run lives").
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
| `--baseline-ledger-dir DIR`                       | Attested ledger whose saved texts prove a page unchanged by fingerprint (rule below).     |
| `--repo`, `--state-dir`, `--board`, `--code-root` | Paths, so a rehearsal never touches the live ones.                                        |
| `--now`                                           | Test-only clock override.                                                                 |

`--offline` skips portals, `gh`, Telegram and the board, but git still talks to the origin of
`--repo` (a temp origin in the rehearsal). Rehearsal on any machine, no writes outside the temp dirs:
`python3 scripts/ci/observe_visa_reattest_organ.py`.

## Unchanged pages are proven by fingerprint, not by the judge

The receipt field `visible_text_sha256` is `portal_read_receipt.fingerprint` of the visible text.
The pack stamp field `content_sha256` is NOT that fingerprint (0 of 18 stamps match), so it is
never used. A fresh read is unchanged when its fingerprint equals the fingerprint of the
baseline text of the same record (`text/<id8>.txt`, or the newest `text/<id8>-<ts>.txt`).

Default baseline, when `--baseline-ledger-dir` is absent: the newest directory (by name) under
`research/visa/` of the code root that holds a saved text for EVERY `OFFICIAL_PORTAL` record of
the anchor pack, with two exclusions. It is never the run's own ledger. An organ ledger
(`*-organ-reattest-seq<N>`) counts only once `rulepack-prod-0<N>.signed.json` exists, because an
unsigned read was never attested by a session. Today that is
`research/visa/2026-10-07-freshness-restamp-seq25`. No baseline means every page goes to the
judge, as before. `--skip-judge` uses a baseline only if given explicitly.

The rows the organ writes carry the fresh receipt's `receipt_fetched_at` and `text_sha256`,
`judged_at` = now, and a `checked_sentence` that is a substring of the fresh text: the
baseline judgement's own quote when the fresh text carries it, else the first complete
sentence of at least 40 characters. A record for which no such sentence exists is left to the
judge. The fold needs no relaxation for these rows. Its new `--baseline-ledger-dir` refuses the
opposite error: a `changed` verdict (even one a disposition accepts) on a text whose
fingerprint equals the baseline's is a contradictory judgement, and the message names both
fingerprints.

## Where the ledger of a run lives

The run removes its worktree, which used to delete the receipts, judgements and texts a human
needs. Before that, on success and on any failure, the organ copies the ledger to
`~/.local/state/nuzantara/visa-reattestation/ledgers/<UTC ts>-seq<anchor>/` and keeps the newest 8.
The path is in the board row `detail`, in the Telegram text, in `state.json` (`ledger_copy`) and
in the heartbeat note (`ledger=<path>`). The wrapper change that reads `state.json` is a declared
pair: copy it to `~/scripts/` on Pro for the heartbeat part to apply.

## First real run, 2026-10-08

The run read the 18 pages and the judge reported page `dcf08e19` (the ITK to ITAS service page)
as changed. The fold refused: a reader reports the page changed and `disposition.json` does not
accept it. Re-reading the page 8 minutes later gave a fingerprint identical to the text attested for
seq-25 on 2026-10-07. So the judge had reported a change on a byte-identical page, a false
positive that would have recurred every week. The failed run's worktree was removed, with the
judgement nobody could read afterwards. This section's two mechanisms exist because of that run.

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
