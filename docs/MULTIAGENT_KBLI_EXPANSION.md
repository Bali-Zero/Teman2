# Multi-Agent KBLI Knowledge Graph Expansion

**Created:** 2026-02-08
**Strategy:** Antigravity IDE + OpenClaw Multi-Agent Orchestration
**Goal:** Expand KG from 1,563 KBLI nodes to 9,612 KBLI nodes (full Qdrant coverage)

---

## 🎯 Overview

This implementation uses **3 specialized agents** running in parallel/sequence to extract, transform, and load KBLI data from Qdrant into the PostgreSQL Knowledge Graph.

### **Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                   Multi-Agent Orchestrator                   │
│              (run_multiagent_kbli_expansion.sh)              │
└─────────────────────┬───────────────────────────────────────┘
                      │
       ┌──────────────┼──────────────┐
       │              │              │
       ▼              ▼              ▼
┌──────────┐   ┌──────────┐  ┌──────────┐
│ Agent 1  │   │ Agent 2  │  │ Agent 3  │
│ Research │──▶│  Coding  │─▶│  Coding  │
│          │   │          │  │          │
│ Extract  │   │Transform │  │  Insert  │
│  KBLI    │   │   to KG  │  │   to PG  │
└────┬─────┘   └────┬─────┘  └────┬─────┘
     │              │              │
     ▼              ▼              ▼
  Qdrant      JSON (nodes)    PostgreSQL
  (9,612)     JSON (edges)    (kg_nodes)
                              (kg_edges)
```

---

## 📦 Files Created

### **Agent Scripts:**

```
scripts/agents/
├── agent1_extract_kbli_qdrant.py    # Extract from Qdrant (Research agent)
├── agent2_transform_kg_entities.py  # Transform to KG format (Coding agent)
├── agent3_insert_postgresql.py      # Insert to PostgreSQL (Coding agent)
└── run_multiagent_kbli_expansion.sh # Orchestrator (coordinates all 3)
```

### **Data Flow:**

```
data/
├── kbli_extraction_YYYYMMDD_HHMMSS.json  # Agent 1 output
└── kg_entities_YYYYMMDD_HHMMSS.json      # Agent 2 output
                                          # Agent 3 reads from here
```

---

## 🚀 Execution

### **Prerequisites:**

1. **Virtualenv activated:**

   ```bash
   cd apps/backend-rag
   source .venv/bin/activate
   ```

2. **Environment variables set:**

   ```bash
   export QDRANT_URL="https://your-qdrant-url"
   export QDRANT_API_KEY="your-key"
   export DATABASE_URL="postgresql://..."
   ```

3. **OpenClaw configured** (optional for monitoring):
   ```bash
   openclaw --version  # Should be 2026.2.3-1+
   ```

### **Run All Agents (Sequential):**

```bash
cd scripts/agents
./run_multiagent_kbli_expansion.sh
```

**Expected output:**

```
══════════════════════════════════════════════════════════
  MULTI-AGENT KBLI EXPANSION - Orchestrator
══════════════════════════════════════════════════════════

[AGENT-1] Connecting to Qdrant...
[AGENT-1] Fetched 100 documents (total: 100)
[AGENT-1] Fetched 100 documents (total: 200)
...
[AGENT-1] ✅ Extracted 9,612 KBLI documents
[AGENT-1] ✅ Data saved to: data/kbli_extraction_20260208_031500.json

[AGENT-2] Transforming 9,612 KBLI documents...
[AGENT-2]   Processed 1,000/9,612 (10.4%)
...
[AGENT-2] ✅ Transformation complete:
[AGENT-2]    Total nodes: 12,389
[AGENT-2]      - KBLI nodes: 9,612
[AGENT-2]      - Sektor nodes: 18
[AGENT-2]      - Perizinan nodes: 2,759
[AGENT-2]    Total edges: 35,234

[AGENT-3] Inserting 12,389 nodes and 35,234 edges...
[AGENT-3]   Nodes: 5,000/12,389 processed (40.4%)
...
[AGENT-3] ✅ Nodes inserted: 12,389/12,389
[AGENT-3] ✅ Edges inserted: 35,234/35,234 (FK violations: 0)

══════════════════════════════════════════════════════════
  FINAL SUMMARY
══════════════════════════════════════════════════════════

✅ All agents completed successfully

Agent 1 (Extract):    45s
Agent 2 (Transform):  32s
Agent 3 (Insert):     89s
Total time:           166s (2m 46s)
```

### **Dry Run (Test Without DB Changes):**

```bash
./run_multiagent_kbli_expansion.sh --dry-run
```

### **Run Individual Agents:**

```bash
# Agent 1 only
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. python scripts/agents/agent1_extract_kbli_qdrant.py

# Agent 2 only (requires Agent 1 output)
PYTHONPATH=. python scripts/agents/agent2_transform_kg_entities.py

# Agent 3 only (requires Agent 2 output)
PYTHONPATH=. python scripts/agents/agent3_insert_postgresql.py

# Agent 3 dry run
PYTHONPATH=. python scripts/agents/agent3_insert_postgresql.py --dry-run
```

---

## 📊 Expected Results

### **Before Expansion:**

```json
{
  "summary": {
    "total_nodes": 42806,
    "total_edges": 131326,
    "kbli_nodes": 1563,       ← Only 16% coverage!
    "perizinan_nodes": 29
  }
}
```

### **After Expansion:**

```json
{
  "summary": {
    "total_nodes": ~55195,     ← +12,389 nodes (+28.9%)
    "total_edges": ~166560,    ← +35,234 edges (+26.8%)
    "kbli_nodes": 9612,        ← 100% coverage! ✅
    "perizinan_nodes": ~2788   ← +2,759 perizinan
  }
}
```

### **Verification:**

```bash
# Check via health endpoint
curl -s https://nuzantara-rag.fly.dev/health/kg-stats | jq '.summary'

# Check via PostgreSQL
psql $DATABASE_URL -c "SELECT COUNT(*) FROM kg_nodes WHERE entity_id LIKE 'kbli:%';"
# Expected: 9612

# Check perizinan
psql $DATABASE_URL -c "SELECT COUNT(*) FROM kg_nodes WHERE entity_type = 'perizinan';"
# Expected: ~2788
```

---

## 🎯 Integration with OpenClaw/Antigravity

### **Using OpenClaw Agents:**

```bash
# Spawn 3 agents in parallel (experimental)
openclaw spawn --agent research \
  --task "run Agent 1: extract KBLI from Qdrant" \
  --workspace /Users/antonellosiano/Projects/nuzantara \
  &

openclaw spawn --agent coding \
  --task "run Agent 2: transform KBLI to KG entities" \
  --workspace /Users/antonellosiano/Projects/nuzantara \
  &

openclaw spawn --agent coding \
  --task "run Agent 3: insert KG entities to PostgreSQL" \
  --workspace /Users/antonellosiano/Projects/nuzantara \
  &

# Monitor all agents
openclaw agent manager
```

### **Using Antigravity IDE:**

1. Open Antigravity IDE
2. Load workspace: `/Users/antonellosiano/Projects/nuzantara`
3. Create 3 artifacts:
   - **Artifact 1 (Agent 1):** "Extract KBLI from Qdrant"
   - **Artifact 2 (Agent 2):** "Transform to KG entities"
   - **Artifact 3 (Agent 3):** "Insert to PostgreSQL"
4. Review artifacts before execution
5. Execute sequentially or in parallel

---

## 🛡️ Error Handling

### **Agent 1 (Extract) Failures:**

- **Qdrant connection timeout:** Increase `timeout` in httpx.AsyncClient
- **API rate limit:** Add exponential backoff in scroll loop
- **Partial extraction:** Resume from `offset` (stored in temp file)

### **Agent 2 (Transform) Failures:**

- **Invalid JSON:** Check extraction file encoding (must be UTF-8)
- **Missing per_skala:** Graceful degradation (skip perizinan nodes)
- **Memory error:** Process in batches (--batch-size flag)

### **Agent 3 (Insert) Failures:**

- **PostgreSQL connection:** Uses `@db_retry` decorator (3 retries)
- **Foreign key violation:** Edges skipped if source/target nodes missing
- **Transaction timeout:** Batch size reduced to 500 (configurable)

---

## 🔍 Monitoring & Debugging

### **Check Agent Logs:**

```bash
# All logs go to stdout with [AGENT-X] prefix
./run_multiagent_kbli_expansion.sh 2>&1 | tee expansion.log

# Filter by agent
grep "\[AGENT-1\]" expansion.log
grep "\[AGENT-2\]" expansion.log
grep "\[AGENT-3\]" expansion.log
```

### **Check Data Files:**

```bash
# List all extraction files
ls -lh data/kbli_extraction_*.json

# Check file size (should be ~3-4 MB for 9,612 documents)
du -h data/kbli_extraction_*.json

# Validate JSON
python -m json.tool data/kbli_extraction_*.json > /dev/null && echo "✅ Valid JSON"
```

### **Database Verification:**

```sql
-- Count by source_collection
SELECT source_collection, COUNT(*)
FROM kg_nodes
WHERE source_collection = 'kbli_2025_final'
GROUP BY source_collection;

-- Check relationship types
SELECT relationship_type, COUNT(*)
FROM kg_edges
WHERE source_collection = 'kbli_2025_final'
GROUP BY relationship_type;
-- Expected: BELONGS_TO (~9,612), REQUIRES (~25,000+)
```

---

## 🚀 Next Steps

### **After Successful Expansion:**

1. **Verify via MCP:**

   ```bash
   # Test nuzantara-mcp server
   openclaw mcp test nuzantara-rag search_kbli "restaurant"
   # Should return all matching KBLI codes
   ```

2. **Update Memory:**
   - Update `~/.claude/projects/.../memory/MEMORY.md` with new counts
   - Document expansion date and stats

3. **Proceed with FASE 2:**
   - KBLI Scale Explosion (x4 variants per KBLI)
   - Script: `scripts/ingestion/expand_kbli_scales.py` (to be created)

4. **Deploy Backend:**
   ```bash
   cd apps/backend-rag
   fly deploy --strategy rolling
   # Health endpoint will show new counts
   ```

---

## 📚 References

- [Antigravity IDE Best Practices](https://developers.googleblog.com/build-with-google-antigravity-our-new-agentic-development-platform/)
- [OpenClaw Multi-Agent Guide](https://lilys.ai/en/notes/openclaw-tutorial-20260204/openclaw-antigravity-ai-autonomous-engineering-team)
- [Production KG Audit Results](docs/AI_ONBOARDING.md#knowledge-graph-analysis)

---

**Status:** ✅ Ready for Execution
**Prepared by:** Claude Sonnet 4.5
**Date:** 2026-02-08
