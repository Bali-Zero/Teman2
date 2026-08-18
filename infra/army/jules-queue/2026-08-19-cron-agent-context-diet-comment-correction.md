# Correct the context-diet comment in cron-agent.sh: its measured numbers were taken in the wrong cwd

**File + anchor**: `infra/launchagents/wrappers/cron-agent.sh`, the comment block
headed `── Context diet (P1, measured on M5 2026-08-12) ──` (around lines
531-551 on current main; grep for `55,881` to find it).

**The defect (documentation-only — no code change)**: the comment states the
boot-context baseline as "measured 55,881-91,679 tokens" and the diet's effect
as "-11,087 tokens (55,881 -> 44,794)". Those numbers were measured from INSIDE
the project checkout, where `CLAUDE.md` (~35.6KB) and
`.claude/rules/cicatrix-superscar.md` (~67KB) auto-load. The cron jobs this
wrapper serves run from `$HOME`, where those files do not load: re-measured
from `$HOME` on 2026-08-12 (two independent lanes, kept separate: lane A
−2,953, lane B −3,007), the real baseline is ~47,124 tokens and the diet cuts
~2,953 (≈6.3%) to ~44,171 — NOT 11K. Reference: memory
`plan_token_consumption_7_structural_cures_2026_08_12` (P1 row) and scar
lesson W113 (a correction that misstates is as bad as the original).

**The precise change**: rewrite ONLY the numeric claims inside that comment
block so it says, in substance:

- baseline from `$HOME` (where these crons actually run): ~47,124 tokens;
  the previously-quoted 55,881-91,679 range was measured inside the project
  checkout, where CLAUDE.md + cicatrix auto-load — a tax these crons never
  paid;
- `--disable-slash-commands`: measured −2,953 and −3,007 in two independent
  `$HOME` lanes (≈6.3%), not −11,087 — the −11K figure was the
  in-checkout measurement;
- keep the rest of the comment (innocence check, second flag rationale,
  `--bare` rejection, kill switch) EXACTLY as it is.

**Scope fence**: do NOT change any executable line, any flag, any other file,
or any other comment. The diff must touch only comment lines inside that one
block. What green looks like: `bash -n infra/launchagents/wrappers/cron-agent.sh`
passes, the diff is comment-only (`git diff` shows no non-`#` line changed),
and grep for `55,881 -> 44,794` returns nothing while grep for `47,124`
returns the new text.
