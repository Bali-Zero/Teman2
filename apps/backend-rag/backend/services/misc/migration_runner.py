"""
NUZANTARA PRIME - Automatic Migration Runner

Provides automatic migration execution with versioning and dependency management.
Replaces manual apply_migration_XXX.py scripts.

Features:
- Automatic discovery of migrations
- Dependency resolution
- Version tracking
- Rollback support
- Dry-run mode
"""

import importlib
import inspect
import logging
import sys
from pathlib import Path
from typing import Any

from db.migration_base import BaseMigration, MigrationError
from db.migration_manager import MigrationManager

logger = logging.getLogger(__name__)


class MigrationRunner:
    """
    Automatic Migration Runner

    Discovers and executes migrations in the correct order based on:
    - Migration number (sequential)
    - Dependencies (explicit dependencies)
    - Already applied migrations (from schema_migrations table)
    """

    def __init__(self, migrations_dir: Path | None = None):
        """
        Initialize migration runner.

        Args:
            migrations_dir: Directory containing migration files (default: backend/migrations)
        """
        if migrations_dir is None:
            # Default to backend/migrations directory
            backend_path = Path(__file__).parent.parent
            migrations_dir = backend_path / "migrations"

        self.migrations_dir = Path(migrations_dir)
        if not self.migrations_dir.exists():
            raise MigrationError(f"Migrations directory not found: {self.migrations_dir}")

        self.migration_manager: MigrationManager | None = None
        self._migration_classes: dict[int, type[BaseMigration]] = {}

    async def initialize(self):
        """Initialize migration manager"""
        self.migration_manager = MigrationManager()
        await self.migration_manager.connect()

    async def close(self):
        """Close migration manager"""
        if self.migration_manager:
            await self.migration_manager.close()

    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    def discover_migrations(self) -> dict[int, type[BaseMigration]]:
        """
        Discover all migration classes in migrations directory.

        Returns:
            Dictionary mapping migration_number -> Migration class
        """
        if self._migration_classes:
            return self._migration_classes

        # Add migrations directory to Python path
        migrations_parent = str(self.migrations_dir.parent)
        if migrations_parent not in sys.path:
            sys.path.insert(0, migrations_parent)

        # Import all migration modules
        migration_files = sorted(self.migrations_dir.glob("migration_*.py"))

        for migration_file in migration_files:
            try:
                # Import module
                module_name = migration_file.stem
                module_path = f"migrations.{module_name}"

                # Skip if already imported
                if module_path in sys.modules:
                    module = sys.modules[module_path]
                else:
                    spec = importlib.util.spec_from_file_location(module_name, migration_file)
                    if spec is None or spec.loader is None:
                        logger.warning(f"Could not load spec for {migration_file}")
                        continue
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_path] = module
                    spec.loader.exec_module(module)

                # Find BaseMigration subclasses
                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, BaseMigration)
                        and obj != BaseMigration
                    ):
                        # Instantiate to get migration number
                        try:
                            instance = obj()
                            migration_number = instance.migration_number
                            self._migration_classes[migration_number] = obj
                            logger.debug(
                                f"Discovered migration {migration_number}: {instance.description}"
                            )
                        except Exception as e:
                            logger.warning(f"Could not instantiate migration {name}: {e}")

            except Exception as e:
                logger.warning(f"Error loading migration file {migration_file}: {e}")

        logger.info(f"Discovered {len(self._migration_classes)} migrations")
        return self._migration_classes

    def resolve_dependencies(self, migrations: dict[int, type[BaseMigration]]) -> list[int]:
        """
        Resolve migration dependencies and return ordered list.

        Args:
            migrations: Dictionary of migration_number -> Migration class

        Returns:
            Ordered list of migration numbers
        """
        # Build dependency graph
        graph: dict[int, set[int]] = {num: set() for num in migrations.keys()}

        for num, migration_class in migrations.items():
            instance = migration_class()
            if instance.dependencies:
                for dep in instance.dependencies:
                    if dep in migrations:
                        graph[num].add(dep)
                    else:
                        logger.warning(f"Migration {num} depends on {dep}, but migration not found")

        # Topological sort
        ordered: list[int] = []
        visited: set[int] = set()
        temp_visited: set[int] = set()

        def visit(node: int):
            if node in temp_visited:
                raise MigrationError(f"Circular dependency detected involving migration {node}")
            if node in visited:
                return

            temp_visited.add(node)
            for dep in graph[node]:
                visit(dep)
            temp_visited.remove(node)
            visited.add(node)
            ordered.append(node)

        for node in sorted(graph.keys()):
            if node not in visited:
                visit(node)

        return ordered

    async def get_applied_migrations(self) -> set[int]:
        """Get set of already applied migration numbers"""
        if not self.migration_manager:
            await self.initialize()

        applied = await self.migration_manager.get_applied_migrations()
        return {m["migration_number"] for m in applied if m.get("migration_number")}

    async def get_pending_migrations(
        self, dry_run: bool = False
    ) -> list[tuple[int, type[BaseMigration]]]:
        """
        Get list of pending migrations in correct order.

        Args:
            dry_run: If True, don't check database (for testing)

        Returns:
            List of (migration_number, Migration class) tuples
        """
        # Discover all migrations
        all_migrations = self.discover_migrations()

        if not all_migrations:
            logger.warning("No migrations discovered")
            return []

        # Resolve dependencies
        ordered_numbers = self.resolve_dependencies(all_migrations)

        # Get applied migrations
        if dry_run:
            applied = set()
        else:
            applied = await self.get_applied_migrations()

        # Filter to pending only
        pending = [(num, all_migrations[num]) for num in ordered_numbers if num not in applied]

        return pending

    async def apply_all(self, dry_run: bool = False, stop_on_error: bool = True) -> dict[str, Any]:
        """
        Apply all pending migrations.

        Args:
            dry_run: If True, validate but don't execute
            stop_on_error: If True, stop on first error

        Returns:
            Dictionary with results
        """
        if not self.migration_manager:
            await self.initialize()

        pending = await self.get_pending_migrations(dry_run=dry_run)

        if not pending:
            logger.info("No pending migrations")
            return {
                "success": True,
                "applied": 0,
                "skipped": 0,
                "errors": [],
            }

        logger.info(f"Found {len(pending)} pending migration(s)")

        applied = []
        errors = []

        for migration_number, migration_class in pending:
            try:
                logger.info(f"Applying migration {migration_number}: {migration_class.__name__}")

                if dry_run:
                    logger.info(f"[DRY RUN] Would apply migration {migration_number}")
                    applied.append(migration_number)
                else:
                    instance = migration_class()
                    success = await instance.apply()
                    if success:
                        applied.append(migration_number)
                        logger.info(f"✅ Migration {migration_number} applied successfully")
                    else:
                        error_msg = f"Migration {migration_number} failed to apply"
                        errors.append({"migration": migration_number, "error": error_msg})
                        logger.error(f"❌ {error_msg}")

                        if stop_on_error:
                            break

            except Exception as e:
                error_msg = f"Error applying migration {migration_number}: {e}"
                errors.append({"migration": migration_number, "error": str(e)})
                logger.error(f"❌ {error_msg}")

                if stop_on_error:
                    break

        return {
            "success": len(errors) == 0,
            "applied": len(applied),
            "skipped": len(pending) - len(applied) - len(errors),
            "errors": errors,
            "applied_migrations": applied,
        }

    async def status(self) -> dict[str, Any]:
        """
        Get migration status report.

        Returns:
            Dictionary with status information
        """
        all_migrations = self.discover_migrations()
        applied = await self.get_applied_migrations()
        pending = await self.get_pending_migrations()

        return {
            "total_migrations": len(all_migrations),
            "applied": len(applied),
            "pending": len(pending),
            "applied_numbers": sorted(applied),
            "pending_numbers": [num for num, _ in pending],
            "migrations": {
                num: {
                    "applied": num in applied,
                    "description": migration_class().description,
                }
                for num, migration_class in all_migrations.items()
            },
        }
