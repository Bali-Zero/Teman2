#!/usr/bin/env python3
"""Organize files into modules for parallel Claude work"""

import subprocess
from collections import defaultdict

# Get coverage data
result = subprocess.run(["python", "-m", "coverage", "report"], capture_output=True, text=True)

files = []
for line in result.stdout.split("\n"):
    if line.startswith("backend/"):
        parts = line.split()
        if len(parts) >= 6:
            try:
                filename = parts[0]
                stmts = int(parts[1])
                miss = int(parts[2])
                cov_str = parts[5].rstrip("%")
                coverage = float(cov_str)
                covered = stmts - miss

                if coverage < 90:
                    target_for_file = int(stmts * 0.9)
                    impact = max(0, target_for_file - covered)

                    files.append(
                        {
                            "file": filename,
                            "stmts": stmts,
                            "miss": miss,
                            "coverage": coverage,
                            "impact": impact,
                        }
                    )
            except (ValueError, IndexError):
                continue

# Group by module/functional area
modules = defaultdict(list)

for f in files:
    path = f["file"]

    # Categorize by functional area
    if "app/routers/" in path:
        # Group routers by domain
        filename = path.split("/")[-1]

        if "crm" in filename:
            modules["Routers - CRM"].append(f)
        elif "oracle" in filename:
            modules["Routers - Oracle"].append(f)
        elif filename in ["agents.py", "autonomous_agents.py", "handlers.py"]:
            modules["Routers - Agents"].append(f)
        elif filename in ["auth.py", "health.py", "productivity.py", "notifications.py"]:
            modules["Routers - Core API"].append(f)
        else:
            modules["Routers - Other"].append(f)

    elif "services/" in path:
        # Group services by domain
        filename = path.split("/")[-1]
        if "team" in filename or "work_session" in filename or "session" in filename:
            modules["Services - Team & Sessions"].append(f)
        elif "memory" in filename or "semantic_cache" in filename:
            modules["Services - Memory & Cache"].append(f)
        elif any(x in filename for x in ["search", "rag", "reranker", "knowledge"]):
            modules["Services - Search & RAG"].append(f)
        elif any(x in filename for x in ["intelligent_router", "query_router", "routing"]):
            modules["Services - Routing"].append(f)
        elif "crm" in filename or "client" in filename:
            modules["Services - CRM & Clients"].append(f)
        elif "personality" in filename or "emotional" in filename or "cultural" in filename:
            modules["Services - AI Personality"].append(f)
        elif any(x in filename for x in ["tool_executor", "zantara_tools", "handler_proxy"]):
            modules["Services - Tools & Execution"].append(f)
        elif any(x in filename for x in ["notification", "alert", "followup"]):
            modules["Services - Notifications"].append(f)
        elif any(x in filename for x in ["pricing", "dynamic_pricing"]):
            modules["Services - Pricing"].append(f)
        else:
            modules["Services - Other"].append(f)

    elif "agents/" in path:
        modules["Agents - ML & Training"].append(f)

    elif "app/main_cloud.py" in path:
        modules["Core - Application Entrypoint"].append(f)

    elif "app/metrics.py" in path:
        modules["Core - Metrics & Monitoring"].append(f)

    elif "core/" in path:
        if "plugins" in path:
            modules["Core - Plugin System"].append(f)
        elif "embeddings" in path:
            modules["Core - Embeddings"].append(f)
        else:
            modules["Core - Other"].append(f)

    elif "middleware/" in path:
        modules["Middleware"].append(f)

    elif "llm/" in path:
        modules["LLM - AI Clients"].append(f)

    elif "utils/" in path:
        modules["Utils"].append(f)

    else:
        modules["Misc"].append(f)

# Sort modules by total impact
module_summary = []
for module_name, module_files in modules.items():
    total_impact = sum(f["impact"] for f in module_files)
    total_stmts = sum(f["stmts"] for f in module_files)
    avg_coverage = (
        sum(f["coverage"] for f in module_files) / len(module_files) if module_files else 0
    )

    module_summary.append(
        {
            "name": module_name,
            "files": module_files,
            "count": len(module_files),
            "impact": total_impact,
            "stmts": total_stmts,
            "avg_coverage": avg_coverage,
        }
    )

module_summary.sort(key=lambda x: x["impact"], reverse=True)

print("=" * 100)
print("🎯 PARALLEL WORK ORGANIZATION - Distribuzione per Claude Sonnet")
print("=" * 100)
print(f"\nTotale Moduli: {len(module_summary)}")
print(f"Totale Files: {sum(m['count'] for m in module_summary)}")
print(f"Totale Impact: {sum(m['impact'] for m in module_summary):,} statements")
print()

print("=" * 100)
print("📦 MODULI ORGANIZZATI PER AREA FUNZIONALE")
print("=" * 100)
print(f"{'#':<3} {'Modulo':<40} {'Files':>6} {'Impact':>8} {'Avg Cov':>9} {'Priority':>12}")
print("-" * 100)

for i, mod in enumerate(module_summary, 1):
    priority = (
        "🔥 CRITICAL"
        if mod["impact"] > 500
        else (
            "🔴 HIGH" if mod["impact"] > 200 else ("🟠 MEDIUM" if mod["impact"] > 100 else "🟡 LOW")
        )
    )
    print(
        f"{i:<3} {mod['name']:<40} {mod['count']:>6} {mod['impact']:>8} {mod['avg_coverage']:>8.1f}% {priority:>12}"
    )

print("=" * 100)

# Create work packages for parallel execution
print("\n" + "=" * 100)
print("👥 ASSEGNAZIONE AI CLAUDE INSTANCES (Parallel Execution)")
print("=" * 100)

# Group into balanced packages
num_claudes = 5  # Recommended number of parallel instances
packages = [[] for _ in range(num_claudes)]
package_impacts = [0] * num_claudes

# Distribute modules using greedy algorithm (assign to least loaded package)
for mod in module_summary:
    # Find package with least impact
    min_idx = package_impacts.index(min(package_impacts))
    packages[min_idx].append(mod)
    package_impacts[min_idx] += mod["impact"]

print(f"\nDistribuzione su {num_claudes} Claude Sonnet instances:")
print()

for idx, package in enumerate(packages, 1):
    total_files = sum(m["count"] for m in package)
    total_impact = sum(m["impact"] for m in package)
    total_test_lines = total_impact * 2

    print(f"{'=' * 100}")
    print(f"🤖 CLAUDE #{idx}")
    print(f"{'=' * 100}")
    print(
        f"Moduli: {len(package)} | Files: {total_files} | Impact: {total_impact:,} | Test Lines: ~{total_test_lines:,}"
    )
    print(f"{'-' * 100}")

    for mod in package:
        print(f"  📦 {mod['name']:<45} ({mod['count']:>2} files, {mod['impact']:>4} impact)")

    print()
    print(f"  📊 Estimated effort: ~{total_test_lines:,} test lines")
    print(f"  ⏱️  Estimated time: ~{max(1, total_files // 6)} weeks")
    print()

print("=" * 100)
print("📋 DETAILED MODULE BREAKDOWN")
print("=" * 100)

for i, mod in enumerate(module_summary, 1):
    print(f"\n{'=' * 100}")
    print(f"MODULE {i}: {mod['name']}")
    print(f"{'=' * 100}")
    print(
        f"Files: {mod['count']} | Impact: {mod['impact']:,} | Total Stmts: {mod['stmts']:,} | Avg Coverage: {mod['avg_coverage']:.1f}%"
    )
    print(f"{'-' * 100}")
    print(f"{'File':<65} {'Stmts':>6} {'Cov%':>7} {'Impact':>8}")
    print(f"{'-' * 100}")

    for f in sorted(mod["files"], key=lambda x: x["impact"], reverse=True):
        fname = f["file"].replace("backend/", "")
        if len(fname) > 62:
            fname = "..." + fname[-59:]
        print(f"{fname:<65} {f['stmts']:>6} {f['coverage']:>6.1f}% {f['impact']:>8}")

print("\n" + "=" * 100)
print("✅ READY FOR PARALLEL EXECUTION!")
print("=" * 100)
print(
    "\nProssimo step: Assegna ogni package a un Claude Sonnet e fai partire il lavoro in parallelo!"
)
