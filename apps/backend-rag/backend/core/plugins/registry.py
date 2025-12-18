"""
Plugin Registry

Central registry for all plugins. Handles loading, discovery, versioning, and lifecycle.
"""

import asyncio
import importlib
import inspect
import logging
from pathlib import Path
from typing import Any

from .plugin import Plugin, PluginCategory, PluginMetadata

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Central registry for all plugins.
    Handles loading, discovery, versioning, and lifecycle.

    Example:
        # Register a plugin
        await registry.register(EmailSenderPlugin)

        # Get a plugin
        plugin = registry.get("gmail.send")

        # List all plugins
        plugins = registry.list_plugins(category=PluginCategory.GOOGLE_WORKSPACE)

        # Search plugins
        results = registry.search("email")
    """

    def __init__(self):
        self._plugins: dict[str, Plugin] = {}
        self._metadata: dict[str, PluginMetadata] = {}
        self._versions: dict[str, list[str]] = {}  # name -> [versions]
        self._aliases: dict[str, str] = {}  # alias -> canonical_name
        self._lock = asyncio.Lock()
        logger.info("Initialized PluginRegistry")

    async def register(self, plugin_class: type[Plugin], config: dict | None = None) -> Plugin:
        """
        Register a plugin instance

        Args:
            plugin_class: Plugin class to instantiate and register
            config: Optional configuration for the plugin

        Returns:
            Registered plugin instance

        Raises:
            ValueError: If plugin with same name and version already registered
        """
        async with self._lock:
            plugin = plugin_class(config)
            metadata = plugin.metadata

            # Check for conflicts
            if metadata.name in self._plugins:
                existing = self._metadata[metadata.name]
                if existing.version == metadata.version:
                    logger.warning(
                        f"Plugin {metadata.name} v{metadata.version} already registered, skipping"
                    )
                    return self._plugins[metadata.name]
                else:
                    logger.warning(
                        f"Plugin {metadata.name} version conflict: existing={existing.version}, new={metadata.version}"
                    )

            # Register
            self._plugins[metadata.name] = plugin
            self._metadata[metadata.name] = metadata

            # Track versions
            if metadata.name not in self._versions:
                self._versions[metadata.name] = []
            if metadata.version not in self._versions[metadata.name]:
                self._versions[metadata.name].append(metadata.version)

            # Register legacy handler key as alias
            if metadata.legacy_handler_key:
                self._aliases[metadata.legacy_handler_key] = metadata.name

            # Call lifecycle hook
            try:
                await plugin.on_load()
                logger.info(
                    f"Registered plugin: {metadata.name} v{metadata.version} ({metadata.category})"
                )
            except Exception as e:
                logger.error(f"Failed to load plugin {metadata.name}: {e}")
                # Rollback registration
                del self._plugins[metadata.name]
                del self._metadata[metadata.name]
                raise

            return plugin

    async def register_batch(
        self, plugin_classes: list[type[Plugin]], config: dict | None = None
    ) -> list[Plugin]:
        """
        Register multiple plugins in batch

        Args:
            plugin_classes: List of plugin classes to register
            config: Optional shared configuration

        Returns:
            List of registered plugins
        """
        plugins = []
        for plugin_class in plugin_classes:
            try:
                plugin = await self.register(plugin_class, config)
                plugins.append(plugin)
            except Exception as e:
                logger.error(f"Failed to register {plugin_class.__name__}: {e}")
        return plugins

    async def unregister(self, name: str):
        """
        Unregister a plugin

        Args:
            name: Plugin name to unregister
        """
        async with self._lock:
            if name in self._plugins:
                plugin = self._plugins[name]
                try:
                    await plugin.on_unload()
                    logger.info(f"Unloaded plugin: {name}")
                except Exception as e:
                    logger.error(f"Error unloading plugin {name}: {e}")

                del self._plugins[name]
                del self._metadata[name]

                # Remove aliases
                self._aliases = {k: v for k, v in self._aliases.items() if v != name}

                logger.info(f"Unregistered plugin: {name}")

    def get(self, name: str) -> Plugin | None:
        """
        Get plugin by name or alias

        Args:
            name: Plugin name or legacy handler key

        Returns:
            Plugin instance or None if not found
        """
        # Try direct lookup
        if name in self._plugins:
            return self._plugins[name]

        # Try alias lookup
        if name in self._aliases:
            canonical_name = self._aliases[name]
            return self._plugins.get(canonical_name)

        return None

    def get_metadata(self, name: str) -> PluginMetadata | None:
        """
        Get plugin metadata by name

        Args:
            name: Plugin name

        Returns:
            Plugin metadata or None
        """
        return self._metadata.get(name)

    def list_plugins(
        self,
        category: PluginCategory | None = None,
        tags: list[str] | None = None,
        allowed_models: list[str] | None = None,
    ) -> list[PluginMetadata]:
        """
        List all plugins, optionally filtered

        Args:
            category: Filter by category
            tags: Filter by tags (any match)
            allowed_models: Filter by allowed models

        Returns:
            List of plugin metadata
        """
        result = list(self._metadata.values())

        if category:
            result = [m for m in result if m.category == category]

        if tags:
            result = [m for m in result if any(tag in m.tags for tag in tags)]

        if allowed_models:
            result = [
                m for m in result if any(model in m.allowed_models for model in allowed_models)
            ]

        # Sort by category, then name
        result.sort(key=lambda m: (m.category, m.name))

        return result

    async def discover_plugins(
        self, plugins_dir: Path, package_prefix: str = "", strict: bool = False
    ):
        """
        Auto-discover plugins in directory

        Args:
            plugins_dir: Directory to search for plugins
            package_prefix: Python package prefix (e.g., "backend.plugins")
            strict: If True, fail on first error. If False, collect errors and continue.

        Returns:
            dict with discovery results: {"discovered": int, "errors": list[str]}
        """
        if not plugins_dir.exists():
            error_msg = f"Plugins directory not found: {plugins_dir}"
            logger.warning(error_msg)
            if strict:
                raise FileNotFoundError(error_msg)
            return {"discovered": 0, "errors": [error_msg]}

        if package_prefix and not all(
            segment.isidentifier() for segment in package_prefix.split(".")
        ):
            error_msg = f"Package prefix {package_prefix} contains invalid characters"
            logger.error(error_msg)
            if strict:
                raise ValueError(error_msg)
            return {"discovered": 0, "errors": [error_msg]}

        logger.info(f"Discovering plugins in {plugins_dir}")
        discovered_count = 0
        errors = []

        for plugin_file in plugins_dir.rglob("*.py"):
            if plugin_file.name.startswith("_"):
                continue

            # Import module
            try:
                relative_path = plugin_file.relative_to(plugins_dir).with_suffix("")
                parts = []
                invalid_path = False
                for part in relative_path.parts:
                    safe_part = part.replace("-", "_")
                    if not safe_part.isidentifier():
                        error_msg = (
                            f"Skipping plugin {plugin_file} due to invalid module segment '{part}'"
                        )
                        logger.warning(error_msg)
                        errors.append(error_msg)
                        invalid_path = True
                        break
                    parts.append(safe_part)

                if invalid_path:
                    if strict:
                        raise ValueError(f"Invalid module path: {plugin_file}")
                    continue

                module_path = ".".join(parts)

                # Build import paths to try
                full_module_paths = []
                if package_prefix:
                    full_module_paths.append(f"{package_prefix}.{module_path}")
                # Try with 'plugins' prefix (common case)
                full_module_paths.append(f"plugins.{module_path}")
                # Try without prefix (for direct execution)
                full_module_paths.append(module_path)

                module = None
                last_error = None
                for full_module_path in full_module_paths:
                    try:
                        # Module path is validated: segments checked with isidentifier(),
                        # prefix validated at line 241-248, only .py files from plugins_dir
                        # nosemgrep: non-literal-import
                        module = importlib.import_module(full_module_path)
                        logger.debug(f"Successfully imported plugin from: {full_module_path}")
                        break
                    except (ImportError, ModuleNotFoundError) as e:
                        last_error = e
                        logger.debug(f"Failed to import {full_module_path}: {e}")
                        continue

                if module is None:
                    error_msg = f"Could not import module using any path: {full_module_paths}. Last error: {last_error}"
                    logger.warning(error_msg)
                    if strict:
                        raise ImportError(error_msg)
                    errors.append(error_msg)
                    continue

                # Find Plugin classes
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, Plugin) and obj != Plugin:
                        try:
                            await self.register(obj)
                            discovered_count += 1
                            logger.debug(f"Registered plugin: {name} from {plugin_file}")
                        except Exception as e:
                            error_msg = f"Failed to register plugin {name} from {plugin_file}: {e}"
                            logger.error(error_msg, exc_info=True)
                            errors.append(error_msg)
                            if strict:
                                raise

            except Exception as e:
                error_msg = f"Failed to load plugin from {plugin_file}: {e}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
                if strict:
                    raise

        logger.info(f"Discovered {discovered_count} plugins")
        if errors:
            logger.warning(f"Encountered {len(errors)} errors during plugin discovery")
            for error in errors[:5]:  # Log first 5 errors
                logger.warning(f"  - {error}")
            if len(errors) > 5:
                logger.warning(f"  ... and {len(errors) - 5} more errors")

        return {"discovered": discovered_count, "errors": errors}

    def search(self, query: str) -> list[PluginMetadata]:
        """
        Search plugins by name, description, or tags

        Args:
            query: Search query string

        Returns:
            List of matching plugin metadata
        """
        query = query.lower()
        results = []

        for metadata in self._metadata.values():
            if (
                query in metadata.name.lower()
                or query in metadata.description.lower()
                or any(query in tag.lower() for tag in metadata.tags)
            ):
                results.append(metadata)

        return results

    def get_statistics(self) -> dict[str, Any]:
        """
        Get registry statistics

        Returns:
            Dictionary with statistics
        """
        category_counts = {}
        for metadata in self._metadata.values():
            category = metadata.category
            category_counts[category] = category_counts.get(category, 0) + 1

        return {
            "total_plugins": len(self._plugins),
            "categories": len(category_counts),
            "category_counts": category_counts,
            "total_versions": sum(len(v) for v in self._versions.values()),
            "aliases": len(self._aliases),
        }

    def get_all_anthropic_tools(self) -> list[dict[str, Any]]:
        """
        Get all plugins as ZANTARA AI tool definitions (legacy Anthropic format for compatibility)

        Returns:
            List of tool definitions for ZANTARA AI
        """
        tools = []
        for plugin in self._plugins.values():
            try:
                tool_def = plugin.to_anthropic_tool_definition()
                tools.append(tool_def)
            except Exception as e:
                logger.error(
                    f"Failed to generate ZANTARA AI tool definition for {plugin.metadata.name}: {e}"
                )
        return tools

    def get_haiku_allowed_tools(self) -> list[dict[str, any]]:
        """
        Get tools allowed for Haiku model (fast, limited set)

        Returns:
            List of tool definitions for Haiku
        """
        tools = []
        for plugin in self._plugins.values():
            if "haiku" in plugin.metadata.allowed_models:
                try:
                    tool_def = plugin.to_anthropic_tool_definition()
                    tools.append(tool_def)
                except Exception as e:
                    logger.error(f"Failed to generate tool definition: {e}")
        return tools

    async def reload_plugin(self, name: str):
        """
        Hot-reload a plugin (admin only)

        Args:
            name: Plugin name to reload
        """
        plugin = self.get(name)
        if not plugin:
            raise ValueError(f"Plugin {name} not found")

        # Get the plugin class
        plugin_class = type(plugin)
        config = plugin.config

        # Unload and reload
        await self.unregister(name)
        await self.register(plugin_class, config)

        logger.info(f"Reloaded plugin: {name}")


# Global registry instance
registry = PluginRegistry()
