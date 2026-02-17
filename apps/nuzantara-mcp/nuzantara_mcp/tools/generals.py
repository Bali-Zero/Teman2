"""Generals (Task Coordination) Tools - 10 tools for multi-agent task orchestration."""

from typing import Any, Optional


def register(mcp, _call, _call_safe):
    # --- Task Management ---

    @mcp.tool()
    async def submit_task(
        task_type: str,
        title: str,
        description: str,
        payload: Optional[dict] = None,
        priority: int = 5,
    ) -> dict:
        """
        Submit a new task to the generals coordination system.

        The task is queued and assigned to an available general (agent)
        for execution. Use wait_for_task to block until completion.

        Args:
            task_type: Type of task:
                - code: Code generation/modification
                - research: Information gathering/analysis
                - orchestration: Multi-step workflow coordination
            title: Short task title
            description: Detailed task description with context
            payload: Optional JSON payload with task-specific data
            priority: Priority 1-10 (higher = more important, default: 5)

        Returns:
            Task object with task_id, status (pending), assigned general.
        """
        body: dict = {
            "task_type": task_type,
            "title": title,
            "description": description,
            "priority": priority,
        }
        if payload:
            body["payload"] = payload
        return await _call("/api/generals/tasks", method="POST", json=body)

    @mcp.tool()
    async def get_task(task_id: int) -> dict:
        """
        Get task details by ID.

        Args:
            task_id: Task ID (integer)

        Returns:
            Full task object: type, status, assigned_to, created_at, result.
        """
        return await _call(f"/api/generals/tasks/{task_id}")

    @mcp.tool()
    async def list_tasks(
        task_type: Optional[str] = None,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """
        List tasks with optional filters.

        Args:
            task_type: Filter by type: code, research, orchestration
            status: Filter: pending, assigned, running, completed, failed, cancelled
            assigned_to: Filter by assigned general name
            limit: Max results (default 50)
            offset: Pagination offset

        Returns:
            List of tasks with summary info.
        """
        params: dict = {"limit": limit, "offset": offset}
        if task_type:
            params["task_type"] = task_type
        if status:
            params["status"] = status
        if assigned_to:
            params["assigned_to"] = assigned_to
        return await _call("/api/generals/tasks", params=params)

    @mcp.tool()
    async def cancel_task(task_id: int) -> dict:
        """
        Cancel a pending or assigned task.

        Only works for tasks not yet running. Running tasks must
        complete or fail on their own.

        Args:
            task_id: Task ID to cancel

        Returns:
            Confirmation with updated task status.
        """
        return await _call(f"/api/generals/tasks/{task_id}", method="DELETE")

    @mcp.tool()
    async def get_task_result(task_id: int) -> dict:
        """
        Get the execution result of a completed task.

        Args:
            task_id: Task ID

        Returns:
            Task result payload, execution time, and status.
        """
        return await _call(f"/api/generals/tasks/{task_id}/result")

    @mcp.tool()
    async def wait_for_task(
        task_id: int,
        timeout: int = 300,
        poll_interval: int = 2,
    ) -> dict:
        """
        Wait for a task to complete (blocking).

        Polls the task status until completed, failed, or timeout.

        Args:
            task_id: Task ID to wait for
            timeout: Max wait time in seconds (default: 300 = 5 min)
            poll_interval: Poll frequency in seconds (default: 2)

        Returns:
            Final task state with result or error details.
        """
        return await _call(
            f"/api/generals/tasks/{task_id}/wait",
            method="POST",
            json={"timeout": timeout, "poll_interval": poll_interval},
            timeout=timeout + 10,
        )

    # --- Shared Memory ---

    @mcp.tool()
    async def read_shared_memory(key: str) -> dict:
        """
        Read a value from the generals shared memory store.

        Shared memory allows generals to exchange data between tasks
        without direct coupling.

        Args:
            key: Memory key to read

        Returns:
            Stored value, or null if key does not exist.
        """
        return await _call(f"/api/generals/memory/{key}")

    @mcp.tool()
    async def write_shared_memory(
        key: str,
        value: Any,
        expires_at: Optional[str] = None,
    ) -> dict:
        """
        Write a value to the generals shared memory store.

        Args:
            key: Memory key
            value: Any JSON-serializable value
            expires_at: Optional expiration datetime (ISO 8601)

        Returns:
            Confirmation with key and stored timestamp.
        """
        body: dict = {"key": key, "value": value}
        if expires_at:
            body["expires_at"] = expires_at
        return await _call("/api/generals/memory", method="POST", json=body)

    # --- Activity & Stats ---

    @mcp.tool()
    async def get_generals_activity(
        general_name: Optional[str] = None,
        task_id: Optional[int] = None,
        activity_type: Optional[str] = None,
        limit: int = 50,
    ) -> dict:
        """
        Get the generals activity log.

        Shows what each general has been doing — task assignments,
        completions, failures, memory operations.

        Args:
            general_name: Filter by specific general
            task_id: Filter by task ID
            activity_type: Filter by activity type
            limit: Max entries (default 50)

        Returns:
            Activity log entries with timestamps and details.
        """
        params: dict = {"limit": limit}
        if general_name:
            params["general_name"] = general_name
        if task_id:
            params["task_id"] = str(task_id)
        if activity_type:
            params["activity_type"] = activity_type
        return await _call("/api/generals/activity", params=params)

    @mcp.tool()
    async def get_generals_stats() -> dict:
        """
        Get system-wide generals statistics.

        Returns aggregate metrics: total tasks, by status, memory usage,
        active generals, throughput rates.

        Returns:
            Stats: tasks (total/pending/running/completed/failed),
            memory (keys/size), activity (recent count).
        """
        return await _call("/api/generals/stats")
