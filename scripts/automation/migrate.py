#!/usr/bin/env python3
"""
NUZANTARA PRIME - Automatic Migration Runner CLI

Replaces manual apply_migration_XXX.py scripts.

Usage:
    python apps/backend-rag/scripts/migrate.py status
    python apps/backend-rag/scripts/migrate.py apply-all
    python apps/backend-rag/scripts/migrate.py apply-all --dry-run
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from services.migration_runner import MigrationRunner


async def main():
    parser = argparse.ArgumentParser(description="NUZANTARA Migration Runner")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show migration status")

    # Apply-all command
    apply_parser = subparsers.add_parser(
        "apply-all", help="Apply all pending migrations"
    )
    apply_parser.add_argument(
        "--dry-run", action="store_true", help="Validate without executing"
    )
    apply_parser.add_argument(
        "--stop-on-error",
        action="store_true",
        default=True,
        help="Stop on first error (default: True)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize migration runner
    migrations_dir = Path(__file__).parent.parent / "backend" / "migrations"
    runner = MigrationRunner(migrations_dir=migrations_dir)

    try:
        await runner.initialize()

        if args.command == "status":
            status = await runner.status()
            print("\nMigration Status:")
            print("=" * 60)
            print(f"Total Migrations: {status['total_migrations']}")
            print(f"Applied: {status['applied']}")
            print(f"Pending: {status['pending']}")
            print()

            if status["applied_numbers"]:
                print("Applied Migrations:")
                for num in status["applied_numbers"]:
                    info = status["migrations"][num]
                    print(f"  ✅ {num:03d}: {info['description']}")

            if status["pending_numbers"]:
                print("\nPending Migrations:")
                for num in status["pending_numbers"]:
                    info = status["migrations"][num]
                    print(f"  ⏳ {num:03d}: {info['description']}")

            return 0

        elif args.command == "apply-all":
            print("Discovering migrations...")
            result = await runner.apply_all(
                dry_run=args.dry_run, stop_on_error=args.stop_on_error
            )

            print("\nMigration Results:")
            print("=" * 60)
            if result["success"]:
                print(f"✅ Successfully applied {result['applied']} migration(s)")
                if result["applied_migrations"]:
                    print(
                        f"   Applied: {', '.join(map(str, result['applied_migrations']))}"
                    )
            else:
                print("❌ Migration failed")
                print(f"   Applied: {result['applied']}")
                print(f"   Errors: {len(result['errors'])}")
                for error in result["errors"]:
                    print(f"     - Migration {error['migration']}: {error['error']}")
                return 1

            return 0

    finally:
        await runner.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
