"""
Distributed task queue with Celery-like interface.

Provides background task processing for:
- Scraping operations
- AI processing
- Data cleanup
- Report generation
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any

from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="task_queue")


class TaskStatus(Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority levels."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Task:
    """Task definition."""

    id: str
    name: str
    args: tuple
    kwargs: dict
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    scheduled_for: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3


class TaskHandler(ABC):
    """Abstract base class for task handlers."""

    def __init__(self, max_retries: int = 3, retry_delay: float = 5.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """Execute the task. Override in subclasses."""
        pass

    async def on_success(self, result: Any, task: Task) -> None:
        """Called when task succeeds. Override for custom handling."""
        pass

    async def on_failure(self, error: Exception, task: Task) -> None:
        """Called when task fails. Override for custom handling."""
        pass


class InMemoryTaskQueue:
    """In-memory task queue for development/single-node deployments."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._tasks: dict[str, Task] = {}
        self._handlers: dict[str, type[TaskHandler]] = {}
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._semaphore = asyncio.Semaphore(max_workers)
        self._lock = asyncio.Lock()

    def register_handler(self, name: str, handler_class: type[TaskHandler]) -> None:
        """Register a task handler."""
        self._handlers[name] = handler_class
        logger.info(f"Registered handler for task '{name}'", action=LogAction.UPDATE)

    async def start(self) -> None:
        """Start the task queue workers."""
        if self._running:
            return

        self._running = True

        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker_loop(), name=f"task_worker_{i}")
            self._workers.append(worker)

        logger.info(
            f"Task queue started with {self.max_workers} workers",
            action=LogAction.START,
        )

    async def stop(self) -> None:
        """Stop the task queue gracefully."""
        if not self._running:
            return

        self._running = False

        # Wait for all workers to finish current tasks
        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

        logger.info("Task queue stopped", action=LogAction.END)

    async def enqueue(
        self,
        name: str,
        *args,
        priority: TaskPriority = TaskPriority.NORMAL,
        delay: timedelta | None = None,
        max_retries: int = 3,
        **kwargs,
    ) -> str:
        """Add a task to the queue."""
        task_id = str(uuid.uuid4())
        scheduled_for = None

        if delay:
            scheduled_for = datetime.now() + delay

        task = Task(
            id=task_id,
            name=name,
            args=args,
            kwargs=kwargs,
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=datetime.now(),
            scheduled_for=scheduled_for,
            max_retries=max_retries,
        )

        async with self._lock:
            self._tasks[task_id] = task

        # Add to queue with priority (lower number = higher priority)
        await self._queue.put((-priority.value, task_id))

        logger.info(
            f"Task '{name}' enqueued",
            action=LogAction.START,
            metadata={
                "task_id": task_id,
                "priority": priority.name,
                "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
            },
        )

        return task_id

    async def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""
        return self._tasks.get(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                return True
            return False

    async def _worker_loop(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                # Wait for a task
                _, task_id = await self._queue.get()

                async with self._semaphore:
                    await self._process_task(task_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Worker error", action=LogAction.ERROR, metadata={"error": str(e)}
                )
                await asyncio.sleep(1)

    async def _process_task(self, task_id: str) -> None:
        """Process a single task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.status != TaskStatus.PENDING:
                return

            # Check scheduled time
            if task.scheduled_for and datetime.now() < task.scheduled_for:
                # Re-queue for later
                await self._queue.put((-task.priority.value, task_id))
                return

            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()

        handler_class = self._handlers.get(task.name)
        if not handler_class:
            logger.error(
                f"No handler for task '{task.name}'",
                action=LogAction.ERROR,
                metadata={"task_id": task_id},
            )
            task.status = TaskStatus.FAILURE
            task.error = f"No handler registered for '{task.name}'"
            return

        handler = handler_class()

        try:
            logger.info(
                f"Executing task '{task.name}'",
                action=LogAction.START,
                metadata={"task_id": task_id},
            )

            result = await handler.execute(*task.args, **task.kwargs)

            async with self._lock:
                task.result = result
                task.status = TaskStatus.SUCCESS
                task.completed_at = datetime.now()

            await handler.on_success(result, task)

            logger.info(
                f"Task '{task.name}' completed",
                action=LogAction.END,
                metadata={
                    "task_id": task_id,
                    "duration_ms": self._get_duration_ms(task),
                },
            )

        except Exception as e:
            async with self._lock:
                task.retry_count += 1

                if task.retry_count < task.max_retries:
                    task.status = TaskStatus.RETRY

                    # Re-queue with delay
                    await asyncio.sleep(handler.retry_delay * task.retry_count)
                    await self._queue.put((-task.priority.value, task_id))

                    logger.warning(
                        f"Task '{task.name}' failed, retrying",
                        action=LogAction.RETRY,
                        metadata={
                            "task_id": task_id,
                            "retry_count": task.retry_count,
                            "error": str(e),
                        },
                    )
                else:
                    task.status = TaskStatus.FAILURE
                    task.error = str(e)
                    task.completed_at = datetime.now()

                    logger.error(
                        f"Task '{task.name}' failed permanently",
                        action=LogAction.ERROR,
                        metadata={
                            "task_id": task_id,
                            "retries": task.retry_count,
                            "error": str(e),
                        },
                    )

            await handler.on_failure(e, task)

    def _get_duration_ms(self, task: Task) -> float:
        """Calculate task duration in milliseconds."""
        if task.started_at and task.completed_at:
            return (task.completed_at - task.started_at).total_seconds() * 1000
        return 0

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        statuses = {}
        for task in self._tasks.values():
            status = task.status.value
            statuses[status] = statuses.get(status, 0) + 1

        return {
            "total_tasks": len(self._tasks),
            "by_status": statuses,
            "max_workers": self.max_workers,
            "running": self._running,
        }


class TaskDecorator:
    """Decorator-based task registration."""

    def __init__(self, queue: InMemoryTaskQueue):
        self._queue = queue

    def __call__(
        self,
        name: str | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
    ):
        """Decorator for registering tasks."""

        def decorator(func: Callable) -> Callable:
            task_name = name or func.__name__

            # Create handler class
            class DynamicHandler(TaskHandler):
                async def execute(self, *args, **kwargs):
                    return await func(*args, **kwargs)

            DynamicHandler.max_retries = max_retries

            self._queue.register_handler(task_name, DynamicHandler)

            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await self._queue.enqueue(
                    task_name,
                    *args,
                    priority=priority,
                    max_retries=max_retries,
                    **kwargs,
                )

            # Attach direct execution method
            wrapper.run = func
            wrapper.delay = wrapper

            return wrapper

        return decorator


# Global queue instance
task_queue = InMemoryTaskQueue()
task = TaskDecorator(task_queue)


async def init_task_queue() -> None:
    """Initialize the global task queue."""
    await task_queue.start()


async def stop_task_queue() -> None:
    """Stop the global task queue."""
    await task_queue.stop()


# Common task handlers


class ScrapeTaskHandler(TaskHandler):
    """Handler for scraping tasks."""

    def __init__(self):
        super().__init__(max_retries=3, retry_delay=10.0)

    async def execute(self, url: str, **options) -> dict[str, Any]:
        """Execute scrape task."""
        from backend.scrapers.engine import ScrapingEngine

        engine = ScrapingEngine()
        return await engine.scrape(url, **options)


class AITaskHandler(TaskHandler):
    """Handler for AI processing tasks."""

    def __init__(self):
        super().__init__(max_retries=2, retry_delay=5.0)

    async def execute(self, content: str, task_type: str = "analyze") -> dict[str, Any]:
        """Execute AI task."""
        from backend.services.ai_engine import AIEngine

        engine = AIEngine()
        return await engine.process(content, task_type)


class CleanupTaskHandler(TaskHandler):
    """Handler for cleanup tasks."""

    async def execute(self, **options) -> dict[str, Any]:
        """Execute cleanup task."""
        from backend.db.cleanup import cleanup_old_data

        result = await cleanup_old_data(**options)
        return {"cleaned_records": result}


# Register default handlers
task_queue.register_handler("scrape", ScrapeTaskHandler)
task_queue.register_handler("ai_process", AITaskHandler)
task_queue.register_handler("cleanup", CleanupTaskHandler)


__all__ = [
    "TaskQueue",
    "Task",
    "TaskStatus",
    "TaskPriority",
    "TaskHandler",
    "InMemoryTaskQueue",
    "task_queue",
    "task",
    "init_task_queue",
    "stop_task_queue",
]
