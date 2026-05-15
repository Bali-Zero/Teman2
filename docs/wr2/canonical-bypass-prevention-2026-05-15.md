# WR2 Canonical-Bypass Prevention Audit (2026-05-15)

> 12-pattern checklist from Gemini 3.1 Pro + Codex GPT-5.5 brainstorming after
> the v2→v3 false-PASS incident on the Bali Tourist Visa Q1-Q2 2026 carousel.
> Each pattern includes detection method + the implemented guard.

## Context

On 2026-05-15 a WR2 carousel run on `bali-tourist-visa-policy-updates-q1-q2-2026`
produced a v2 PDF with label/value overlap on 5/9 slides. The critic gate
returned PASS. Investigation revealed:

1. v2 design-architect found a renderer bug (`[:35]` hard-truncate in
   `render_dark_status_list`) and patched a session-local copy at
   `/tmp/wr2_canva_pdf_render_LOCAL.py` instead of editing the canonical
   `scripts/wr2_canva_pdf_render.py`.
2. v3 rerun reused the same `/tmp/...LOCAL.py` stale file (still bugged),
   bypassing canonical fixes committed in the meantime.
3. Critic's "vision sweep" checked Playwright PNG previews (clean) rather
   than the ReportLab PDF deliverable (bugged).

This document captures the systematic audit performed afterward.

## 12 patterns

### P0 — Already detected and fixed

#### 1. Shadow execution path (`/tmp/LOCAL.py`)

**Pattern**: agent writes a patched copy of a canonical script to `/tmp/`
during a run, then later runs reuse it instead of pulling canonical.

**Guard implemented**:
- `wr2-design-architect.md` Rule #15 (constitution-level): never write
  `/tmp/wr2_*_LOCAL*.py`. Edit canonical + commit.
- Pre-flight: at run start, delete any leftover `/tmp/wr2_*_LOCAL*.py`.

#### 2. Interpreter/worktree shadowing

**Pattern**: launchd plist pins `.venv/bin/python`, `_pdf_pipeline.py`
uses `sys.executable`, manual runs use system `python3` — different
interpreters, different `sys.path`, different cached modules.

**Guard implemented**: `_log_canonicity_banner()` in
`scripts/wr2_canva_pdf_render.py:main()` logs at startup:
- `Path(__file__).resolve()`
- `sys.executable` + `sys.version`
- `git rev-parse --short HEAD`
- `sha256(tokens.json)` first 12 chars
- WARNING if script path != canonical

Banner appears in every render log; misalignment is immediately visible.

#### 3. Critic validates wrong artifact (PNG vs PDF)

**Pattern**: critic vision sweep opens `rendered/slide-NN.png` (Playwright
CSS preview) while the actual deliverable to Canva is the ReportLab
subprocess PDF. Two parallel pipelines, different bugs.

**Guard implemented**: `wr2-critic.md` Pre-Rubric vision sweep section
hardened to require `Read` of `carousel.pdf` with `pages="1-N"` parameter,
NOT PNG previews. Sequence: sha256(PDF) → Read pages → ALSO Read hero JPGs
for Article 5.10 anchor.

#### 4. Legacy adapter masking storyboard schema drift

**Pattern**: `_schema_adapter.py` accepts pre-2026-05-13 `slide_type`
schema and silently converts to v2 `layout_family`. Hides that storyboard
still emits old format → "fix appears done" while bug remains.

**Guard implemented**: `is_legacy_schema()` now logs HIGH-VISIBILITY
metric `[wr2-schema-adapter] METRIC legacy_schema_adapted=1 draft=<id>`.
Optional hard-fail via `WR2_DISALLOW_LEGACY_SCHEMA=1` env var (recommended
cutoff 2026-06-15).

#### 5. Brand/token drift (hardcoded constants vs tokens.json SSOT)

**Pattern**: `~/.claude/skills/bali-zero-brand/tokens.json` is documented
SSOT; renderer hardcoded `COLOR_BG_ANTRACITE = "#2C2F38"` etc. Skill
maintainer updates tokens → renderer never reflects.

**Guard implemented**: `_load_brand_tokens()` reads `tokens.json` at
startup with fallback to hardcoded values. Logs drift detection
(non-blocking) when loaded value differs from baseline.

#### 6. Tigris cache overwrite (CDN stale)

**Pattern**: upload key `wr2-pdf/<draft_id>.pdf` is fixed per draft.
Retry overwrites same URL while Canva or CDN may serve old bytes.

**Guard implemented**: `_tigris.upload_pdf()` now defaults to
content-addressed key `wr2-pdf/<draft_id>/<sha8>.pdf`. Each render version
gets its own URL. Plus HEAD verification after PUT logs ETag + length.

### P1 — Detected, guard documented (not yet implemented)

#### 7. Stale bytecode / pycache shadow

**Pattern**: `scripts/__pycache__/wr2_canva_pdf_render.cpython-314.pyc`
runs old bytecode if mtime drifts or different Python version.

**Guard recommended**: run renderer subprocess with `PYTHONDONTWRITEBYTECODE=1`
or `-B`; delete `__pycache__` during deploy. Pycache cleanup is one-line
addition to `wr2_canva_pdf_apply.py`.

#### 8. Shared `/tmp/` cache races (parallel agents)

**Pattern**: `/tmp/wr2_<draft_id>.pdf` and `/tmp/wr2_hero_cache/hero_NN.jpg`
shared names. Parallel agent runs cross-contaminate.

**Guard recommended**: per-run tempdir keyed by `draft_id + attempt_uuid`.
Hero cache keyed by URL hash, not slide number.

#### 9. Env context bleed (PYTHONPATH leak)

**Pattern**: agent injects `PYTHONPATH=/tmp` for Step 2 test, leaks to
Step 7 subprocess which loads wrong library.

**Guard recommended**: `subprocess.run(env={})` with explicit allow-list
of variables needed.

#### 10. Tool emulation bypass (agent writes custom .py instead of using tool)

**Pattern**: agent decides tool is "broken", writes custom Python script
with hardcoded credentials, loses tool's safety/format logic.

**Guard recommended**: block new `.py`/`.sh` creation during ops runs
(non-dev sessions). Allow only in explicit dev mode.

### P2 — Lower severity but worth tracking

#### 11. Phantom revert (context hallucination)

**Pattern**: agent has buggy original code in context window from
session start; during "optimization" step writes over canonical file
restoring the bug.

**Guard recommended**: principle of least privilege. Production-run
agents have no write access to `scripts/`, only output dirs.

#### 12. Parallel agent overwrite race

**Pattern**: Agent A and B both writing same file path. A's critic
approves; B overwrites just before Tigris upload.

**Guard recommended**: ephemeral UUID dirs per agent, atomic moves
to publish path only after critic PASS.

## Verification

Date of audit: 2026-05-15 (post-incident)
Brainstorming participants: Gemini 3.1 Pro (free OAuth) + Codex GPT-5.5
(ChatGPT Pro subscription)
Reference incident: v3 carousel `DAHJu_EsF0U` with overlap on slides
3/4/5/6/7/8.

## Future actions

- 2026-05-22 (1 week): verify metrics `legacy_schema_adapted=1` count → 0
  in production logs (indicates storyboard has stopped emitting legacy).
- 2026-06-15: set `WR2_DISALLOW_LEGACY_SCHEMA=1` in production.
- 2026-06-15: implement P1 items #7-#10.
- 2026-07-01: implement P2 items #11-#12 (lower priority).
