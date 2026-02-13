"""
Main entry point for AI Corporation
"""

import asyncio
import sys
from loguru import logger

from .core.model_router import ModelRouter
from .core.task_queue import TaskQueue
from .agents.ceo_agent import CEOAgent


class AICorporation:
    """Основной класс ИИ-Корпорации"""
    
    def __init__(self):
        self.model_router = None
        self.task_queue = None
        self.ceo_agent = None
        self.shutdown_event = asyncio.Event()
        
        logger.info("AI Corporation initializing...")
    
    async def initialize(self):
        """Инициализация всех компонентов"""
        logger.info("Initializing Model Router...")
        self.model_router = ModelRouter()
        
        logger.info("Initializing Task Queue...")
        self.task_queue = TaskQueue(
            redis_url="redis://redis:6379",
            max_concurrent_tasks=3
        )
        await self.task_queue.connect()
        
        logger.info("Initializing CEO Agent...")
        self.ceo_agent = CEOAgent(
            model_router=self.model_router,
            task_queue=self.task_queue
        )
        
        logger.success("AI Corporation initialized successfully!")
    
    async def start(self):
        """Запуск всех сервисов"""
        logger.info("Starting AI Corporation services...")
        
        queue_task = asyncio.create_task(
            self.task_queue.process_queue(self._task_handler)
        )
        
        try:
            await self.shutdown_event.wait()
        except KeyboardInterrupt:
            logger.info("Shutdown signal received...")
        finally:
            await self.stop()
            queue_task.cancel()
    
    async def _task_handler(self, task):
        """Обработчик задач"""
        logger.info(f"Processing task: {task.id}")
        return {"status": "completed", "result": "Task processed"}
    
    async def stop(self):
        """Остановка всех сервисов"""
        logger.info("Stopping AI Corporation services...")
        if self.task_queue:
            await self.task_queue.disconnect()
        logger.success("AI Corporation stopped successfully!")


def main():
    """Точка входа"""
    corporation = AICorporation()
    asyncio.run(corporation.initialize())
    asyncio.run(corporation.start())


if __name__ == "__main__":
    main()
