# Jules dispatch — the active arm for Google's async cloud implementer

**Born**: 2026-07-06, from Zero's mandate "coinvolgilo attivamente nel workflow, senza
teatro" — same day the operator minted the API key (Keychain `jules-api-key`) and the
first fully-autonomous dispatch ran (session `5555115025998095815`, the W89 pricelist
codex-flags fix).

## Contract (non-negotiable)

**Jules generates; Fable grades.** This tool dispatches tasks and reads state — it can
never merge, never push to main, never approve its own output. Landing is always:

1. `jules_dispatch.py new --prompt "<scoped task with file:line anchors + acceptance>"`
2. Poll `status`/`activities` (or arm a Monitor on the session state).
3. When the session completes: fetch the diff (session outputs / Jules branch),
   **verify independently** — re-read the diff line-by-line against the task spec,
   re-run the touched tests, check scope + reward-hacking (same 6-step contract as the
   Antigravity arm, CLAUDE.md §5).
4. Land via your own branch + PR + auto-merge. Credit Jules as co-author.

Jules's own GitHub publish is NOT required (and historically failed on app perms) —
the patch is evidence, the landing lane is ours.

## Usage

```bash
python3 scripts/jules_dispatch.py list-sources
python3 scripts/jules_dispatch.py new --prompt "..." [--source sources/github/Balizero1987/Teman2] [--branch main] [--title ...]
python3 scripts/jules_dispatch.py status sessions/<id>
python3 scripts/jules_dispatch.py activities sessions/<id> [--limit 30]
python3 scripts/jules_dispatch.py --selftest   # offline guilt+innocence (6 checks)
```

Key: Keychain `jules-api-key` (env `JULES_API_KEY` overrides — tests only). The key
never reaches stdout; error bodies are scrubbed (`AIza…` shapes redacted).

## Task-authoring discipline

A Jules prompt must carry: exact file + line anchor · the precise change · the repo
rule/scar that motivates it · explicit scope fence ("do NOT change anything else") ·
what green looks like. Under-specified prompts produce plausible-but-wrong diffs that
waste the verification lane. Quota: Ultra tier ~300 sessions/day — the constraint is
verification bandwidth, not dispatch.

## API notes (v1alpha — expect drift)

Base `https://jules.googleapis.com/v1alpha`, header `X-Goog-Api-Key`. Sessions:
`POST /sessions` (prompt + sourceContext.githubRepoContext.startingBranch),
`GET /sessions/{id}`, `GET /sessions/{id}/activities`. Alpha caveat: field names may
change; the tool fails visible (HTTP body scrubbed + exit 1), never silent.
