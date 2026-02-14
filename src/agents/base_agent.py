"""
ИИ-Корпорация 2.0 — Base Agent
Базовый класс для всех агентов системы
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any

from loguru import logger

from src.core.model_router import ModelRouter, ModelResponse
from src.core.task_queue import TaskQueue


@dataclass
class AgentResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    agent_name: str = ""
    model_used: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    metadata: dict = field(default_factory=dict)


class BaseAgent(ABC):
    """Базовый класс для всех агентов"""

    def __init__(
        self,
        name: str,
        router: ModelRouter,
        task_queue: TaskQueue,
    ):
        self.name = name
        self.router = router
        self.task_queue = task_queue
        self._task_count = 0
        self._total_cost = 0.0

    @abstractmethod
    async def execute(
        self, instruction: str, **kwargs
    ) -> AgentResult:
        """Основной метод выполнения задачи"""
        pass

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """Список возможностей агента"""
        pass

    async def _generate(
        self,
        prompt: str,
        system_prompt: str = "",
        task_type: str = "general",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> ModelResponse:
        """Обёртка для генерации через роутер"""
        response = await self.router.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            task_type=task_type,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        self._task_count += 1
        self._total_cost += response.cost_usd
        return response

    def _build_result(
        self,
        success: bool,
        data: Any = None,
        error: str = None,
        response: ModelResponse = None,
        **metadata,
    ) -> AgentResult:
        """Построение стандартного результата"""
        return AgentResult(
            success=success,
            data=data,
            error=error,
            agent_name=self.name,
            model_used=response.model_used if response else "",
            tokens_used=(
                (response.tokens_in + response.tokens_out)
                if response else 0
            ),
            cost_usd=response.cost_usd if response else 0.0,
            metadata=metadata,
        )

    def get_stats(self) -> dict:
        """Статистика агента"""
        return {
            "agent": self.name,
            "tasks_completed": self._task_count,
            "total_cost": round(self._total_cost, 4),
        }
