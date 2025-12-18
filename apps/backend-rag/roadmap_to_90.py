#!/usr/bin/env python3
"""Generate detailed roadmap to 90% coverage"""

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

print("=" * 90)
print("🎯 ROADMAP TO 90% COVERAGE")
print("=" * 90)
print(f"📍 Current:     {CURRENT_COVERAGE:.2f}% ({current_covered:,} / {TOTAL_STMTS:,} statements)")
print(f"🎯 Target:      {TARGET_COVERAGE:.1f}% ({target_covered:,} / {TOTAL_STMTS:,} statements)")
print(
    f"📊 Gap:         {TARGET_COVERAGE - CURRENT_COVERAGE:.2f}% ({gap_statements:,} statements to cover)"
)
print("")
print("💪 EFFORT REQUIRED:")
print(f"   • Test lines to write:    ~{gap_statements * 2:.0f} lines (2x ratio)")
print(f"   • Test files to create:   ~{gap_statements / 100:.0f} files")
print("   • Estimated time:         4-6 weeks")
print("=" * 90)

# Get detailed file list
result = subprocess.run(["python", "-m", "coverage", "report"], capture_output=True, text=True)

files = []
for line in result.stdout.split("\n"):
    if line.startswith("backend/"):
        parts = line.split()
        # Format: filename stmts miss branch brpart coverage% missing_lines
        if len(parts) >= 5:
            try:
                filename = parts[0]
                stmts = int(parts[1])
                miss = int(parts[2])

                # Coverage is in column 6 (index 5), with % sign
                # Format: filename stmts miss branch brpart coverage% missing
                if len(parts) < 6:
                    continue
                cov_str = parts[5].rstrip("%")
                coverage = float(cov_str)

                covered = stmts - miss

                # Calculate impact if we bring this file to 90%
                if coverage < 90:  # Include ALL files under 90%
                    target_for_file = int(stmts * 0.9)
                    impact = max(0, target_for_file - covered)

                    files.append(
                        {
                            "file": filename,
                            "stmts": stmts,
                            "miss": miss,
                            "covered": covered,
                            "coverage": coverage,
                            "impact": impact,
                            "roi": impact / stmts if stmts > 0 else 0,
                        }
                    )
            except (ValueError, IndexError):
                # Skip lines that don't parse correctly
                continue

# Sort by impact
files.sort(key=lambda x: x["impact"], reverse=True)

# Phase 1: Critical files (0-30% coverage)
phase1 = [f for f in files if f["coverage"] < 30]
phase2 = [f for f in files if 30 <= f["coverage"] < 60]
phase3 = [f for f in files if 60 <= f["coverage"] < 90]

print("\n" + "=" * 90)
print("📋 IMPLEMENTATION PLAN")
print("=" * 90)


def print_phase(phase_num, title, file_list, target_cov):
    total_impact = sum(f["impact"] for f in file_list)
    total_stmts = sum(f["stmts"] for f in file_list)

    print(f"\n{'=' * 90}")
    print(f"Phase {phase_num}: {title}")
    print(f"{'=' * 90}")
    print(
        f"Files: {len(file_list)} | Impact: {total_impact:,} statements | Test lines: ~{total_impact * 2:,}"
    )
    print(f"{'-' * 90}")
    print(f"{'File':<55} {'Stmts':>6} {'Now':>7} {'→ 90%':>7} {'Impact':>8}")
    print(f"{'-' * 90}")

    for f in file_list[:15]:  # Top 15 per phase
        fname = f["file"].replace("backend/", "")
        if len(fname) > 52:
            fname = "..." + fname[-49:]

        print(
            f"{fname:<55} {f['stmts']:>6} {f['coverage']:>6.1f}% {target_cov:>6}% {f['impact']:>7}"
        )

    if len(file_list) > 15:
        remaining = len(file_list) - 15
        remaining_impact = sum(f["impact"] for f in file_list[15:])
        print(
            f"{'... and ' + str(remaining) + ' more files':<55} {'':<6} {'':<7} {'':<7} {remaining_impact:>7}"
        )

    print(f"{'-' * 90}")
    print(f"{'PHASE TOTAL':<55} {total_stmts:>6} {'':<7} {'':<7} {total_impact:>7}")
    print()

    # Estimate time
    weeks = max(1, len(file_list) // 6)  # ~6 files per week
    print(f"⏱️  Estimated time: {weeks} weeks ({len(file_list)} files, ~6 files/week)")
    print(f"📝 Test lines: ~{total_impact * 2:,} lines")


print_phase(1, "CRITICAL - Low Coverage Files (0-30%)", phase1, 90)
print_phase(2, "MEDIUM - Mid Coverage Files (30-60%)", phase2, 90)
print_phase(3, "POLISH - High Coverage Files (60-90%)", phase3, 90)

# Summary
total_files = len(files)
total_impact = sum(f["impact"] for f in files)

print("\n" + "=" * 90)
print("📊 SUMMARY")
print("=" * 90)
print(f"Total files to improve:     {total_files}")
print(f"Total statements to cover:  {total_impact:,}")
print(f"Total test lines needed:    ~{total_impact * 2:,}")
print("")
print(
    f"Phase 1 (Critical):         {len(phase1)} files | {sum(f['impact'] for f in phase1):,} stmts"
)
print(
    f"Phase 2 (Medium):           {len(phase2)} files | {sum(f['impact'] for f in phase2):,} stmts"
)
print(
    f"Phase 3 (Polish):           {len(phase3)} files | {sum(f['impact'] for f in phase3):,} stmts"
)
print("=" * 90)

# Timeline
total_weeks = max(1, total_files // 6)
print("\n⏱️  TIMELINE:")
print(f"   Parallel work (2 devs):   ~{total_weeks // 2} weeks")
print(f"   Single developer:         ~{total_weeks} weeks")
print(f"   Conservative estimate:    ~{total_weeks + 2} weeks (with buffer)")

# Top 20 priority list
print("\n" + "=" * 90)
print("🔥 TOP 20 PRIORITY FILES (Highest Impact)")
print("=" * 90)
print(f"{'#':<3} {'File':<60} {'Impact':>8} {'Current':>8}")
print("-" * 90)

for i, f in enumerate(files[:20], 1):
    fname = f["file"].replace("backend/", "")
    if len(fname) > 57:
        fname = "..." + fname[-54:]

    priority = "🔥" if i <= 5 else ("🔴" if i <= 10 else "🟠")
    print(f"{i:<2} {priority} {fname:<57} {f['impact']:>7} {f['coverage']:>7.1f}%")

print("=" * 90)
