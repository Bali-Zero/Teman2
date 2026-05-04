# Zantara Onboarding for Subhi — Design Spec

**Date:** 2026-05-04
**Author:** Antonello + Claude Opus 4.7 (1M context)
**Status:** Brainstorm complete, awaiting user review before implementation
**Subject:** Subhi Darajat (Growth Systems Owner, probation 2026-04-30 → 2026-07-29)

---

## 1. Goal

Give Subhi an autonomous Claude Code "tutor" running locally on his MacBook
Pro 16GB, with **complete read access** to Bali Zero memory (except the
`Subhi/` confidential folder containing his own assessment, OSINT dossier,
and contract draft), that:

1. Speaks **bahasa Indonesia** with him (codice/commit/PR remain English)
2. Enforces his RBAC perimeter: VERDE (`apps/mouth/**`, GA4/GSC) → green-light;
   GIALLO (backend new endpoints) → escalate to Asya/Antonello pair;
   ROSSO (RAG core, Qdrant, secrets, Fly) → refuse with educational redirect.
3. Maps his work to the 60-day mission (`00_MISI_SUBHI_60_HARI_BAHASA.md`)
   with daily exercises that escalate D1 (fix tracking) → D2 (12 money pages)
   → D3 (Article-to-Tool components) → D4 (organic distribution) → D5
   (WhatsApp contextual CTAs).
4. Remains under Antonello control: MAX plan quota is Antonello's, daily
   memory mirror filtered+audited, GitHub PAT scoped `sancho/*` only,
   no Fly/Pro/secrets access.

## 2. Non-goals

- **Not** installing on Subhi's PC remotely. Subhi runs the install script
  himself, supervised live by Antonello via WhatsApp video call. Ownership
  of the setup is preserved.
- **Not** giving Subhi access to Antonello's `~/.claude/projects/.../memory/`
  directly. He sees a _daily-refreshed mirror_ in his own repo, with
  the `Subhi/` folder excluded.
- **Not** building a multi-agent orchestration. One sub-agent (`zantara-onboarding`)
  is enough for the 90-day probation. A second (`sancho-reviewer`) for
  PR review is added at week 5+ once Subhi has shipped his first PRs.
- **Not** giving NB write access (no `source_add`, `studio_create`,
  `note_create`). Read-only across all NB.

## 3. Profile recap (from clarifying questions)

Subhi's answers to the profiling questionnaire (2026-05-04):

| #   | Question                 | Answer                        | Implication                                 |
| --- | ------------------------ | ----------------------------- | ------------------------------------------- |
| 1   | OS                       | Win11 → switch to MacBook Pro | macOS (matches Antonello Pro)               |
| 2   | RAM                      | 16GB                          | Sufficient. No local Ollama.                |
| 3   | Terminal use             | Sometimes                     | VSCode integrated terminal OK               |
| 4   | Git                      | Basic (clone/commit/push)     | Linear `sancho/*` flow, no rebase chirurgia |
| 5   | VSCode                   | Daily user                    | Skip install                                |
| 6   | AI tools                 | GitHub Copilot user           | Coexist, no duplication                     |
| 7   | Account for Claude OAuth | `subhi@balizero.com`          | MAX plan #2 of Antonello's 3                |
| 8   | Internet                 | Stable                        | MCP remoti OK                               |
| 9   | Language                 | Mix bahasa+EN                 | Bahasa narrative, EN code                   |
| 10  | Setup window             | Morning 09-11 WITA            | Day 1 = morning standup window              |
| 11  | Multi-device             | Yes, often                    | Git-driven sync, no local-only state        |

## 4. Architecture

```
┌─ Subhi MacBook Pro 16GB ──────────────────────────────────────────┐
│                                                                   │
│  VSCode (Copilot stays, Claude added)                             │
│   ├── Integrated Terminal                                         │
│   │    └── claude (CLI v2.0+)                                     │
│   │         ├── OAuth: subhi@balizero.com → MAX plan #2           │
│   │         ├── Memory: /Users/subhi/.claude/projects/<repo>/     │
│   │         └── Settings: /Users/subhi/.claude/settings.json      │
│   │                                                               │
│   └── Cloned repos:                                               │
│        ├── ~/Projects/nuzantara-subhi/      ← onboarding workspace│
│        │   ├── .claude/agents/zantara-onboarding.md                  │
│        │   ├── .claude/memory-mirror/        ← daily filtered     │
│        │   ├── .claude/settings.json                              │
│        │   ├── .claude/hooks/                                     │
│        │   ├── docs/onboarding/              ← bahasa             │
│        │   ├── exercises/                    ← Day 1-7 detailed   │
│        │   └── CLAUDE.md                                          │
│        └── ~/Projects/nuzantara/             ← real work repo     │
│            (work happens on branches sancho/*)                    │
│                                                                   │
│  External MCP (read-only, scoped):                                │
│   ├── github         → PAT scoped balizero/nuzantara sancho/*     │
│   ├── notebooklm-mcp → NB-1, NB-2, NB-9, NB-OPS read              │
│   ├── filesystem     → confined to ~/Projects/nuzantara-subhi/    │
│   └── fetch          → public docs only                           │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼ git push origin sancho/<branch>
              GitHub balizero/nuzantara (branch protection main)
                              │ PR review by Antonello
                              ▼
                            Fly deploy
```

**Boundary layers (defense in depth):**

1. **OAuth-level**: MAX plan owned by Antonello, revocable.
2. **GitHub-level**: fine-grained PAT `sancho/*` write only.
3. **MCP-level**: filesystem confined to `~/Projects/nuzantara-subhi/`.
4. **Settings-level**: `permissions.deny` on Bash patterns
   (`fly|gcloud|sudo|rm -rf|curl|sh`) and Read patterns (`.env`, `.ssh`).
5. **Hook-level**: PreToolUse `subhi-bash-guard.sh` rejects out-of-scope
   commands with bahasa educational message.
6. **Sub-agent-level**: prompt explicitly refuses ROSSO topics.

## 5. The sub-agent `zantara-onboarding`

**Location:** `~/Projects/nuzantara-subhi/.claude/agents/zantara-onboarding.md`

**Frontmatter:**

```yaml
---
name: zantara-onboarding
description: Tutor Bali Zero untuk Subhi Darajat (Growth Systems Owner)
  selama 90-day probation. Use when Subhi asks about codebase Nuzantara,
  NotebookLM authority, RBAC, task routing, conventions, atau 60-day
  mission. Always responds in Bahasa Indonesia.
model: claude-sonnet-4-6
tools: Read, Grep, Glob, Bash, Edit, Write, mcp__github__*, mcp__notebooklm-mcp__*
---
```

**System prompt structure:**

- Identity (bahasa)
- HARD LANGUAGE RULE: "Selalu jawab dalam Bahasa Indonesia kepada Subhi"
- 5 main tasks (codebase, NB authority, RBAC enforcement, sancho workflow, 60-day mission)
- Boundaries (HARD): never give secrets, never push main, never touch ROSSO
- Style (santai professional, contoh konkret, koreksi halus)
- Knowledge base pointers (CLAUDE.md, docs/onboarding/, memory-mirror/)
- 5 example interactions (visa CTA → green, embedding model → red,
  what is NB-2 → answer with NB-2 query proposal)

**Permission scope:**

- Read/Grep/Glob: anywhere in repo (read-only)
- Edit/Write: confined by `permissions.deny` to `apps/mouth/**`,
  `docs/onboarding/**`, `e2e/**`, `exercises/**`. Backend/cell/organism/
  fly.toml/.github/ → denied.
- Bash: allowlist git/npm/pnpm/node/python3/pytest/playwright/gh + ls/cat/grep
- mcp**github**: scoped via PAT
- mcp**notebooklm-mcp**: read-only (no source_add/studio_create)

**Why one agent, not five:** cognitive overhead, 5x maintenance, YAGNI for 90-day probation. Adding `sancho-reviewer.md` at week 5+ is the only planned split.

## 6. Memory mirror

**Pattern:** Antonello's `~/.claude/projects/-Users-nuzantara/memory/` (231 .md files, ~2.5MB) filtered nightly into `~/Projects/nuzantara-subhi/.claude/memory-mirror/` and pushed to GitHub.

**Inclusion rule:** "Tutto eccetto cartella `Subhi/`" (per Antonello directive 2026-05-04).

**Exclude patterns (mandatory):**

- `Subhi/**` — entire confidential folder (23 files: OSINT, valutazione, contract)
- `reference_subhi_folder.md` — pointer to above
- `discovery_token_*.md` — security audits
- `MEMORY_ARCHIVE.md` — historical depth
- Any file matching content regex: `ANTHROPIC_API_KEY|sk-ant-|ghp_[a-zA-Z0-9]{36}|gho_|gsk_|antonellosiano@gmail.com|kaiser198719871987@gmail.com`

**Include:** everything else, including memories about other team members (Ari, Asya, Krisna, Damar, Surya), lessons learned, scar incidents, project memos, audits, NB references, conventions, feedback rules.

**Index `MEMORY.md` redaction:** `sed` removes lines linking to `Subhi/` folder or `reference_subhi_folder.md`.

**Sync mechanism:**

- Script: `~/Desktop/nuzantara/scripts/subhi-memory-mirror.sh` (lives on Antonello Pro, NOT in Subhi repo)
- LaunchAgent: `com.balizero.subhi-memory-mirror.daily.plist` — 04:00 WITA daily
- Push: `git push origin subhi/memory-mirror` to `balizero/nuzantara-subhi` repo
- Subhi pulls via `git pull` morning standup

**First-run safety:** manual approval. Mirror generates `_AUDIT.txt` listing included/excluded files + redaction count. Antonello receives Telegram notification, reviews `_AUDIT.txt`, manually approves first push. Subsequent runs are cron-driven without notification (unless audit anomalies detected).

## 7. MCP whitelist + permissions

**Settings file:** `~/Projects/nuzantara-subhi/.claude/settings.json`

```jsonc
{
  "model": "claude-sonnet-4-6",
  "mcpServers": {
    "github": {
      "command": "uvx",
      "args": ["mcp-server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "<PAT>" },
    },
    "notebooklm-mcp": {
      "command": "uvx",
      "args": ["notebooklm-mcp"],
      "env": { "NLM_PROFILE": "subhi" },
    },
    "filesystem": {
      "command": "uvx",
      "args": [
        "mcp-server-filesystem",
        "/Users/subhi/Projects/nuzantara-subhi",
      ],
    },
    "fetch": { "command": "uvx", "args": ["mcp-server-fetch"] },
  },
  "permissions": {
    "allow": [
      "Bash(git:*)",
      "Bash(npm:*)",
      "Bash(pnpm:*)",
      "Bash(npx:*)",
      "Bash(node:*)",
      "Bash(python3:*)",
      "Bash(pytest:*)",
      "Bash(playwright:*)",
      "Bash(gh pr:*)",
      "Bash(gh issue view:*)",
      "Bash(gh repo view:*)",
      "Bash(ls:*)",
      "Bash(cat:*)",
      "Bash(grep:*)",
      "Bash(rg:*)",
      "Bash(find:*)",
    ],
    "deny": [
      "Bash(fly:*)",
      "Bash(gcloud:*)",
      "Bash(aws:*)",
      "Bash(ssh:*)",
      "Bash(scp:*)",
      "Bash(rsync:*)",
      "Bash(rm -rf:*)",
      "Bash(curl * | bash)",
      "Bash(curl * | sh)",
      "Bash(sudo:*)",
      "Read(/Users/subhi/.ssh/**)",
      "Read(/Users/subhi/.aws/**)",
      "Read(/Users/subhi/.config/gh/**)",
      "Read(**/*.env)",
      "Read(**/.nuzantara-secrets*)",
      "Edit(**/apps/backend-rag/**)",
      "Edit(**/apps/cell/**)",
      "Edit(**/apps/organism/**)",
      "Edit(**/fly.toml)",
      "Edit(**/.github/**)",
      "Write(**/apps/backend-rag/**)",
      "Write(**/apps/cell/**)",
      "Write(**/apps/organism/**)",
    ],
  },
  "env": {
    "BALI_ZERO_USER": "subhi",
    "BALI_ZERO_ROLE": "growth-systems-owner",
    "BALI_ZERO_PROBATION_END": "2026-07-29",
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/subhi-bash-guard.sh",
          },
        ],
      },
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/subhi-session-log.sh",
          },
        ],
      },
    ],
  },
}
```

## 8. Hooks

**`subhi-bash-guard.sh`** (PreToolUse on Bash):

1. **CWD check**: reject if cwd is not under `~/Projects/nuzantara-subhi/` or `~/Projects/nuzantara/`
2. **Branch check**: if cmd is `git push`, reject unless current branch matches `sancho/*`
3. **Pattern reject**: regex match against `fly|gcloud|sudo|rm -rf /|chmod 777|curl.*\| (bash|sh)`. On match: bahasa educational message + exit 2.

**`subhi-session-log.sh`** (Stop hook):

- Append-only JSONL to `~/Projects/nuzantara-subhi/.claude/session-log.jsonl` (gitignored)
- Fields: timestamp, model, token usage (in/out/cache), cwd, exit reason
- Used for weekly onboarding review (Antonello reads, Subhi never sees it modified)

## 9. Repo structure `nuzantara-subhi`

**Type:** new private repo `balizero/nuzantara-subhi` (separate from `balizero/nuzantara`).

```
nuzantara-subhi/
├── .claude/
│   ├── agents/
│   │   ├── zantara-onboarding.md           ← THE TUTOR (bahasa)
│   │   └── sancho-reviewer.md           ← week 5+ addition
│   ├── memory-mirror/                   ← daily refresh
│   │   ├── MEMORY.md                    ← redacted index
│   │   ├── project_*.md
│   │   ├── discovery_*.md
│   │   ├── feedback_*.md
│   │   ├── reference_*.md
│   │   ├── lessons.md
│   │   └── _AUDIT.txt
│   ├── settings.json
│   └── hooks/
│       ├── subhi-bash-guard.sh
│       └── subhi-session-log.sh
├── docs/onboarding/
│   ├── 00_SELAMAT_DATANG.md
│   ├── 01_HARI_PERTAMA.md
│   ├── 02_RBAC_BAHASA.md                ← from subhi-rbac-permissions
│   ├── 03_TASK_ROUTING_BAHASA.md        ← from subhi-task-routing
│   ├── 04_BAHASA_CODEBASE_TOUR.md       ← apps/mouth/ guided tour
│   ├── 05_NB_AUTHORITY_GUIDE.md         ← how to use NB-2/NB-9
│   ├── 06_SANCHO_BRANCH_WORKFLOW.md     ← git workflow
│   ├── 07_60_DAY_MISSION_BAHASA.md      ← copy from induction kit
│   └── 99_FAQ.md
├── exercises/
│   ├── day1_setup_check.md              ← detailed below
│   ├── day2_codebase_tour.md
│   ├── day3_first_pr.md
│   ├── day4_playwright_test.md
│   ├── day5_article_inventory.md
│   ├── day6_(no_work_weekend).md
│   └── day7_money_pages_pick.md
├── CLAUDE.md                            ← project context auto-loaded
├── .gitignore                           ← session-log.jsonl, .env
└── README.md                            ← bahasa orientation
```

## 10. Exercises Day 1-7 (mapped to mission)

Mapped to `00_MISI_SUBHI_60_HARI_BAHASA.md` deliverables D1 (fix tracking)
through D5 (WhatsApp CTAs). Start date assumed: Tuesday 6 May 2026
(if Subhi has MacBook Pro from that day onward — actual start date TBD
by Antonello).

| Day | Date       | Mission ref      | Title                                    | Files touched                                                          | Visible deliverable               |
| --- | ---------- | ---------------- | ---------------------------------------- | ---------------------------------------------------------------------- | --------------------------------- |
| 1   | Tue 6 May  | §10 setup        | Setup check                              | none                                                                   | tutor reply screenshot WA         |
| 2   | Wed 7 May  | §10 + §13.1      | Codebase tour bahasa                     | read-only `FunnelFeature.tsx`, `analytics.ts`, `HeaderWhatsAppCTA.tsx` | bahasa explanation + bug analysis |
| 3   | Thu 8 May  | §D1 fix tracking | First PR `sancho/d1-funnel-tracking-fix` | edit `FunnelFeature.tsx`, `analytics.ts`                               | PR open balizero/nuzantara        |
| 4   | Fri 9 May  | §D1 test         | Playwright e2e test                      | edit `funnel-ctas.spec.ts`                                             | green test screenshot             |
| 5   | Sat 10 May | §D2 audit        | Article inventory                        | grep `apps/mouth/src/content/articles/**`                              | CSV 149 articles classified       |
| 6   | Sun 11 May | weekend          | (no work — §12.7 weekend rule)           | —                                                                      | —                                 |
| 7   | Mon 12 May | §D2 selection    | 12 money pages picked                    | NB-2/NB-9 query                                                        | bahasa rationale + slug list      |

**Beyond Day 7:** the tutor itself generates exercises on-demand when
Subhi asks "apa misi hari ini" by reading `00_MISI_SUBHI_60_HARI_BAHASA.md`

- current calendar date. No need to pre-write 60 exercises.

**Exercise template:**

```markdown
# Hari N — <bahasa title>

**Tanggal:** <YYYY-MM-DD WITA>
**Mission ref:** §<section>
**Estimasi waktu:** <minutes>

## Tujuan

## Konteks

## Pre-requisiti

## Langkah-langkah

## Verifikasi

## Kalau ada error

## Selesai?

## Linked tutor prompts
```

## 11. Pre-requisites (Antonello Day 0 prep, ~25 min)

| #   | Step                                                                   | Owner               | Time | Blocker for?     |
| --- | ---------------------------------------------------------------------- | ------------------- | ---- | ---------------- |
| 1   | MacBook Pro joined to tailnet `balizero`                               | Subhi (guided WA)   | 5min | install script   |
| 2   | SSH key Subhi MacBook generated                                        | Subhi               | 1min | git clone        |
| 3   | SSH key added to GitHub `subhi@balizero.com`                           | Subhi               | 1min | git clone        |
| 4   | GitHub fine-grained PAT scoped `balizero/nuzantara` `sancho/*` write   | Antonello           | 5min | settings.json    |
| 5   | Repo `balizero/nuzantara-subhi` created (Subhi+Antonello collaborator) | Antonello           | 2min | clone repo       |
| 6   | NLM share NB-1, NB-2, NB-9, NB-OPS to subhi@balizero.com               | Antonello (NLM CLI) | 3min | tutor NB queries |
| 7   | Tailscale ACL verified (Subhi NOT seeing `nuzantara` Pro)              | Antonello           | 5min | security         |
| 8   | MAX plan #2 OAuth login validated with subhi@balizero.com              | Antonello           | 2min | claude command   |

**Note:** Tailscale verification 2026-05-04 13:30 shows MacBook NOT yet joined to tailnet (only Windows `laptop-i9elf7cc` visible). Step 1 is the first action when MacBook arrives.

## 12. Day 1 onboarding flow (90 min total)

```
T+0    09:30 WITA  Subhi arrives kantor Kuta with MacBook
T+5    09:35       Antonello: "Open MacBook, log in macOS"
T+10   09:40       WhatsApp video call active (audio + screen share)
T+10   09:40       Antonello sends gist link to install script
T+15   09:45       Subhi: bash <(curl -sL <gist>) — follows prompts
T+30   10:00       Install complete: claude, nlm, tailscale all up
T+35   10:05       Subhi opens VSCode on ~/Projects/nuzantara-subhi/
T+40   10:10       Subhi opens integrated terminal, runs claude
T+45   10:15       Subhi: /agent zantara-onboarding halo
T+50   10:20       Tutor responds in bahasa, presents scope
T+55   10:25       Antonello verifies reply, screenshot to shared note
T+60   10:30       Subhi reads docs/onboarding/00_SELAMAT_DATANG.md
T+75   10:45       Subhi completes exercises/day1_setup_check.md
T+90   11:00       Daily standup: tomorrow Day 2 codebase tour
```

## 13. Install script overview

`scripts/subhi-tutor-install.sh` — runs on Subhi's MacBook (he executes,
NOT Antonello via SSH). Steps:

1. macOS check + Xcode CLI tools
2. Homebrew install (if absent)
3. brew install: node@20, gh
4. brew cask install: tailscale, visual-studio-code (if absent)
5. npm install -g `@anthropic-ai/claude-code`
6. brew install uv → `uv tool install notebooklm-mcp-cli`
7. tailscale up (interactive login)
8. `mkdir -p ~/Projects && cd ~/Projects`
9. `gh auth login` (web flow)
10. `gh repo clone balizero/nuzantara-subhi`
11. `gh repo clone balizero/nuzantara`
12. `claude` (interactive OAuth login with subhi@balizero.com)
13. `nlm login` (interactive Google OAuth)
14. Print next-step instructions in bahasa

## 14. Failure modes + recovery

| Symptom                               | Likely cause            | Fix                                                |
| ------------------------------------- | ----------------------- | -------------------------------------------------- |
| `claude: command not found`           | npm global path missing | re-export `~/.npm-global/bin` in `~/.zshrc`        |
| OAuth login fails                     | MAX quota / network     | check admin Anthropic, retry                       |
| MCP not loading                       | uvx missing/path        | `brew reinstall uv && uv tool install ...`         |
| `/agent zantara-onboarding` not found | wrong CWD               | must be `~/Projects/nuzantara-subhi/`              |
| NLM login fails                       | Google MFA              | `nlm login --clear` interactive                    |
| Repo clone fails                      | SSH key not registered  | `gh auth login` redo                               |
| Bash hook rejects valid command       | over-restrictive regex  | edit `subhi-bash-guard.sh` whitelist, commit, pull |

## 15. Open issues / risks

1. **MacBook not in tailnet yet** (verified 2026-05-04). Step 1 of pre-reqs blocks everything else. Antonello must guide tailscale up live with Subhi.

2. **OAuth quota MAX plan #2**: assumes Antonello has MAX plan #2 dedicated to Subhi. If not, falls back to Subhi's personal Google account → he pays for his own MAX (per `subhi-rbac-permissions.md` "PROPRIO Claude Code MAX subscription"). Antonello to confirm.

3. **NB share `subhi@balizero.com`**: requires Antonello to share NB-1/NB-2/NB-9/NB-OPS via NLM CLI before Day 1. If forgotten, tutor's NB queries return 403.

4. **Memory mirror first push** could leak content if regex misses. First-run audit + manual approval required before push. Antonello reviews `_AUDIT.txt`.

5. **GitHub PAT rotation**: PAT in `settings.json` is plaintext (Claude doesn't yet support keychain-backed PAT in MCP env). Mitigation: PAT scoped narrowly + rotate every 90 days + Subhi `.gitignore` includes `settings.json`. Trade-off accepted.

6. **Tailscale ACL**: default-allow tailnet means Subhi could `ssh nuzantara` (Pro) if Pro has SSH server enabled. Pro `Remote Login` is currently OFF (verified 2026-05-04 — but verify before Day 1). If ON, Tailscale ACL must restrict `subhi@` group.

7. **Sub-agent prompt drift**: tutor prompt is large. Risk of hallucination on edge cases (e.g., "is `apps/cell/` red or yellow?"). Mitigation: weekly Antonello review of session logs for first 30 days.

8. **Copilot coexistence**: Subhi uses Copilot in VSCode. Both tools may suggest competing edits. No technical conflict, but UX confusion possible. Mitigation: tutor docs mention Copilot is fine for inline completion, but ROSSO-bound code should not be Copilot-accepted blindly.

## 16. Implementation order

1. **Phase 0 — Pre-reqs** (Antonello, ~25 min): GitHub PAT, repo create, NLM share, tailnet check, ACL.
2. **Phase 1 — Memory mirror script** (~1h): `subhi-memory-mirror.sh` + LaunchAgent + first-run audit.
3. **Phase 2 — Repo skeleton** (~2h): `nuzantara-subhi` repo with all `.claude/`, `docs/onboarding/`, `exercises/day1-7`, `CLAUDE.md`.
4. **Phase 3 — Sub-agent + hooks** (~1.5h): `zantara-onboarding.md`, `subhi-bash-guard.sh`, `subhi-session-log.sh`, `settings.json`.
5. **Phase 4 — Install script** (~1h): `subhi-tutor-install.sh` + gist hosting.
6. **Phase 5 — Dry-run on Antonello Mini** (~30min): test full flow on a clean macOS account before Subhi sees it.
7. **Phase 6 — Day 1 live setup** (90 min, with Subhi).

**Total Antonello time pre-Day-1:** ~6 hours.
**Total Subhi time Day 1:** 90 min.

## 17. Success criteria

After Day 1:

- [ ] Subhi can run `claude` and get response in bahasa
- [ ] `/agent zantara-onboarding halo` returns scoped intro in bahasa
- [ ] `git status` works in `~/Projects/nuzantara/`
- [ ] Subhi can read `docs/onboarding/00_SELAMAT_DATANG.md`
- [ ] Hooks reject `fly` and `gcloud` commands with bahasa message

After Week 1:

- [ ] First PR `sancho/d1-funnel-tracking-fix` opened
- [ ] Memory mirror auto-pushed for 5+ consecutive days
- [ ] Subhi has invoked tutor 20+ times (session log)
- [ ] Zero ROSSO-list edit attempts (or all rejected by deny rules)

After 30 days:

- [ ] Subhi shipped 5+ PRs on `sancho/*`
- [ ] D1 (tracking fix) deployed and verified GA4
- [ ] D2 (12 money pages) at least 6/12 done
- [ ] No security incident (no leaked secret, no out-of-scope edit)

## 18. Decisions log

| #   | Decision                                                     | Rationale                                                                                         | Date       |
| --- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- | ---------- |
| 1   | Approach 1 (Local + Git sync)                                | Multi-device handled by Git pull, no cloud cost                                                   | 2026-05-04 |
| 2   | Single sub-agent (not 5 split)                               | Cognitive overhead, 90-day scope                                                                  | 2026-05-04 |
| 3   | Model `sonnet` not `opus`                                    | Quota saving, sufficient for Q&A                                                                  | 2026-05-04 |
| 4   | Tools include Edit/Write                                     | Subhi is Builder track, needs autonomy                                                            | 2026-05-04 |
| 5   | NB read-only full access                                     | Ground-truth value > minimal RBAC                                                                 | 2026-05-04 |
| 6   | Bahasa Indonesia hardcoded output                            | Subhi native, no auto-detect drift                                                                | 2026-05-04 |
| 7   | Memory: tutto eccetto cartella `Subhi/`                      | Subhi sees other team memos but not own assessment                                                | 2026-05-04 |
| 8   | Repo separato `nuzantara-subhi` (not branch)                 | RBAC cleaner                                                                                      | 2026-05-04 |
| 9   | Memory mirror first push manual approval, then cron          | Safety net                                                                                        | 2026-05-04 |
| 10  | Exercises mapped to 60-day mission deliverables              | Ground exercises in real work, not toy tasks                                                      | 2026-05-04 |
| 11  | Renamed sub-agent: `bali-zero-tutor` → `zantara-onboarding`  | Antonello directive: tie-in to Zantara brand, warmer name                                         | 2026-05-04 |
| 12  | Tutor rebalanced: 60% teacher / 30% RBAC enforcer / 10% peer | Antonello directive: Subhi must "talk with Claude and have everything explained" — not be policed | 2026-05-04 |

---

## 19. Conversational continuity layer

**Driver (Antonello, 2026-05-04):** _"voglio che Subhi possa parlare con te
e tu gli spieghi tutto"_ — the tutor must feel like a partner that
remembers prior conversations, explains the system at depth, and only
enforces RBAC when actually needed (not as primary register).

### 19.1 Memory layers — three of them

The tutor reads from three distinct memory sources, each with different
semantics:

| Layer                         | Path                                       | Refresh                         | What it holds                                                                                                |
| ----------------------------- | ------------------------------------------ | ------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Project memory mirror**     | `.claude/memory-mirror/`                   | Daily 04:00 WITA cron           | Antonello's full memory minus `Subhi/` folder — static system knowledge                                      |
| **Subhi conversation memory** | `~/.claude/projects/<encoded-cwd>/memory/` | Per-session, native Claude Code | Subhi's own past sessions: questions asked, answers given, patterns                                          |
| **Subhi tutor notes**         | `.claude/memory-mirror-subhi/`             | Stop hook on each tutor exit    | Curated facts extracted from sessions: "Subhi understood X on day N", "Confused about Y", "Working on PR #Z" |

The first is push-from-Antonello (system knowledge). The second is native
Claude Code memory (conversational). The third is **new** — generated by
the Stop hook scanning the session and writing 1-3 line summaries.

### 19.2 Sub-agent prompt rebalance

Old structure (gatekeeper-first):

```
1. Identitas
2. ATURAN BAHASA
3. 5 Tugas (codebase, NB, RBAC, sancho, mission)
4. Style
```

New structure (teacher-first):

```
1. Identitas (warmer intro)
2. ATURAN BAHASA (unchanged — hard constraint)
3. Conversational continuity (NEW — read prior session before responding)
4. 5 Tugas — REORDERED: explain codebase, NB authority, mission first;
   RBAC enforcement absorbed into examples, not a primary section
5. Boundaries (HARD — kept, but framed as "kapan kamu harus tolak", not
   as the agent's main job)
6. Style (warmer — "santai professional, partner not policeman")
```

### 19.3 Stop hook extension

`subhi-session-log.sh` (T4 Step 5) gets a second responsibility: extract
session summary and write to `.claude/memory-mirror-subhi/<date>.md`.

Pseudocode:

```bash
# After appending to session-log.jsonl:
TODAY=$(date +%Y-%m-%d)
SUMMARY_FILE=".claude/memory-mirror-subhi/${TODAY}.md"
mkdir -p "$(dirname "$SUMMARY_FILE")"

# Use jq + heuristics to extract: topics asked, files touched, decisions made
TOPICS=$(echo "$INPUT" | jq -r '.transcript // empty' | head -200 |
  grep -oE 'NB-[0-9]|FunnelFeature|sancho/|GA4|KBLI|visa|tax|property' | sort -u)
FILES=$(echo "$INPUT" | jq -r '.tool_calls[].tool_input.file_path // empty' | sort -u | head -10)

cat >> "$SUMMARY_FILE" <<EOF
## Sesi $(date +%H:%M)

**Topik:** $(echo "$TOPICS" | tr '\n' ', ')
**File disentuh:** $(echo "$FILES" | tr '\n' ', ')
**Durasi:** ~$DURATION min

EOF
```

The next session, the sub-agent's first action is to read
`.claude/memory-mirror-subhi/$(date +%Y-%m-%d).md` and the previous 3 days,
giving it concrete recall: _"Kemarin Subhi tanya tentang X, saya kasih
solusi Y, dia setuju. Hari ini probable continuation: Z."_

### 19.4 New decision facts

- **Name change**: `bali-zero-tutor` → `zantara-onboarding`. Sub-agent
  invoked as `/agent zantara-onboarding "<pertanyaan>"`. User-facing name
  in greetings: "Zantara Onboarding" (or just "Zantara" in casual reply).
- **Brand tie-in**: connects to existing Zantara persona (`zantara_core.py`
  is the production system prompt for client-facing Zantara). The tutor
  is a _training-mode_ Zantara, scoped to Subhi only, no client access.

### 19.5 Why not unify with production Zantara

Production Zantara serves clients via WhatsApp/Telegram/web/Instagram
(`apps/backend-rag/backend/channels/`). Different goals:

- Production Zantara: pricing accuracy, NPWP/NIB handling, immigration
  consultation, never-make-promises
- Onboarding Zantara: explain-the-codebase, RBAC navigation, exercise
  generation, internal mission tracking

Sharing the prompt would either bloat production (Subhi-specific guidance)
or weaken onboarding (production safety constraints irrelevant to Subhi).
Keep separate, share the _brand_, share the _bahasa default_.

---

**End of design.** Implementation pending user review.
