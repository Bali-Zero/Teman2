# kbli-navigator (rebuild sandbox) — NOT the production app

> **PRODUCTION = `apps/mouth`** → https://balizero.com/kbli (`/kbli-navigator` 301s there).
> This standalone Next.js app is the design/rebuild **sandbox** historically deployed to
> `kbli-navigator-rebuild.vercel.app` only. Do not fix production bugs here.

## The three forms of the KBLI Navigator (scar family #1 HOME-fork — keep them straight)

| Form | Where | Data | Status |
|---|---|---|---|
| **Web (PROD)** | `apps/mouth` → balizero.com/kbli | `apps/mouth/data/KBLI_2025_FINAL_CLEAN.json`, byte-synced from canonical by `scripts/sync_kbli_dataset.sh` (CI-enforced) | LIVE |
| **This sandbox** | `apps/kbli-navigator` | `data/kbli-2025.json` (gitignored, materialized locally; falls back to canonical `source_documents/…` — see `lib/kbli-bali-l4.ts`) | sandbox |
| **Native macOS app** | `~/Desktop/kbli-navigator-app` (outside this repo) | its own `Resources/KBLI_2025_FINAL_CLEAN.json`, refreshed from canonical by its `deploy/install-3mac.sh` | per-machine install |

**Canonical dataset (single source of truth):** `data/source_documents/KBLI_2025_FINAL_CLEAN.json`
(root `source_documents/` is a tracked symlink alias). After ANY dataset change: run
`bash scripts/sync_kbli_dataset.sh`, and re-run the native app deploy to refresh its copy.

## If you are here to change the KBLI experience users see

Go to `apps/mouth/src/app/kbli/**` + `apps/mouth/src/lib/kbli-*.ts`. Dataset quality gates:
`python3 scripts/kbli_dataset_lint.py` (anti-presunzione lint) and
`python3 scripts/kbli_audit_vs_oss.py` (OSS ground-truth audit).
