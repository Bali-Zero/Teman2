"""
Coding General - Executes code-related tasks

Polls generals_tasks table for tasks with task_type='code',
executes them, and updates status/result in the database.
"""

import asyncio
import json
import logging
import shlex
import subprocess
import traceback
from datetime import datetime, timezone
from typing import Any

import asyncpg

from backend.app.core.config import settings
from backend.generals.onboarding_context import (
    get_enforced_env,
    get_working_directory,
    log_onboarding_compliance,
    validate_command,
)

logger = logging.getLogger(__name__)


class CodingGeneral:
    """General responsible for executing code-related tasks.

    Every execution respects AI_ONBOARDING.md Golden Rules:
    - Virtualenv enforced in PATH
    - PYTHONPATH set to backend root
    - Commands validated for hardcoded secrets
    - Working directory defaults to apps/backend-rag/
    """

    def __init__(self, database_url: str | None = None, poll_interval: int = 5):
        """
        Initialize Coding General.

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
        self.general_name = "coding_general"

        # Load onboarding context — this is our constitution
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
            logger.info("✅ Coding General: Database pool initialized")
        except Exception as e:
            logger.error(f"❌ Coding General: Failed to initialize pool: {e}", exc_info=True)
            raise

    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("✅ Coding General: Database pool closed")

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

    async def _write_memory(
        self,
        key: str,
        value: dict[str, Any],
        expires_at: datetime | None = None,
    ) -> None:
        """Write to shared memory (generals_memory table)."""
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
                    metadata={"key": key},
                )

        except Exception as e:
            logger.warning(f"Failed to write memory: {e}")

    async def _read_memory(self, key: str) -> dict[str, Any] | None:
        """Read from shared memory (generals_memory table)."""
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
                    await conn.execute(
                        "DELETE FROM generals_memory WHERE key = $1",
                        key,
                    )
                    return None

                await self._log_activity(
                    "memory_read",
                    f"Read memory key: {key}",
                    metadata={"key": key},
                )
                return dict(row["value"])

        except Exception as e:
            logger.error(f"❌ Coding General: Error reading memory: {e}", exc_info=True)
            return None

    async def poll_task(self) -> dict[str, Any] | None:
        """
        Poll for pending code tasks.

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
                    WHERE task_type = 'code'
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
            logger.error(f"❌ Coding General: Error polling task: {e}", exc_info=True)
            await self._log_activity("error", f"Poll error: {str(e)}", metadata={"error": str(e)})
            return None

    async def execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a code task.

        Args:
            task: Task record from database

        Returns:
            Result dictionary with status and output
        """
        task_id = task["id"]
        title = task["title"]
        description = task.get("description", "")
        payload = task.get("payload") or {}
        if isinstance(payload, str):
            payload = json.loads(payload)

        logger.info(f"🔧 Coding General: Executing task {task_id}: {title}")

        await self._log_activity(
            "task_started",
            f"Started execution: {title}",
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
            "output": "",
            "error": None,
            "execution_time_seconds": 0,
        }

        start_time = datetime.now(timezone.utc)

        try:
            # Extract execution details from payload
            command = payload.get("command")
            script_path = payload.get("script_path")
            code = payload.get("code")
            working_dir = payload.get("working_dir")
            env_vars = payload.get("env_vars", {})

            if not any([command, script_path, code]):
                raise ValueError("Task payload must contain 'command', 'script_path', or 'code'")

            # AI_ONBOARDING: Enforce Golden Rules environment
            # - Virtualenv in PATH
            # - PYTHONPATH includes backend root
            # - Custom env vars merged on top
            env = get_enforced_env()
            if payload.get("env_vars"):
                env.update(payload["env_vars"])

            # AI_ONBOARDING: Validate command against Golden Rules
            if command:
                is_valid, warning = validate_command(command)
                if warning:
                    logger.warning(f"📋 Onboarding check: {warning}")
                    await self._log_activity(
                        "onboarding_warning",
                        warning,
                        task_id=task_id,
                        metadata={"command": command},
                    )

            # AI_ONBOARDING: Default working directory to backend root
            if not working_dir:
                working_dir = get_working_directory(payload)

            # Execute based on what's provided
            if command:
                # Execute shell command
                result["output"] = await self._execute_command(command, working_dir, env)
                result["status"] = "completed"

            elif script_path:
                # Execute Python script
                result["output"] = await self._execute_script(
                    script_path, payload.get("args", []), working_dir, env
                )
                result["status"] = "completed"

            elif code:
                # Execute Python code string
                result["output"] = await self._execute_code(
                    code, payload.get("globals", {}), working_dir
                )
                result["status"] = "completed"

        except Exception as e:
            error_msg = str(e)
            error_trace = traceback.format_exc()
            result["error"] = error_msg
            result["traceback"] = error_trace
            logger.error(f"❌ Coding General: Task {task_id} failed: {error_msg}", exc_info=True)

        finally:
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            result["execution_time_seconds"] = execution_time

        # Update task in database
        await self._update_task_result(task_id, result)

        # Write to generals_memory on successful completion
        if result["status"] == "completed":
            await self._write_memory(
                f"coding:task:{task_id}:result",
                {
                    "task_id": task_id,
                    "title": title,
                    "output": result["output"][:500],
                    "execution_time": result["execution_time_seconds"],
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        return result

    async def _execute_command(
        self,
        command: str,
        working_dir: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int = 300,
    ) -> str:
        """Execute a shell command with timeout."""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=working_dir,
                env=env,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace")

            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, command, output)

            return output

        except asyncio.TimeoutError:
            process.kill()
            raise RuntimeError(f"Command timed out after {timeout}s: {command}") from None

        except subprocess.CalledProcessError:
            raise

        except Exception as e:
            raise RuntimeError(f"Command execution failed: {e}") from e

    async def _execute_script(
        self,
        script_path: str,
        args: list[str] | None = None,
        working_dir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> str:
        """Execute a Python script."""
        import sys

        args = args or []
        cmd_parts = [shlex.quote(sys.executable), shlex.quote(script_path)]
        cmd_parts.extend(shlex.quote(a) for a in args)

        return await self._execute_command(" ".join(cmd_parts), working_dir, env)

    async def _execute_code(
        self, code: str, globals_dict: dict[str, Any] | None = None, working_dir: str | None = None
    ) -> str:
        """Execute Python code string."""
        import io
        import sys

        globals_dict = globals_dict or {}
        locals_dict = {}

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()

        try:
            if working_dir:
                import os

                old_cwd = os.getcwd()
                os.chdir(working_dir)
                try:
                    exec(code, globals_dict, locals_dict)
                finally:
                    os.chdir(old_cwd)
            else:
                exec(code, globals_dict, locals_dict)

            output = captured_output.getvalue()
            return output

        except Exception as e:
            raise RuntimeError(f"Code execution failed: {e}") from e

        finally:
            sys.stdout = old_stdout

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
                f"Task {status}: {result.get('output', '')[:100]}",
                task_id=task_id,
                metadata={"execution_time": result.get("execution_time_seconds")},
            )

        except Exception as e:
            logger.error(f"❌ Coding General: Failed to update task result: {e}", exc_info=True)

    async def run_loop(self) -> None:
        """Main polling loop - runs indefinitely."""
        if not self.pool:
            await self.initialize()

        self.running = True
        logger.info("🚀 Coding General: Starting task polling loop")

        while self.running:
            try:
                task = await self.poll_task()

                if task:
                    await self.execute_task(task)
                else:
                    # No tasks available, wait before next poll
                    await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.info("🛑 Coding General: Polling loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Coding General: Error in polling loop: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval)

        logger.info("✅ Coding General: Polling loop stopped")

    def stop(self) -> None:
        """Stop the polling loop."""
        self.running = False
        logger.info("🛑 Coding General: Stop requested")
