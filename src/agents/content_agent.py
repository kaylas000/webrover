"""
ИИ-Корпорация 2.0 — Content Agent
Генерация статей, перевод, суммаризация, SEO-оптимизация
"""
from loguru import logger

from src.agents.base_agent import BaseAgent, AgentResult
from src.core.model_router import ModelRouter
from src.core.task_queue import TaskQueue


class ContentAgent(BaseAgent):
    """Агент для создания и обработки контента"""

    ARTICLE_SYSTEM_PROMPT = """Ты — профессиональный копирайтер и SEO-специалист.
Пиши структурированные, информативные статьи с:
- Цепляющим заголовком H1
- Логичной структурой с подзаголовками H2/H3
- SEO-оптимизацией (ключевые слова 1-3% плотность)
- Практическими примерами и советами
- Заключением с call-to-action
Формат: Markdown. Язык: по запросу пользователя."""

    TRANSLATION_SYSTEM_PROMPT = """Ты — профессиональный переводчик.
Переводи точно, сохраняя:
- Смысл и тон оригинала
- Форматирование (заголовки, списки, выделение)
- Специальную терминологию
- Естественность на целевом языке
НЕ добавляй пояснений. Просто переведи текст."""

    SUMMARY_SYSTEM_PROMPT = """Ты — аналитик контента.
Создай структурированное резюме:
- Основные тезисы (3-5 пунктов)
- Ключевые выводы
- Важные цифры и факты
Будь кратким, но информативным."""

    def __init__(
        self, router: ModelRouter, task_queue: TaskQueue
    ):
        super().__init__("ContentAgent", router, task_queue)

    def get_capabilities(self) -> list[str]:
        return [
            "write_article",
            "translate",
            "summarize",
            "seo_optimize",
            "rewrite",
        ]

    async def execute(
        self,
        instruction: str,
        action: str = "write_article",
        **kwargs,
    ) -> AgentResult:
        """Диспетчер действий"""
        actions = {
            "write_article": self._write_article,
            "translate": self._translate,
            "summarize": self._summarize,
            "seo_optimize": self._seo_optimize,
            "rewrite": self._rewrite,
        }

        handler = actions.get(action, self._write_article)
        return await handler(instruction, **kwargs)

    async def _write_article(
        self, instruction: str, **kwargs
    ) -> AgentResult:
        """Генерация SEO-статьи"""
        word_count = kwargs.get("word_count", 2000)

        prompt = f"""Напиши статью по следующему заданию:
{instruction}

Требования:
- Объём: ~{word_count} слов
- Формат: Markdown
- Включи мета-описание в начале (meta_description: ...)
- Минимум 5 подзаголовков H2
- Используй списки и примеры
- Добавь заключение"""

        try:
            response = await self._generate(
                prompt=prompt,
                system_prompt=self.ARTICLE_SYSTEM_PROMPT,
                task_type="content",
                max_tokens=min(word_count * 3, 8192),
                temperature=0.7,
            )

            actual_words = len(response.text.split())

            return self._build_result(
                success=True,
                data=response.text,
                response=response,
                word_count=actual_words,
                requested_words=word_count,
            )
        except Exception as e:
            logger.error(
                f"ContentAgent: Article generation failed: {e}"
            )
            return self._build_result(
                success=False, error=str(e)
            )

    async def _translate(
        self, instruction: str, **kwargs
    ) -> AgentResult:
        """Перевод текста"""
        target_lang = kwargs.get("target_lang", "en")
        source_lang = kwargs.get("source_lang", "auto")

        prompt = f"Переведи следующий текст на {target_lang}:\n\n{instruction}"

        if source_lang != "auto":
            prompt = (
                f"Исходный язык: {source_lang}\n" + prompt
            )

        try:
            response = await self._generate(
                prompt=prompt,
                system_prompt=self.TRANSLATION_SYSTEM_PROMPT,
                task_type="translation",
                temperature=0.3,
            )
            return self._build_result(
                success=True,
                data=response.text,
                response=response,
                target_lang=target_lang,
            )
        except Exception as e:
            return self._build_result(
                success=False, error=str(e)
            )

    async def _summarize(
        self, instruction: str, **kwargs
    ) -> AgentResult:
        """Суммаризация текста"""
        max_length = kwargs.get("max_length", 500)

        prompt = (
            f"Суммаризуй текст "
            f"(максимум {max_length} слов):\n\n"
            f"{instruction}"
        )

        try:
            response = await self._generate(
                prompt=prompt,
                system_prompt=self.SUMMARY_SYSTEM_PROMPT,
                task_type="general",
                max_tokens=max_length * 2,
                temperature=0.3,
            )
            return self._build_result(
                success=True,
                data=response.text,
                response=response,
            )
        except Exception as e:
            return self._build_result(
                success=False, error=str(e)
            )

    async def _seo_optimize(
        self, instruction: str, **kwargs
    ) -> AgentResult:
        """SEO-оптимизация текста"""
        keywords = kwargs.get("keywords", [])
        keywords_str = (
            ", ".join(keywords)
            if keywords
            else "определи самостоятельно"
        )

        prompt = f"""Оптимизируй статью для SEO:

Ключевые слова: {keywords_str}

Текст:
{instruction}

Задачи:
1. Оптимизируй заголовок H1 (включи ключевое слово)
2. Добавь мета-описание (150-160 символов)
3. Проверь плотность ключевых слов (1-3%)
4. Улучши подзаголовки H2/H3
5. Добавь внутренние ссылки (placeholder)
6. Верни оптимизированный текст в Markdown"""

        try:
            response = await self._generate(
                prompt=prompt,
                system_prompt=self.ARTICLE_SYSTEM_PROMPT,
                task_type="content",
                max_tokens=8192,
                temperature=0.5,
            )
            return self._build_result(
                success=True,
                data=response.text,
                response=response,
                keywords=keywords,
            )
        except Exception as e:
            return self._build_result(
                success=False, error=str(e)
            )

    async def _rewrite(
        self, instruction: str, **kwargs
    ) -> AgentResult:
        """Рерайт текста"""
        style = kwargs.get("style", "professional")

        prompt = (
            f"Перепиши текст в стиле: {style}. "
            f"Сохрани смысл, но измени структуру и "
            f"формулировки.\n\nТекст:\n{instruction}"
        )

        try:
            response = await self._generate(
                prompt=prompt,
                system_prompt=(
                    "Ты — профессиональный редактор. "
                    "Перепиши текст, сохраняя смысл."
                ),
                task_type="content",
                temperature=0.8,
            )
            return self._build_result(
                success=True,
                data=response.text,
                response=response,
                style=style,
            )
        except Exception as e:
            return self._build_result(
                success=False, error=str(e)
            )
