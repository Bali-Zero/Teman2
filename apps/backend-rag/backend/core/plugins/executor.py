"""
Plugin Executor

Executes plugins with performance monitoring, caching, rate limiting, and error handling.
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict
from typing import Any, Protocol

from .plugin import Plugin, PluginInput, PluginOutput
from .registry import registry

logger = logging.getLogger(__name__)

# Constants for circuit breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_COOLDOWN_SECONDS = 60


# Redis client protocol for type hints
class RedisClient(Protocol):
    """Protocol for Redis client interface"""

    async def get(self, key: str) -> str | None:
        """Get value from Redis"""
        ...

    async def setex(self, key: str, time: int, value: str) -> bool:
        """Set value with expiration"""
        ...

    async def incr(self, key: str) -> int:
        """Increment counter"""
        ...

    async def expire(self, key: str, time: int) -> bool:
        """Set expiration"""
        ...

    async def delete(self, key: str) -> bool:
        """Delete key"""
        ...

    async def ping(self) -> bool:
        """Ping Redis"""
        ...


class PluginExecutor:
    """
    Executes plugins with:
    - Performance monitoring
    - Caching (Redis optional)
    - Rate limiting
    - Error handling
    - Retry logic
    - Timeout management

    Example:
        executor = PluginExecutor()
        result = await executor.execute(
            "gmail.send",
            {"to": "user@example.com", "subject": "Test"},
            user_id="user123"
        )
    """

    def __init__(self, redis_client: RedisClient | None = None):
        """
        Initialize executor

        Args:
            redis_client: Optional Redis client for caching and distributed rate limiting.
                         Should be an async Redis client (e.g., redis.asyncio.Redis).
                         If None, falls back to in-memory storage.
        """
        self.redis = redis_client
        self._redis_available = redis_client is not None
        self._metrics = defaultdict(
            lambda: {
                "calls": 0,
                "successes": 0,
                "failures": 0,
                "total_time": 0.0,
                "last_error": None,
                "last_success": None,
                "cache_hits": 0,
                "cache_misses": 0,
            }
        )
        self._rate_limits = defaultdict(list)  # plugin -> [timestamps]
        self._circuit_breakers = {}  # plugin -> {failures, last_failure_time}
        logger.info("Initialized PluginExecutor")

    async def execute(
        self,
        plugin_name: str,
        input_data: dict[str, Any],
        use_cache: bool = True,
        user_id: str | None = None,
        timeout: float | None = None,
        retry_count: int = 0,
    ) -> PluginOutput:
        """
        Execute a plugin with all enhancements

        Args:
            plugin_name: Plugin name to execute
            input_data: Input data dictionary
            use_cache: Whether to use caching
            user_id: User ID for auth and rate limiting
            timeout: Custom timeout (overrides plugin default)
            retry_count: Number of retries on failure (0 = no retry)

        Returns:
            PluginOutput with results
        """
        # Get plugin
        plugin = registry.get(plugin_name)
        if not plugin:
            logger.warning(f"Plugin not found: {plugin_name}")
            return PluginOutput(success=False, error="Plugin not found")

        # Check circuit breaker
        if self._is_circuit_broken(plugin_name):
            logger.warning(f"Circuit breaker open for {plugin_name}")
            return PluginOutput(
                success=False,
                error="Service temporarily unavailable (circuit breaker open)",
            )

        # Check rate limit
        if plugin.metadata.rate_limit and not await self._check_rate_limit(
            plugin_name, plugin.metadata.rate_limit, user_id
        ):
            logger.warning(
                f"Rate limit exceeded for {plugin_name} (limit: {plugin.metadata.rate_limit}/min)"
            )
            return PluginOutput(
                success=False,
                error="Rate limit exceeded. Please try again later.",
                metadata={"rate_limit": plugin.metadata.rate_limit},
            )

        # Check auth requirements
        if plugin.metadata.requires_auth and not user_id:
            return PluginOutput(success=False, error="Authentication required")

        # Validate and parse input
        try:
            validated_input = plugin.input_schema(**input_data)
        except Exception as e:
            return PluginOutput(success=False, error=f"Input validation failed: {str(e)}")

        # Check cache
        if use_cache and self.redis:
            cached = await self._get_cached(plugin_name, input_data)
            if cached:
                self._metrics[plugin_name]["cache_hits"] += 1
                logger.debug(f"Cache hit for {plugin_name}")
                return cached
            self._metrics[plugin_name]["cache_misses"] += 1

        # Execute with retry
        for attempt in range(retry_count + 1):
            try:
                result = await self._execute_with_monitoring(plugin, validated_input, timeout)

                # Cache if successful
                if result.success and use_cache and self.redis:
                    await self._cache_result(plugin_name, input_data, result)

                # Reset circuit breaker on success
                if plugin_name in self._circuit_breakers:
                    del self._circuit_breakers[plugin_name]

                return result

            except (KeyboardInterrupt, SystemExit):
                # Don't catch system signals
                raise
            except asyncio.TimeoutError:
                logger.warning(
                    f"Plugin {plugin_name} execution timeout (attempt {attempt + 1}/{retry_count + 1})"
                )
                if attempt < retry_count:
                    wait_time = 2**attempt
                    logger.info(f"Retrying {plugin_name} in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    return PluginOutput(
                        success=False,
                        error=f"Plugin execution timeout after {retry_count + 1} attempts",
                        metadata={"attempts": retry_count + 1},
                    )
            except Exception as e:
                logger.error(
                    f"Plugin {plugin_name} execution failed (attempt {attempt + 1}/{retry_count + 1}): {e}",
                    exc_info=True,
                )

                if attempt < retry_count:
                    # Wait before retry with exponential backoff
                    wait_time = 2**attempt
                    logger.info(f"Retrying {plugin_name} in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    # Final failure
                    return PluginOutput(
                        success=False,
                        error=f"Plugin execution failed after {retry_count + 1} attempts: {str(e)}",
                        metadata={"attempts": retry_count + 1},
                    )

    async def _execute_with_monitoring(
        self, plugin: Plugin, input_data: PluginInput, timeout: float | None = None
    ) -> PluginOutput:
        """
        Execute plugin with monitoring

        Args:
            plugin: Plugin instance
            input_data: Validated input data
            timeout: Optional timeout override

        Returns:
            Plugin output

        Raises:
            asyncio.TimeoutError: If execution times out
            Exception: If execution fails
        """
        plugin_name = plugin.metadata.name
        start_time = time.time()

        try:
            # Validate
            if not await plugin.validate(input_data):
                return PluginOutput(success=False, error="Input validation failed")

            # Execute with timeout (use 3x estimated time for safety margin)
            execution_timeout = timeout or (plugin.metadata.estimated_time * 3)

            output = await asyncio.wait_for(plugin.execute(input_data), timeout=execution_timeout)

            # Record metrics
            execution_time = time.time() - start_time
            await self._record_success(plugin_name, execution_time)

            # Add metadata
            if not output.metadata:
                output.metadata = {}
            output.metadata["execution_time"] = execution_time
            output.metadata["plugin_version"] = plugin.metadata.version
            output.metadata["timestamp"] = time.time()

            return output

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            await self._record_failure(plugin_name, "Timeout")
            return PluginOutput(
                success=False,
                error=f"Plugin execution timeout (>{execution_timeout}s)",
                metadata={"execution_time": execution_time},
            )

        except Exception as e:
            execution_time = time.time() - start_time
            await self._record_failure(plugin_name, str(e))
            raise

    async def _check_rate_limit(
        self, plugin_name: str, limit: int, user_id: str | None = None
    ) -> bool:
        """
        Check if plugin has exceeded rate limit.

        Uses Redis for distributed rate limiting if available,
        otherwise falls back to in-memory storage.

        Args:
            plugin_name: Plugin name
            limit: Rate limit (calls per minute)
            user_id: Optional user ID for per-user rate limiting

        Returns:
            True if within rate limit, False otherwise
        """
        # Use user-specific rate limit if user_id provided
        key = f"{plugin_name}:{user_id}" if user_id else plugin_name
        redis_key = f"plugin:rate_limit:{key}"

        # Try Redis first for distributed rate limiting
        if self._redis_available and self.redis:
            try:
                # Use Redis INCR with expiration for atomic rate limiting
                current = await self.redis.incr(redis_key)

                # Set expiration on first call (60 seconds)
                if current == 1:
                    await self.redis.expire(redis_key, 60)

                # Check limit
                if current > limit:
                    logger.warning(f"Rate limit exceeded for {key} (Redis)")
                    return False

                return True
            except Exception as e:
                logger.warning(f"Redis rate limit check failed, falling back to memory: {e}")
                # Fall through to in-memory rate limiting

        # Fallback to in-memory rate limiting
        now = time.time()
        minute_ago = now - 60

        # Clean old timestamps
        self._rate_limits[key] = [ts for ts in self._rate_limits[key] if ts > minute_ago]

        # Check limit
        if len(self._rate_limits[key]) >= limit:
            logger.warning(f"Rate limit exceeded for {key} (memory)")
            return False

        # Record this call
        self._rate_limits[key].append(now)
        return True

    async def _get_cached(
        self, plugin_name: str, input_data: dict[str, Any]
    ) -> PluginOutput | None:
        """
        Get cached result if exists

        Args:
            plugin_name: Plugin name
            input_data: Input data

        Returns:
            Cached output or None
        """
        if not self.redis:
            return None

        try:
            cache_key = self._generate_cache_key(plugin_name, input_data)
            cached = await self.redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return PluginOutput(**data)
        except Exception as e:
            logger.error(f"Cache retrieval error: {e}")

        return None

    async def _cache_result(
        self, plugin_name: str, input_data: dict[str, Any], output: PluginOutput
    ):
        """
        Cache execution result

        Args:
            plugin_name: Plugin name
            input_data: Input data
            output: Plugin output
        """
        if not self.redis:
            return

        try:
            cache_key = self._generate_cache_key(plugin_name, input_data)
            cache_value = output.json()
            await self.redis.setex(cache_key, 3600, cache_value)  # 1 hour TTL
            logger.debug(f"Cached result for {plugin_name}")
        except Exception as e:
            logger.error(f"Cache write error: {e}")

    def _generate_cache_key(self, plugin_name: str, input_data: dict[str, Any]) -> str:
        """
        Generate cache key from plugin name and input

        Args:
            plugin_name: Plugin name
            input_data: Input data

        Returns:
            Cache key string
        """
        # Create deterministic hash of input data using SHA-256 for better security
        input_str = json.dumps(input_data, sort_keys=True)
        input_hash = hashlib.sha256(input_str.encode()).hexdigest()
        return f"plugin:{plugin_name}:{input_hash}"

    async def _record_success(self, plugin_name: str, execution_time: float):
        """Record successful execution"""
        self._metrics[plugin_name]["calls"] += 1
        self._metrics[plugin_name]["successes"] += 1
        self._metrics[plugin_name]["total_time"] += execution_time
        self._metrics[plugin_name]["last_success"] = time.time()

    async def _record_failure(self, plugin_name: str, error: str):
        """Record failed execution"""
        self._metrics[plugin_name]["calls"] += 1
        self._metrics[plugin_name]["failures"] += 1
        self._metrics[plugin_name]["last_error"] = error

        # Update circuit breaker
        if plugin_name not in self._circuit_breakers:
            self._circuit_breakers[plugin_name] = {"failures": 0, "last_failure_time": 0}

        self._circuit_breakers[plugin_name]["failures"] += 1
        self._circuit_breakers[plugin_name]["last_failure_time"] = time.time()

    def _is_circuit_broken(self, plugin_name: str) -> bool:
        """
        Check if circuit breaker is open for plugin

        Args:
            plugin_name: Plugin name

        Returns:
            True if circuit is broken, False otherwise
        """
        if plugin_name not in self._circuit_breakers:
            return False

        breaker = self._circuit_breakers[plugin_name]

        # Circuit breaker: open if threshold failures in cooldown period
        if breaker["failures"] >= CIRCUIT_BREAKER_FAILURE_THRESHOLD:
            time_since_failure = time.time() - breaker["last_failure_time"]
            if time_since_failure < CIRCUIT_BREAKER_COOLDOWN_SECONDS:
                return True
            else:
                # Reset after cooldown
                del self._circuit_breakers[plugin_name]

        return False

    def get_metrics(self, plugin_name: str) -> dict[str, Any]:
        """
        Get plugin metrics

        Args:
            plugin_name: Plugin name

        Returns:
            Dictionary with metrics
        """
        metrics = dict(self._metrics[plugin_name])

        if metrics["calls"] > 0:
            metrics["avg_time"] = metrics["total_time"] / metrics["calls"]
            metrics["success_rate"] = metrics["successes"] / metrics["calls"]

            if metrics["successes"] + metrics["cache_hits"] > 0:
                metrics["cache_hit_rate"] = metrics["cache_hits"] / (
                    metrics["successes"] + metrics["cache_hits"]
                )
            else:
                metrics["cache_hit_rate"] = 0.0
        else:
            metrics["avg_time"] = 0.0
            metrics["success_rate"] = 0.0
            metrics["cache_hit_rate"] = 0.0

        return metrics

    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """
        Get metrics for all plugins

        Returns:
            Dictionary mapping plugin names to metrics
        """
        return {name: self.get_metrics(name) for name in self._metrics}

    async def warm_plugins(self, plugin_names: list[str]):
        """
        Warm up plugins by calling on_load

        Args:
            plugin_names: List of plugin names to warm up
        """
        logger.info(f"Warming up {len(plugin_names)} plugins...")
        for name in plugin_names:
            plugin = registry.get(name)
            if plugin:
                try:
                    await plugin.on_load()
                    logger.info(f"Warmed up: {name}")
                except Exception as e:
                    logger.error(f"Failed to warm up {name}: {e}")


# Global executor instance
executor = PluginExecutor()
