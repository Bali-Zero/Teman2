# M5 unmerged worktree orphan report — 28 worktrees (no open PR)
> Generated 2026-06-27 by Claude Code. Read-only triage of M5 worktrees that are
> UNMERGED into origin/main AND have no open PR. The recurring finding: these are not
> junk — most are complete, clean features/fixes that were simply never PR'd
> (superscar #2: built-but-not-armed). Verdict legend below. NO destructive action taken.

**Verdict counts:** PR-ABLE (clean-applies): 18 · PR-ABLE (needs rebase): 5 · LIKELY-SUPERSEDED: 3 · KEEP (uncommitted): 2

## 🟢 PR-ABLE (clean-applies) (18)
| branch | age | ahead | dirty | subject | key files |
|---|---|---|---|---|---|
| `codex/fix-wa-migration-234-collision` | 6d | 1 | 0 | fix(migrations): clear 234 collision before deploy | apps/backend-rag/backend/db/migrations_v2/235_routing_proposal_quarantine_autorouted.sql,a… |
| `fix/accounting-import-button-restore` | 1d | 1 | 0 | fix(accounting): restore Import Cashout PDF button (lost in  | apps/mouth/src/app/(workspace)/accounting/page.tsx,apps/mouth/src/lib/api/workspace/accoun… |
| `agent/nuzantara/backend-rag/intake-vision-fallback` | 2d | 1 | 0 | feat(intake): add fallback page and text-layer recovery | apps/backend-rag/backend/services/intake/classify.py,apps/backend-rag/backend/services/int… |
| `agent/air-m5/backend-rag/intake-wa-priority` | 2d | 1 | 0 | fix(intake): prioritize whatsapp pending jobs | apps/backend-rag/backend/services/intake/worker.py,apps/backend-rag/backend/tests/services… |
| `agent/air-m5/docs/ig-metrics-2026` | 1d | 1 | 0 | docs(research): free competitor IG metrics feasibility (mark | research/marketing/2026-06-26-free-competitor-ig-metrics-feasibility.md |
| `agent/air-m5/docs/research-rescue-0626` | 1d | 1 | 0 | docs(research): rescue 2 deep-research captures (marketing + | research/marketing/2026-06-25-perfect-agentic-workflow-psychology-sota-comms.md,research/v… |
| `agent/air-m5/docs/rups-2026` | 4d | 2 | 3 | docs(legal): tracker CSV — 7 setup-team leaders pre-seeded | research/legal/rups-2026/00-README.md,research/legal/rups-2026/01-client-notice-rups-2026-… |
| `agent/air-m5/infra/complete-control` | 0d | 1 | 0 | fix(infra): drain drive poll backlog safely | apps/backend-rag/backend/services/crm/drive_poll_service.py,apps/backend-rag/backend/servi… |
| `agent/air-m5/infra/fly-api-diagnostics` | 0d | 1 | 0 | chore(infra): add Fly API diagnostic workflow | .github/workflows/fly-api-diagnostics.yml |
| `agent/air-m5/infra/fly-oom-detector` | 0d | 3 | 0 | fix(infra): include Fly process group in OOM alerts | .github/workflows/cron-fly-restart-detector.yml |
| `agent/air-m5/infra/intake-venv-autoheal` | 0d | 1 | 1 | fix(intake): self-heal worker venv before trusting it (scar  | apps/backend-rag/backend/services/intake/intake-worker-run.sh |
| `agent/air-m5/mouth/portal-ux-refresh-drive` | 1d | 2 | 0 | chore(ci): retrigger portal checks | apps/backend-rag/backend/app/routers/portal_drive.py,apps/backend-rag/backend/tests/unit/r… |
| `agent/air-m5/ops/git-bonifica` | 0d | 1 | 0 | fix(infra): clear stale drive worker error after success | apps/backend-rag/backend/tests/unit/workers/test_drive_poll_worker.py,apps/backend-rag/bac… |
| `agent/air-m5/ops/intake-blob-retention` | 4d | 1 | 0 | feat(intake): blob retention — reclaim disk from terminal in | infra/launchagents/com.nuzantara.intake-blob-retention.plist,infra/launchagents/intake-blo… |
| `agent/air-m5/ops/kbli-navigator-native` | 3d | 4 | 0 | docs(kbli-navigator): inline implementation plan (8 tasks, T | docs/superpowers/plans/2026-06-23-kbli-navigator-native-app.md,docs/superpowers/specs/2026… |
| `fix/worktree-isolation-overmatch-w86` | 4d | 1 | 0 | fix(hooks): worktree_isolation over-match — structural path- | infra/claude-hooks/test_w84_strip_noise_cross_line.py,infra/claude-hooks/worktree_isolatio… |
| `agent/air-m5/organism/premise-gate` | 4d | 1 | 0 | feat(hooks): premise_gate — the L1 detector (anti-false-prem | infra/claude-hooks/premise_gate.py,infra/claude-hooks/test_premise_gate.py |
| `agent/air-m5/wr2/ig-upload-endpoint` | 1d | 1 | 0 | feat(wr2): operator-gated IG publish from the app — Tigris u | apps/backend-rag/backend/app/routers/wr2_publish.py,apps/backend-rag/backend/tests/unit/ro… |

## 🟡 PR-ABLE (needs rebase) (5)
| branch | age | ahead | dirty | subject | key files |
|---|---|---|---|---|---|
| `codex/prod-rapidfuzz-hotfix` | 2d | 1 | 0 | fix(backend): include rapidfuzz in prod image | apps/backend-rag/requirements-prod.lock.txt,apps/backend-rag/requirements-prod.txt |
| `agent/air-m5/intel/kbli-book-trend-chapters` | 4d | 6 | 0 | fix(kbli): apply SEA-LION review — 3 objective ID translatio | apps/mouth/public/static/news/kbli2025-consulting-in-bali-the-first-door-to-close-cover.pn… |
| `agent/air-m5/mouth/voice-concierge` | 4d | 10 | 0 | docs: refresh docs inventory | apps/backend-rag/.env.example,apps/backend-rag/backend/app/core/config.py,apps/backend-rag… |
| `agent/air-m5/mouth/voice-spoken-tts` | 3d | 1 | 0 | fix(voice): keep local TTS on short spoken answers | apps/mouth/src/app/(workspace)/intelligence/voice-concierge/VoiceConciergeClient.test.tsx,… |
| `agent/air-m5/wr2/hero-retry-backoff` | 3d | 2 | 0 | feat(wr2): grounding module + topic-selector hook (flag-off, | research/operations/SPEC-wr2-research-step-grounding.md,scripts/wr2_grounding.py,scripts/w… |

## 🟠 LIKELY-SUPERSEDED (3)
| branch | age | ahead | dirty | subject | key files |
|---|---|---|---|---|---|
| `agent/air-m5/ops/operational-hotfixes-0618` | 8d | 2 | 3 | feat(intake): add INTAKE_GATE_DISABLED operator kill-switch  | apps/backend-rag/backend/app/core/config.py,apps/backend-rag/backend/data/bali_zero_offici… |
| `agent/air-m5/backend-rag/ig-stream-toolmap` | 6d | 3 | 2 | chore(docs): bump test count 1070→1071 (docs-sync, regressio | apps/backend-rag/backend/services/rag/agentic/orchestrator_streaming_core.py,apps/backend-… |
| `ocr-min-size-guard` | 6d | 3 | 0 | fix(intake): stage-priority claim — drain downstream before  | apps/backend-rag/backend/services/intake/classify.py,apps/backend-rag/backend/services/int… |

## 🔴 KEEP (uncommitted) (2)
| branch | age | ahead | dirty | subject | key files |
|---|---|---|---|---|---|
| `agent/air-m5/backend-rag/livekit-audio-doctor` | 5d | 8 | 25 | fix(docs): unshallow inventory audit history | apps/backend-rag/.env.example,apps/backend-rag/backend/app/core/config.py,apps/backend-rag… |
| `agent/air-m5/backend-rag/mlx-provider-l1` | 6d | 1 | 11 | feat(llm): add MLXProvider — local Apple Silicon LLM via Ope | apps/backend-rag/backend/llm/provider_registry.py,apps/backend-rag/backend/llm/providers/_… |

## Recommended next actions (Zero's call)
- 🟢 **clean-applies**: open PRs (auto-merge) — the work reaches main instead of rotting.
- 🟡 **needs rebase**: rebase onto origin/main first, then PR.
- 🟠 **superseded**: verify content is already in main by another path, then `git worktree remove` + `git branch -D`.
- 🔴 **uncommitted**: leave alone — has unsaved work (W80 risk).
