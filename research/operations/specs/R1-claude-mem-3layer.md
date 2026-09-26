---
spec_id: R1
title: claude-mem 3-layer progressive memory — evaluate vs current MOS
tier: research
priority: P4
effort_estimate: 60 min evaluation, 4-8h migration if adopt
status: DRAFT
basis: 2026-05-21-arming-arsenal Part 6 + ClaudeFa.st rank #2
---

# R1 — claude-mem 3-layer memory evaluation

## Problem

claude-mem (open-source) propone 3-layer progressive memory:

1. **L1 Hot** — recent conversation state (in-context)
2. **L2 Warm** — last N days session (compressed, recall on demand)
3. **L3 Cold** — long-term semantic (vector DB, semantic search)

Nuzantara current state:

- MOS SQLite (`~/.claude/memory.db`, 10.9MB, 2516 memories) — full text
- File-based `~/.claude/projects/<id>/memory/*.md` — markdown
- MEMORY.md index (200 lines hardcoded limit issue #40614)

Gap: NO semantic search (L3 cold). Memory grow linearly → SessionStart load fastest 5 importance≥7, miss historical detail.

## Context

claude-mem features:

- Vector embedding (semantic recall)
- Auto-compress old sessions
- Plugin in `~/.claude/plugins/`
- L3 querying via "remember X about Y from N weeks ago"

Risk:

- Add dependency (one more tool to maintain)
- Possible double-memory con MOS existing
- License compat (verify MIT/Apache)

## Acceptance criteria (evaluation)

- [ ] Read claude-mem README + architecture
- [ ] Test install in pilot environment (NOT prod)
- [ ] Compare query latency: MOS vs claude-mem L3 (semantic test)
- [ ] Identify migration path or "stay with MOS"
- [ ] Decision documented

## Implementation steps (evaluation)

### Step 1 — Source code review

```bash
# Find claude-mem repo
# https://github.com/<author>/claude-mem (verifica via GitHub search)
git clone <repo> /tmp/claude-mem-eval
cat /tmp/claude-mem-eval/README.md
ls /tmp/claude-mem-eval/
```

### Step 2 — Architecture diff vs MOS

| Aspect          | MOS (current)      | claude-mem                     |
| --------------- | ------------------ | ------------------------------ |
| Storage         | SQLite             | (verify: SQLite + vector DB)   |
| Semantic search | FTS5 (text)        | Vector embed                   |
| Layers          | 1 (flat)           | 3 (hot/warm/cold)              |
| Compression     | Manual archive     | Auto                           |
| CLI             | `mem`              | (verify name)                  |
| Integration     | Hook + Claude Code | Plugin in `~/.claude/plugins/` |

### Step 3 — Test install pilot

```bash
# Install in SEPARATE Claude Code profile (slot 2 maybe?)
# To avoid contaminating production MOS

mkdir -p /tmp/claude-mem-pilot/
cp -r /tmp/claude-mem-eval/* /tmp/claude-mem-pilot/
cd /tmp/claude-mem-pilot
# Follow install instructions
```

### Step 4 — Query latency benchmark

Test 10 query stylistically:

- "Find memory about Subhi onboarding"
- "What did we decide about Postgres password leak"
- "Recall Tailscale topology config"

Measure:

- MOS query: `mem query "..."` (claim <10ms target)
- claude-mem L3 query: vector search latency

### Step 5 — Migration plan (if adopt)

If decision = adopt:

1. Export MOS SQLite → JSONL
2. Import to claude-mem L3 (vector embed batch)
3. Verify recall fidelity (sample queries)
4. Deprecate MOS or keep dual-write?
5. Update SessionStart hook to read from claude-mem

If decision = stay MOS:

1. Document why (R1 memory entry)
2. Identify gap closure (semantic search via MOS alternative)

### Step 6 — Decision memory entry

```bash
cat > ~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/decision_claude_mem_evaluation_2026_05_21.md << 'EOF'
---
name: claude-mem-evaluation
description: R1 spec — evaluate claude-mem 3-layer vs MOS current. Decision: <ADOPT|STAY|HYBRID>.
metadata:
  type: decision
---

# claude-mem evaluation outcome (R1 2026-05-21)

## Decision: <ADOPT|STAY|HYBRID>

## Why

<rationale based on benchmark>

## Migration path (if ADOPT)

<list step>

## Gap closure (if STAY)

<plan to add semantic search to MOS or accept gap>
EOF
```

## Verification

### Test 1 — claude-mem install non-prod

Pilot environment ok, no contaminazione produzione MOS.

### Test 2 — Semantic query

Su 10 query, claude-mem L3 returns relevant memories with cosine similarity score.

### Test 3 — Latency

Average query <500ms (acceptable per UX).

## Rollback

```bash
# If pilot bad, just delete pilot dir
rm -rf /tmp/claude-mem-pilot
# Restore default Claude Code profile
```

## Open questions

1. **Vector DB choice**: claude-mem uses what? sqlite-vss? Chroma? Qdrant local? Verifica.
2. **Embedding model**: `text-embedding-3-small` (Nuzantara standard) supported? If not, drift risk.
3. **Resource cost**: vector DB local = disk + RAM. Quanto?
4. **OSS license**: must be MIT/Apache compatibile con Nuzantara closed-source private.
5. **Maintenance burden**: chi mantiene se Nuzantara adopt? Antonello already saturato.

## Estimated breakdown

| Step                 | Tempo      |
| -------------------- | ---------- |
| Source review        | 15 min     |
| Architecture diff    | 10 min     |
| Pilot install        | 20 min     |
| Benchmark            | 10 min     |
| Decision + memory    | 5 min      |
| **Total** evaluation | **60 min** |
| Migration if adopt   | **4-8h**   |
