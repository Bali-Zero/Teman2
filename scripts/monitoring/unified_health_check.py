#!/usr/bin/env python3
"""
NUZANTARA PRIME - Unified Health Check Script

Replaces:
- scripts/health_check.py
- apps/backend-rag/scripts/health_check.py

Usage:
    python apps/backend-rag/scripts/unified_health_check.py
    python apps/backend-rag/scripts/unified_health_check.py --json
    python apps/backend-rag/scripts/unified_health_check.py --continuous
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from services.unified_health_service import UnifiedHealthService


async def main():
    parser = argparse.ArgumentParser(description="NUZANTARA Unified Health Check")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously (like backend_agent)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Check interval in seconds (for continuous mode)",
    )

    args = parser.parse_args()

    service = UnifiedHealthService()
    await service.initialize()

    try:
        if args.continuous:
            # Continuous monitoring mode (like backend_agent)
            import logging

            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(levelname)s - %(message)s",
            )

            while True:
                report = await service.run_all_checks()
                if args.json:
                    print(json.dumps(report, indent=2))
                else:
                    print(service.format_report(report))
                    print()

                await asyncio.sleep(args.interval)
        else:
            # Single check mode
            report = await service.run_all_checks()

            if args.json:
                print(json.dumps(report, indent=2))
                return 0 if report["overall_status"] == "ok" else 1
            else:
                print(service.format_report(report))
                return 0 if report["overall_status"] == "ok" else 1

    finally:
        await service.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
