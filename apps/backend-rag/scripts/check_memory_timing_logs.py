#!/usr/bin/env python3
"""
Script per verificare i log di timing e metriche del memory orchestrator.

Controlla:
- Timing metrics nei log
- Errori di memory orchestrator
- Lock contention metrics
- Performance metrics
"""

import re
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def parse_log_line(line: str) -> dict | None:
    """Parse a log line and extract relevant information."""
    # Pattern per log con timing
    memory_pattern = r"(Memory|memory|orchestrator|Orchestrator)"
    error_pattern = r"(ERROR|WARNING|Failed|failed|unavailable|degraded)"
    lock_pattern = r"(lock|Lock|timeout|Timeout|contention)"

    result = {
        "timestamp": None,
        "has_timing": False,
        "has_memory": False,
        "has_error": False,
        "has_lock": False,
        "timing_value": None,
        "line": line.strip(),
    }

    # Extract timestamp
    timestamp_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
    if timestamp_match:
        result["timestamp"] = timestamp_match.group(1)

    # Check for timing
    timing_match = re.search(r"(\d+\.\d+)ms", line)
    if timing_match:
        result["has_timing"] = True
        result["timing_value"] = float(timing_match.group(1))

    # Check for memory-related
    if re.search(memory_pattern, line):
        result["has_memory"] = True

    # Check for errors
    if re.search(error_pattern, line):
        result["has_error"] = True

    # Check for lock-related
    if re.search(lock_pattern, line):
        result["has_lock"] = True

    return result if (result["has_memory"] or result["has_timing"] or result["has_error"]) else None


def analyze_logs(log_file: Path) -> dict:
    """Analyze log file for memory orchestrator timing and errors."""
    stats = {
        "total_lines": 0,
        "memory_lines": 0,
        "error_lines": 0,
        "timing_lines": 0,
        "lock_lines": 0,
        "timings": [],
        "errors": [],
        "memory_operations": [],
    }

    if not log_file.exists():
        print(f"⚠️  Log file not found: {log_file}")
        return stats

    with open(log_file, encoding="utf-8", errors="ignore") as f:
        for line in f:
            stats["total_lines"] += 1
            parsed = parse_log_line(line)

            if not parsed:
                continue

            if parsed["has_memory"]:
                stats["memory_lines"] += 1
                stats["memory_operations"].append(parsed)

            if parsed["has_error"]:
                stats["error_lines"] += 1
                stats["errors"].append(parsed)

            if parsed["has_timing"]:
                stats["timing_lines"] += 1
                stats["timings"].append(parsed["timing_value"])

            if parsed["has_lock"]:
                stats["lock_lines"] += 1

    return stats


def print_summary(stats: dict):
    """Print summary of log analysis."""
    print("\n" + "=" * 80)
    print("MEMORY ORCHESTRATOR TIMING & ERROR ANALYSIS")
    print("=" * 80)

    print("\n📊 Statistics:")
    print(f"  Total lines analyzed: {stats['total_lines']}")
    print(f"  Memory-related lines: {stats['memory_lines']}")
    print(f"  Error lines: {stats['error_lines']}")
    print(f"  Timing lines: {stats['timing_lines']}")
    print(f"  Lock-related lines: {stats['lock_lines']}")

    if stats["timings"]:
        print("\n⏱️  Timing Metrics:")
        print(f"  Count: {len(stats['timings'])}")
        print(f"  Min: {min(stats['timings']):.2f}ms")
        print(f"  Max: {max(stats['timings']):.2f}ms")
        print(f"  Avg: {sum(stats['timings']) / len(stats['timings']):.2f}ms")
        print(f"  Median: {sorted(stats['timings'])[len(stats['timings']) // 2]:.2f}ms")

    if stats["errors"]:
        print(f"\n❌ Errors Found: {len(stats['errors'])}")
        print("  Recent errors:")
        for error in stats["errors"][:10]:
            print(f"    - {error['line'][:100]}...")

    if stats["memory_operations"]:
        print(f"\n💾 Memory Operations: {len(stats['memory_operations'])}")
        print("  Recent operations:")
        for op in stats["memory_operations"][:10]:
            timing_info = f" ({op['timing_value']}ms)" if op["timing_value"] else ""
            print(f"    - {op['line'][:100]}{timing_info}...")

    print("\n" + "=" * 80)


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze memory orchestrator timing and error logs"
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("logs/app.log"),
        help="Path to log file (default: logs/app.log)",
    )
    parser.add_argument(
        "--fly-logs",
        action="store_true",
        help="Fetch logs from Fly.io instead of local file",
    )
    parser.add_argument(
        "--app-name",
        default="nuzantara-rag",
        help="Fly.io app name (default: nuzantara-rag)",
    )

    args = parser.parse_args()

    if args.fly_logs:
        print("📥 Fetching logs from Fly.io...")
        import subprocess

        try:
            result = subprocess.run(
                ["fly", "logs", "-a", args.app_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                # Save to temp file
                temp_log = Path("/tmp/fly_logs.txt")
                temp_log.write_text(result.stdout)
                args.log_file = temp_log
                print(f"✅ Logs fetched and saved to {temp_log}")
            else:
                print(f"❌ Failed to fetch logs: {result.stderr}")
                return 1
        except FileNotFoundError:
            print(
                "❌ fly CLI not found. Install it from https://fly.io/docs/hands-on/install-flyctl/"
            )
            return 1
        except subprocess.TimeoutExpired:
            print("❌ Timeout fetching logs")
            return 1

    stats = analyze_logs(args.log_file)
    print_summary(stats)

    # Return non-zero if errors found
    return 1 if stats["error_lines"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
