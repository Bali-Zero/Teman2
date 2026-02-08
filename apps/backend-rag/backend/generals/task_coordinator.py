"""
Task Coordinator for ZAN (ZANTARA)

Coordinates tasks between Coding General and Intelligence General.
Provides high-level API for ZANTARA to submit tasks and monitor execution.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class TaskCoordinator:
    """
    Coordinator for The Generals Multi-Agent System.

    Provides:
    - Task submission API
    - Task status monitoring
    - Result retrieval
    - Memory management
    - Activity monitoring
    """

    def __init__(self, database_url: str | None = None):
        """
        Initialize Task Coordinator.

        Args:
            database_url: PostgreSQL connection string (defaults to settings.database_url)
        """
        self.database_url = database_url or settings.database_url
        if not self.database_url:
            raise ValueError("DATABASE_URL not configured")
        self.pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        """Initialize database connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60,
            )
            logger.info("✅ Task Coordinator: Database pool initialized")
        except Exception as e:
            logger.error(f"❌ Task Coordinator: Failed to initialize pool: {e}", exc_info=True)
            raise

    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("✅ Task Coordinator: Database pool closed")

    async def submit_task(
        self,
        task_type: str,
        title: str,
        description: str = "",
        payload: dict[str, Any] | None = None,
        priority: int = 5,
    ) -> int:
        """
        Submit a new task to the generals system.

        Args:
            task_type: 'code' or 'research'
            title: Task title
            description: Task description
            payload: Task-specific data (JSON-serializable)
            priority: Priority 1-10 (higher = more important, default: 5)

        Returns:
            Task ID

        Raises:
            ValueError: If task_type is invalid
        """
        if task_type not in ["code", "research", "orchestration"]:
            raise ValueError(
                f"Invalid task_type: {task_type}. Must be 'code', 'research', or 'orchestration'"
            )

        if not (1 <= priority <= 10):
            raise ValueError(f"Invalid priority: {priority}. Must be between 1 and 10")

        if not self.pool:
            await self.initialize()

        try:
            async with self.pool.acquire() as conn:
                task_id = await conn.fetchval(
                    """
                    INSERT INTO generals_tasks (task_type, title, description, payload, priority, status)
                    VALUES ($1, $2, $3, $4, $5, 'pending')
                    RETURNING id
                    """,
                    task_type,
                    title,
                    description,
                    json.dumps(payload or {}),
                    priority,
                )

                logger.info(f"✅ Task Coordinator: Submitted task {task_id} ({task_type}): {title}")
                return task_id

        except Exception as e:
            logger.error(f"❌ Task Coordinator: Failed to submit task: {e}", exc_info=True)
            raise

    @staticmethod
    def _parse_jsonb_fields(record: dict[str, Any]) -> dict[str, Any]:
        """Parse JSONB fields that asyncpg may return as strings."""
        for field in ("payload", "result", "metadata"):
            val = record.get(field)
            if isinstance(val, str):
                try:
                    record[field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
        return record

    async def get_task(self, task_id: int) -> dict[str, Any] | None:
        """
        Get task details by ID.

        Args:
            task_id: Task ID

        Returns:
            Task record or None if not found
        """
        if not self.pool:
            await self.initialize()

        try:
            async with self.pool.acquire() as conn:
                task = await conn.fetchrow(
                    """
                    SELECT id, task_type, assigned_to, status, priority, title, description,
                           payload, result, error_message,
                           created_at, assigned_at, started_at, completed_at, updated_at
                    FROM generals_tasks
                    WHERE id = $1
                    """,
                    task_id,
                )

                if not task:
                    return None

                return self._parse_jsonb_fields(dict(task))

        except Exception as e:
            logger.error(f"❌ Task Coordinator: Failed to get task: {e}", exc_info=True)
            return None

    async def get_tasks(
        self,
        task_type: str | None = None,
        status: str | None = None,
        assigned_to: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Get multiple tasks with filters.

        Args:
            task_type: Filter by task type ('code' or 'research')
            status: Filter by status ('pending', 'assigned', 'in_progress', 'completed', 'failed', 'cancelled')
            assigned_to: Filter by assigned general ('coding_general' or 'intelligence_general')
            limit: Maximum number of tasks to return
            offset: Offset for pagination

        Returns:
            List of task records
        """
        if not self.pool:
            await self.initialize()

        try:
            conditions = []
            params = []
            param_idx = 1

            if task_type:
                conditions.append(f"task_type = ${param_idx}")
                params.append(task_type)
                param_idx += 1

            if status:
                conditions.append(f"status = ${param_idx}")
                params.append(status)
                param_idx += 1

            if assigned_to:
                conditions.append(f"assigned_to = ${param_idx}")
                params.append(assigned_to)
                param_idx += 1

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            params.extend([limit, offset])

            async with self.pool.acquire() as conn:
                tasks = await conn.fetch(
                    f"""
                    SELECT id, task_type, assigned_to, status, priority, title, description,
                           payload, result, error_message,
                           created_at, assigned_at, started_at, completed_at, updated_at
                    FROM generals_tasks
                    WHERE {where_clause}
                    ORDER BY priority DESC, created_at DESC
                    LIMIT ${param_idx} OFFSET ${param_idx + 1}
                    """,
                    *params,
                )

                return [self._parse_jsonb_fields(dict(task)) for task in tasks]

        except Exception as e:
            logger.error(f"❌ Task Coordinator: Failed to get tasks: {e}", exc_info=True)
            return []

    async def cancel_task(self, task_id: int) -> bool:
        """
        Cancel a pending or assigned task.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled, False if task not found or cannot be cancelled
        """
        if not self.pool:
            await self.initialize()

        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE generals_tasks
                    SET status = 'cancelled',
                        updated_at = NOW()
                    WHERE id = $1
                      AND status IN ('pending', 'assigned')
                    """,
                    task_id,
                )

                cancelled = result == "UPDATE 1"
                if cancelled:
                    logger.info(f"✅ Task Coordinator: Cancelled task {task_id}")
                else:
                    logger.warning(
                        f"⚠️ Task Coordinator: Could not cancel task {task_id} (not found or already in progress)"
                    )

                return cancelled

        except Exception as e:
            logger.error(f"❌ Task Coordinator: Failed to cancel task: {e}", exc_info=True)
            return False

    async def get_task_result(self, task_id: int) -> dict[str, Any] | None:
        """
        Get task execution result.

        Args:
            task_id: Task ID

        Returns:
            Result dictionary or None if task not found or not completed
        """
        task = await self.get_task(task_id)
        if not task:
            return None

        if task["status"] not in ["completed", "failed"]:
            return None

        result = task.get("result")
        if result and isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                pass

        return {
            "task_id": task_id,
            "status": task["status"],
            "result": result,
            "error_message": task.get("error_message"),
            "completed_at": task.get("completed_at"),
        }

    async def wait_for_task(
        self, task_id: int, timeout: int = 300, poll_interval: int = 2
    ) -> dict[str, Any] | None:
        """
        Wait for a task to complete.

        Args:
            task_id: Task ID
            timeout: Maximum seconds to wait (default: 300)
            poll_interval: Seconds between status checks (default: 2)

        Returns:
            Task result or None if timeout or error
        """
        start_time = datetime.now(timezone.utc)

        while True:
            task = await self.get_task(task_id)
            if not task:
                logger.warning(f"⚠️ Task Coordinator: Task {task_id} not found")
                return None

            status = task["status"]
            if status in ["completed", "failed", "cancelled"]:
                return await self.get_task_result(task_id)

            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed >= timeout:
                logger.warning(f"⚠️ Task Coordinator: Timeout waiting for task {task_id}")
                return None

            await asyncio.sleep(poll_interval)

    async def get_memory(self, key: str) -> dict[str, Any] | None:
        """
        Read from shared memory.

        Args:
            key: Memory key

        Returns:
            Memory value or None if not found/expired
        """
        if not self.pool:
            await self.initialize()

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT value, expires_at, general_name, created_at, updated_at
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

                value = row["value"]
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        pass

                return {
                    "key": key,
                    "value": value,
                    "general_name": row["general_name"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "expires_at": row["expires_at"],
                }

        except Exception as e:
            logger.error(f"❌ Task Coordinator: Error reading memory: {e}", exc_info=True)
            return None

    async def set_memory(
        self, key: str, value: dict[str, Any], expires_at: datetime | None = None
    ) -> bool:
        """
        Write to shared memory.

        Args:
            key: Memory key
            value: Memory value (will be stored as JSONB)
            expires_at: Optional expiration timestamp

        Returns:
            True if successful
        """
        if not self.pool:
            await self.initialize()

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO generals_memory (key, value, general_name, expires_at)
                    VALUES ($1, $2, 'task_coordinator', $3)
                    ON CONFLICT (key) DO UPDATE
                    SET value = $2,
                        expires_at = $3,
                        updated_at = NOW()
                    """,
                    key,
                    json.dumps(value),
                    expires_at,
                )

                logger.debug(f"✅ Task Coordinator: Set memory key: {key}")
                return True

        except Exception as e:
            logger.error(f"❌ Task Coordinator: Error writing memory: {e}", exc_info=True)
            return False

    async def delete_memory(self, key: str) -> bool:
        """
        Delete a memory key.

        Args:
            key: Memory key

        Returns:
            True if deleted, False if not found
        """
        if not self.pool:
            await self.initialize()

        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM generals_memory
                    WHERE key = $1
                    """,
                    key,
                )

                deleted = result == "DELETE 1"
                if deleted:
                    logger.debug(f"✅ Task Coordinator: Deleted memory key: {key}")
                return deleted

        except Exception as e:
            logger.error(f"❌ Task Coordinator: Error deleting memory: {e}", exc_info=True)
            return False

    async def get_activity(
        self,
        general_name: str | None = None,
        task_id: int | None = None,
        activity_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get activity log entries.

        Args:
            general_name: Filter by general name
            task_id: Filter by task ID
            activity_type: Filter by activity type
            limit: Maximum number of entries

        Returns:
            List of activity records
        """
        if not self.pool:
            await self.initialize()

        try:
            conditions = []
            params = []
            param_idx = 1

            if general_name:
                conditions.append(f"general_name = ${param_idx}")
                params.append(general_name)
                param_idx += 1

            if task_id:
                conditions.append(f"task_id = ${param_idx}")
                params.append(task_id)
                param_idx += 1

            if activity_type:
                conditions.append(f"activity_type = ${param_idx}")
                params.append(activity_type)
                param_idx += 1

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            params.append(limit)

            async with self.pool.acquire() as conn:
                activities = await conn.fetch(
                    f"""
                    SELECT id, general_name, task_id, activity_type, message, metadata, created_at
                    FROM generals_activity
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ${param_idx}
                    """,
                    *params,
                )

                return [self._parse_jsonb_fields(dict(activity)) for activity in activities]

        except Exception as e:
            logger.error(f"❌ Task Coordinator: Failed to get activity: {e}", exc_info=True)
            return []

    async def get_stats(self) -> dict[str, Any]:
        """
        Get system statistics.

        Returns:
            Dictionary with task counts, memory stats, etc.
        """
        if not self.pool:
            await self.initialize()

        try:
            async with self.pool.acquire() as conn:
                # Task statistics
                task_stats = await conn.fetchrow(
                    """
                    SELECT 
                        COUNT(*) as total_tasks,
                        COUNT(*) FILTER (WHERE status = 'pending') as pending_tasks,
                        COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress_tasks,
                        COUNT(*) FILTER (WHERE status = 'completed') as completed_tasks,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed_tasks,
                        COUNT(*) FILTER (WHERE task_type = 'code') as code_tasks,
                        COUNT(*) FILTER (WHERE task_type = 'research') as research_tasks
                    FROM generals_tasks
                    """
                )

                # Memory statistics
                memory_stats = await conn.fetchrow(
                    """
                    SELECT 
                        COUNT(*) as total_memories,
                        COUNT(*) FILTER (WHERE expires_at IS NOT NULL AND expires_at < NOW()) as expired_memories
                    FROM generals_memory
                    """
                )

                # Activity statistics
                activity_stats = await conn.fetchrow(
                    """
                    SELECT 
                        COUNT(*) as total_activities,
                        COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as recent_activities
                    FROM generals_activity
                    """
                )

                return {
                    "tasks": dict(task_stats),
                    "memory": dict(memory_stats),
                    "activity": dict(activity_stats),
                }

        except Exception as e:
            logger.error(f"❌ Task Coordinator: Failed to get stats: {e}", exc_info=True)
            return {}


# ========================================
# FastAPI Router for ZAN API
# ========================================

router = APIRouter(prefix="/api/generals", tags=["generals"])

# Initialize coordinator instance
_coordinator_instance: TaskCoordinator | None = None


def get_coordinator() -> TaskCoordinator:
    """Get or create singleton TaskCoordinator instance."""
    global _coordinator_instance
    if _coordinator_instance is None:
        _coordinator_instance = TaskCoordinator()
    return _coordinator_instance


# Request/Response Models
class TaskSubmitRequest(BaseModel):
    """Request model for submitting a task."""

    task_type: str = Field(..., description="Task type: 'code' or 'research'")
    title: str = Field(..., description="Task title")
    description: str = Field(default="", description="Task description")
    payload: dict[str, Any] = Field(default_factory=dict, description="Task-specific payload")
    priority: int = Field(
        default=5, ge=1, le=10, description="Priority (1-10, higher = more important)"
    )


class TaskResponse(BaseModel):
    """Response model for task details."""

    id: int
    task_type: str
    assigned_to: str | None
    status: str
    priority: int
    title: str
    description: str | None
    payload: dict[str, Any] | None
    result: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    assigned_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime


class TaskResultResponse(BaseModel):
    """Response model for task result."""

    task_id: int
    status: str
    result: dict[str, Any] | None
    error_message: str | None
    completed_at: datetime | None


class MemoryRequest(BaseModel):
    """Request model for memory operations."""

    key: str = Field(..., description="Memory key")
    value: dict[str, Any] = Field(..., description="Memory value")
    expires_at: datetime | None = Field(None, description="Optional expiration timestamp")


class MemoryResponse(BaseModel):
    """Response model for memory."""

    key: str
    value: dict[str, Any]
    general_name: str | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None


class StatsResponse(BaseModel):
    """Response model for system statistics."""

    tasks: dict[str, Any]
    memory: dict[str, Any]
    activity: dict[str, Any]


# API Endpoints
@router.post("/tasks", response_model=dict[str, int], status_code=status.HTTP_201_CREATED)
async def submit_task(
    request: TaskSubmitRequest,
    coordinator: TaskCoordinator = Depends(get_coordinator),
) -> dict[str, int]:
    """
    Submit a new task to the generals system.

    Args:
        request: Task submission request
        coordinator: TaskCoordinator instance

    Returns:
        Dictionary with task_id
    """
    try:
        task_id = await coordinator.submit_task(
            task_type=request.task_type,
            title=request.title,
            description=request.description,
            payload=request.payload,
            priority=request.priority,
        )
        return {"task_id": task_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to submit task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit task: {str(e)}",
        )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    coordinator: TaskCoordinator = Depends(get_coordinator),
) -> TaskResponse:
    """
    Get task details by ID.

    Args:
        task_id: Task ID
        coordinator: TaskCoordinator instance

    Returns:
        Task details
    """
    task = await coordinator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return TaskResponse(**task)


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    task_type: str | None = None,
    status: str | None = None,
    assigned_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
    coordinator: TaskCoordinator = Depends(get_coordinator),
) -> list[TaskResponse]:
    """
    List tasks with optional filters.

    Args:
        task_type: Filter by task type ('code' or 'research')
        status: Filter by status
        assigned_to: Filter by assigned general
        limit: Maximum number of tasks
        offset: Pagination offset
        coordinator: TaskCoordinator instance

    Returns:
        List of tasks
    """
    tasks = await coordinator.get_tasks(
        task_type=task_type,
        status=status,
        assigned_to=assigned_to,
        limit=limit,
        offset=offset,
    )
    return [TaskResponse(**task) for task in tasks]


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_task(
    task_id: int,
    coordinator: TaskCoordinator = Depends(get_coordinator),
) -> None:
    """
    Cancel a pending or assigned task.

    Args:
        task_id: Task ID
        coordinator: TaskCoordinator instance
    """
    cancelled = await coordinator.cancel_task(task_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task not found or cannot be cancelled",
        )


@router.get("/tasks/{task_id}/result", response_model=TaskResultResponse)
async def get_task_result(
    task_id: int,
    coordinator: TaskCoordinator = Depends(get_coordinator),
) -> TaskResultResponse:
    """
    Get task execution result.

    Args:
        task_id: Task ID
        coordinator: TaskCoordinator instance

    Returns:
        Task result
    """
    result = await coordinator.get_task_result(task_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or not completed",
        )
    return TaskResultResponse(**result)


@router.post("/tasks/{task_id}/wait", response_model=TaskResultResponse)
async def wait_for_task(
    task_id: int,
    timeout: int = 300,
    poll_interval: int = 2,
    coordinator: TaskCoordinator = Depends(get_coordinator),
) -> TaskResultResponse:
    """
    Wait for a task to complete.

    Args:
        task_id: Task ID
        timeout: Maximum seconds to wait (default: 300)
        poll_interval: Seconds between status checks (default: 2)
        coordinator: TaskCoordinator instance

    Returns:
        Task result
    """
    result = await coordinator.wait_for_task(task_id, timeout=timeout, poll_interval=poll_interval)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Task did not complete within timeout period",
        )
    return TaskResultResponse(**result)


@router.get("/memory/{key}", response_model=MemoryResponse)
async def get_memory(
    key: str,
    coordinator: TaskCoordinator = Depends(get_coordinator),
) -> MemoryResponse:
    """
    Read from shared memory.

    Args:
        key: Memory key
        coordinator: TaskCoordinator instance

    Returns:
        Memory value
    """
    memory = await coordinator.get_memory(key)
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory key not found")
    return MemoryResponse(**memory)


@router.post("/memory", response_model=dict[str, bool], status_code=status.HTTP_201_CREATED)
async def set_memory(
    request: MemoryRequest,
    coordinator: TaskCoordinator = Depends(get_coordinator),
) -> dict[str, bool]:
    """
    Write to shared memory.

    Args:
        request: Memory request
        coordinator: TaskCoordinator instance

    Returns:
        Success status
    """
    success = await coordinator.set_memory(
        key=request.key,
        value=request.value,
        expires_at=request.expires_at,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set memory",
        )
    return {"success": True}


@router.delete("/memory/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    key: str,
    coordinator: TaskCoordinator = Depends(get_coordinator),
) -> None:
    """
    Delete a memory key.

    Args:
        key: Memory key
        coordinator: TaskCoordinator instance
    """
    deleted = await coordinator.delete_memory(key)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory key not found")


@router.get("/activity", response_model=list[dict[str, Any]])
async def get_activity(
    general_name: str | None = None,
    task_id: int | None = None,
    activity_type: str | None = None,
    limit: int = 100,
    coordinator: TaskCoordinator = Depends(get_coordinator),
) -> list[dict[str, Any]]:
    """
    Get activity log entries.

    Args:
        general_name: Filter by general name
        task_id: Filter by task ID
        activity_type: Filter by activity type
        limit: Maximum number of entries
        coordinator: TaskCoordinator instance

    Returns:
        List of activity records
    """
    return await coordinator.get_activity(
        general_name=general_name,
        task_id=task_id,
        activity_type=activity_type,
        limit=limit,
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    coordinator: TaskCoordinator = Depends(get_coordinator),
) -> StatsResponse:
    """
    Get system statistics.

    Args:
        coordinator: TaskCoordinator instance

    Returns:
        System statistics
    """
    stats = await coordinator.get_stats()
    return StatsResponse(**stats)
