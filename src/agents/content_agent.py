"""
Content Agent - агенты для работы с контентом
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from loguru import logger
from datetime import datetime
import re
import hashlib

from ..core.model_router import ModelRouter
from ..tools.parser import ContentParser
from ..tools.translator import TextTranslator
from ..tools.seo_optimizer import SEOOptimizer
from ..utils.decorators import measure_time, retry, cache_result, timeout


class ContentAgent:
    """Агент для создания и обработки контента"""
    
    def __init__(self, model_router: ModelRouter):
        self.model_router = model_router
        
        # Инициализируем инструменты
        self.parser = ContentParser()
        self.translator = TextTranslator(model_router)
        self.seo_optimizer = SEOOptimizer(model_router)
        
        # Кэш для структур статей
        self._structure_cache = {}
        self._structure_cache_timestamps = {}
        
        logger.info("Content Agent initialized")
    
    @measure_time
    @cache_result(maxsize=100, ttl=3600)
    async def generate_article(
        self,
        topic: str,
        keywords: List[str],
        target_length: int = 2000,
        language: str = "ru",
        style: str = "professional"
    ) -> Dict:
        """
        Сгенерировать статью
        
        Args:            topic: Тема статьи
            keywords: Ключевые слова
            target_length: Целевая длина (слов)
            language: Язык (ru, en, etc.)
            style: Стиль (professional, casual, technical)
        
        Returns:
            Dict с результатами
        """
        
        logger.info(f"Generating article: {topic[:100]}...")
        logger.info(f"Keywords: {keywords}, Length: {target_length}")
        
        start_time = datetime.now()
        
        try:
            # Шаг 1: Создаем структуру статьи
            structure = await self._create_article_structure(topic, keywords, style)
            
            if not structure:
                raise ValueError("Failed to create article structure")
            
            # Шаг 2: Генерируем контент для каждого раздела
            sections = await self._generate_sections(structure, language)
            
            if not sections:
                raise ValueError("Failed to generate sections")
            
            # Шаг 3: Собираем статью
            article = self._assemble_article(sections, topic, keywords)
            
            # Шаг 4: Применяем SEO оптимизацию
            optimized_article = await self.seo_optimizer.optimize(
                article,
                keywords,
                target_length
            )
            
            # Шаг 5: Переводим если нужно
            if language != "ru":
                optimized_article = await self.translator.translate(
                    optimized_article,
                    target_lang=language
                )
            
            elapsed_time = (datetime.now() - start_time).total_seconds()
            
            logger.success(f"Article generated successfully in {elapsed_time:.1f}s")
            
            return {                "status": "success",
                "topic": topic,
                "content": optimized_article,
                "word_count": len(optimized_article.split()),
                "keywords_used": keywords,
                "generation_time": elapsed_time,
                "sections": len(sections),
                "language": language,
                "style": style
            }
            
        except Exception as e:
            logger.error(f"Error generating article: {e}")
            return {
                "status": "error",
                "error": str(e),
                "topic": topic
            }
    
    @cache_result(maxsize=50, ttl=7200)
    async def _create_article_structure(
        self,
        topic: str,
        keywords: List[str],
        style: str
    ) -> Optional[Dict]:
        """Создать структуру статьи с кэшированием"""
        
        # Создаем ключ кэша
        cache_key = hashlib.md5(
            f"{topic}:{",".join(keywords)}:{style}".encode()
        ).hexdigest()
        
        # Проверяем кэш
        if cache_key in self._structure_cache:
            logger.info("Using cached article structure")
            return self._structure_cache[cache_key]
        
        # Используем облачную модель для лучшей структуры
        model_type, model_name = self.model_router.select_model(
            task_type="content",
            complexity=0.7
        )
        
        structure_prompt = f"""
Создай структуру статьи на тему: "{topic}"

Ключевые слова: {", ".join(keywords)}
Стиль: {style}
Структура должна включать:
1. Заголовок (H1)
2. Введение (150-200 слов)
3. 3-5 основных разделов (каждый 300-500 слов)
4. Заключение (150-200 слов)

Формат ответа (строго в JSON):
{{
    "title": "Заголовок статьи",
    "introduction": "Краткое введение",
    "sections": [
        {{
            "heading": "Заголовок раздела",
            "keywords": ["ключевые", "слова"],
            "bullet_points": ["Основные тезисы"]
        }}
    ],
    "conclusion": "Краткое заключение"
}}
"""
        
        try:
            if model_type == "cloud":
                # Используем Claude
                from anthropic import AsyncAnthropic
                import os
                
                client = AsyncAnthropic(api_key=os.getenv("CLAUDE_API_KEY"))
                
                response = await asyncio.wait_for(
                    client.messages.create(
                        model="claude-4.5-sonnet",
                        max_tokens=2000,
                        messages=[{"role": "user", "content": structure_prompt}]
                    ),
                    timeout=30
                )
                
                response_text = response.content[0].text
                
                # Извлекаем JSON из ответа
                json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
                if json_match:
                    structure = json.loads(json_match.group())
                    
                    # Сохраняем в кэш
                    self._structure_cache[cache_key] = structure
                    self._structure_cache_timestamps[cache_key] = datetime.now()
                    
                    logger.info(f"Article structure created and cached")                    return structure
            
            # Локальная генерация (упрощенная)
            structure = self._generate_fallback_structure(topic, keywords)
            
            # Сохраняем в кэш
            self._structure_cache[cache_key] = structure
            self._structure_cache_timestamps[cache_key] = datetime.now()
            
            return structure
            
        except asyncio.TimeoutError:
            logger.warning("Timeout creating article structure, using fallback")
            return self._generate_fallback_structure(topic, keywords)
        except Exception as e:
            logger.error(f"Error creating article structure: {e}")
            return self._generate_fallback_structure(topic, keywords)
    
    def _generate_fallback_structure(self, topic: str, keywords: List[str]) -> Dict:
        """Сгенерировать резервную структуру статьи"""
        
        return {
            "title": f"Все о {topic}",
            "introduction": f"В этой статье мы рассмотрим {topic}...",
            "sections": [
                {
                    "heading": f"Что такое {topic}",
                    "keywords": keywords[:2] if len(keywords) >= 2 else keywords,
                    "bullet_points": ["Базовая информация", "Основные концепции"]
                },
                {
                    "heading": f"Преимущества {topic}",
                    "keywords": keywords[2:4] if len(keywords) > 2 else keywords[:2],
                    "bullet_points": ["Ключевые преимущества", "Практическая польза"]
                },
                {
                    "heading": f"Как использовать {topic}",
                    "keywords": keywords[-2:] if len(keywords) > 2 else keywords[:2],
                    "bullet_points": ["Пошаговая инструкция", "Лучшие практики"]
                }
            ],
            "conclusion": f"Подводя итоги, {topic} - это..."
        }
    
    @retry(max_attempts=3, delay=2)
    @timeout(120)
    async def _generate_section_content(
        self,
        heading: str,
        keywords: List[str],        section_type: str,
        bullet_points: List[str] = None
    ) -> str:
        """Сгенерировать контент для одного раздела с повторными попытками"""
        
        model_type, model_name = self.model_router.select_model(
            task_type="content",
            complexity=0.5 if section_type == "section" else 0.3
        )
        
        content_prompt = f"""
Напиши контент для раздела статьи.

Заголовок: {heading}
Тип раздела: {section_type}
Ключевые слова: {", ".join(keywords)}
{"Основные тезисы: " + ", ".join(bullet_points) if bullet_points else ""}

Требования:
- Объем: 300-500 слов для основных разделов, 150-200 для введения/заключения
- Стиль: профессиональный, информативный
- Используй ключевые слова естественным образом
- Избегай повторений
- Добавляй примеры и практические советы

Напиши только контент раздела, без дополнительных комментариев.
"""
        
        try:
            if model_type == "cloud":
                from anthropic import AsyncAnthropic
                import os
                
                client = AsyncAnthropic(api_key=os.getenv("CLAUDE_API_KEY"))
                
                response = await client.messages.create(
                    model="claude-4.5-sonnet",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": content_prompt}]
                )
                
                content = response.content[0].text
            
            else:
                # Локальная генерация
                content = f"Раздел: {heading}\n\n" + " ".join([
                    f"Это пример контента о {heading.lower()}. " * 50
                ])
            
            return content.strip()            
        except Exception as e:
            logger.error(f"Error generating section content: {e}")
            # Возвращаем заглушку
            return f"## {heading}\n\n[Контент будет добавлен после обработки]"
    
    async def _generate_sections(self, structure: Dict, language: str) -> List[Dict]:
        """Сгенерировать контент для разделов"""
        
        sections = []
        
        # Генерируем введение
        intro_content = await self._generate_section_content(
            structure["introduction"],
            structure["sections"][0]["keywords"] if structure["sections"] else [],
            "introduction"
        )
        sections.append({
            "type": "introduction",
            "content": intro_content
        })
        
        # Генерируем основные разделы
        for i, section in enumerate(structure["sections"]):
            logger.info(f"Generating section {i+1}/{len(structure["sections"])}")
            
            content = await self._generate_section_content(
                section["heading"],
                section["keywords"],
                "section",
                section.get("bullet_points", [])
            )
            
            sections.append({
                "type": "section",
                "heading": section["heading"],
                "content": content
            })
        
        # Генерируем заключение
        conclusion_content = await self._generate_section_content(
            structure["conclusion"],
            structure["sections"][-1]["keywords"] if structure["sections"] else [],
            "conclusion"
        )
        sections.append({
            "type": "conclusion",
            "content": conclusion_content
        })
                return sections
    
    def _assemble_article(self, sections: List[Dict], topic: str, keywords: List[str]) -> str:
        """Собрать статью из разделов"""
        
        article_parts = []
        
        # Заголовок
        article_parts.append(f"# {topic}\n")
        
        # Введение
        intro = next((s for s in sections if s["type"] == "introduction"), None)
        if intro:
            article_parts.append(intro["content"])
            article_parts.append("\n")
        
        # Основные разделы
        for section in [s for s in sections if s["type"] == "section"]:
            article_parts.append(f"## {section["heading"]}\n")
            article_parts.append(section["content"])
            article_parts.append("\n")
        
        # Заключение
        conclusion = next((s for s in sections if s["type"] == "conclusion"), None)
        if conclusion:
            article_parts.append("## Заключение\n")
            article_parts.append(conclusion["content"])
        
        # Мета-информация
        article_parts.append(f"\n\n---\n**Ключевые слова:** {", ".join(keywords)}")
        
        return "\n".join(article_parts)
    
    @measure_time
    @retry(max_attempts=3, delay=2)
    async def parse_and_summarize(self, url: str, max_length: int = 500) -> Dict:
        """Спарсить и суммаризировать веб-страницу"""
        
        logger.info(f"Parsing URL: {url}")
        
        try:
            # Парсим контент
            content = await self.parser.parse_url(url)
            
            if not content:
                return {"status": "error", "error": "Could not parse URL", "url": url}
            
            # Суммаризируем
            summary = await self._summarize_content(content, max_length)
                        return {
                "status": "success",
                "url": url,
                "original_length": len(content),
                "summary": summary,
                "summary_length": len(summary)
            }
            
        except Exception as e:
            logger.error(f"Error parsing URL: {e}")
            return {"status": "error", "error": str(e), "url": url}
    
    @cache_result(maxsize=200, ttl=86400)
    async def _summarize_content(self, content: str, max_length: int) -> str:
        """Суммаризировать контент с кэшированием"""
        
        model_type, model_name = self.model_router.select_model(
            task_type="content",
            complexity=0.4
        )
        
        summary_prompt = f"""
Суммаризируй следующий текст, сохраняя ключевые идеи:

{content[:4000]}  # Ограничиваем длину

Требования:
- Объем: не более {max_length} слов
- Сохрани основные тезисы
- Используй понятный язык
- Выдели ключевые моменты списком

Напиши только суммаризацию, без дополнительных комментариев.
"""
        
        try:
            if model_type == "cloud":
                from anthropic import AsyncAnthropic
                import os
                
                client = AsyncAnthropic(api_key=os.getenv("CLAUDE_API_KEY"))
                
                response = await asyncio.wait_for(
                    client.messages.create(
                        model="claude-4.5-sonnet",
                        max_tokens=500,
                        messages=[{"role": "user", "content": summary_prompt}]
                    ),
                    timeout=30
                )                
                summary = response.content[0].text
            
            else:
                # Простая суммаризация (первые предложения)
                sentences = re.split(r"[.!?]+", content)
                summary = ". ".join(sentences[:5]) + "."
            
            return summary.strip()
            
        except asyncio.TimeoutError:
            logger.warning("Timeout summarizing content, using simple method")
            sentences = re.split(r"[.!?]+", content)
            return ". ".join(sentences[:5]) + "."
        except Exception as e:
            logger.error(f"Error summarizing content: {e}")
            return content[:max_length] + "..."
    
    @measure_time
    async def batch_generate_articles(
        self,
        topics: List[Dict],
        concurrent_limit: int = 3
    ) -> List[Dict]:
        """Сгенерировать несколько статей параллельно"""
        
        logger.info(f"Batch generating {len(topics)} articles")
        
        results = []
        semaphore = asyncio.Semaphore(concurrent_limit)
        
        async def generate_single(topic_info):
            async with semaphore:
                result = await self.generate_article(**topic_info)
                return result
        
        # Создаем задачи
        tasks = [generate_single(topic) for topic in topics]
        
        # Выполняем параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем результаты
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append({
                    "status": "error",
                    "error": str(result),
                    "topic": topics[i].get("topic", "unknown")                })
            else:
                final_results.append(result)
        
        logger.success(f"Batch generation completed: {len(final_results)} articles")
        
        return final_results
