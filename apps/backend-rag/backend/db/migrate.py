#!/usr/bin/env python3
"""
NUZANTARA PRIME - Migration CLI Tool
Centralized tool for managing database migrations
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

from db.migration_base import MigrationError
from db.migration_manager import MigrationManager

from app.core.config import settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def cmd_status(manager: MigrationManager):
    """Show migration status"""
    status = await manager.get_status()

    print("\n" + "=" * 70)
    print("MIGRATION STATUS")
    print("=" * 70)
    print(f"Total migrations discovered: {status['total']}")
    print(f"Applied: {status['applied']}")
    print(f"Pending: {status['pending']}")

    if status["applied_list"]:
        print(f"\n✅ Applied migrations: {', '.join(map(str, status['applied_list']))}")

    if status["pending_list"]:
        print(f"\n⏳ Pending migrations: {', '.join(map(str, status['pending_list']))}")

    print("=" * 70 + "\n")


async def cmd_list(manager: MigrationManager):
    """List all migrations"""
    discovered = await manager.discover_migrations()
    applied_migrations = await manager.get_applied_migrations()
    applied_numbers = {m["migration_number"] for m in applied_migrations}

    print("\n" + "=" * 70)
    print("ALL MIGRATIONS")
    print("=" * 70)

    for migration_info in sorted(discovered, key=lambda x: x["number"]):
        number = migration_info["number"]
        file = migration_info["file"]
        status = "✅ APPLIED" if number in applied_numbers else "⏳ PENDING"
        print(f"{number:03d}: {file:50s} {status}")

    print("=" * 70 + "\n")


async def cmd_apply(
    manager: MigrationManager, migration_number: int | None = None, dry_run: bool = False
):
    """Apply migration(s)"""
    if migration_number:
        # Apply specific migration
        # This would require importing the specific migration class
        print(f"⚠️  Applying specific migration {migration_number} not yet implemented")
        print("Use 'apply-all' to apply all pending migrations")
        return False
    else:
        # Apply all pending migrations
        if dry_run:
            print("\n🔍 DRY RUN - No changes will be made\n")

        result = await manager.apply_all_pending(dry_run=dry_run)

        print("\n" + "=" * 70)
        print("MIGRATION RESULTS")
        print("=" * 70)

        if result["applied"]:
            print(f"✅ Applied: {len(result['applied'])} migrations")
            for num in result["applied"]:
                print(f"   - Migration {num:03d}")

        if result["skipped"]:
            print(f"⏭️  Skipped: {len(result['skipped'])} migrations")

        if result["failed"]:
            print(f"❌ Failed: {len(result['failed'])} migrations")
            for failure in result["failed"]:
                print(f"   - Migration {failure['number']:03d}: {failure['error']}")

        print("=" * 70 + "\n")

        return len(result["failed"]) == 0


async def cmd_info(manager: MigrationManager, migration_number: int):
    """Show info about a specific migration"""
    applied_migrations = await manager.get_applied_migrations()
    applied_dict = {m["migration_number"]: m for m in applied_migrations}

    print("\n" + "=" * 70)
    print(f"MIGRATION {migration_number:03d} INFO")
    print("=" * 70)

    if migration_number in applied_dict:
        info = applied_dict[migration_number]
        print("Status: ✅ APPLIED")
        print(f"Applied at: {info['executed_at']}")
        print(f"Description: {info['description']}")
    else:
        print("Status: ⏳ PENDING")
        print("This migration has not been applied yet")

    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="NUZANTARA PRIME - Database Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show migration status
  python -m db.migrate status

  # List all migrations
  python -m db.migrate list

  # Apply all pending migrations
  python -m db.migrate apply-all

  # Dry run (show what would be applied)
  python -m db.migrate apply-all --dry-run

  # Show info about migration 007
  python -m db.migrate info 7
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Status command
    subparsers.add_parser("status", help="Show migration status")

    # List command
    subparsers.add_parser("list", help="List all migrations")

    # Apply command
    apply_parser = subparsers.add_parser("apply-all", help="Apply all pending migrations")
    apply_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be applied without executing"
    )

    # Info command
    info_parser = subparsers.add_parser("info", help="Show info about a specific migration")
    info_parser.add_argument("migration_number", type=int, help="Migration number")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Check database URL
    if not settings.database_url:
        logger.error("❌ DATABASE_URL not configured")
        logger.error("Set DATABASE_URL environment variable or configure in .env file")
        sys.exit(1)

    # Create migration manager
    try:
        manager = MigrationManager()
    except MigrationError as e:
        logger.error(f"❌ Failed to initialize migration manager: {e}")
        sys.exit(1)

    # Execute command with connection pooling
    async def run_with_pool():
        async with manager:
            if args.command == "status":
                return await cmd_status(manager)
            elif args.command == "list":
                return await cmd_list(manager)
            elif args.command == "apply-all":
                return await cmd_apply(manager, dry_run=args.dry_run)
            elif args.command == "info":
                return await cmd_info(manager, args.migration_number)
            else:
                parser.print_help()
                return False

    try:
        success = asyncio.run(run_with_pool())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
