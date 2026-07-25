---
date: 2026-07-26
domain: operations
client_case: none
sources:
  - .claude/skills/modus/PENDING-ARMS.md (ledger under reconciliation)
  - scripts/pending_arms_report.py (run 2026-07-26, counts)
  - research/operations/2026-07-26-verdetto-seo-1967-e-ledger-stale.md (the trigger)
  - live probes this session: gh, ssh mini, codex CLI, claude CLI, postgres MCP, curl
---

# PENDING-ARMS reconciliation, 2026-07-26 — the operator-gated bucket is not trustworthy

## Why this pass exists

Closing one stale ledger line (META_EN, decided and armed 13 days before the ledger said so)
raised the obvious question: how many of the rest are like it? The reconciliation counts at the
start of this session:

```
total=211  phantom_operator=0  tech_debt_overdue=114
operator_gated_overdue=65  firebreak=10  natural_wait=10  fresh=12  malformed=0
```

`operator_gated_overdue=65` is the number that matters, because every line in it is a claim that
**a human must act and has not** — and each one is a standing reason for a session to stop. If
that bucket is inflated, the ledger is teaching the organism to wait for people who owe it
nothing.

## Method — and the trap that made the obvious method wrong

W88 says: decide "already done?" by CONTENT, never by a proxy. The repo already has that rule as
code, `scripts/branch_graveyard_cleanup.sh::content_on_main()`. **It is disarmed.** It opens with

```bash
mb=$(git merge-base "$MAIN_REF" "$branch" 2>/dev/null) || return 1
```

and since the 2026-07-13 PII history-purge rewrote all 7,837 commits, `git merge-base` between
`origin/main` and any pre-purge branch is **empty** — verified on all three surviving pre-purge
branches this session. The function therefore returns "content NOT on main" for every one of them
**without comparing a single blob**. The "0 content-on-main deletable across 83 branches"
recorded on 2026-07-13 is an artefact of that, not a fact about content. This is the third
generation of the W88 trap: first the SHA-ancestor, then the three-dot diff, now the merge-base
itself.

So the method used here is per-line and evidential, not mechanical:

1. Take the line's **own** declared proof criterion — never a substitute of my own invention.
2. Execute it live this turn (disk, ssh, CLI probe, prod DB, HTTP).
3. Close only on a pass. Where the criterion is unexecutable, say so and leave the line open.
4. Where a branch is involved, take the file-set from the commits the branch **authored**
   (`tip^..tip`) and blob-compare per file — never merge-base, never three-dot.

## Verdicts

### CLOSED on their own criterion (4)

| line | criterion | evidence |
|---|---|---|
| `~/.claude/CLAUDE.md` §External LLM arsenal — Kimi block (opened 07-19, `operator[control-plane]`) | "the global file mentions kimi-code CLI + Allegro subscription" | present at `~/.claude/CLAUDE.md:169-170`: `~/.kimi-code/bin/kimi`, `kimi-code/k3`, "Allegro-tier". Done, unrecorded. |
| Codex model slugs sol/terra/luna (opened 07-21, `operator[business]`) | "`codex exec -m <slug> … PING` returns a model answer (not a 400) for each slug" | all three answered `PING-OK`, rc=0, this session. **The line's premise is false today.** |
| Mini main checkout 1 unpushed commit blocking the 5min cron (opened 07-18, `operator[control-plane]`) | "`git_alignment` ancestor=yes AND `mini-git-pull.log` shows `OK pulled`" | `git merge-base --is-ancestor HEAD origin/main` = **yes**; log at 03:57:26 today: `OK pulled to 258d5fedd (1 commits from origin)`. HEAD moved between two probes 20 minutes apart — the cron is not merely unblocked, it is running. |
| META_EN flip (closed in the sibling PR) | "view-source of /kbli/28180 shows an English `<title>`" | HTTP 200 + full-coverage English title, live. |

### RE-OWNED — not operator-gated at all (2)

**tri-LLM `claude-opus` seat `down (no_json)`.** Tagged "me … or `operator[secret]` if it turns
out to be a token rotation". It is neither a rotation nor a bot-health regression: it is a
credential **shape** bug, root-caused and cured this session (sibling PR). `review_claude_opus`
assigned the raw output of `security find-generic-password -s "Claude Code-credentials" -w`
straight into `CLAUDE_CODE_OAUTH_TOKEN` — but that keychain item is a **JSON document**, measured
7,993 characters, whose token lives at `claudeAiOauth.accessToken` and is 108 characters. Every
`claude` spawn carried ~8KB of JSON as its bearer token, failed auth, printed prose instead of
JSON, and `parse_verdict` reported the opaque `no_json` — which reads as "the reviewer
misbehaved". It only bites when the env var is absent, i.e. exactly the unattended cron/Action
context the bot runs in and never the interactive session anyone would debug it from.

**Mini repo relocation (`~/Desktop/nuzantara` → symlink).** Tagged `operator[business] (confirm
intent — Legge 5)`. The intent is already **recorded**: memory
`decision_repo_moved_out_of_desktop_tcc_immunity_2026_07_16` (on disk, 2026-07-16 19:28) is the
fleet-wide decision to move off TCC-protected `~/Desktop`, and the symlink's own mtime is
`16 lug 11:05` the same day. The business half is answered; what remains is the docs-sync half,
which is a session's job — and it is real: `CLAUDE.md` §11 still instructs `cd ~/Desktop/nuzantara`
for deploys.

### Half-done, and the ledger did not say so (1)

**P0 `apps/cell/.env` — rotation + W38 NOSUPERUSER demotion.** Two independent halves:

- **NOSUPERUSER: DONE.** Live prod read via the read-only MCP:
  `SELECT rolname, rolsuper FROM pg_roles` → `backend_rag_v2` is `rolsuper=false`, as are
  `nuzantara_rag` and `nuzantara_readonly`; only `postgres` is superuser. W38 is satisfied on prod.
- **Permissions: CLEAN fleet-wide.** `stat` only, no file opened: Pro `-rw-------`
  `nuzantara:staff` (both `~/nuzantara/...` and the `~/Desktop/...` symlink resolve to the same
  inode, size 1886); M5 `-rw-------` `balizero:staff`; Mini has no such file.
- **Password rotation: genuinely `operator[secret]`, still open.** Unverifiable without reading
  the value, which is exactly what must not happen. Runbook below.

### CONTESTED — two sessions, two answers, not reconciled (1)

**GLM 5.2 seat.** Left open, and deliberately NOT closed either way.

- My probe, run twice ~20 minutes apart:
  `CLAUDE_CONFIG_DIR=~/.claude-glm claude -p "PONG" --model glm-5.2` →
  `Failed to authenticate. API Error: 401 token expired or incorrect`, rc=1.
- A **sibling session**, concurrently, reports the opposite: PR #3161 (title:
  *"the seat was never dead, the probe was …"*, still **OPEN**) plus a memory line asserting
  **GLM VIVO** — z.ai exposes two endpoints and the subscription lives on `/api/anthropic`.
  `~/.claude-glm/settings.json` on this machine already names `z.ai/api/anthropic`, and its
  `backups/` directory was touched at 03:53 today, i.e. mid-session by that sibling.

So the endpoint half looks fixed and the **auth** half still fails from my invocation. Two
readings are possible and I cannot discriminate them from here: the sibling drives the seat
through the shim rather than through `claude --model glm-5.2`, or #3161 is not yet fully applied
to the path I invoke. Either way the honest state is **contested, pending #3161's merge**, not
"confirmed dead" — which is what an earlier draft of this report said on the strength of my probe
alone.

Recorded because the failure mode is the interesting part: a single-session live probe reads like
hard evidence, and it is — of *that invocation*, on *that path*, at *that minute*. It is not
evidence about the seat. W100's line continues: the refuter hallucinates, the ground truth ages,
agreement lies — and now, a probe answers a narrower question than the one it appears to answer.

## Meta-pattern — what these share

Every stale line above is the **same defect as the one that triggered this pass**, and it is not
"someone forgot to write it down". It is structural: **the ledger records the moment a gap is
opened and has no organ that notices when the world closes it.** The proof criteria are excellent
— specific, executable, falsifiable — and nothing ever executes them. A line's age therefore
measures *time since it was written*, not *time the gap has existed*, and the two diverge without
limit. That is W78 (no unlearning) operating at the level of the instrument the organism uses to
decide what still needs doing.

The Codex-slug line is the sharpest case, because it is worse than stale: it is **actively
misleading**. `.claude/skills/modus/SKILL.md` §Arsenal row 119 tells every session that
`sol`/`terra`/`luna` are dead and must not be used with `-m`. All three answer today. A ledger
that only rots is noise; a doctrine table that rots removes capability.

**Cheap structural cure, not built here** (it would be a self-modifying change to the reporter,
which wants its own lane): `pending_arms_report.py` already parses the `proof:` field of every
line. A `--verify` mode could execute the mechanically-executable subset (a `grep` of a named
file, a `curl` of a named URL, a named CLI probe) and mark lines *criterion-passes-but-still-open*.
That converts the bucket from a to-do list into a reconciliation, which is what the W81 antidote
claims it already is.

## §Solo-operatore

1. **`backend_rag_v2` password rotation** (`operator[secret]`). Everything else on that P0 is
   verified done. Atomic sequence, so no consumer sees a half-rotated credential:
   1. `fly secrets set DATABASE_URL=... -a nuzantara-rag --stage` (staged, not deployed).
   2. `ALTER ROLE backend_rag_v2 WITH PASSWORD '<new>'` on prod (superuser session — the
      read-only MCP cannot and must not do this).
   3. `fly deploy` to release the staged secret in one rollout.
   4. Update the local `.env` on Pro and M5 (Mini has none) — write in place, keep `0600`,
      never `cat` the file to verify; confirm with `stat` and a live app health probe.
   5. Verify: `/health` 200 on `nuzantara-rag`, plus one real DB-backed endpoint.
   The demotion step in the original line is **not needed** — already `NOSUPERUSER` on prod.
2. **GLM 5.2 z.ai seat** (`operator[business]`) — **do not act on my probe alone**: it is
   contested against a sibling session's concurrent finding (see above). Resolve by merging #3161
   and re-probing through the shim; only recharge if the seat still fails after that.
