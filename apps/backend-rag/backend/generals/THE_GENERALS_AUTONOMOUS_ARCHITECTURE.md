# THE GENERALS: Autonomous Architecture for Project Nuzantara

**Philosophy:** Sovereign Agents within a Constitutional Framework.
**Version:** 1.0 (2026-02-09)

## 1. Governance & Philosophy

The Generals are not just workers; they are **autonomous entities** with distinct identities, responsibilities, and permissions. They operate under a "Golden Cage" philosophy:

1.  **Full Autonomy:** Agents can read, write, commit, and deploy code/content without human approval, _provided_ they pass all automated checks.
2.  **Constitutional Compliance:** The `AI_ONBOARDING.md` is the supreme law. Any action violating these rules (e.g., hardcoded secrets, no type hints) is rejected by pre-commit hooks or the CI/CD pipeline.
3.  **Proactive, Not Reactive:** Agents don't just wait for tasks. They have schedules (Cron) and watch for events (Triggers) to self-initiate work.
4.  **Radical Transparency:** Every decision, success, and failure is logged to `generals_activity` and visible in the dashboard.

## 2. The Five Generals

### 1. Coding General (The Builder)

**Identity:** Precise, rigorous, test-obsessed.
**Role:** Maintain codebase health, implement features, fix bugs.
**Monitors:**

- GitHub Issues & PRs
- Sentry Error Logs (via API)
- `TODO` comments in code
- `generals_tasks` (Type: `code`)
  **Autonomy Level:** High (Can merge PRs if tests pass).

### 2. Intelligence General (The Strategist)

**Identity:** Analytical, far-seeing, objective.
**Role:** Research market trends, analyze competitor data, provide strategic insights.
**Monitors:**

- User queries (via API)
- News feeds (via Bali Intel Scraper)
- `generals_tasks` (Type: `research`)
  **Autonomy Level:** Medium (Produces reports/recommendations, rarely code).

### 3. Antigravity General (The Orchestrator)

**Identity:** Efficient, holistic, system-aware.
**Role:** Manage deployments, resolve conflicts, keep the system running.
**Monitors:**

- Deployment status (Fly.io/Vercel)
- System Health (Health checks)
- Cross-agent conflicts
- `generals_tasks` (Type: `orchestration`)
  **Autonomy Level:** Critical (Can rollback deployments, restart services).

### 4. Marketing & Media General (The Voice)

**Identity:** Creative, engaging, trend-aware.
**Role:** Manage social presence, draft blog posts, optimize SEO.
**Monitors:**

- Content Calendar
- Trending Topics (via Perplexity)
- Social Media metrics
  **Autonomy Level:** High for drafting, Medium for publishing (Human approval often needed for final voice check initially).

### 5. Perplexity General (The Truth Seeker)

**Identity:** Skeptical, fact-focused, real-time.
**Role:** Verify claims, real-time web research, fact-check other Generals.
**Monitors:**

- "Verify this" requests
- Breaking news alerts
- Competitor pricing pages
  **Autonomy Level:** High (Read-only web access, generates verification reports).

## 3. Trigger Strategy

| General          | Cron Schedule           | Event Triggers                                                    |
| :--------------- | :---------------------- | :---------------------------------------------------------------- |
| **Coding**       | Daily 04:00 (Tech Debt) | Sentry Error (Immediate)<br>New GitHub Issue<br>PR Review Request |
| **Intelligence** | Daily 08:00 (Briefing)  | User Research Request<br>Market Anomaly Detected                  |
| **Antigravity**  | Every 5 min (Health)    | Deploy Failure<br>Database Lock Timeout<br>Disk Space Warning     |
| **Marketing**    | Daily 09:00 (Social)    | New Blog Post Published (Promote it)<br>Viral Trend Detected      |
| **Perplexity**   | Hourly (News Check)     | "Fact Check" Request<br>Competitor Site Change                    |

## 4. Conflict Resolution Protocol

When multiple Generals act autonomously, conflicts will happen. We use a **Layered Resolution Strategy**:

### Layer 1: Database Locking (Pre-Emption)

- **Mechanism:** `FOR UPDATE SKIP LOCKED` on `generals_tasks`.
- **Rule:** One task, one General. No two agents process the same task ID.

### Layer 2: Resource Locking (Concurrency)

- **Mechanism:** Shared Memory Locks in Postgres/Redis.
- **Key:** `lock:resource:{resource_id}` (e.g., `lock:file:backend/main.py`).
- **TTL:** Locks expire automatically after 60s to prevent deadlocks.

### Layer 3: Git Branching (Code Conflicts)

- **Mechanism:** Feature Branches.
  - Coding General works on `feat/issue-123`.
  - Antigravity General works on `fix/deploy-456`.
- **Resolution:**
  - Generals act as their own Release Managers.
  - If merge conflict -> General attempts `git rebase origin/main`.
  - If rebase fails -> Antigravity General is summoned to adjudicate (or fallback to human).

### Layer 4: Hierarchy (The Tie-Breaker)

- **Rule:** If Antigravity commands a stop, all other Generals must yield.
- **Reason:** System stability (Antigravity) > New Features (Coding) > Research (Intelligence).

## 5. Decision Making Trees

### Coding General: "The Bug Fix Loop"

1.  **Trigger:** Sentry reports `IndexError` in `search.py`.
2.  **Analyze:** Read stack trace.
3.  **Reproduce:** Create a reproduction script `reprod_issue_123.py`.
4.  **Confirm:** Does script fail?
    - Yes -> Proceed.
    - No -> Log "Cannot reproduce" and mark Sentry issue as "Needs Info".
5.  **Fix:** Modify code.
6.  **Verify:** Run reproduction script AND existing tests.
7.  **Commit:** `fix(search): handle empty list in search.py`
8.  **Deploy:** Push to branch, open PR.
9.  **Merge:** Check CI status. Green? Merge.

### Marketing General: "The Trend Jack"

1.  **Trigger:** Perplexity General reports "Bali Digital Nomad Visa" is trending.
2.  **Assess:** Is this relevant to Nuzantara? (Score > 0.8)
3.  **Draft:** Generate Tweet/LinkedIn post draft.
4.  **Check:** Ask Perplexity "Is this legally accurate?"
5.  **Refine:** Edit based on feedback.
6.  **Publish:**
    - Confidence > 0.95? Auto-post.
    - Confidence < 0.95? Send to Human Review via Telegram.

## 6. Implementation Architecture

### Directory Structure

```
apps/backend-rag/backend/generals/
├── coding/
│   ├── agent.py
│   ├── skills/
├── intelligence/
├── antigravity/
├── marketing/
├── perplexity/
├── core/
│   ├── base_agent.py      # Common DNA
│   ├── memory.py          # Shared Memory
│   ├── triggers.py        # Event Listeners
│   └── communications.py  # Inter-agent chat
```

### Shared Memory Schema

We extend `generals_memory` to support **Resource Locks** and **Agent State**.

```sql
CREATE TABLE generals_locks (
    resource_key VARCHAR(255) PRIMARY KEY,
    owner_general VARCHAR(50) NOT NULL,
    acquired_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);
```
