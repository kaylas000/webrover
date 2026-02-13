"""
Task Queue - управление очередью задач
"""

import asyncio
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import time
from loguru import logger
import redis.asyncio as redis
import json


class TaskPriority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    id: str
    type: str
    priority: TaskPriority
    complexity: float
    payload: Dict
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)


class TaskQueue:
    """Очередь задач с приоритетами"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", max_concurrent_tasks: int = 3):
        self.redis_url = redis_url
        self.max_concurrent_tasks = max_concurrent_tasks
        self.redis_client: Optional[redis.Redis] = None
        self.queue: List[Task] = []
        logger.info(f"Task Queue initialized (max concurrent: {max_concurrent_tasks})")
    
    async def connect(self):
        """Подключиться к Redis"""
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
            logger.success("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
    
    async def disconnect(self):
        """Отключиться от Redis"""
        if self.redis_client:
            await self.redis_client.close()
    
    async def add_task(self, task_id: str, task_type: str, priority: TaskPriority, complexity: float, payload: Dict):
        """Добавить задачу в очередь"""
        task = Task(id=task_id, type=task_type, priority=priority, complexity=complexity, payload=payload)
        insert_pos = 0
        for i, queued_task in enumerate(self.queue):
            if queued_task.priority.value > task.priority.value:
                insert_pos = i
                break
        self.queue.insert(insert_pos, task)
        logger.info(f"Task {task_id} added to queue")
    
    async def process_queue(self, task_handler: Callable):
        """Обработать очередь задач"""
        logger.info("Starting task queue processing...")
        while True:
            if self.queue:
                task = self.queue.pop(0)
                task.status = TaskStatus.RUNNING
                try:
                    result = await task_handler(task)
                    logger.success(f"Task {task.id} completed")
                except Exception as e:
                    logger.error(f"Task {task.id} failed: {e}")
            await asyncio.sleep(0.1)
