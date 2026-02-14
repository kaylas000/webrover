"""
ИИ-Корпорация 2.0 — DevOps Agent
Генерация кода, тесты, code review, документация
"""
import re

from loguru import logger

from src.agents.base_agent import BaseAgent, AgentResult
from src.core.model_router import ModelRouter
from src.core.task_queue import TaskQueue


class DevOpsAgent(BaseAgent):
    """Агент для разработки кода и DevOps задач"""

    CODE_SYSTEM_PROMPT = """Ты — senior разработчик с 10+ лет опыта.
Генерируй production-ready код с:
- Типизацией (type hints для Python, TypeScript для JS)
- Обработкой ошибок (try/except, error boundaries)
- Docstrings и комментариями
- Следованием best practices и SOLID принципам
Формат: код в блоках markdown. После кода — описание решений."""

    TEST_SYSTEM_PROMPT = """Ты — QA-инженер. Пиши unit-тесты с:
- Покрытием основных сценариев (happy path)
- Граничных случаев (edge cases)
- Негативных сценариев (error handling)
- Используй pytest для Python, Jest для JS
- Применяй fixtures и моки где нужно"""

    REVIEW_SYSTEM_PROMPT = """Ты — senior code reviewer. Проверяй код на:
1. Баги и потенциальные ошибки
2. Безопасность (SQL injection, XSS, etc.)
3. Производительность
4. Читаемость и maintainability
5. Соответствие best practices
Формат: Critical/Warning/Good + Score X/10"""

    def __init__(self, router: ModelRouter, task_queue: TaskQueue):
        super().__init__("DevOpsAgent", router, task_queue)

    def get_capabilities(self) -> list[str]:
        return ["generate_code", "write_tests", "code_review",
                "write_docs", "explain_code", "refactor"]

    async def execute(self, instruction: str, action: str = "generate_code", **kwargs) -> AgentResult:
        actions = {
            "generate_code": self._generate_code,
            "write_tests": self._write_tests,
            "code_review": self._code_review,
            "write_docs": self._write_docs,
            "explain_code": self._explain_code,
            "refactor": self._refactor,
        }
        handler = actions.get(action, self._generate_code)
        return await handler(instruction, **kwargs)

    async def _generate_code(self, instruction: str, **kwargs) -> AgentResult:
        language = kwargs.get("language", "python")
        framework = kwargs.get("framework", "")
        fw = f"Фреймворк: {framework}" if framework else ""
        prompt = f"Задача: {instruction}
Язык: {language}
{fw}
Требования: production-ready, обработка ошибок, типизация"
        try:
            response = await self._generate(prompt=prompt, system_prompt=self.CODE_SYSTEM_PROMPT, task_type="coding", max_tokens=4096, temperature=0.3)
            code_blocks = self._extract_code_blocks(response.text)
            return self._build_result(success=True, data={"full_response": response.text, "code_blocks": code_blocks, "language": language}, response=response)
        except Exception as e:
            return self._build_result(success=False, error=str(e))

    async def _write_tests(self, instruction: str, **kwargs) -> AgentResult:
        prompt = f"Напиши unit-тесты для:
{instruction}
Минимум 5 тестов: happy path + edge cases + error cases"
        try:
            response = await self._generate(prompt=prompt, system_prompt=self.TEST_SYSTEM_PROMPT, task_type="coding", max_tokens=4096, temperature=0.3)
            code_blocks = self._extract_code_blocks(response.text)
            return self._build_result(success=True, data={"full_response": response.text, "test_code": code_blocks}, response=response)
        except Exception as e:
            return self._build_result(success=False, error=str(e))

    async def _code_review(self, instruction: str, **kwargs) -> AgentResult:
        prompt = f"Проведи code review:

{instruction}"
        try:
            response = await self._generate(prompt=prompt, system_prompt=self.REVIEW_SYSTEM_PROMPT, task_type="analysis", max_tokens=2048, temperature=0.3)
            score = self._extract_score(response.text)
            return self._build_result(success=True, data={"review": response.text, "score": score}, response=response)
        except Exception as e:
            return self._build_result(success=False, error=str(e))

    async def _write_docs(self, instruction: str, **kwargs) -> AgentResult:
        doc_type = kwargs.get("doc_type", "readme")
        prompt = f"Напиши {doc_type} документацию для:
{instruction}"
        try:
            response = await self._generate(prompt=prompt, system_prompt="Ты — технический писатель. Пиши документацию в Markdown.", task_type="content", max_tokens=4096, temperature=0.5)
            return self._build_result(success=True, data=response.text, response=response, doc_type=doc_type)
        except Exception as e:
            return self._build_result(success=False, error=str(e))

    async def _explain_code(self, instruction: str, **kwargs) -> AgentResult:
        prompt = f"Объясни этот код подробно:
{instruction}
Включи: назначение, разбор по блокам, сложность Big O, проблемы"
        try:
            response = await self._generate(prompt=prompt, system_prompt="Ты — senior разработчик-ментор. Объясняй код понятно.", task_type="analysis", temperature=0.5)
            return self._build_result(success=True, data=response.text, response=response)
        except Exception as e:
            return self._build_result(success=False, error=str(e))

    async def _refactor(self, instruction: str, **kwargs) -> AgentResult:
        prompt = f"Отрефактори этот код:
{instruction}
Применяй SOLID, DRY, улучши читаемость. Покажи результат и объясни изменения."
        try:
            response = await self._generate(prompt=prompt, system_prompt=self.CODE_SYSTEM_PROMPT, task_type="coding", max_tokens=4096, temperature=0.3)
            code_blocks = self._extract_code_blocks(response.text)
            return self._build_result(success=True, data={"full_response": response.text, "refactored_code": code_blocks}, response=response)
        except Exception as e:
            return self._build_result(success=False, error=str(e))

    @staticmethod
    def _extract_code_blocks(text: str) -> list[dict]:
        pattern = r"```(\w*)
(.*?)```"
        matches = re.finditer(pattern, text, re.DOTALL)
        return [{"language": m.group(1) or "text", "code": m.group(2).strip()} for m in matches]

    @staticmethod
    def _extract_score(text: str) -> int:
        match = re.search(r"(\d+)\s*/\s*10", text)
        return int(match.group(1)) if match else 0
