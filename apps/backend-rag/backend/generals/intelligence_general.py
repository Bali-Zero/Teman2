"""
Intelligence General - Performs research and analysis using Gemini 3 Pro

Polls generals_tasks table for tasks with task_type='research',
uses Gemini 3 Pro for analysis, and updates status/result in the database.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

from backend.app.core.config import settings
from backend.generals.onboarding_context import (
    get_intelligence_system_instruction,
    log_onboarding_compliance,
)

# Import Gemini client
try:
    from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient, get_genai_client
except ImportError:
    GENAI_AVAILABLE = False
    GenAIClient = None
    get_genai_client = None

logger = logging.getLogger(__name__)


class IntelligenceGeneral:
    """General responsible for research and intelligence tasks using Gemini 3 Pro.

    Every research task includes AI_ONBOARDING.md as system context,
    ensuring all analysis and code suggestions follow the Golden Rules.
    """

    def __init__(self, database_url: str | None = None, poll_interval: int = 5):
        """
        Initialize Intelligence General.

        Args:
            database_url: PostgreSQL connection string (defaults to settings.database_url)
            poll_interval: Seconds between task polls (default: 5)
        """
        self.database_url = database_url or settings.database_url
        if not self.database_url:
            raise ValueError("DATABASE_URL not configured")
        self.poll_interval = poll_interval
        self.pool: asyncpg.Pool | None = None
        self.running = False
        self.general_name = "intelligence_general"

        # Load onboarding context — this is our constitution
        log_onboarding_compliance(self.general_name)

        # Initialize Gemini client
        self.genai_client: GenAIClient | None = None
        if GENAI_AVAILABLE and get_genai_client:
            try:
                self.genai_client = get_genai_client()
                if not self.genai_client.is_available:
                    logger.warning("⚠️ Intelligence General: Gemini client not available")
                    self.genai_client = None
                else:
                    logger.info("✅ Intelligence General: Gemini client initialized")
            except Exception as e:
                logger.error(
                    f"❌ Intelligence General: Failed to initialize Gemini: {e}", exc_info=True
                )
                self.genai_client = None
        else:
            logger.warning("⚠️ Intelligence General: Gemini SDK not available")

    async def initialize(self) -> None:
        """Initialize database connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60,
            )
            logger.info("✅ Intelligence General: Database pool initialized")
        except Exception as e:
            logger.error(f"❌ Intelligence General: Failed to initialize pool: {e}", exc_info=True)
            raise

    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("✅ Intelligence General: Database pool closed")

    async def _log_activity(
        self,
        activity_type: str,
        message: str,
        task_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log activity to generals_activity table."""
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO generals_activity (general_name, task_id, activity_type, message, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    self.general_name,
                    task_id,
                    activity_type,
                    message,
                    json.dumps(metadata or {}),
                )
        except Exception as e:
            logger.warning(f"Failed to log activity: {e}")

    async def _read_memory(self, key: str) -> dict[str, Any] | None:
        """
        Read from shared memory.

        Args:
            key: Memory key

        Returns:
            Memory value or None if not found/expired
        """
        if not self.pool:
            return None

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT value, expires_at
                    FROM generals_memory
                    WHERE key = $1
                    """,
                    key,
                )

                if not row:
                    return None

                # Check expiration
                if row["expires_at"] and row["expires_at"] < datetime.now(timezone.utc):
                    # Expired, delete it
                    await conn.execute(
                        """
                        DELETE FROM generals_memory
                        WHERE key = $1
                        """,
                        key,
                    )
                    return None

                await self._log_activity(
                    "memory_read", f"Read memory key: {key}", metadata={"key": key}
                )
                return dict(row["value"])

        except Exception as e:
            logger.error(f"❌ Intelligence General: Error reading memory: {e}", exc_info=True)
            return None

    async def _write_memory(
        self, key: str, value: dict[str, Any], expires_at: datetime | None = None
    ) -> None:
        """
        Write to shared memory.

        Args:
            key: Memory key
            value: Memory value (will be stored as JSONB)
            expires_at: Optional expiration timestamp
        """
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO generals_memory (key, value, general_name, expires_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (key) DO UPDATE
                    SET value = $2,
                        general_name = $3,
                        expires_at = $4,
                        updated_at = NOW()
                    """,
                    key,
                    json.dumps(value),
                    self.general_name,
                    expires_at,
                )

                await self._log_activity(
                    "memory_written",
                    f"Wrote memory key: {key}",
                    metadata={"key": key, "expires_at": str(expires_at)},
                )

        except Exception as e:
            logger.error(f"❌ Intelligence General: Error writing memory: {e}", exc_info=True)

    async def poll_task(self) -> dict[str, Any] | None:
        """
        Poll for pending research tasks.

        Returns:
            Task record or None if no tasks available
        """
        if not self.pool:
            await self.initialize()

        try:
            async with self.pool.acquire() as conn:
                # Get highest priority pending task
                task = await conn.fetchrow(
                    """
                    SELECT id, task_type, title, description, payload, priority, created_at
                    FROM generals_tasks
                    WHERE task_type = 'research'
                      AND status = 'pending'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                    """
                )

                if not task:
                    return None

                # Assign task to this general
                await conn.execute(
                    """
                    UPDATE generals_tasks
                    SET status = 'assigned',
                        assigned_to = $1,
                        assigned_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $2
                    """,
                    self.general_name,
                    task["id"],
                )

                await self._log_activity(
                    "task_polled",
                    f"Polled task: {task['title']}",
                    task_id=task["id"],
                )

                return dict(task)

        except Exception as e:
            logger.error(f"❌ Intelligence General: Error polling task: {e}", exc_info=True)
            await self._log_activity("error", f"Poll error: {str(e)}", metadata={"error": str(e)})
            return None

    async def execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a research task using Gemini 3 Pro.

        Args:
            task: Task record from database

        Returns:
            Result dictionary with status and analysis
        """
        task_id = task["id"]
        title = task["title"]
        description = task.get("description", "")
        payload = task.get("payload") or {}
        if isinstance(payload, str):
            payload = json.loads(payload)

        logger.info(f"🧠 Intelligence General: Executing task {task_id}: {title}")

        await self._log_activity(
            "task_started",
            f"Started research: {title}",
            task_id=task_id,
            metadata={"payload": payload},
        )

        # Update status to in_progress
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE generals_tasks
                        SET status = 'in_progress',
                            started_at = NOW(),
                            updated_at = NOW()
                        WHERE id = $1
                        """,
                        task_id,
                    )
            except Exception as e:
                logger.warning(f"Failed to update task status: {e}")

        result = {
            "status": "failed",
            "analysis": "",
            "insights": [],
            "sources": [],
            "error": None,
            "model_used": None,
            "token_usage": {},
            "execution_time_seconds": 0,
        }

        start_time = datetime.now(timezone.utc)

        try:
            if not self.genai_client:
                raise RuntimeError("Gemini client not available")

            # Extract research parameters from payload
            query = payload.get("query") or description or title
            context = payload.get("context", "")
            memory_keys = payload.get("memory_keys", [])  # Keys to read from shared memory
            save_to_memory = payload.get(
                "save_to_memory", False
            )  # Whether to save result to memory
            memory_key = payload.get("memory_key")  # Key to save result under
            max_tokens = payload.get("max_tokens", 8192)
            temperature = payload.get("temperature", 0.7)

            # Build context from shared memory if requested
            memory_context = ""
            if memory_keys:
                memory_data = []
                for key in memory_keys:
                    mem_value = await self._read_memory(key)
                    if mem_value:
                        memory_data.append(f"{key}: {json.dumps(mem_value)}")
                if memory_data:
                    memory_context = "\n\nShared Memory Context:\n" + "\n".join(memory_data)

            # AI_ONBOARDING: Build system instruction with Golden Rules context
            system_instruction = get_intelligence_system_instruction()

            # Build user prompt
            user_prompt = f"""Research Query: {query}"""
            if context:
                user_prompt += f"\n\nAdditional Context:\n{context}"
            if memory_context:
                user_prompt += memory_context
            user_prompt += "\n\nPlease provide a comprehensive analysis."

            # Use Gemini 3 Pro (or closest equivalent)
            # Using PRO_MODEL which is gemini-2.0-flash-lite or gemini-2.0-pro-exp if available
            model_name = (
                payload.get("model") or "gemini-2.0-flash-lite"
            )  # Use Flash as Pro equivalent

            logger.info(f"🧠 Intelligence General: Using model {model_name} for task {task_id}")

            # Generate analysis
            response = await self.genai_client.generate_content(
                contents=user_prompt,
                model=model_name,
                system_instruction=system_instruction,
                max_output_tokens=max_tokens,
                temperature=temperature,
            )

            analysis_text = response.get("text", "")
            model_used = response.get("model", model_name)
            token_usage = response.get("usage", {})

            # Extract insights (simple extraction - can be enhanced)
            insights = []
            if "insight" in analysis_text.lower() or "finding" in analysis_text.lower():
                # Try to extract structured insights
                lines = analysis_text.split("\n")
                for line in lines:
                    if any(
                        keyword in line.lower()
                        for keyword in ["insight", "finding", "conclusion", "key point"]
                    ):
                        insights.append(line.strip())

            # Extract sources if mentioned
            sources = []
            if "source" in analysis_text.lower() or "reference" in analysis_text.lower():
                lines = analysis_text.split("\n")
                for line in lines:
                    if any(
                        keyword in line.lower()
                        for keyword in ["source:", "reference:", "http", "www."]
                    ):
                        sources.append(line.strip())

            result["status"] = "completed"
            result["analysis"] = analysis_text
            result["insights"] = insights[:10]  # Limit to 10 insights
            result["sources"] = sources[:10]  # Limit to 10 sources
            result["model_used"] = model_used
            result["token_usage"] = token_usage

            # Save to memory if requested
            if save_to_memory and memory_key:
                expires_at = None
                if payload.get("memory_ttl_seconds"):
                    from datetime import timedelta

                    expires_at = datetime.now(timezone.utc) + timedelta(
                        seconds=payload["memory_ttl_seconds"]
                    )

                await self._write_memory(
                    memory_key,
                    {
                        "task_id": task_id,
                        "query": query,
                        "analysis": analysis_text,
                        "insights": insights,
                        "model_used": model_used,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                    expires_at=expires_at,
                )

        except Exception as e:
            error_msg = str(e)
            result["error"] = error_msg
            logger.error(
                f"❌ Intelligence General: Task {task_id} failed: {error_msg}", exc_info=True
            )

        finally:
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            result["execution_time_seconds"] = execution_time

        # Update task in database
        await self._update_task_result(task_id, result)

        return result

    async def _update_task_result(self, task_id: int, result: dict[str, Any]) -> None:
        """Update task with execution result."""
        if not self.pool:
            return

        try:
            status = "completed" if result["status"] == "completed" else "failed"
            error_message = result.get("error")

            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE generals_tasks
                    SET status = $1,
                        result = $2,
                        error_message = $3,
                        completed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $4
                    """,
                    status,
                    json.dumps(result),
                    error_message,
                    task_id,
                )

            await self._log_activity(
                f"task_{status}",
                f"Task {status}: {result.get('analysis', '')[:100]}",
                task_id=task_id,
                metadata={
                    "execution_time": result.get("execution_time_seconds"),
                    "model_used": result.get("model_used"),
                    "token_usage": result.get("token_usage"),
                },
            )

        except Exception as e:
            logger.error(
                f"❌ Intelligence General: Failed to update task result: {e}", exc_info=True
            )

    async def run_loop(self) -> None:
        """Main polling loop - runs indefinitely."""
        if not self.pool:
            await self.initialize()

        if not self.genai_client:
            logger.error("❌ Intelligence General: Cannot start - Gemini client not available")
            return

        self.running = True
        logger.info("🚀 Intelligence General: Starting task polling loop")

        while self.running:
            try:
                task = await self.poll_task()

                if task:
                    await self.execute_task(task)
                else:
                    # No tasks available, wait before next poll
                    await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.info("🛑 Intelligence General: Polling loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Intelligence General: Error in polling loop: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval)

        logger.info("✅ Intelligence General: Polling loop stopped")

    def stop(self) -> None:
        """Stop the polling loop."""
        self.running = False
        logger.info("🛑 Intelligence General: Stop requested")
