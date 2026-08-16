# mergeos-step4: derived-state consumer sweep — who actually READS the volatile counts

Read-only analysis. No plan to edit/commit/push anything — output is a report only.

Context: Merge-OS v3 step 4 (council doc
`research/operations/2026-08-14-merge-os-v3-research-council.md` §C2 + §6 step 4)
mandates removing volatile counts/inventories from tracked docs (linking to
`docs_sync.py --json` / CI artifacts instead). §6 makes one check a hard
precondition: "Requires the ASSUMPTION check: grep-verified no programmatic
consumer — one dependency sweep before deletion." This task IS that sweep,
done exhaustively so the implementing session inherits evidence, not a guess.

Scope — enumerate every tracked file carrying an auto-regenerated volatile
block or count, starting from (but not limited to):

- every `<!-- DOCSYNC:*_START/END -->` block (grep the markers repo-wide):
  `docs/AI_ONBOARDING.md` QUICK_NUMBERS, `INDEX.md` AUTOMATION_COVERAGE, any others
- `docs/DOCS_INVENTORY.md` (the scheduled-refresh target)
- anything `scripts/docs_sync.py` and `.github/workflows/docs-inventory-refresh.yml` write
- any other tracked file a generator script rewrites on a schedule (search
  `infra/launchagents/`, `.github/workflows/`, `scripts/` for writers whose
  target is a tracked `.md`/`.json`)

For EACH such file/block, answer: who reads it? Classify every reader found
by grep into: (a) the writer itself, (b) the docs-sync auditor/gate
(`scripts/ci/docs_sync_gate.sh`, `check-docs-sync`), (c) tests, (d) a REAL
programmatic consumer (code whose runtime behavior depends on the value),
(e) prose/human reference only. Class (d) is the finding that would block
step 4 — quote the exact file:line for any candidate and say whether the
dependency is on the VALUE or merely on the block's existence.

Output: one markdown table per derived file — reader file:line | class
(a-e) | what it does with the value — followed by a verdict line per file:
"safe to untrack per C2" or "has a class-(d) consumer: <which>". If any
generator or block is found beyond the starting list, include it and say
how it was found. Do not cap the sweep; if output length forces a cut, say
exactly what was dropped.
