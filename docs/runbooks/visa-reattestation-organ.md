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
   attested read of that record gets a `none` judgement written by the organ itself
   (`judge: "fingerprint"`, no model). Then
   `portal_judge.py --ids <the rest> --judge claude --reader organ-<model>-<yyyymmdd>`
   (`--all` when nothing matched; skipped when every page matched). The judge goes through
   `claude-cascade.sh --claude-only`. Exit 1 means at least one `unsure`.
5. On judge exit 0, `fold_pack_generic --baseline-root <root>` writes `rulepack-prod-0<N+1>.source.json` INSIDE the ledger
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
| `--baseline-root DIR`                             | Directory of ledgers the attested reads are proven from (default `research/visa`).        |
| `--repo`, `--state-dir`, `--board`, `--code-root` | Paths, so a rehearsal never touches the live ones.                                        |
| `--now`                                           | Test-only clock override.                                                                 |

`--offline` skips portals, `gh`, Telegram and the board, but git still talks to the origin of
`--repo` (a temp origin in the rehearsal). Rehearsal on any machine, no writes outside the temp dirs:
`python3 scripts/ci/observe_visa_reattest_organ.py`.

## Unchanged pages are proven by fingerprint, not by the judge

The receipt field `visible_text_sha256` is `portal_read_receipt.fingerprint` of the visible text.
The pack stamp field `content_sha256` is NOT that fingerprint (0 of 18 stamps match), so it is
never used. A fresh read is unchanged when its fingerprint equals the fingerprint of the
ATTESTED read of the same record. That read is proven, never named:

- A ledger under the baseline root (`--baseline-root`, default `research/visa` of the code root)
  attests the anchor pack when it holds a successful receipt (HTTP 200, key phrase found) dated
  exactly at one of the pack's portal `verified_at` stamps. The fold stamps the earliest read of
  the ledger it consumed, so that receipt marks the ledger.
- The attested read of a record is that ledger's latest successful receipt not after the pack's
  `created_at`. Its text is the receipt's own `text_file`, and the file must carry the fingerprint
  the receipt recorded. A newer text file for the same id is never used.
- The run's own ledger is excluded by path. A record with no provable attested read goes to the
  judge. The chosen `(ledger, fetched_at)` per record is logged and listed in the attestation note.

Taking only receipts dated at or before the stamp would prove 2 of the 18 pages, because the stamp is
the earliest read of the whole set. On 2026-10-08 the rule above proved 18 of 18 against the seq-25
ledger, including the page below.

The rows the organ writes carry the fresh receipt's `receipt_fetched_at` and `text_sha256`,
`judged_at` = now, and a `checked_sentence` that is a substring of the fresh text: the attested
ledger's own quote when the fresh text carries it, else the first complete sentence of at least 40
characters. A record for which no such sentence exists is left to the judge.

The fold re-proves every `judge: fingerprint` row: its `text_sha256`, the fresh receipt's
fingerprint and the attested read's fingerprint must be one value, and without `--baseline-root`
such a row is refused. A `changed` verdict on a text whose fingerprint equals the attested read's is
downgraded to `none`, needs no disposition, and is listed as a baseline disagreement in the fold
output and in the attestation note, so the signing session sees that a judge disagreed with the
previous attestation on an unchanged page.

## Where the ledger of a run lives

The run removes its worktree, which used to delete the receipts, judgements and texts a human
needs. Before that, on success and on any failure, the organ copies the ledger to
`~/.local/state/nuzantara/visa-reattestation/ledgers/<UTC ts>-seq<anchor>/` and keeps the newest 8 (only directories named like that are ever pruned). The copy is verified (same
entries and sizes) before the worktree is removed; symlinks are copied as links and one leaving the
ledger refuses the copy. If the copy fails, the worktree is kept, the board row says where, and
`state.json` has `ledger_copy: null` and `worktree_kept`. The next run reaps that worktree, so read it first.
The path is in the board row `detail` and `error_summary`, in the Telegram text, and in
`~/.local/state/nuzantara/visa-reattestation/state.json` under `ledger_copy`. The heartbeat note
does not carry it: read the board row or `state.json`.

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
