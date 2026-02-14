"""
ИИ-Корпорация 2.0 — Main Entry Point
Запуск всей системы
"""
import asyncio
import uvicorn
from loguru import logger

from src.core.config import settings
from src.core.gpu_manager import GPUManager
from src.core.model_router import ModelRouter
from src.core.task_queue import TaskQueue
from src.agents.ceo_agent import CEOAgent
from src.agents.content_agent import ContentAgent
from src.agents.devops_agent import DevOpsAgent
from src.interfaces.telegram_bot import TelegramInterface
from src.interfaces.api_gateway import create_api


async def main():
    """Точка входа ИИ-Корпорации 2.0"""

    # Настройка логирования
    logger.add(
        f"{settings.logs_dir}/ai_corp_{{time}}.log",
        rotation="100 MB",
        retention="30 days",
        level="INFO",
    )

    logger.info("=" * 60)
    logger.info("🤖 ИИ-Корпорация 2.0 — Запуск")
    logger.info("=" * 60)

    # 1. Инициализация ядра
    gpu_manager = GPUManager()
    model_router = ModelRouter(gpu_manager)
    task_queue = TaskQueue()

    # 2. Запуск очереди задач
    await task_queue.start(num_workers=settings.max_concurrent_tasks)

    # 3. Инициализация агентов
    content_agent = ContentAgent(model_router, task_queue)
    devops_agent = DevOpsAgent(model_router, task_queue)

    ceo = CEOAgent(model_router, task_queue)
    ceo.register_agent("content_agent", content_agent)
    ceo.register_agent("devops_agent", devops_agent)

    # 4. Запуск интерфейсов
    telegram = TelegramInterface(ceo)
    api_app = create_api(ceo)

    logger.info("✅ All components initialized")

    # Проверяем GPU
    gpu_status = await gpu_manager.get_status()
    logger.info(
        f"🖥 GPU: {gpu_status.free_vram_gb:.1f}GB free / "
        f"{gpu_status.total_vram_gb:.1f}GB total"
    )

    # Запускаем все сервисы параллельно
    try:
        await asyncio.gather(
            # Telegram Bot
            telegram.start(),

            # FastAPI в отдельном потоке
            asyncio.to_thread(
                uvicorn.run,
                api_app,
                host="0.0.0.0",
                port=8000,
                log_level="info",
            ),
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await task_queue.stop()
        await telegram.stop()
        logger.info("🛑 ИИ-Корпорация 2.0 остановлена")


if __name__ == "__main__":
    asyncio.run(main())
