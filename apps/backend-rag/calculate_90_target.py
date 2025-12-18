#!/usr/bin/env python3
"""Calculate exact effort needed to reach 90% coverage"""

import subprocess

# Current stats
TOTAL_STMTS = 13198
CURRENT_MISS = 5340
CURRENT_COVERAGE = 57.94
TARGET_COVERAGE = 90.0

# Calculate gap
current_covered = TOTAL_STMTS - CURRENT_MISS
target_covered = int(TOTAL_STMTS * (TARGET_COVERAGE / 100))
gap_statements = target_covered - current_covered
remaining_miss_allowed = TOTAL_STMTS - target_covered

print("=" * 80)
print("🎯 TARGET: 90% COVERAGE")
print("=" * 80)
print(f"Total statements:           {TOTAL_STMTS:,}")
print(f"Currently covered:          {current_covered:,} ({CURRENT_COVERAGE:.2f}%)")
print(f"Target covered (90%):       {target_covered:,}")
print("")
print("📊 GAP TO CLOSE:")
print(f"  Statements to cover:      {gap_statements:,}")
print(f"  Current uncovered:        {CURRENT_MISS:,}")
print(f"  Allowed uncovered at 90%: {remaining_miss_allowed:,}")
print(f"  Must cover:               {gap_statements:,} statements")
print("")
print("💪 EFFORT ESTIMATE:")
print(f"  Test lines needed:        ~{gap_statements * 1.8:.0f} lines (1.8x ratio)")
print("  Files to improve:         ~35-40 files")
print("  Estimated time:           ~4-6 weeks")
print("=" * 80)

# Parse coverage report to find high-impact targets
result = subprocess.run(
    ["python", "-m", "coverage", "report", "--skip-covered"], capture_output=True, text=True
)

files_data = []
for line in result.stdout.split("\n"):
    if line.startswith("backend/"):
        parts = line.split()
        if len(parts) >= 6:
            filename = parts[0]
            try:
                stmts = int(parts[1])
                miss = int(parts[2])
                coverage_str = parts[-1].rstrip("%")
                coverage = float(coverage_str)

                # Calculate impact: how many statements we'd cover if we get this to 90%
                if coverage < 90:
                    covered_now = stmts - miss
                    target_for_file = int(stmts * 0.9)
                    impact = target_for_file - covered_now
                    roi = impact / stmts  # ROI per statement in file

                    files_data.append(
                        {
                            "file": filename,
                            "stmts": stmts,
                            "miss": miss,
                            "coverage": coverage,
                            "impact": impact,
                            "roi": roi,
                        }
                    )
            except (ValueError, IndexError):
                continue

# Sort by impact (highest first)
files_data.sort(key=lambda x: x["impact"], reverse=True)

print("\n🎯 TOP 30 HIGH-IMPACT FILES (Best ROI for 90% target)")
print("=" * 100)
print(f"{'File':<65} {'Stmts':>6} {'Cov%':>6} {'Impact':>7} {'Priority':>10}")
print("=" * 100)

total_impact = 0
for i, f in enumerate(files_data[:30], 1):
    total_impact += f["impact"]
    priority = (
        "🔥 CRITICAL"
        if f["impact"] > 150
        else ("🔴 HIGH" if f["impact"] > 80 else ("🟠 MEDIUM" if f["impact"] > 40 else "🟡 LOW"))
    )

    # Shorten filename for display
    fname = f["file"].replace("backend/", "")
    if len(fname) > 62:
        fname = "..." + fname[-59:]

    print(f"{fname:<65} {f['stmts']:>6} {f['coverage']:>5.1f}% {f['impact']:>7} {priority:>10}")

print("=" * 100)
print(f"Total impact from top 30: {total_impact:,} statements")
print(f"Coverage gain from top 30: ~{(total_impact / TOTAL_STMTS * 100):.1f}%")
print("")

# Calculate milestones
milestone_files = {"70%": [], "80%": [], "90%": []}

accumulated = current_covered
for f in files_data:
    accumulated += f["impact"]
    current_pct = (accumulated / TOTAL_STMTS) * 100

    if current_pct < 70:
        milestone_files["70%"].append(f["file"])
    elif current_pct < 80:
        milestone_files["80%"].append(f["file"])
    elif current_pct < 90:
        milestone_files["90%"].append(f["file"])
    else:
        break

print("📈 MILESTONE BREAKDOWN:")
print("=" * 80)
print(f"To reach 70% coverage: {len(milestone_files['70%'])} files")
print(f"To reach 80% coverage: {len(milestone_files['80%'])} additional files")
print(f"To reach 90% coverage: {len(milestone_files['90%'])} additional files")
print("")
print(
    f"TOTAL FILES TO IMPROVE: {len(milestone_files['70%']) + len(milestone_files['80%']) + len(milestone_files['90%'])} files"
)
print("=" * 80)

# Effort per milestone
print("\n⏱️  ESTIMATED EFFORT PER MILESTONE:")
print("=" * 80)
milestones = [
    ("70%", len(milestone_files["70%"]), 12.06),
    ("80%", len(milestone_files["80%"]), 22.06),
    ("90%", len(milestone_files["90%"]), 32.06),
]

for target, num_files, gap_pct in milestones:
    gap_stmts = int(TOTAL_STMTS * gap_pct / 100)
    test_lines = int(gap_stmts * 1.8)
    weeks = max(1, num_files // 5)  # ~5 files per week

    print(f"{target} Coverage:")
    print(f"  Files to improve:    {num_files}")
    print(f"  Statements to cover: {gap_stmts:,}")
    print(f"  Test lines needed:   ~{test_lines:,}")
    print(f"  Estimated time:      {weeks} weeks")
    print()
