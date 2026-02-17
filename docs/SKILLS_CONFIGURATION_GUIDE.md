# Claude Code Skills - Configuration & Lazy Loading Guide

**Date:** 2026-02-02
**Project:** Nuzantara
**Claude Code Version:** 2.1.9+

---

## Executive Summary

Skills in Claude Code are **natively lazy-loaded** - they only consume context when invoked. This document explains how to leverage skills for Nuzantara workflows while maintaining optimal token efficiency.

**Key Insight:** Skills are MORE token-efficient than CLAUDE.md content.

---

## Skills vs MCP Servers vs CLAUDE.md

| Feature              | Skills                      | MCP Servers                     | CLAUDE.md            |
| -------------------- | --------------------------- | ------------------------------- | -------------------- |
| **Loading**          | On-demand (lazy)            | On-demand (with Tool Search)    | Always loaded        |
| **Invocation**       | `/skill-name` or Skill tool | Automatic via Tool Search       | Always in context    |
| **Context Impact**   | 0 tokens until invoked      | ~8.7K tokens (with Tool Search) | ~5-10K tokens always |
| **Use Case**         | Workflows, commands         | External integrations           | Project knowledge    |
| **Token Efficiency** | ⭐⭐⭐⭐⭐                  | ⭐⭐⭐⭐                        | ⭐⭐                 |

**Recommendation:** Move repetitive workflows from CLAUDE.md to Skills for better token efficiency.

---

## How Skills Lazy Loading Works

### Native Lazy Loading (Built-in)

Skills are loaded on-demand automatically:

1. **Invocation** - User calls `/skill-name` or Skill tool
2. **Loading** - Skill definition and code are loaded into context
3. **Execution** - Skill runs with full context access
4. **Cleanup** - After execution, skill can be unloaded

**No configuration needed** - this happens automatically.

### Token Impact

```
Before invocation:     0 tokens
During execution:      ~500-2000 tokens (depends on skill size)
After execution:       0 tokens (if skill completes)
```

Contrast with CLAUDE.md:

```
Always:                ~5,000-10,000 tokens
```

---

## Recommended Skills for Nuzantara

### Development Workflow Skills

#### 1. Sentinel Runner

**Purpose:** Run quality checks before commits

```bash
# Install
claude skill install sentinel-runner

# Usage
/sentinel
```

**Why:** Automates the `./sentinel` workflow (Ruff, pytest, health checks)

#### 2. Deploy to Fly.io

**Purpose:** Deploy backend with verification

```bash
# Usage
/deploy backend
/deploy frontend
```

**Workflow:**

1. Run tests
2. Deploy to Fly.io
3. Verify health endpoints
4. Check logs for errors

#### 3. CRM Data Populator

**Purpose:** Populate CRM with test data

```bash
# Usage
/populate-crm --clients 10 --practices 20
```

**Workflow:**

1. Read client/company name lists
2. Generate realistic data
3. Insert into PostgreSQL
4. Verify insertion
5. Report summary

### Debugging Skills

#### 4. Fly Logs Analyzer

**Purpose:** Fetch and analyze production logs

```bash
# Usage
/fly-logs --app nuzantara-rag --lines 100 --filter ERROR
```

**Workflow:**

1. Fetch logs from Fly.io
2. Parse and categorize errors
3. Identify patterns
4. Suggest fixes

#### 5. Database Inspector

**Purpose:** Quick CRM database queries

```bash
# Usage
/db-inspect --table clients --limit 10
/db-inspect --query "SELECT * FROM practices WHERE status='active'"
```

### AI/RAG Skills

#### 6. Evidence Score Debugger

**Purpose:** Debug evidence scoring issues

```bash
# Usage
/debug-evidence --query "What is the visa cost?"
```

**Workflow:**

1. Run query through RAG pipeline
2. Show evidence score breakdown
3. Display chunks retrieved
4. Explain why ABSTAIN triggered (if applicable)

---

## Creating Custom Skills for Nuzantara

### Skill Structure

Skills are TypeScript/JavaScript files with this structure:

```typescript
// ~/.claude/skills/nuzantara-deploy.ts

export default {
  name: "deploy",
  description: "Deploy Nuzantara backend to Fly.io with verification",

  // This is loaded only when skill is invoked
  async run({ args, tools }) {
    // Step 1: Run tests
    const testResult = await tools.bash({
      command: "cd apps/backend-rag && source .venv/bin/activate && pytest",
      description: "Run backend tests",
    });

    if (testResult.exitCode !== 0) {
      return "❌ Tests failed. Aborting deploy.";
    }

    // Step 2: Deploy
    const deployResult = await tools.bash({
      command: "fly deploy -c apps/backend-rag/fly.toml",
      description: "Deploy to Fly.io",
    });

    // Step 3: Verify
    const healthCheck = await tools.bash({
      command: "curl https://nuzantara-rag.fly.dev/health",
      description: "Check health endpoint",
    });

    return `✅ Deploy complete!\n${healthCheck.stdout}`;
  },
};
```

### Installation

```bash
# Create skill directory
mkdir -p ~/.claude/skills/nuzantara

# Create skill file
# (use the structure above)

# Claude Code will auto-detect it
```

### Best Practices for Custom Skills

#### 1. Keep Skills Focused

✅ **Good:** `/deploy-backend` - single purpose
❌ **Bad:** `/do-everything` - kitchen sink

#### 2. Use Descriptive Names

✅ **Good:** `/populate-crm-test-data`
❌ **Bad:** `/pctd`

#### 3. Provide Clear Descriptions

```typescript
description: "Deploy Nuzantara backend to Fly.io, run health checks, and verify RAG endpoints are responding";
```

#### 4. Handle Errors Gracefully

```typescript
try {
  const result = await tools.bash({ command: "..." });
  if (result.exitCode !== 0) {
    return `❌ Failed: ${result.stderr}`;
  }
} catch (error) {
  return `❌ Error: ${error.message}`;
}
```

#### 5. Return Useful Summaries

```typescript
return `
✅ CRM populated successfully!

Created:
- 15 clients
- 23 practices
- 8 leads

Database: postgresql://localhost:15432/nuzantara_rag
`;
```

---

## Skill Marketplace

### Finding Skills

```bash
# List available skills
claude skill search

# Search for specific skills
claude skill search database
claude skill search deploy
```

### Installing from Marketplace

```bash
# Install a skill
claude skill install @author/skill-name

# List installed skills
claude skill list

# Remove a skill
claude skill uninstall @author/skill-name
```

---

## Advanced: Lazy Agent Loader Skill

There's a marketplace skill specifically for token optimization:

### Installation

```bash
claude skill install lazy-agent-loader
```

### What It Does

The **Lazy Agent Loader** skill creates a registry of available agents/workflows and loads them only when needed.

**Example:**

```typescript
// Registry (always in context, ~200 tokens)
{
  agents: [
    { name: "deploy", keywords: ["deploy", "fly.io", "production"] },
    { name: "test", keywords: ["test", "pytest", "quality"] },
    { name: "crm", keywords: ["client", "practice", "database"] },
  ];
}

// Agents loaded on-demand (~2K tokens each when needed)
```

**Token Savings:**

- Without: 6K tokens (3 agents × 2K)
- With: 200 tokens (registry only)
- Savings: 97% until agent is needed

---

## Recommended Skills for Installation

### For Nuzantara Development

1. **@official/deploy-verifier** - Deploy with verification
2. **@official/test-runner** - Smart test execution
3. **@official/log-analyzer** - Parse production logs
4. **@korallis/performance-optimization** - Code optimization suggestions
5. **@community/database-inspector** - Quick DB queries

### Installation Commands

```bash
# Install all recommended
claude skill install @official/deploy-verifier
claude skill install @official/test-runner
claude skill install @official/log-analyzer
claude skill install @korallis/performance-optimization
```

---

## Token Optimization Strategy

### Move from CLAUDE.md to Skills

**Before (in CLAUDE.md):**

```markdown
## Common Commands

### Deploy Backend

1. Run tests: `cd apps/backend-rag && pytest`
2. Deploy: `fly deploy -c apps/backend-rag/fly.toml`
3. Verify: `curl https://nuzantara-rag.fly.dev/health`

### Run Sentinel

1. Activate venv: `source .venv/bin/activate`
2. Run: `./sentinel`
3. Check results: `cat sentinel-results/latest.log`
```

**Token cost:** Always loaded (~800 tokens)

**After (as Skills):**

```bash
/deploy-backend
/sentinel
```

**Token cost:** 0 tokens until invoked

### Best of Both Worlds

- **CLAUDE.md**: Core project knowledge, architecture, critical rules
- **Skills**: Repetitive workflows, commands, procedures

---

## Monitoring Skills Usage

### Check Skills Performance

Claude Code doesn't show per-skill token usage, but you can estimate:

```bash
# Verbose mode shows tool usage
export CLAUDE_VERBOSE=true
claude

# Look for:
[Skill] Loading: deploy-backend
[Skill] Tokens: ~1,850
[Skill] Completed in 4.2s
```

### Optimization Checklist

- [ ] Identify repetitive workflows in CLAUDE.md
- [ ] Convert to skills (if >3 uses per week)
- [ ] Keep CLAUDE.md under 5K tokens
- [ ] Use skills for commands/procedures
- [ ] Use MCP servers for external integrations
- [ ] Prefer skills over long system prompts

---

## Example: CRM Populator Skill

Full implementation of a Nuzantara-specific skill:

```typescript
// ~/.claude/skills/nuzantara/populate-crm.ts

export default {
  name: "populate-crm",
  description:
    "Populate Nuzantara CRM with realistic test data for clients, companies, and practices",

  args: {
    clients: {
      type: "number",
      default: 10,
      description: "Number of clients to create",
    },
    practices: {
      type: "number",
      default: 15,
      description: "Number of practices to create",
    },
  },

  async run({ args, tools }) {
    const { clients, practices } = args;

    // Step 1: Read name lists
    const clientNames = await tools.read({
      file_path:
        "/Users/antonellosiano/Projects/nuzantara/data/client-names.txt",
    });

    const companyNames = await tools.read({
      file_path:
        "/Users/antonellosiano/Projects/nuzantara/data/company-names.txt",
    });

    // Step 2: Generate SQL
    const sql = generateCRMInsertSQL({
      clientNames: clientNames.split("\n"),
      companyNames: companyNames.split("\n"),
      numClients: clients,
      numPractices: practices,
    });

    // Step 3: Execute via postgres MCP
    const result = await tools.mcp_postgres__query({
      sql: sql,
    });

    // Step 4: Verify
    const verification = await tools.mcp_postgres__query({
      sql: "SELECT COUNT(*) FROM clients; SELECT COUNT(*) FROM practices;",
    });

    return `
✅ CRM populated successfully!

Created:
- ${clients} clients
- ${practices} practices

Total in DB:
- ${verification.rows[0].count} total clients
- ${verification.rows[1].count} total practices

Next steps:
1. View clients: /db-inspect --table clients
2. Assign leads: /assign-leads
3. Test RAG queries with client data
    `;
  },
};

function generateCRMInsertSQL({
  clientNames,
  companyNames,
  numClients,
  numPractices,
}) {
  // Implementation here
  // Generate realistic INSERT statements with:
  // - Random client names from list
  // - Random company names from list
  // - Realistic emails, phones, visa types
  // - Practice associations
}
```

**Usage:**

```bash
/populate-crm --clients 20 --practices 30
```

**Token Impact:**

- CLAUDE.md approach: ~2,000 tokens always
- Skill approach: 0 tokens until invoked, then ~1,500 tokens during execution

---

## Skills vs Hooks vs Plugins

### Quick Reference

| Type       | Purpose              | Loading          | Token Impact          |
| ---------- | -------------------- | ---------------- | --------------------- |
| **Skill**  | Workflow automation  | On-demand        | 0 until invoked       |
| **Hook**   | Event-driven actions | Auto (on events) | Minimal (~100 tokens) |
| **Plugin** | IDE integration      | Always active    | Variable              |

**For Nuzantara:** Use Skills for workflows, Hooks for automation (e.g., pre-commit checks).

---

## Migration Plan: CLAUDE.md → Skills

### Step 1: Audit CLAUDE.md

Identify content that can become skills:

- [ ] Common commands (deploy, test, etc.)
- [ ] Multi-step procedures
- [ ] Data generation scripts
- [ ] Debug workflows

### Step 2: Create Skills

For each identified workflow:

1. Create skill file in `~/.claude/skills/nuzantara/`
2. Implement with proper error handling
3. Test skill invocation
4. Remove from CLAUDE.md

### Step 3: Measure Impact

Before:

```bash
# Check CLAUDE.md size
wc -w CLAUDE.md  # ~3,000 words = ~4,000 tokens
```

After:

```bash
# Should be <1,500 words = <2,000 tokens
```

**Target:** Reduce CLAUDE.md to <2K tokens by moving workflows to skills.

---

## References

- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills)
- [Lazy Agent Loader Skill](https://mcpmarket.com/tools/skills/lazy-agent-loader)
- [Skills Hook Limitations & Solutions](https://dev.to/aabyzov/claude-code-hook-limitations-no-skill-invocation-lazy-plugin-loading-and-how-i-solved-it-44f2)
- [Performance Optimization Skill](https://claude-plugins.dev/skills/@korallis/Droidz/performance-optimization)

---

## Changelog

### 2026-02-02 - Initial Documentation

- Documented native lazy loading behavior
- Created CRM Populator skill example
- Recommended skills for Nuzantara
- Migration plan from CLAUDE.md to skills

---

**Maintained by:** Claude Code + Antonello
**Last Updated:** 2026-02-02
**Next Review:** 2026-03-02 (or when creating new skills)
