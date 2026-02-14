"""
ИИ-Корпорация 2.0 — CEO Agent
Центральный координатор: принимает миссии, разбивает на подзадачи
"""
import asyncio
import json
import re
from typing import Optional

from loguru import logger

from src.agents.base_agent import BaseAgent, AgentResult
from src.core.model_router import ModelRouter
from src.core.task_queue import TaskQueue


class CEOAgent(BaseAgent):
    """CEO Agent — координатор всей системы"""

    PLANNING_SYSTEM_PROMPT = """Ты — CEO AI-корпорации. Твоя задача:
1. Проанализировать миссию пользователя
2. Разбить её на конкретные подзадачи
3. Назначить каждую подзадачу подходящему агенту
4. Определить приоритет и порядок выполнения

Доступные агенты:
- content_agent: написание статей, SEO-оптимизация, перевод, парсинг
- devops_agent: генерация кода, тесты, code review, документация

Ответь СТРОГО в формате JSON:
{
    "mission_analysis": "краткий анализ миссии",
    "subtasks": [
        {
            "id": 1,
            "agent": "content_agent",
            "action": "write_article",
            "instruction": "конкретная инструкция для агента",
            "priority": "high",
            "depends_on": []
        }
    ],
    "estimated_time_minutes": 10,
    "estimated_cost_usd": 0.5
}"""

    REPORT_SYSTEM_PROMPT = """Ты — CEO AI-корпорации.
Составь краткий отчёт о выполненной миссии на основе результатов.
Формат: понятный для человека, с ключевыми метриками."""

    def __init__(
        self,
        router: ModelRouter,
        task_queue: TaskQueue,
        agents: dict[str, BaseAgent] = None,
    ):
        super().__init__("CEO", router, task_queue)
        self.agents: dict[str, BaseAgent] = agents or {}

    def register_agent(self, name: str, agent: BaseAgent):
        """Регистрация специализированного агента"""
        self.agents[name] = agent
        logger.info(f"CEO: Agent '{name}' registered")

    def get_capabilities(self) -> list[str]:
        return [
            "mission_planning",
            "task_decomposition",
            "agent_coordination",
            "progress_reporting",
            "resource_optimization",
        ]

    async def execute(
        self,
        instruction: str,
        callback=None,
        **kwargs,
    ) -> AgentResult:
        """Принимает миссию и координирует выполнение"""
        logger.info(
            f"CEO: New mission received: {instruction[:100]}..."
        )

        # Шаг 1: Планирование
        plan = await self._create_plan(instruction)
        if not plan:
            return self._build_result(
                success=False,
                error="Failed to create execution plan",
            )

        if callback:
            await callback(
                f"📋 План готов: {len(plan['subtasks'])} подзадач"
            )

        # Шаг 2: Выполнение подзадач
        results = await self._execute_plan(plan, callback)

        # Шаг 3: Сборка отчёта
        report = await self._create_report(
            instruction, plan, results
        )

        total_cost = sum(
            r.cost_usd for r in results.values() if r
        )
        total_tokens = sum(
            r.tokens_used for r in results.values() if r
        )

        all_success = all(
            r and r.success for r in results.values()
        )

        return self._build_result(
            success=all_success,
            data={
                "report": report,
                "plan": plan,
                "subtask_results": {
                    k: {
                        "success": v.success if v else False,
                        "data_preview": (
                            str(v.data)[:500]
                            if v and v.data else None
                        ),
                        "error": v.error if v else "Not executed",
                    }
                    for k, v in results.items()
                },
                "total_cost": total_cost,
                "total_tokens": total_tokens,
            },
            cost_usd=total_cost,
        )

    async def _create_plan(
        self, mission: str
    ) -> Optional[dict]:
        """Создание плана выполнения миссии"""
        try:
            response = await self._generate(
                prompt=f"Миссия: {mission}",
                system_prompt=self.PLANNING_SYSTEM_PROMPT,
                task_type="architecture",
                temperature=0.3,
            )

            plan = self._extract_json(response.text)
            if plan and "subtasks" in plan:
                logger.info(
                    f"CEO: Plan created with "
                    f"{len(plan['subtasks'])} subtasks"
                )
                return plan

            logger.error(
                f"CEO: Invalid plan format: "
                f"{response.text[:200]}"
            )
            return None

        except Exception as e:
            logger.error(f"CEO: Planning failed: {e}")
            return None

    async def _execute_plan(
        self,
        plan: dict,
        callback=None,
    ) -> dict[str, Optional[AgentResult]]:
        """Выполнение плана с учётом зависимостей"""
        results: dict[str, Optional[AgentResult]] = {}
        completed_ids: set[int] = set()
        subtasks = plan.get("subtasks", [])

        while len(completed_ids) < len(subtasks):
            # Задачи, чьи зависимости выполнены
            ready_tasks = [
                st for st in subtasks
                if st["id"] not in completed_ids
                and all(
                    dep in completed_ids
                    for dep in st.get("depends_on", [])
                )
            ]

            if not ready_tasks:
                logger.warning("CEO: Deadlock detected, breaking")
                break

            # Запускаем готовые задачи параллельно
            coros = [
                self._execute_subtask(st, results)
                for st in ready_tasks
            ]
            batch_results = await asyncio.gather(
                *coros, return_exceptions=True
            )

            for st, result in zip(ready_tasks, batch_results):
                task_key = f"task_{st['id']}"

                if isinstance(result, Exception):
                    logger.error(
                        f"CEO: Subtask {st['id']} failed: {result}"
                    )
                    results[task_key] = AgentResult(
                        success=False,
                        error=str(result),
                        agent_name=st.get("agent", "unknown"),
                    )
                else:
                    results[task_key] = result

                completed_ids.add(st["id"])

                if callback:
                    is_ok = (
                        result
                        and not isinstance(result, Exception)
                        and result.success
                    )
                    status = "✅" if is_ok else "❌"
                    action = st.get("action", "unknown")
                    await callback(
                        f"{status} Подзадача {st['id']}: {action}"
                    )

        return results

    async def _execute_subtask(
        self,
        subtask: dict,
        previous_results: dict,
    ) -> AgentResult:
        """Выполнение одной подзадачи"""
        agent_name = subtask.get("agent", "")
        action = subtask.get("action", "")
        instruction = subtask.get("instruction", "")

        agent = self.agents.get(agent_name)
        if not agent:
            return AgentResult(
                success=False,
                error=f"Agent '{agent_name}' not found",
                agent_name=agent_name,
            )

        logger.info(
            f"CEO: Dispatching to {agent_name}: "
            f"{action} - {instruction[:80]}..."
        )

        # Контекст из предыдущих задач
        context = ""
        for dep_id in subtask.get("depends_on", []):
            dep_key = f"task_{dep_id}"
            dep_result = previous_results.get(dep_key)
            if dep_result and dep_result.success and dep_result.data:
                context += (
                    f"\nРезультат задачи {dep_id}: "
                    f"{str(dep_result.data)[:1000]}"
                )

        full_instruction = instruction
        if context:
            full_instruction += (
                f"\n\nКонтекст из предыдущих задач:{context}"
            )

        return await agent.execute(
            instruction=full_instruction,
            action=action,
        )

    async def _create_report(
        self,
        mission: str,
        plan: dict,
        results: dict,
    ) -> str:
        """Создание итогового отчёта"""
        try:
            results_summary = "\n".join(
                f"- {key}: "
                f"{'✅ Успешно' if (v and v.success) else '❌ Ошибка'}"
                + (f" ({v.error})" if v and v.error else "")
                for key, v in results.items()
            )

            plan_json = json.dumps(
                plan, ensure_ascii=False
            )[:1000]

            response = await self._generate(
                prompt=(
                    f"Миссия: {mission}\n"
                    f"План: {plan_json}\n"
                    f"Результаты:\n{results_summary}"
                ),
                system_prompt=self.REPORT_SYSTEM_PROMPT,
                task_type="general",
                temperature=0.5,
                max_tokens=1024,
            )
            return response.text

        except Exception as e:
            logger.error(
                f"CEO: Report generation failed: {e}"
            )
            return (
                f"Миссия выполнена. "
                f"Результаты: {len(results)} подзадач обработано."
            )

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        """Извлечение JSON из текста модели"""
        patterns = [
            r'```json\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
            r'(\{.*\})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
