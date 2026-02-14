"""
ИИ-Корпорация 2.0 — Task Queue
Асинхронная приоритетная очередь задач с retry логикой
"""
import asyncio
import uuid
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional
from enum import Enum

from loguru import logger

from src.core.config import settings, Priority


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class Task:
    id: str
    name: str
    priority: Priority
    handler: Callable[..., Coroutine]
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retries: int = 0
    max_retries: int = 3
    timeout: int = 600
    callback: Optional[Callable] = None

    def __lt__(self, other: "Task") -> bool:
        """Для PriorityQueue: по приоритету, затем по времени"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at

    @property
    def duration(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return time.time() - self.started_at
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority.name,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
            "retries": self.retries,
            "error": self.error,
        }


class TaskQueue:
    """Асинхронная приоритетная очередь задач"""

    def __init__(self, max_concurrent: int = None):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._max_concurrent = (
            max_concurrent or settings.max_concurrent_tasks
        )
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._tasks: dict[str, Task] = {}
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._stats = {
            "total_submitted": 0,
            "total_completed": 0,
            "total_failed": 0,
        }

    async def start(self, num_workers: int = None):
        """Запуск воркеров очереди"""
        num_workers = num_workers or self._max_concurrent
        self._running = True

        for i in range(num_workers):
            worker = asyncio.create_task(
                self._worker(f"worker-{i}")
            )
            self._workers.append(worker)

        logger.info(f"TaskQueue started with {num_workers} workers")

    async def stop(self):
        """Остановка очереди"""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(
            *self._workers, return_exceptions=True
        )
        self._workers.clear()
        logger.info("TaskQueue stopped")

    async def submit(
        self,
        name: str,
        handler: Callable[..., Coroutine],
        *args,
        priority: Priority = Priority.MEDIUM,
        timeout: int = None,
        callback: Optional[Callable] = None,
        **kwargs,
    ) -> str:
        """Добавление задачи в очередь"""
        task_id = str(uuid.uuid4())[:8]

        task = Task(
            id=task_id,
            name=name,
            priority=priority,
            handler=handler,
            args=args,
            kwargs=kwargs,
            timeout=timeout or settings.task_timeout_seconds,
            max_retries=settings.max_retries,
            callback=callback,
        )

        self._tasks[task_id] = task
        await self._queue.put(task)
        self._stats["total_submitted"] += 1

        logger.info(
            f"Task submitted: {task_id} '{name}' "
            f"[{priority.name}] "
            f"(queue size: {self._queue.qsize()})"
        )
        return task_id

    async def _worker(self, worker_name: str):
        """Воркер, обрабатывающий задачи"""
        logger.debug(f"{worker_name} started")

        while self._running:
            try:
                task: Task = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0,
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            async with self._semaphore:
                await self._execute_task(task, worker_name)

    async def _execute_task(self, task: Task, worker_name: str):
        """Выполнение одной задачи"""
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        logger.info(
            f"[{worker_name}] Executing: {task.id} '{task.name}'"
        )

        try:
            task.result = await asyncio.wait_for(
                task.handler(*task.args, **task.kwargs),
                timeout=task.timeout,
            )
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            self._stats["total_completed"] += 1

            logger.info(
                f"[{worker_name}] Completed: {task.id} "
                f"({task.duration:.1f}s)"
            )

            # Callback если есть
            if task.callback:
                try:
                    await task.callback(task)
                except Exception as e:
                    logger.error(
                        f"Callback error for {task.id}: {e}"
                    )

        except asyncio.TimeoutError:
            task.status = TaskStatus.FAILED
            task.error = f"Timeout after {task.timeout}s"
            task.completed_at = time.time()
            self._stats["total_failed"] += 1
            logger.error(f"[{worker_name}] Timeout: {task.id}")

        except Exception as e:
            logger.error(
                f"[{worker_name}] Error: {task.id}: {e}"
            )

            # Retry логика с exponential backoff
            if task.retries < task.max_retries:
                task.retries += 1
                task.status = TaskStatus.RETRYING
                logger.info(
                    f"Retrying {task.id} "
                    f"(attempt {task.retries}/{task.max_retries})"
                )
                await asyncio.sleep(2 ** task.retries)
                await self._queue.put(task)
            else:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = time.time()
                self._stats["total_failed"] += 1

    def get_task(self, task_id: str) -> Optional[Task]:
        """Получение задачи по ID"""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[dict]:
        """Список всех задач"""
        return [t.to_dict() for t in self._tasks.values()]

    def get_stats(self) -> dict:
        """Статистика очереди"""
        active = sum(
            1 for t in self._tasks.values()
            if t.status == TaskStatus.RUNNING
        )
        pending = sum(
            1 for t in self._tasks.values()
            if t.status == TaskStatus.PENDING
        )
        return {
            **self._stats,
            "active_tasks": active,
            "pending_tasks": pending,
            "queue_size": self._queue.qsize(),
        }
