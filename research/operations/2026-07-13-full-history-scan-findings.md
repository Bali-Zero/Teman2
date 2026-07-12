---
date: 2026-07-13
domain: compliance
client_case: n/a (infra/security — Phase 1 scan results, see purge plan)
adversarial_review: devils-advocate (2026-07-13) — reviewed the purge plan this doc feeds into; findings led directly to discovering a 3rd dossier path variant + the research/visa/clients/ directory (removed via PR #2332), see amendment in 2026-07-12-git-history-pii-purge-plan.md
sources:
  - 2026-07-12-git-history-pii-purge-plan.md (this same PR, Phase 1)
  - gitleaks 8.30.1 full-history scan (25m37s, 11217 commits, 2.38GB)
  - trufflehog 3.95.9 full-history scan (14m22s, 618065 chunks)
  - targeted grep across 12367 commits (known PII/secret patterns)
---

# Phase 1 scan results — full git history

Ran all three scanners from the purge plan against the real repo (read-only,
zero writes). Two items need attention **before** the rest of the purge
planning proceeds — flagged first, separately from the bulk findings.

## 🔴 Needs Zero's decision NOW, independent of the purge timeline

### 1. Live Sentry auth token, still valid, found in history
- **Detector**: trufflehog `SentryToken`, **Verified: true** (trufflehog actually
  pinged Sentry's API and confirmed the token still authenticates — this is
  the only one of 232 findings that came back verified-live).
- **Location**: `scripts/monitoring/sentry_monitor.py:34`, commit `86ee1b71c3`
  (2025-12-18). File no longer exists in current HEAD (`git cat-file -e
  HEAD:scripts/monitoring/sentry_monitor.py` → not found) — it was deleted at
  some point, but the token was never rotated, so it still works today if
  anyone reads it out of history.
- **Why this matters independent of the history purge**: rotating a live
  credential doesn't need to wait for the git-history rewrite — you can
  revoke/rotate the Sentry token in the Sentry dashboard right now, same as
  any other secret-in-the-clear response (scar family #4). The history purge
  (Phase 2/3) removes the string from git; rotating the token removes its
  power regardless of whether the string is ever purged.
- **Recommended action** (operator[secret], same class as the API-key
  rotation done earlier this session): log into Sentry → Settings → Auth
  Tokens → revoke the token used by `sentry_monitor.py` circa Dec 2025 → if
  Sentry monitoring is still active anywhere, issue a fresh token via env var
  (never hardcoded).
- **Checked**: swept the live tree (`grep -rln "SENTRY"`, excluding
  `.venv`/`node_modules`) for any residual wiring of this specific token.
  All 6 live Sentry-related files (`sentry_config.py`, `sentry-quota-check.sh`,
  `.env.example` ×2, `oracle_universal.py`, `test_sentry_lazy_import.py`)
  read the token/DSN from `SENTRY_DSN`/`SENTRY_AUTH_TOKEN` env vars, never a
  hardcoded literal. The old token is dormant — not copied into anything live
  — but it's still a **working credential sitting in public git history**,
  which is reason enough to revoke it regardless of current wiring.

### 2. Full client due-diligence dossier, live in HEAD today, in a public repo
- **File**: `research/property/paco-pak-due-diligence-2026-05-22.html` — 3.0MB,
  **still present in current HEAD** (not just history).
- **Why flagged**: filename contains what reads as a real client identifier
  ("paco-pak"), file size (3MB) is consistent with a full exported dossier
  with embedded assets, and trufflehog's `Box` detector fired on 5 distinct
  lines (417, 454, 557, 689, 834) — consistent with embedded Box.com
  file-sharing links/tokens, which would mean this dossier links out to (or
  embeds) live cloud-storage references, not just static text.
- **I have NOT opened/read the file's content** in this pass — flagging its
  existence and location only, per this repo's PII handling discipline
  (verify existence/shape before deciding whether to look closer, and even
  then treat any real PII as something to redact, never transcribe into a
  memory/report).
- **Recommended action**: this is a **separate, likely higher-priority**
  finding than the general history purge — if it's genuinely a real client's
  due-diligence file sitting in a **public** repository today, that is an
  active exposure right now, not a historical one. Needs a human read (or an
  agent read strictly for classification, redaction-first, same pattern as
  the CRM_AUTOMATION_GUIDELINE.md incident) to confirm what's actually inside
  before deciding: redact-in-place, move to a private location, or both.
- A duplicate copy also exists at `paco-pak-due-diligence-2026-05-22.html`
  (repo root, from an earlier commit — same content, different path over
  time).

## Bulk findings summary (Phase 1 scan proper)

| Source | Result |
|---|---|
| Targeted grep (NIB/NPWP/zantara-secret-2024/admin-key-2024 patterns) | 308 matching commits — expected, mostly the already-known CRM_AUTOMATION_GUIDELINE.md + zantara-secret-2024 history, not yet deduplicated to unique root causes |
| gitleaks (11217 commits, 2.38GB, 25m37s) | 6402 raw findings — **not yet triaged**, gitleaks' generic ruleset has a high false-positive rate on a repo this size (test fixtures, example configs, lockfiles all trigger it); full JSON at `/tmp/purge-scan-reports/gitleaks-full-history.json`, needs a dedicated triage pass before being actionable |
| trufflehog (618065 chunks, 14m22s) | 232 findings, of which **1 verified-live** (the Sentry token above) and 231 unverified; **25 are venv/dependency false positives** (installed Python packages accidentally committed — a `.gitignore` gap, not a real leak); **206 remain to classify** |

### trufflehog findings by category (real repo code, venv excluded — 206 total)

| Detector | Unique files | Read as |
|---|---|---|
| Postgres | 36 | Mostly connection strings in test fixtures (`test_config.py`, `test_wr2_supervisor.py`) and docs/runbooks — likely local/test credentials, not prod, but **not yet individually confirmed** |
| GoogleGeminiAPIKey | 18 | Concentrated in one-off debug scripts (`test_gemini_key_*.py`, `list_gemini_models.py`) — looks like dev-session throwaway keys, needs confirmation none are still active |
| TelegramBotToken | 10 | Mix of plists, shell wrappers, docs — overlaps with known bot token rotation history |
| Box | 3 | The due-diligence file (flagged above) + `logo_zan.svg` (likely a false-positive — Box-pattern match inside SVG metadata, low concern) |
| SentryToken | 3 | The live one (flagged above) + 2 lockfile hits (`requirements*.lock.txt` — near-certainly a false positive, a hash or version string matching the pattern) |
| PrivateKey | 6 | `service-account.json` (Google service account — **not in current HEAD**, but the private key material is in history) + 5 scripts that likely embedded it for one-off migration/testing |
| GCP / GCPApplicationDefaultCredentials | 6 | `service-account.json` + Google Drive migration scripts (`reorganize_gdrive.py`, `scan_gdrive_*.py`) |
| FlyIO | 1 | `apps/cell/com.cell.organism.plist` |
| CloudflareApiToken, LangSmith, YoutubeApiKey, Circle | 1-2 each | Low-volume, not yet individually reviewed |

**None of these 206 have been verified live or dead yet** (trufflehog's automated
verification either doesn't support the detector type, e.g. Postgres connection
strings, or came back unverified) — that classification work is Phase 1's
remaining task, not something to guess at.

## What Phase 1 has NOT done (by design — see the plan doc)

- Has not read the content of any flagged file beyond what's needed to
  classify size/location/detector type (no PII transcribed anywhere in this
  report or in the session, per standing discipline).
- Has not deduplicated the 6402 gitleaks findings into unique root causes —
  that triage is real work, sized more like its own session than a
  sub-step here.
- Has not attempted to verify the ~205 unverified trufflehog findings that
  *can* be checked live (some detector types support it) — only the 1 that
  trufflehog auto-verified was checked.
- Has not touched Phase 2 (dry-run rewrite) or Phase 3 (the actual purge) —
  per the plan, those still require the findings to be triaged first, and
  Phase 3 specifically requires Zero's scoped GO.

## Recommended next step

Given the two flagged items above are **live exposures today**, not just
historical residue, they arguably don't need to wait for the full
purge-planning cycle:

1. Sentry token: rotate now (operator[secret], ~5 min in the Sentry dashboard).
2. `paco-pak-due-diligence-2026-05-22.html`: needs a decision — read+classify
   (redaction-first discipline) or move it out of the public repo immediately
   as a precaution while classification happens.

The bulk of the 206+6402 findings is real work but not on fire — that's the
next scoped session/lane, most likely gitleaks triage first (dedupe the 6402
down to unique root causes) since it's the noisiest input, then cross-reference
against trufflehog's more precise 206.
