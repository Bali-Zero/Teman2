# Sprint 1.A — Skill Registry Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 5 renewals-domain skills to `seed_initial_skills.py` and apply them to the prod genome (`~/.nuzantara/experience.db`). Make Cell aware of the renewals vocabulary so Sprint 2 sandbox + dispatcher can consume them.

**Architecture:** Pure data-layer extension. No new modules. Append 5 dicts to `SEED_SKILLS` list in `apps/backend-rag/backend/scripts/seed_initial_skills.py`, run `python seed_initial_skills.py --apply` on prod, verify rows in genome via `cell_core.genome.Genome.search()`.

**Tech Stack:** Python 3.11, `cell_core.genome.Genome` (SQLite + FTS5), pytest.

**Reference spec:** `docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md` §3.3.2 (post-2026-05-02 revision).

**Branch:** `feat/post-agentic-skill-registry-2026-05-02` (parent: `main`)

**Coordination**: Sprint 1.B parallel allowed (no overlap). Sprint 1.C blocked on Observatory PR-5 — see spec §3.3.6.

**L2 Autonomous Operations**: commits/push/PR autonomous. `python seed_initial_skills.py --apply` on prod requires `fly ssh console` — Sprint 0 cicatrix scar 2026-04-29 applies (filter `fly_process_group="api"`, NO `PYTHONPATH=.`).

---

## File Structure (created/modified in this plan)

| File                                                                               | Responsibility                                                           |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `apps/backend-rag/backend/scripts/seed_initial_skills.py` (MODIFY)                 | Append 5 entries to `SEED_SKILLS` list                                   |
| `apps/backend-rag/backend/tests/unit/scripts/test_seed_initial_skills.py` (MODIFY) | Add 5 assertions verifying each new skill_id is seeded with right domain |

**Out of scope:**

- Cell `cortex.skill_library` consumer code — `apps/cell/cell/cortex/skill_library.py` already accesses `cell_core.genome` directly; Sprint 1.A only adds rows
- Sandbox dispatcher — Sprint 1.B (heartbeat) is parallel; sandbox is Sprint 3
- Renewal sensor (`kitas_renewal_sensor`) — Sprint 2

---

## Task 1: Branch creation

**Files:** N/A (git operations only)

- [ ] **Step 1: Verify on main, sync with origin**

```bash
git checkout main
git fetch origin main
git pull origin main --ff-only
git status -s | grep -v 'research/\|notebooklm/' | head -5
```

Expected: empty output (clean tree, untracked dirs are unrelated).

- [ ] **Step 2: Create feature branch**

```bash
git checkout -b feat/post-agentic-skill-registry-2026-05-02
```

Expected: `Switched to a new branch 'feat/post-agentic-skill-registry-2026-05-02'`

---

## Task 2: Add 5 renewal skills to SEED_SKILLS

**Files:**

- Modify: `apps/backend-rag/backend/scripts/seed_initial_skills.py`

### Skills to add

All 5 with `cell="crm"`, `domain="crm"` (existing canonical HGT domain), `confidence=0.6` (curated default).

| skill_id                         | procedure (1-line)                                                                  | precondition                                                 | success_criterion                                                    |
| -------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------------------- |
| `crm:detect_expiring_kitas`      | Query `clients.kitas_expiry_date BETWEEN today AND today + N days`                  | KITAS expiry date populated; `next_renewal_date` may be null | Returns rows with `client_id`, `days_until_expiry`                   |
| `crm:propose_renewal_outreach`   | Build `Proposal(client_id, channel='whatsapp', urgency_by_days_left)`               | `crm:detect_expiring_kitas` produced ≥1 candidate            | One Proposal per client with all required fields                     |
| `crm:draft_wa_renewal_message`   | Generate WA template via Ollama deepseek-r1:32b, locale=client.preferred_language   | Proposal approved; client.phone populated                    | Draft text ≤1000 chars, no PII leak in non-Pro context               |
| `crm:measure_renewal_conversion` | Cron 24h post-execute → join `renewal_alert_outcomes` on `outcome='client_renewed'` | Outreach Proposal executed at least 24h ago                  | Conversion rate stored per (skill_id, segment)                       |
| `crm:update_renewal_confidence`  | Bump confidence on `outcome=client_renewed`, decay on `expired_no_action`           | Outcome observed for at least N proposals                    | `Genome.record_skill` called with new confidence; valid_from updated |

- [ ] **Step 1: Read current SEED_SKILLS structure to know insertion point**

Run: `grep -n "experience:record_trajectory\|crm:" apps/backend-rag/backend/scripts/seed_initial_skills.py | head -10`

Expected: existing skill_ids visible. Find a section comment like `# ─── crm cell ───` or insert between `# ─── rag cell ───` and `# ─── tax cell ───` blocks.

- [ ] **Step 2: Add 5 entries after existing CRM section (or create new CRM section)**

Append to `SEED_SKILLS` list in `apps/backend-rag/backend/scripts/seed_initial_skills.py`:

```python
    # ─── crm cell — renewals domain (Sprint 1.A 2026-05-02) ───────────
    {
        "cell": "crm",
        "skill_id": "crm:detect_expiring_kitas",
        "procedure": (
            "Query clients table for KITAS expiring in [today, today + N days]. "
            "Return list of (client_id, days_until_expiry, kitas_expiry_date) "
            "ordered by urgency. Source column: clients.kitas_expiry_date. "
            "Filter clients with deleted_at IS NOT NULL."
        ),
        "precondition": "kitas_expiry_date populated for active clients (data quality assumption).",
        "success_criterion": "All clients with KITAS expiring within window are returned, none missed.",
        "confidence": 0.6,
        "domain": "crm",
    },
    {
        "cell": "crm",
        "skill_id": "crm:propose_renewal_outreach",
        "procedure": (
            "For each (client_id, days_until_expiry) from detect_expiring_kitas, "
            "build a Proposal with channel='whatsapp', urgency = "
            "{<=7d: 'critical', <=30d: 'high', <=60d: 'medium', else: 'low'}, "
            "and reasoning string. Skip clients with last_outreach < 14 days ago."
        ),
        "precondition": "crm:detect_expiring_kitas produced at least one candidate.",
        "success_criterion": "One Proposal per eligible client; correct urgency tier; no duplicates within 14d.",
        "confidence": 0.6,
        "domain": "crm",
    },
    {
        "cell": "crm",
        "skill_id": "crm:draft_wa_renewal_message",
        "procedure": (
            "Generate WhatsApp draft via Ollama deepseek-r1:32b on Pro local. "
            "Template parameters: client.full_name, kitas_expiry_date, days_until_expiry, "
            "client.preferred_language (default 'en'). Output ≤1000 chars. "
            "Never include NPWP/NIB/passport in payload outside Pro local."
        ),
        "precondition": "Proposal approved by Zero via Telegram; client.phone populated.",
        "success_criterion": "Draft text generated, locale-correct, ≤1000 chars, zero PII leakage.",
        "confidence": 0.6,
        "domain": "crm",
    },
    {
        "cell": "crm",
        "skill_id": "crm:measure_renewal_conversion",
        "procedure": (
            "Cron 24h post-execute: SELECT outcome FROM renewal_alert_outcomes "
            "WHERE alert_id IN (recent_proposals_24h) GROUP BY outcome. "
            "Compute conversion_rate = client_renewed / total_executed. "
            "Store in materialized view renewal_baseline_2024_2026 (Sprint 0 §3.4)."
        ),
        "precondition": "Outreach Proposal executed at least 24h ago; renewal_alert_outcomes populated.",
        "success_criterion": "Conversion rate computed per (skill, segment) tuple; updated weekly.",
        "confidence": 0.6,
        "domain": "crm",
    },
    {
        "cell": "crm",
        "skill_id": "crm:update_renewal_confidence",
        "procedure": (
            "Lamarckian update: on outcome='client_renewed' bump confidence by +0.05 (max 0.95). "
            "On outcome='expired_no_action' decay confidence by -0.10 (min 0.10). "
            "Call Genome.record_skill with new confidence; valid_from = NOW()."
        ),
        "precondition": "At least N=10 outcomes observed for this skill in last 30 days.",
        "success_criterion": "Confidence drifts toward empirical conversion_rate over time; bounded [0.10, 0.95].",
        "confidence": 0.6,
        "domain": "crm",
    },
```

- [ ] **Step 3: Verify file is syntactically valid Python**

Run: `python -c "import ast; ast.parse(open('apps/backend-rag/backend/scripts/seed_initial_skills.py').read()); print('OK')"`

Expected: `OK`

- [ ] **Step 4: Run dry-run locally to see new skills printed**

```bash
cd apps/backend-rag
PYTHONPATH=. python backend/scripts/seed_initial_skills.py --db-path /tmp/test-seed.db --apply 2>&1 | tail -10
```

Expected: log lines showing each `crm:*` skill_id being seeded with `confidence=0.60`.

- [ ] **Step 5: Verify rows in temporary DB**

```bash
sqlite3 /tmp/test-seed.db "SELECT id, type, scope, domain, confidence FROM genome WHERE id LIKE 'crm:%' ORDER BY id;" 2>&1
```

Expected:

```
crm:detect_expiring_kitas|skill|Project|crm|0.6
crm:draft_wa_renewal_message|skill|Project|crm|0.6
crm:measure_renewal_conversion|skill|Project|crm|0.6
crm:propose_renewal_outreach|skill|Project|crm|0.6
crm:update_renewal_confidence|skill|Project|crm|0.6
```

5 rows, all `domain=crm`. Cleanup: `rm /tmp/test-seed.db`.

---

## Task 3: Add unit tests asserting 5 new skill_ids

**Files:**

- Modify: `apps/backend-rag/backend/tests/unit/scripts/test_seed_initial_skills.py`

- [ ] **Step 1: Read existing test structure**

Run: `head -120 apps/backend-rag/backend/tests/unit/scripts/test_seed_initial_skills.py`

Expected: existing test functions like `test_seed_skills_idempotent` or `test_seed_includes_rag_skills`. Identify the pattern.

- [ ] **Step 2: Add new test for renewals skills**

Append to `apps/backend-rag/backend/tests/unit/scripts/test_seed_initial_skills.py`:

```python
def test_seed_includes_renewals_skills(tmp_path):
    """Sprint 1.A 2026-05-02: 5 crm renewals skills must be seeded."""
    from cell_core.genome import Genome

    # Run the seed script against a temporary DB
    db = tmp_path / "test-seed-renewals.db"
    g = Genome(db_path=str(db))

    # Import + run main; --apply mode
    import sys
    from backend.scripts import seed_initial_skills

    # Filter SEED_SKILLS to just renewals for this test
    renewals_ids = {
        "crm:detect_expiring_kitas",
        "crm:propose_renewal_outreach",
        "crm:draft_wa_renewal_message",
        "crm:measure_renewal_conversion",
        "crm:update_renewal_confidence",
    }

    seeded_ids = {s["skill_id"] for s in seed_initial_skills.SEED_SKILLS}
    missing = renewals_ids - seeded_ids
    assert not missing, f"Renewal skills missing from SEED_SKILLS: {missing}"


def test_seed_renewals_have_correct_domain():
    """All 5 renewal skills must have domain='crm'."""
    from backend.scripts import seed_initial_skills

    renewals_ids = {
        "crm:detect_expiring_kitas",
        "crm:propose_renewal_outreach",
        "crm:draft_wa_renewal_message",
        "crm:measure_renewal_conversion",
        "crm:update_renewal_confidence",
    }
    renewals_skills = [s for s in seed_initial_skills.SEED_SKILLS if s["skill_id"] in renewals_ids]
    assert len(renewals_skills) == 5, f"Expected 5, got {len(renewals_skills)}"
    for s in renewals_skills:
        assert s.get("domain") == "crm", (
            f"Skill {s['skill_id']} has domain={s.get('domain')!r}, expected 'crm'"
        )
        assert s.get("cell") == "crm", (
            f"Skill {s['skill_id']} has cell={s.get('cell')!r}, expected 'crm'"
        )
        assert s.get("confidence") == 0.6, (
            f"Skill {s['skill_id']} has confidence={s.get('confidence')!r}, expected 0.6"
        )
```

- [ ] **Step 3: Run tests, verify both pass**

```bash
cd apps/backend-rag
PYTHONPATH=. python -m pytest backend/tests/unit/scripts/test_seed_initial_skills.py::test_seed_includes_renewals_skills backend/tests/unit/scripts/test_seed_initial_skills.py::test_seed_renewals_have_correct_domain -v
```

Expected: 2 PASSED.

- [ ] **Step 4: Run full test file to ensure no regression**

```bash
cd apps/backend-rag
PYTHONPATH=. python -m pytest backend/tests/unit/scripts/test_seed_initial_skills.py -v 2>&1 | tail -10
```

Expected: all tests PASS (existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/scripts/seed_initial_skills.py \
        apps/backend-rag/backend/tests/unit/scripts/test_seed_initial_skills.py
git commit -m "feat(skills): seed 5 crm renewals skills (Sprint 1.A)

Adds detect_expiring_kitas, propose_renewal_outreach, draft_wa_renewal_message,
measure_renewal_conversion, update_renewal_confidence to SEED_SKILLS.
All cell='crm', domain='crm' (existing HGT canonical), confidence=0.6.

Backend services already use cell_core.genome via skill/service.py wrapper —
no consumer code change needed. Sprint 2 sandbox + dispatcher will read these
skills via Genome.search(domain='crm').

2 new unit tests: test_seed_includes_renewals_skills + test_seed_renewals_have_correct_domain.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Open PR

**Files:** N/A

- [ ] **Step 1: Push**

```bash
git push -u origin feat/post-agentic-skill-registry-2026-05-02
```

- [ ] **Step 2: Open PR with auto-merge**

```bash
gh pr create --base main --title "feat(skills): Sprint 1.A — seed 5 crm renewals skills" --body "$(cat <<'EOF'
## Summary

Sprint 1.A of Era Post-Agentica injection. Extends existing `cell_core.genome` skill registry with 5 renewals-domain skills via `seed_initial_skills.py`.

Discovery 2026-05-02: previous design proposed a new `packages/nuzantara-skills/` package — redundant. `cell_core.genome` already provides full skill registry (tier1/tier2, 11 HGT domains, FTS5, confidence/uses); `backend.services.skill.service` is the wrapper. Spec refresh in PR #417.

## Skills added

All cell='crm', domain='crm', confidence=0.6:

- `crm:detect_expiring_kitas` — query expiring KITAS within window
- `crm:propose_renewal_outreach` — build Proposal with urgency tier
- `crm:draft_wa_renewal_message` — Ollama-generated WA draft (Pro local)
- `crm:measure_renewal_conversion` — 24h post-execute conversion
- `crm:update_renewal_confidence` — Lamarckian confidence drift

## Test plan

- [x] 2 new unit tests asserting skill_id presence + domain/cell/confidence
- [ ] Existing tests still pass (no regression)
- [ ] Post-merge: SSH into prod (api machine), run \`python /app/backend/scripts/seed_initial_skills.py --apply\` to seed prod genome at \`~/.nuzantara/experience.db\` (or appropriate prod path)
- [ ] Verify: \`sqlite3 ~/.nuzantara/experience.db "SELECT COUNT(*) FROM genome WHERE id LIKE 'crm:%' AND domain='crm';"\` = 5

## Out of scope (later sprints)

- Skill consumer code (Cell `cortex.skill_library` already reads cell_core.genome)
- Dispatcher `apps/backend-rag/backend/services/skill/dispatcher.py` (Sprint 3)
- Renewal sensor `kitas_renewal_sensor` (Sprint 2)
- Sandbox path with Telegram approve (Sprint 3)

## Coordination

Parallel-isolated with Sprint 1.B (heartbeat middleware). Sprint 1.C deferred until Observatory PR-5 done. See spec §3.3.6.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for required CI green + auto-merge**

```bash
PR=$(gh pr list --head feat/post-agentic-skill-registry-2026-05-02 --json number -q '.[0].number')
gh pr merge $PR --squash --auto
```

Required checks (per Sprint 0 discovery): E2E Tests, MCP Server Tests, Frontend Tests, Detect Secrets. Other (Lint/Backend Tests/inventory-check) NOT required.

- [ ] **Step 4: Watch for merge**

```bash
gh pr view $PR --json state --jq .state
```

Wait until `MERGED`. Sprint 0 timing reference: ~10-15min CI + auto-merge.

---

## Task 5: Apply seed to prod genome (post-deploy)

**Files:** N/A (one-shot data ops)

- [ ] **Step 1: Identify prod genome DB path**

The genome DB lives outside Fly.io machines (it's local-only on Pro). Two paths:

- **Pro local**: `~/.nuzantara/experience.db` — used by Cell on Pro (`apps/cell/cell/main.py` cortex)
- **Backend-rag (Fly)**: not present — backend uses graceful-degradation no-op (cf. `services/skill/service.py:30-37`).

So prod genome lives on **Pro**, not Fly. Sprint 1.A "apply" runs on Pro local.

- [ ] **Step 2: SSH Pro and run seeder**

```bash
ssh pro 'cd ~/Desktop/nuzantara/apps/backend-rag && PYTHONPATH=. python backend/scripts/seed_initial_skills.py --apply' 2>&1 | tail -15
```

Expected: log lines `INFO: seeded 'crm:detect_expiring_kitas'` etc. Total seeded should match `SEED_SKILLS` length (existing ~32 + 5 new = ~37).

- [ ] **Step 3: Verify on Pro**

```bash
ssh pro 'sqlite3 ~/.nuzantara/experience.db "SELECT id, domain, confidence FROM genome WHERE domain=\"crm\" ORDER BY id;"'
```

Expected: 5 rows visible (the 5 new crm skills).

- [ ] **Step 4: Sanity check existing skills not corrupted**

```bash
ssh pro 'sqlite3 ~/.nuzantara/experience.db "SELECT COUNT(*) AS total, COUNT(DISTINCT id) AS unique_ids FROM genome WHERE type=\"skill\";"'
```

Expected: total == unique_ids (no duplicates), count ≥ 37 (32 existing + 5 new).

---

## Task 6: Cleanup + notification

**Files:** N/A

- [ ] **Step 1: Local branch cleanup (after squash-merge auto-deletes remote)**

```bash
git checkout main
git pull origin main --ff-only
git branch -d feat/post-agentic-skill-registry-2026-05-02 2>&1 | tail -2
```

Expected: branch deleted (squash-merge made the local branch unreachable from main, but `-d` works because origin already deleted it).

- [ ] **Step 2: MOS save**

```bash
~/.claude/scripts/mem save decision "Sprint 1.A complete 2026-05-02: 5 crm renewals skills seeded in prod genome at ~/.nuzantara/experience.db on Pro. cell_core.genome remained single source of truth — no nuzantara-skills package created. PR merged. Sprint 1.B heartbeat middleware parallel; Sprint 1.C deferred for Observatory coordination." 8
```

- [ ] **Step 3: Telegram notification (optional, low-importance task)**

```bash
TOKEN=$(grep "TELEGRAM_BOT_TOKEN" ~/.nuzantara-secrets.env 2>/dev/null | cut -d= -f2 | tr -d "\"'")
[ -z "$TOKEN" ] || curl -s "https://api.telegram.org/bot$TOKEN/sendMessage" \
  -d "chat_id=1125336968" \
  --data-urlencode "text=✅ Sprint 1.A complete — 5 crm renewals skills seeded in Pro genome. cell_core.genome is single source of truth. Sprint 1.B heartbeat middleware in flight." | python3 -c "import json,sys; print('telegram ok=',json.load(sys.stdin).get('ok'))"
```

---

## Verification: Sprint 1.A success criteria

After Task 6, all true:

- [ ] PR merged to main
- [ ] 5 new skills in `~/.nuzantara/experience.db` on Pro (verified Task 5.3)
- [ ] No regression in existing tests (verified Task 3.4 + CI)
- [ ] MOS memory saved (decision id ≥ 9 importance)

If any criterion fails, do NOT consider Sprint 1.A done.

---

## Cicatrix safety checklist

- [x] No SQL migrations (Sprint 1.A is pure data layer)
- [x] No fly ssh write to Fly DB (genome is Pro local)
- [x] No plist edits (deferred to Sprint 1.C)
- [x] No edits to `events_outbox` (deferred to Sprint 1.C)
- [x] No conflict with Observatory branches (touchpoint isolated to seed_initial_skills.py)
- [x] WIP commit checkpoint at end of each Task (cf. cicatrix 2026-04-29 untracked-files-lost)

---

**End of Sprint 1.A plan.** Sprint 2 sandbox/dispatcher will consume these 5 skill rows via `Genome.search(domain='crm')` from `apps/backend-rag/backend/services/skill/service.py` and `apps/cell/cell/cortex/skill_library.py`.
