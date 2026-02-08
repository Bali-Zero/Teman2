"""
Antigravity General - System Orchestrator

Polls generals_tasks table for tasks with task_type='orchestration',
executes system-level coordination and multi-tool workflows.
"""

import asyncio
import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any

import asyncpg

from backend.app.core.config import settings
from backend.generals.onboarding_context import (
    get_enforced_env,
    log_onboarding_compliance,
)

logger = logging.getLogger(__name__)


class AntigravityGeneral:
    """General responsible for system orchestration and multi-tool coordination.

    Capabilities:
    - IDE control via AppleScript (Antigravity.app)
    - Multi-file coordination
    - System-level automation
    - Complex workflow execution
    """

    def __init__(self, database_url: str | None = None, poll_interval: int = 10):
        """
        Initialize Antigravity General.

        Args:
            database_url: PostgreSQL connection string (defaults to settings.database_url)
            poll_interval: Seconds between task polls (default: 10)
        """
        self.database_url = database_url or settings.database_url
        if not self.database_url:
            raise ValueError("DATABASE_URL not configured")
        self.poll_interval = poll_interval
        self.pool: asyncpg.Pool | None = None
        self.running = False
        self.general_name = "antigravity_general"

        # Load onboarding context
        log_onboarding_compliance(self.general_name)

    async def initialize(self) -> None:
        """Initialize database connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60,
            )
            logger.info("✅ Antigravity General: Database pool initialized")
        except Exception as e:
            logger.error(f"❌ Antigravity General: Failed to initialize pool: {e}", exc_info=True)
            raise

    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("✅ Antigravity General: Database pool closed")

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
                    json.dumps(metadata) if metadata else None,
                )
        except Exception as e:
            logger.error(f"Failed to log activity: {e}")

    async def _write_memory(
        self,
        key: str,
        value: Any,
        category: str = "orchestration",
    ) -> None:
        """Write to shared memory (generals_memory table)."""
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO generals_memory (general_name, key, value, category)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (key) 
                    DO UPDATE SET 
                        value = EXCLUDED.value,
                        category = EXCLUDED.category,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    self.general_name,
                    key,
                    json.dumps(value) if not isinstance(value, str) else value,
                    category,
                )
                logger.info(f"✅ Memory written: {key} (category: {category})")
        except Exception as e:
            logger.error(f"Failed to write memory: {e}")

    async def _execute_applescript(self, script: str) -> tuple[str, str, int]:
        """
        Execute AppleScript command.

        Args:
            script: AppleScript code to execute

        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        cmd = ["osascript", "-e", script]
        env = get_enforced_env()

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout_bytes, stderr_bytes = await process.communicate()
            stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
            return_code = process.returncode or 0

            return stdout, stderr, return_code

        except Exception as e:
            error_msg = f"AppleScript execution failed: {e}\n{traceback.format_exc()}"
            logger.error(error_msg)
            return "", error_msg, 1

    async def _control_antigravity_app(self, command: str) -> tuple[str, str, int]:
        """
        Control Antigravity.app via AppleScript.

        Args:
            command: 'open' | 'quit' | 'activate' | 'status'

        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        scripts = {
            "open": 'tell application "Antigravity" to activate',
            "quit": 'tell application "Antigravity" to quit',
            "activate": 'tell application "Antigravity" to activate',
            "status": 'tell application "System Events" to get name of processes',
        }

        script = scripts.get(command)
        if not script:
            return "", f"Unknown command: {command}", 1

        stdout, stderr, code = await self._execute_applescript(script)

        # For status, check if Antigravity is in the process list
        if command == "status":
            is_running = "Antigravity" in stdout
            return "running" if is_running else "stopped", stderr, code

        return stdout, stderr, code

    async def _execute_orchestration_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a complex orchestration task.

        Task payload can contain:
        - app_command: Control Antigravity app ('open'|'quit'|'activate'|'status')
        - applescript: Raw AppleScript to execute
        - description: Human-readable task description

        Returns:
            Result dictionary with execution details
        """
        result = {
            "status": "started",
            "steps": [],
            "error": None,
        }

        # Handle app control
        if "app_command" in task:
            app_cmd = task["app_command"]
            logger.info(f"🌐 Antigravity: Executing app command '{app_cmd}'")

            stdout, stderr, code = await self._control_antigravity_app(app_cmd)
            result["steps"].append(
                {
                    "type": "app_command",
                    "command": app_cmd,
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": code,
                }
            )

            if code != 0:
                result["status"] = "failed"
                result["error"] = f"App command failed: {stderr}"
                return result

        # Handle raw AppleScript
        if "applescript" in task:
            script = task["applescript"]
            logger.info("🌐 Antigravity: Executing AppleScript")

            stdout, stderr, code = await self._execute_applescript(script)
            result["steps"].append(
                {
                    "type": "applescript",
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": code,
                }
            )

            if code != 0:
                result["status"] = "failed"
                result["error"] = f"AppleScript failed: {stderr}"
                return result

        # Handle orchestration description (future: LLM-based planning)
        if "description" in task and not result["steps"]:
            description = task["description"]
            logger.info(f"🌐 Antigravity: Processing orchestration '{description}'")
            result["steps"].append(
                {
                    "type": "orchestration",
                    "description": description,
                    "note": "Complex orchestration support coming soon",
                }
            )

        result["status"] = "completed"
        return result

    async def _process_task(self, task_row: dict) -> None:
        """Process a single orchestration task."""
        task_id = task_row["id"]
        title = task_row["title"]
        description = task_row["description"] or ""
        payload_str = task_row["payload"]

        logger.info(f"🌐 Antigravity General: Processing task {task_id}: {title}")

        # Parse payload
        try:
            payload = json.loads(payload_str) if payload_str else {}
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON payload: {e}"
            logger.error(error_msg)
            await self._update_task_status(task_id, "failed", error=error_msg)
            return

        # Update to in_progress
        await self._update_task_status(task_id, "in_progress")
        await self._log_activity("task_started", f"Started task: {title}", task_id=task_id)

        # Execute orchestration
        try:
            result = await self._execute_orchestration_task(payload)

            # Update task with result
            await self._update_task_status(
                task_id,
                "completed" if result["status"] == "completed" else "failed",
                result=result,
                error=result.get("error"),
            )

            # Write to memory
            memory_key = f"task_{task_id}_result"
            await self._write_memory(memory_key, result, category="orchestration")

            # Log completion
            status = result["status"]
            steps_count = len(result["steps"])
            await self._log_activity(
                "task_completed" if status == "completed" else "task_failed",
                f"Task {task_id}: {status} ({steps_count} steps)",
                task_id=task_id,
                metadata={"result": result},
            )

            logger.info(f"✅ Antigravity: Task {task_id} {status} ({steps_count} steps)")

        except Exception as e:
            error_msg = f"Task execution failed: {e}\n{traceback.format_exc()}"
            logger.error(error_msg)
            await self._update_task_status(task_id, "failed", error=error_msg)
            await self._log_activity("task_failed", f"Task {task_id} failed: {e}", task_id=task_id)

    async def _update_task_status(
        self,
        task_id: int,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Update task status in database."""
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                if status == "completed" or status == "failed":
                    await conn.execute(
                        """
                        UPDATE generals_tasks
                        SET status = $1, result = $2, error = $3, completed_at = $4
                        WHERE id = $5
                        """,
                        status,
                        json.dumps(result) if result else None,
                        error,
                        datetime.now(timezone.utc),
                        task_id,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE generals_tasks
                        SET status = $1
                        WHERE id = $2
                        """,
                        status,
                        task_id,
                    )
        except Exception as e:
            logger.error(f"Failed to update task status: {e}")

    async def run(self) -> None:
        """Main loop: poll for orchestration tasks and execute them."""
        self.running = True
        logger.info(f"🌐 Antigravity General: Starting (poll interval: {self.poll_interval}s)")

        if not self.pool:
            await self.initialize()

        while self.running:
            try:
                # Poll for pending orchestration tasks
                async with self.pool.acquire() as conn:
                    tasks = await conn.fetch(
                        """
                        SELECT id, title, description, payload, created_at
                        FROM generals_tasks
                        WHERE task_type = 'orchestration' 
                          AND status = 'pending'
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 5
                        """
                    )

                if tasks:
                    logger.info(f"🌐 Antigravity: Found {len(tasks)} orchestration tasks")
                    for task in tasks:
                        await self._process_task(dict(task))

                # Sleep before next poll
                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.info("🌐 Antigravity General: Received shutdown signal")
                self.running = False
                break
            except Exception as e:
                logger.error(f"🌐 Antigravity General: Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval)

        logger.info("🌐 Antigravity General: Stopped")

    async def stop(self) -> None:
        """Stop the general gracefully."""
        logger.info("🌐 Antigravity General: Stopping...")
        self.running = False
        await self.close()


# Singleton instance for service initialization
_antigravity_general: AntigravityGeneral | None = None


def get_antigravity_general() -> AntigravityGeneral:
    """Get or create Antigravity General singleton."""
    global _antigravity_general
    if _antigravity_general is None:
        _antigravity_general = AntigravityGeneral()
    return _antigravity_general
