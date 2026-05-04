# Subhi Tutor Design — Addendum B (option-B revision)

**Date:** 2026-05-04 (revised same-day)
**Supersedes:** sections in `2026-05-04-subhi-tutor-design.md` listed below
**Status:** Approved, used for implementation

## Why this addendum

Re-evaluation of "separate repo `balizero/nuzantara-subhi`" decision in light
of the Tailscale tailnet (`zero@balizero.com` + `subhi@balizero.com` already
share a private network, ref `reference_tailscale_balizero.md`). The tailnet
makes a private rsync sync trivial — eliminating the need to push the entire
Bali Zero memory dump (~200 markdown files) to a GitHub repo just to
distribute it to Subhi.

Antonello directive 2026-05-04: **option B** — single repo, local scaffold,
Tailscale rsync.

## Changes vs. original design

### REMOVED

- §11 pre-req "Create `balizero/nuzantara-subhi` repo": **dropped**
- §11 pre-req "GitHub fine-grained PAT scoped repo": **dropped** (gh auth login flow is enough; PAT only needed for MCP github inside Subhi's settings.json, scoped to `balizero/nuzantara` repo only with `sancho/*` write)
- §6 "Memory mirror — Sync mechanism — `git push origin subhi/memory-mirror`": **replaced** with rsync over Tailscale
- §9 "Repo structure `nuzantara-subhi`": **replaced** with local directory `~/zantara-onboarding/`
- Decision #8 ("Repo separato `nuzantara-subhi` (not branch)"): **superseded** by Decision #13 below

### ADDED / MODIFIED

#### New §4.bis — Architecture (option B)

```
┌─ Subhi MacBook Pro 16GB ──────────────────────────────────────────┐
│                                                                   │
│  ~/zantara-onboarding/         ← static tutor setup               │
│   ├── .claude/                                                    │
│   │   ├── agents/zantara-onboarding.md                            │
│   │   ├── memory-mirror/        ← rsync target (NOT git)          │
│   │   ├── memory-mirror-subhi/  ← session summaries (local-only)  │
│   │   ├── settings.json                                           │
│   │   └── hooks/                                                  │
│   ├── docs/onboarding/          ← bahasa docs (rsync target)      │
│   ├── exercises/                ← Day 1-7 (rsync target)          │
│   ├── CLAUDE.md                                                   │
│   └── README.md                                                   │
│                                                                   │
│  ~/Projects/nuzantara/          ← MAIN work repo                  │
│   (clone of balizero/nuzantara, branches sancho/*)                │
│                                                                   │
└────────────────┬──────────────────────────────────────────────────┘
                 │ rsync over Tailscale (Pro → Mac, daily 04:00)
                 │ no GitHub, no PAT, no public exposure
                 ▼
┌─ Antonello Pro nuzantara ──────────────────────────────────────────┐
│  ~/Desktop/nuzantara/scripts/subhi/                                │
│   ├── subhi-memory-mirror.sh    ← filter Antonello memory dir      │
│   ├── subhi-rsync-push.sh       ← rsync staging → Subhi Tailscale  │
│   └── (config, tests)                                              │
│                                                                    │
│  ~/Desktop/subhi_TUTOR_KIT/     ← single-source-of-truth scaffold  │
│   (versioned in nuzantara repo at apps/zantara-onboarding/)        │
└────────────────────────────────────────────────────────────────────┘
```

#### New §6 — Memory mirror sync (replaces old §6)

**Path A (default):** rsync over Tailscale.

- Pro generates filtered mirror in `~/Desktop/subhi_TUTOR_KIT/staging/.claude/memory-mirror/`
- Cron 04:00 WITA runs `subhi-rsync-push.sh`:
  ```bash
  rsync -avz --delete \
    ~/Desktop/subhi_TUTOR_KIT/staging/.claude/memory-mirror/ \
    subhi@<subhi-tailscale-ip>:~/zantara-onboarding/.claude/memory-mirror/
  ```
- Subhi Mac: nothing to do, files appear automatically.
- If Subhi Mac offline at 04:00: rsync retries hourly until success (LaunchAgent retry logic).

**Path B (fallback):** if Tailscale connectivity fails for >24h, manual fallback:

- Antonello creates a tarball: `tar czf /tmp/subhi-mirror-$(date +%Y%m%d).tgz -C ~/Desktop/subhi_TUTOR_KIT/staging .claude/memory-mirror/`
- Sends via Telegram or AirDrop (1-2 MB tar)
- Subhi extracts: `tar xzf <file> -C ~/zantara-onboarding/`

**Path C (manual review at any time):** Antonello SSHs Subhi Mac via Tailscale (if Subhi has SSH server enabled — opt-in by Subhi, not default), runs rsync ad-hoc.

#### New §9 — Local scaffold structure (replaces old §9)

The scaffold lives in **two places**:

1. **Source of truth on Pro** (versioned in `balizero/nuzantara` at `apps/zantara-onboarding/`): the canonical version. When Antonello updates the sub-agent prompt or adds an exercise, it goes here, gets committed, and the next nightly rsync distributes to Subhi.

2. **Distributed copy on Subhi Mac** (`~/zantara-onboarding/`): rsync target. Subhi reads but does not version-control this directory. If Subhi modifies a file (e.g., his own notes), they live in `~/zantara-onboarding/local/` which rsync excludes via `--filter=':- .rsyncignore'`.

#### New decision row

| #   | Decision                                | Rationale                                                                                     | Date       |
| --- | --------------------------------------- | --------------------------------------------------------------------------------------------- | ---------- |
| 13  | Option B: single repo + Tailscale rsync | Eliminates 2nd GitHub repo, 2nd PAT, public dump of Bali Zero memory. Tailnet already exists. | 2026-05-04 |

## Plan tasks affected

| Task                                         | Change                                                                                                               |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| T0 step 3 (`gh repo create nuzantara-subhi`) | **DROP**                                                                                                             |
| T0 step 1 (PAT)                              | **SIMPLIFY**: PAT scoped only to `balizero/nuzantara`, write `sancho/*`, read repo. No 2nd repo to scope.            |
| T0 step 7 (Subhi GitHub username)            | **DROP** (no separate repo collaborator)                                                                             |
| T2 step 5+ (git push)                        | **REPLACE**: rsync over Tailscale instead of git push                                                                |
| T3 LaunchAgent                               | **MODIFY**: runs both `subhi-memory-mirror.sh` AND `subhi-rsync-push.sh`                                             |
| T3 add hourly retry agent                    | **NEW**: `com.balizero.subhi-rsync-retry.hourly.plist` retries rsync if 04:00 push failed                            |
| T4 (clone nuzantara-subhi)                   | **REPLACE**: scaffold goes to `~/Desktop/subhi_TUTOR_KIT/` on Pro, versioned in main repo `apps/zantara-onboarding/` |
| T4 step 9 (commit + push)                    | **REPLACE**: commit to main repo `apps/zantara-onboarding/`                                                          |
| T4-bis                                       | **UNCHANGED in logic**, paths shift to scaffold dir                                                                  |
| T5 (bahasa docs + exercises)                 | **UNCHANGED in logic**, paths shift to scaffold dir                                                                  |
| T6 (install script)                          | **REWRITE**: instead of `gh repo clone nuzantara-subhi`, runs Tailscale auth + initial rsync from Pro                |
| T7 (runbook)                                 | **UPDATE**: WhatsApp message language adjusted, no "wait for repo creation" steps                                    |
| T8 (Mini dry-run)                            | **UPDATE**: dry-run includes Tailscale rsync test, not git clone                                                     |
| T9 (Day 1 live)                              | **UPDATE**: minor — Subhi runs install script that triggers rsync                                                    |

## Path changes summary

| Old path                                                                                       | New path                                                                                                                                                                             |
| ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `~/Projects/nuzantara-subhi/` (Subhi Mac)                                                      | `~/zantara-onboarding/` (Subhi Mac, NOT git)                                                                                                                                         |
| `balizero/nuzantara-subhi` GitHub repo                                                         | does not exist                                                                                                                                                                       |
| `balizero/nuzantara-subhi` branch `subhi/memory-mirror`                                        | does not exist                                                                                                                                                                       |
| `~/Projects/nuzantara-subhi/.claude/agents/zantara-onboarding.md`                              | `~/zantara-onboarding/.claude/agents/zantara-onboarding.md` (Subhi Mac) AND `~/Desktop/nuzantara/apps/zantara-onboarding/.claude/agents/zantara-onboarding.md` (Pro source of truth) |
| `~/Projects/nuzantara-subhi/.claude/memory-mirror/`                                            | `~/zantara-onboarding/.claude/memory-mirror/` (rsync target)                                                                                                                         |
| Mirror script writes to `~/Projects/nuzantara-subhi/.claude/memory-mirror/` and pushes via git | Mirror script writes to `~/Desktop/subhi_TUTOR_KIT/staging/.claude/memory-mirror/` on Pro, separate rsync script ships to Subhi                                                      |

## Pre-requisites simplified

Pre-Day-1 work for Antonello, revised list (~15 min, was 25):

| #   | Step                                                                                                                        | Notes                                                                                                                                   |
| --- | --------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Verify GitHub PAT for `balizero/nuzantara` (not nuzantara-subhi)                                                            | Existing PAT reusable if scope already covers `sancho/*`                                                                                |
| 2   | Verify MAX plan #2 OAuth slot for Subhi                                                                                     | Unchanged                                                                                                                               |
| 3   | ~~Create repo nuzantara-subhi~~                                                                                             | **REMOVED**                                                                                                                             |
| 4   | NLM share NB-1, NB-2, NB-9, NB-OPS to subhi@balizero.com                                                                    | Unchanged                                                                                                                               |
| 5   | Verify Tailscale ACL — Subhi can REACH Pro on port 22 (or rsync alt) but cannot read filesystem outside the rsync drop zone | **MODIFIED**: needs RW on `~/zantara-onboarding/` only, no other Pro access                                                             |
| 6   | Pro decision: enable SSH server OR use rsync over Tailscale's built-in `ts ssh`                                             | **NEW**: required for Pro→Subhi rsync. Recommendation: use `tailscale ssh` rather than enabling macOS Remote Login (more granular ACL). |
| 7   | ~~Subhi GitHub username for collaborator add~~                                                                              | **REMOVED**                                                                                                                             |
| 8   | Confirm MacBook Pro arrival window                                                                                          | Unchanged                                                                                                                               |

## Security implications

**Pro:** lower attack surface — no public repo containing Bali Zero memory dump.
**Pro:** simpler RBAC — 1 GitHub PAT scoped narrowly.
**Pro:** faster propagation — rsync direct, no GitHub round-trip.

**Caveat:** Tailscale ACL becomes the **single point** of access control for the
mirror. Misconfigured ACL = Subhi can read Pro filesystem. Verify ACL with:

```bash
# As Antonello, simulate Subhi's tailnet view
tailscale debug acl-test --user subhi@balizero.com --dst nuzantara
# Should show: only allowed traffic is rsync drop zone (ts ssh user-restricted)
```

**Caveat:** if Subhi's MacBook is stolen, the local `~/zantara-onboarding/` is
unencrypted plain text containing Bali Zero memo, lessons, audits. Mitigation:
FileVault on (verify Day 1 setup), no critical secrets in the mirror (regex
already strips them in T2), MacBook erase remote possible via Find My Mac.

## Open questions for implementation

1. **Tailscale rsync via `ts ssh` or via raw SSH on tailnet IP?**
   - `tailscale ssh subhi@<tag>` adds tailnet-level auth (good)
   - Raw SSH on tailnet IP requires Pro Remote Login enabled (worse)
   - **Decision**: prefer `tailscale ssh` if Subhi Mac has it (ships with Tailscale 1.50+)

2. **Subhi rsync target writable by Antonello but readable by Subhi?**
   - If `~/zantara-onboarding/` is owned by `subhi`, Antonello can't rsync into it via `tailscale ssh subhi@...` without sudo
   - **Decision**: Antonello rsyncs as Subhi user (`tailscale ssh subhi@subhi-mac` then run rsync server). Or Subhi runs a pull cron on his side instead of Antonello pushing.
   - **Final**: Subhi-side **pull** cron is simpler — less ACL surgery. LaunchAgent on Subhi Mac runs `rsync ...nuzantara:/Users/nuzantara/Desktop/subhi_TUTOR_KIT/staging/...` every morning at 06:00 WITA (after Pro 04:00 generation, before Subhi 09:00 standup).

3. **Initial bootstrap (first install)** when Subhi Mac has nothing:
   - Install script runs first rsync immediately after Tailscale auth completes
   - Sets up the LaunchAgent for daily pull
   - Tested on Mini in T8

## Self-review

- [x] All 13 affected tasks mapped to changes
- [x] No orphan paths (every old path has a new path)
- [x] Security implications enumerated
- [x] 3 open questions surface decisions implementer needs
- [x] Compatible with existing Sezione 19 (conversational continuity) — no path conflict
