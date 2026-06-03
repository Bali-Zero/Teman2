# Residual Ops Hub — 2026-06-03 (post 3-ondate armata)

> **Audience:** whole Bali Zero / Nuzantara team. This is the single team-reachable
> record of every credential rotation, env reconstruction, privilege change, and
> open decision that came out of the 3-wave automation campaign (sessions S1–S18)
> and its residue cleanup. Anything marked **NEEDS-ANTONELLO** is blocked on a
> human-only value or an outward-facing decision.
>
> **Status legend:** ✅ done & verified · ⏳ in progress · ⛔ blocked (NEEDS-ANTONELLO) · ℹ️ informational
>
> Origin session: `b9c591db` (M5 → Pro via ssh). Master plan:
> `docs/superpowers/plans/2026-06-02-18-sessioni-armata-invincibile.md`.

---

## 1. Credential rotations

### 1.1 BRIDGE_SKILLS_API_KEY — ✅ ROTATED & VERIFIED (2026-06-03)

The Pro↔Fly skills bridge (`cell:skills` Redis stream pull) authenticates with a
dedicated `BRIDGE_SKILLS_API_KEY`. The old value had been world-readable in a
plist backup → treated as compromised. Rotated **bilaterally and atomically**.

| Side | What | Verified |
|---|---|---|
| Consumer (Pro) | `~/Library/LaunchAgents/com.nuzantara.skills-bridge-consumer.plist` → `EnvironmentVariables:BRIDGE_SKILLS_API_KEY` = new 64-hex; plist re-locked `0400`; bootout+bootstrap | `launchctl print` state=active, last exit 0 |
| Validator (Fly) | `fly secrets set BRIDGE_SKILLS_API_KEY -a nuzantara-rag` → machine `7847d95ce257d8` restarted to release v3431 | secret digest `2eff2df2a270f60b` |

**Live functional proof:** `GET https://nuzantara-rag.fly.dev/api/bridge/skills?count=1`
- with NEW key → **HTTP 200** + real payload (a CRM skill event)
- with arbitrary/invalid key → **HTTP 401**

The old leaked key is now inert (rejected server-side).

- **Code path (validator):** `apps/backend-rag/backend/app/routers/bridge.py` →
  `_check_skills_auth()` does `hmac.compare_digest(x_bridge_skills_auth, os.getenv("BRIDGE_SKILLS_API_KEY"))`,
  header alias `X-Bridge-Skills-Auth`.
- **Rotation runbook (next time):**
  1. `NEWKEY=$(openssl rand -hex 32)`
  2. Update plist env var (unlock `chmod u+w`, PlistBuddy `Set`, re-lock `chmod 0400`).
  3. `fly secrets set BRIDGE_SKILLS_API_KEY="$NEWKEY" -a nuzantara-rag` (restarts api machine ~1 min).
  4. `launchctl bootout` + `bootstrap` the consumer.
  5. Verify: `curl -H "X-Bridge-Skills-Auth: $NEWKEY" .../api/bridge/skills?count=1` → 200; fake key → 401.
  6. Shred the temp key file. **Both sides must change together or the bridge breaks.**
- **Rollback:** none needed (forward-only). If the bridge breaks, re-run the
  runbook with a fresh key — there is no "old key" to restore once Fly is set.

### 1.2 S5 checklist — ⛔ NEEDS-ANTONELLO (outward-facing)

Other long-lived secrets flagged for rotation but **not** auto-rotatable from a
session (they touch external services / third-party accounts):
`GH_TOKEN` · `FIREWORKS_API_KEY` · `SCRAPER_*` (post-publish-poller) ·
`TELEGRAM_BOT_TOKEN` · `POST_PUBLISH_SECRET`. Rotate from the owning console and
update both the consumer env and any Fly/GitHub secret.

---

## 2. Environment variables reconstructed / missing

### 2.1 WA_MIRROR_DATABASE_URL — ✅ RECONSTRUCTED & VERIFIED (2026-06-03)

- **Value:** `postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev`
- **Why deterministic:** consumer `scripts/wa-mirror-attention-classifier.py:46`
  comments *"writes to 127.0.0.1:5432/nuzantara_dev (Postgres local)"*; local PG
  login role is `nuzantara` with peer auth (no password). The WA-mirror cutover
  (2026-05-24, Symbiosis Law 2) made WhatsApp data local-only — this DB holds all
  `whatsapp_*` tables incl. `whatsapp_message_context` (23,763 rows verified).
- **What was actually missing:** the *entire URL* was absent from
  `~/.nuzantara-secrets.env`, not a password. Now appended (backup `.bak-wamirror-*`).
- **Verify:** `psql "$WA_MIRROR_DATABASE_URL" -c "SELECT count(*) FROM whatsapp_message_context;"`
  then `WA_ATTENTION_DRY_RUN=1 .venv/bin/python scripts/wa-mirror-attention-classifier.py` → exit 0.
- **Consumers:** `wa-mirror-attention-classifier.py`, `wa-mirror-attention-telegram.py`,
  `wa-mirror-strategic-recap`.

### 2.2 HEALTHCHECK_EMAIL / HEALTHCHECK_PIN — ⛔ NEEDS-ANTONELLO

Login credentials for the real account `healthcheck@balizero.com` (role=client).
**Not reconstructable** — a real login only Antonello holds. Consumer
`login-healthcheck` (every 5 min) stays exit78 until provided (it only logs, no
spam). Add both to `~/.nuzantara-secrets.env`, then `launchctl kickstart` the agent.

### 2.3 INTEL_LAKE_PRODUCER_TOKEN — ⛔ NEEDS-ANTONELLO

Opaque producer token for intel-lake drain. **Not reconstructable.** Consumer
`intel-lake.outbox-drain.minute` was bootout (no more 60 s spam). Once provided:
add to env, `launchctl bootstrap` the agent.

### 2.4 EVENTBUS_DATABASE_URL — ✅ aliased (earlier in campaign)

Set as alias of `DATABASE_URL` in `~/.nuzantara-secrets.env`. Fixed
`outbox-prune.weekly` (was exit2).

---

## 3. Privilege change

### 3.1 W38 — backend_rag_v2 SUPERUSER demotion — ✅ EXECUTED & SMOKE-TESTED (2026-06-03)

- **Action:** `ALTER ROLE backend_rag_v2 NOSUPERUSER;` on prod Postgres.
- **Why safe (pre-checked):** `backend_rag_v2` *owns* its objects + has explicit
  grants + no RLS policy depends on superuser + required extensions already
  installed. Demotion does not remove ownership or grants.
- **Smoke (PASS):** `SELECT` 77,025 rows · `CREATE TEMP TABLE`+`INSERT` (write
  path) OK · backend `/health` 200 · portal endpoints 401 (auth, not 500).
- **Rollback:** `ALTER ROLE backend_rag_v2 SUPERUSER;`
- **Still open (separate window each):** 4 more over-privileged app roles —
  `nuzantara_rag`, `zantara_rag_user`, `nuzantara_memory`, `backend_ts_user`.
  Spec: PR #1049. Demote one at a time, low-traffic window, per-role smoke.

---

## 4. Automations repaired / retired (campaign fase (c))

Backups: `~/Library/LaunchAgents-backup-20260603.tar.gz`, `~/.nuzantara-secrets.env.bak-20260603`.

| Agent | Was | Action | State |
|---|---|---|---|
| `outbox-prune.weekly` | exit2 (EVENTBUS_DATABASE_URL unset) | alias env + plist `set -a;source;set +a` | ✅ exit0 |
| `translate.hourly` | exit1 (pyenv, no httpx; then gemma4 missing) | repoint to `.venv/bin/python`; `OLLAMA_MODEL=gemma3:27b` (gemma4 was a custom model lost in the ~/.ollama wipe) | ✅ exit0 |
| `wr2.canva-renderer` | exit78 (wrapper absent) | bootout+disable (wrapper gone, killswitch off) | ℹ️ retired |
| `workspace-event-bridge-sheets-import` | exit127 (worktree deleted) | bootout+disable | ℹ️ retired |
| `wr3.editorial-bench.monthly`, `wr3.yt-metrics.weekly` | exit127 (.openclaw/bin/wr3 absent) | bootout+disable | ℹ️ retired |
| `intel-lake.outbox-drain.minute`, `e2e-probe.6h` | spam (token missing) | bootout (recoverable) | ⛔ awaits token §2.3 |
| `cell-observatory` (+selfcheck,prune) | crash (OPENROUTER/MINIMAX_API_KEY) | bootout+disable — deprecated, replaced by `com.balizero.observatory` + `observatory-server` (both running) | ℹ️ retired |

S4 worktree-cleanup cron installed: `com.nuzantara.agent-worktree-cleanup.daily`
(00:15) — worktrees 23→7, WIP preserved. W64 (`asyncpg.InterfaceError`) merged
(#1048). ~44 world-readable plist backups chmod 0400 (W65).

---

## 5. The 3 waves — final state

| Wave | Sessions | State |
|---|---|---|
| ONDA 1 | S1,S4,S5,S6,S15,S16 | ✅ merged (PR #1020–#1025) |
| ONDA 2 | S2,S3,S7,S10,S13,S14 | ✅ merged (PR #1028–#1032) — S7 had failed, recovered |
| ONDA 3 | S8,S9,S11,S12,S17,S18 | ✅ merged (PR #1052–#1057) |

### 5.1 P0 production bug found + fixed (S11 → PR #1072) — ✅ LIVE

3 portal routers (`portal_dashboard`, `portal_family`, `portal_notification_prefs`)
were defined + in the manifest but never `include_router()`-ed in
`apps/backend-rag/backend/app/setup/router_registration.py` → **404 in prod** on
Family, Settings→Notifiche, dashboard summary + iCal export. Fixed in both
`include_routers()` and `include_light_routers()`; added
`TestPortalManifestRegistrationParity` regression guard. Auto-deployed via
`fly-deploy.yml`; post-deploy curl: the 3 ex-404 endpoints now return 401
(route registered). **Resolved in prod.**

### 5.2 ONDA 3 PRs that are proposals, not activations

- **#1054 (S17):** 5 agent designs in `research/agent-craft/proposed-agents/`
  (document-intake-classifier, compliance-deadline-sentinel, lead-intake-qualifier,
  client-onboarding-orchestrator, company-docs-consistency-auditor). Merged =
  saved, **not installed**. Decision pending §6.
- **#1057 (S8):** 6 carousel briefs; render TODO (pipeline is long-running, stops
  at Telegram review gate — never auto-publishes, Law 5).
- **#1056 (S9):** 2 client dossiers (Marc Buckner visa E33G, Paco Pak property
  lease Seseh) — DRAFT / NEEDS-ANTONELLO review.
- **#1052 (S18):** rag-eval harness + golden set. Resolved villa-KBLI = **55203**
  (55193 was stale KBLI-2020). Prod-arm needs a service-role JWT (§6).

---

## 6. Open decisions (NEEDS-ANTONELLO — not blockers)

1. **S18 prod-arm:** generate a short-lived service-role JWT to arm rag-eval
   against prod (harness already runs `--offline` exit 0). *Authorized — generating.*
2. **S17 agents:** install the 5 proposed agents into `~/.claude/agents/`? (review first)
3. **S8 carousel:** complete the WR2 render, then the Telegram review gate.
4. **§1.2 / §2.2 / §2.3:** rotate S5 external secrets; provide the 2 unrecoverable
   env values (HEALTHCHECK, INTEL_LAKE).

---

*Maintained by the autonomous ops loop. The mirror in Claude memory is
`audit_3_ondate_automazioni_2026_06_03.md` (not team-reachable — this file is the
shared source of truth).*
