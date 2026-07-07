---
date: 2026-07-02
domain: operations
session: flight M3 (Mini-Pro2, ops-hygiene-sweep worktree, operator airborne)
mandate: "GEAR 2 — (A) graveyard sweep W88-correct + worktree reap 3-AND; (B) security catch-up: vitest critical chain + Python patch-tier"
prs: ["#1915 vitest ^4.1.9", "#1925 pip 35-advisory close"]
---

# Ops Hygiene Sweep — 2026-07-02 (flight session M3)

## TL;DR

- **A/branches**: 8 remote branches deleted, all verified content-on-main by blob-per-file (W88-correct) + independent spot-check; 2 zombie + 3 stale left report-only; the 5 protected flight branches were never on origin.
- **A/worktrees**: nothing reaped. Mini's `backend-rag-livekit-audio-probe` fails 3-AND (dirty: uncommitted `local_audio` work) → report-only. Pro inspected read-only.
- **B/Node**: vitest critical GHSA-5xrq-8626-4rwp (CVE-2026-47429) closed on all 3 vulnerable packages → **PR #1915**, tests 21/21 + 47/47 + 12/12, root npm audit critical 1→0, auto-merge armed.
- **B/Python**: pip-audit found the real work — **9 vulnerable packages / 35 advisories on the prod lock**, all closed → **PR #1925**, full pytest 15,724 passed, failure set byte-identical to main-locks baseline, prod post-audit 0 vulnerable, auto-merge armed.

---

## A. Branch graveyard (W88-correct)

Tool: `scripts/branch_graveyard_cleanup.sh` (blob-per-file `content_on_main()`, never three-dot).

**Dry-run**: 0 ancestor-merged · 8 content-on-main · 2 zombie `claude/*` · 3 stale (>90d).

**Independent verification before apply** (the last grep is not delegable): blob-per-file re-executed by hand on the riskiest (`agent/air-m5/wr2/a3-tone-per-tier`, last commit 0d — squash-landed today) and one control (`regulatory-watcher-20260616`): all blobs identical on main.

**Applied — 8 deleted from origin** (re-fetch + grep proves 0 survivors, 120 refs remain):
`feat/bvcl-sampling-infra-2026-05-13`, `docs/r5-phase2-indexing-parity-audit-2026-05-16`, `chore/wr2-intel-cleanup-2026-05-21`, `feat/wa-dashboard-m1-readonly-2026-05-25`, `agent/nuzantara/wr2/wr2-cron-audit-2026-05-26`, `worktree-vercel-deploy-cost-cut`, `agent/nuzantara/ops/regulatory-watcher-20260616`, `agent/air-m5/wr2/a3-tone-per-tier`.

**Report-only (content NOT on main — operator decision)**:
- Zombie `claude/*`: `claude/review-cell-genome-concept-RRwat` (55d), `claude/slack-session-Eef2p` (46d)
- Stale >90d: `backend-quality` (96d), `air` (95d), `feature/layer2-openapi-pipeline` (92d)
- Superseded by #1915: `agent/nuzantara/infra/dependabot-vitest-bump` (2026-06-02, month-stale lockfile) — deletable after #1915 merges.

Protected flight branches (`heartbeat-organs`, `wr2-next-c123`, `sonnet5-cron`, `modus-bench-run1`, `registry-audit-run2`) were never on origin — the apply could not touch them by construction; verified anyway.

## A2. Worktree reap (3-AND: no live process ∧ no lease ∧ content-on-main)

**Mini** — `backend-rag-livekit-audio-probe`: lsof empty ✓, no `agent_lock:*` in Redis ✓, branch has 0 unique commits ✓ **BUT worktree dirty** with uncommitted work (`local_audio/` services, tests, `requirements-livekit-worker.txt`, dedicated venv). Uncommitted content is not on main → 3-AND fails → **left intact** (leave-dirty toward siblings, W80).

**Pro** (read-only via ssh, never touched): 3 protected flight worktrees at cc40a125a; 3 `codex-*-runtime` worktrees detached at 75c7a5da8 (long-lived runtime lanes — W81-style armed infra, not reaped without local probes); main checkout **dirty** with sibling mata-garuda/wa-mirror work in flight (existing `PENDING-ALIGN:Pro` stands).

## B1. Node critical — vitest chain (audit 2026-06-29)

Live re-audit this session: root lockfile 1 critical (`vitest <3.2.6`, GHSA-5xrq-8626-4rwp — Vitest UI server arbitrary file read/execute). Full-repo grep found **3 vulnerable pins** (the "chain"): `admin-dashboard-local` ^1.6.0, `wa-mirror` ^2.1.8, `team-agent/bridge` ^1.2.0. All bumped to **^4.1.9** (fleet alignment).

- Tests on v4.1.9: admin-dashboard-local **21/21**, wa-mirror **47/47**, bridge **12/12**. Root npm audit **critical 1→0** (22 remain: 20 moderate + 2 low, out of scope).
- **PR #1915**, auto-merge armed; first CI round failed on `npm ci` sync — see Meta-pattern; cured by regenerating the lock with npm@10 (= CI node 22), which also cured the Snyk Node red.
- Supersedes: stale branch `dependabot-vitest-bump` (2026-06-02) and an **insufficient staged bump on Pro's main** (`^1.6.0 → ^1.6.1`, still <3.2.6 — discard on pull, will conflict with #1915).

## B2. Python security bumps (pip-audit-driven)

Interpretation declared: the Dependabot "minor-and-patch" group is mostly minor/major on floors — instead of blind floor-chasing, `pip-audit` ran on the **deployed locks**: prod = 9 vulnerable / 35 advisories. Applied patch-tier everywhere possible + minor **only where security-forced** (aiohttp, PyJWT, pypdf); majors report-only.

Bumps (locks recompiled with uv, minimal movement): aiohttp 3.14.1 · langchain 1.3.11 · langgraph-checkpoint 4.1.1 · langgraph-sdk 0.3.15 dev / 0.4.2 prod (forced: `langchain>=1.3.9 → langgraph>=1.2.4 → sdk>=0.4.2`, unsatisfiability proven by resolver; drags websockets 16.0→15.0.1 prod-only) · langsmith 0.8.18 · pydantic-settings 2.14.2 · PyJWT 2.13.0 · pypdf 6.14.2 · python-multipart 0.0.32.

- **pip-audit prod lock post: 0 vulnerable** (was 9/35). Dev lock: transformers (fix = major 5.x) + torch (CVE-2025-3000, no fix) remain — both already in the CI pip-audit ignore list (`tests.yml`), **report-only**.
- **Full pytest, ephemeral venv from the new lock**: 15,724 passed / 19 failed / 143 errors — failure set **byte-identical** (162=162, `comm` empty both directions) to a baseline venv built from main's locks in the same environment. All failures pre-existing local-env (missing `nuzantara_dev` DB, spacy model, migrations DB). **Bumps are test-neutral.**
- **PR #1925**, auto-merge armed.
- Not adopted: Dependabot minor floors (anthropic 0.113, google-genai 2.x MAJOR, otel 1.43, torch 2.12 floor, selenium 4.45, …) and `pytest-timeout>=2.4.0` (minor) — report-only, no CVE forcing them.

## §Meta-pattern

1. **The lock artifact is generator-version-dependent (W88 family, new face).** A lockfile regenerated with npm 11 is *content-different* from the same intent under CI's npm 10 — `npm ci` rejected it ("Missing: react-dom@18.3.1"), and the *same broken artifact* silently failed a second, unrelated guard (Snyk). The proxy "npm install exit 0 + tests green locally" lied about CI-armability. Antidote applied: regenerate with the CI generator version (`npx -y npm@10`), probe with the CI-identical command (`npm ci --dry-run`). Rule: **lock regeneration must use the CI's generator version, and the sync probe is `npm ci`, not `npm install`.**
2. **Esiste≠Armato at the credential layer (W87 sibling).** GitHub MCP: connected ✓, `Bad credentials` on first real call. `gh` on Mini: not authenticated. Both "exist" in tool listings; neither was armed. The working path was Pro's `gh` over ssh. Third instance of this family this quarter → the arsenal needs a per-seat 1-call health-ping, not presence checks.
3. **"Patch-tier only" is not closed under security fixes.** The langchain patch (1.3.9) transitively *requires* a minor (langgraph-sdk 0.4.2) and a downgrade (websockets 15.0.1). A tier policy on direct pins cannot bound the resolver's closure — the honest gate is the diff-vs-baseline test run, not the version arithmetic.

## §Solo-operatore

- **Pro staged `vitest ^1.6.1`**: discard (`git restore --staged`+checkout) in favour of #1915 — it is an insufficient fix and will conflict on pull.
- **Zombie/stale branches** (5, listed above): delete or rescue — content NOT on main, operator judgment.
- **transformers/torch CVEs**: fixes are major-tier (5.x) or nonexistent; embedding/CrossEncoder stack frozen by data-invariant — needs a planned migration, not a bump.
- **GitHub MCP token** dead (`Bad credentials`) + `gh` unauthenticated on Mini: rotate/re-auth if Mini should be PR-capable without Pro.
- **DeepSeek refuter balance** (already in PENDING-ARMS, HTTP 402).
- Local test env gaps on Mini (no `nuzantara_dev` DB, no spacy model in fresh venvs): 162 pre-existing failures/errors in any full local pytest — decide whether Mini should carry a full test DB.

## Evidence trail

Scratchpad (session): graveyard dry-run/apply reports, pip-audit pre/post JSON, pytest logs (bumped + baseline), uv resolver logs, failsets (`comm` proof). PRs: #1915, #1925. Deleted-branch proof: re-fetch + grep exit 1.
