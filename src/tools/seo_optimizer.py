"""
SEO Optimizer - оптимизатор контента для поисковых систем
"""

import asyncio
import re
from typing import Dict, List, Optional
from loguru import logger
from collections import Counter

from ..core.model_router import ModelRouter


class SEOOptimizer:
    """Оптимизатор контента для SEO"""
    
    def __init__(self, model_router: ModelRouter):
        self.model_router = model_router
        
        # Параметры для оптимизации
        self.target_keyword_density = 0.02  # 2%
        self.min_keyword_density = 0.01  # 1%
        self.max_keyword_density = 0.03  # 3%
        
        logger.info("SEO Optimizer initialized")
    
    async def optimize(
        self,
        content: str,
        keywords: List[str],
        target_length: Optional[int] = None,
        generate_meta: bool = True
    ) -> str:
        """
        Оптимизировать контент для SEO
        
        Args:
            content: Исходный контент
            keywords: Ключевые слова
            target_length: Целевая длина (опционально)
            generate_meta: Генерировать мета-теги
        
        Returns:
            Оптимизированный контент
        """
        
        logger.info(f"Optimizing content with {len(keywords)} keywords")
        
        try:
            # Анализируем текущий контент            analysis = self._analyze_content(content, keywords)
            
            # Оптимизируем плотность ключевых слов
            optimized_content = await self._optimize_keyword_density(
                content,
                keywords,
                analysis
            )
            
            # Оптимизируем структуру
            optimized_content = self._optimize_structure(optimized_content)
            
            # Генерируем мета-теги
            if generate_meta:
                meta_tags = await self._generate_meta_tags(
                    optimized_content,
                    keywords
                )
                
                # Добавляем мета-теги в конец контента
                optimized_content += "\n\n" + meta_tags
            
            # Проверяем длину
            if target_length:
                optimized_content = self._adjust_length(
                    optimized_content,
                    target_length
                )
            
            logger.success("Content optimized successfully")
            return optimized_content
            
        except Exception as e:
            logger.error(f"Error optimizing content: {e}")
            return content
    
    def _analyze_content(self, content: str, keywords: List[str]) -> Dict:
        """Анализировать контент"""
        
        # Разбиваем на слова
        words = re.findall(r"\b\w+\b", content.lower())
        
        # Считаем частоту слов
        word_freq = Counter(words)
        total_words = len(words)
        
        # Анализируем ключевые слова
        keyword_stats = {}
        for keyword in keywords:
            keyword_lower = keyword.lower()            count = word_freq.get(keyword_lower, 0)
            density = count / total_words if total_words > 0 else 0
            
            keyword_stats[keyword] = {
                "count": count,
                "density": density,
                "target_density": self.target_keyword_density,
                "needs_optimization": not (self.min_keyword_density <= density <= self.max_keyword_density)
            }
        
        # Анализируем структуру
        headings = re.findall(r"^#+\s+(.+)$", content, re.MULTILINE)
        paragraphs = re.split(r"\n\s*\n", content)
        
        return {
            "total_words": total_words,
            "unique_words": len(word_freq),
            "keyword_stats": keyword_stats,
            "headings_count": len(headings),
            "paragraphs_count": len(paragraphs),
            "readability_score": self._calculate_readability(content)
        }
    
    async def _optimize_keyword_density(
        self,
        content: str,
        keywords: List[str],
        analysis: Dict
    ) -> str:
        """Оптимизировать плотность ключевых слов"""
        
        # Находим ключевые слова, которые нужно добавить
        keywords_to_add = [
            kw for kw, stats in analysis["keyword_stats"].items()
            if stats["needs_optimization"] and stats["density"] < self.target_keyword_density
        ]
        
        if not keywords_to_add:
            return content
        
        # Генерируем предложения с ключевыми словами
        model_type, model_name = self.model_router.select_model(
            task_type="content",
            complexity=0.3
        )
        
        prompt = f"""
        Создай 3-5 предложений для вставки в статью.
        
        Ключевые слова для использования: {", ".join(keywords_to_add)}        
        Требования:
        1. Предложения должны быть релевантны теме статьи
        2. Используй ключевые слова естественным образом
        3. Не повторяй одно и то же
        4. Пиши на том же языке, что и статья
        
        Напиши только предложения, по одному на строку.
        """
        
        if model_type == "cloud":
            from anthropic import AsyncAnthropic
            import os
            
            client = AsyncAnthropic(api_key=os.getenv("CLAUDE_API_KEY"))
            
            response = await client.messages.create(
                model="claude-4.5-sonnet",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            new_sentences = response.content[0].text.strip().split("\n")
        else:
            # Локальная генерация (простая)
            new_sentences = [
                f"Это предложение с ключевым словом {kw}."
                for kw in keywords_to_add[:3]
            ]
        
        # Вставляем предложения в контент
        paragraphs = re.split(r"(\n\s*\n)", content)
        
        # Вставляем после первого абзаца
        if len(paragraphs) > 2:
            insert_position = 2
            paragraphs.insert(insert_position, "\n\n" + " ".join(new_sentences) + "\n\n")
        
        optimized_content = "".join(paragraphs)
        
        return optimized_content
    
    def _optimize_structure(self, content: str) -> str:
        """Оптимизировать структуру контента"""
        
        # Проверяем наличие заголовков
        if not re.search(r"^#+\s+", content, re.MULTILINE):
            # Добавляем заголовок, если его нет
            lines = content.split("\n")
            if lines:                first_line = lines[0].strip()
                if len(first_line) < 100:  # Если первая строка короткая
                    content = "# " + first_line + "\n\n" + "\n".join(lines[1:])
        
        # Проверяем длину абзацев
        paragraphs = re.split(r"\n\s*\n", content)
        optimized_paragraphs = []
        
        for para in paragraphs:
            if len(para.strip()) > 500:  # Если абзац слишком длинный
                # Разбиваем на два
                sentences = re.split(r"(?<=[.!?])\s+", para)
                mid_point = len(sentences) // 2
                para1 = " ".join(sentences[:mid_point])
                para2 = " ".join(sentences[mid_point:])
                optimized_paragraphs.extend([para1, para2])
            else:
                optimized_paragraphs.append(para)
        
        content = "\n\n".join(optimized_paragraphs)
        
        return content
    
    async def _generate_meta_tags(
        self,
        content: str,
        keywords: List[str]
    ) -> str:
        """Сгенерировать мета-теги"""
        
        # Извлекаем первые 160 символов для описания
        description = content[:160].strip()
        if len(content) > 160:
            description = description[:description.rfind(" ")] + "..."
        
        # Генерируем заголовок
        model_type, model_name = self.model_router.select_model(
            task_type="content",
            complexity=0.2
        )
        
        prompt = f"""
        Создай SEO-заголовок (до 60 символов) для статьи.
        
        Первые предложения статьи:
        {content[:300]}
        
        Ключевые слова: {", ".join(keywords)}
        
        Требования:        1. Длина до 60 символов
        2. Включай главное ключевое слово
        3. Привлекательный для кликов
        4. Уникальный
        
        Напиши только заголовок.
        """
        
        if model_type == "cloud":
            from anthropic import AsyncAnthropic
            import os
            
            client = AsyncAnthropic(api_key=os.getenv("CLAUDE_API_KEY"))
            
            response = await client.messages.create(
                model="claude-4.5-sonnet",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            
            title = response.content[0].text.strip()
        else:
            # Локальная генерация
            title = "SEO оптимизированная статья"
        
        # Формируем мета-теги
        meta_tags = f"""
<!-- SEO Meta Tags -->
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="keywords" content="{", ".join(keywords)}">
<meta name="robots" content="index, follow">
"""
        
        return meta_tags
    
    def _adjust_length(self, content: str, target_length: int) -> str:
        """Отрегулировать длину контента"""
        
        words = content.split()
        current_length = len(words)
        
        if current_length <= target_length:
            return content
        
        # Обрезаем до целевого размера
        truncated_words = words[:target_length]
        
        # Находим последнюю точку для корректного завершения
        truncated_text = " ".join(truncated_words)        last_sentence_end = max(
            truncated_text.rfind("."),
            truncated_text.rfind("!"),
            truncated_text.rfind("?")
        )
        
        if last_sentence_end > 0:
            truncated_text = truncated_text[:last_sentence_end + 1]
        
        truncated_text += "\n\n[... статья продолжается на сайте ...]"
        
        return truncated_text
    
    def _calculate_readability(self, content: str) -> float:
        """Рассчитать читаемость текста (упрощенно)"""
        
        # Считаем среднюю длину слов и предложений
        words = re.findall(r"\b\w+\b", content)
        sentences = re.split(r"[.!?]+", content)
        
        avg_word_length = sum(len(w) for w in words) / len(words) if words else 0
        avg_sentence_length = len(words) / len(sentences) if sentences and len(sentences) > 1 else 0
        
        # Простая метрика читаемости
        readability = 100 - (avg_word_length * 2 + avg_sentence_length * 0.5)
        
        return max(0, min(100, readability))
    
    async def generate_seo_report(self, content: str, keywords: List[str]) -> Dict:
        """Сгенерировать отчет по SEO"""
        
        analysis = self._analyze_content(content, keywords)
        
        # Оцениваем оптимизацию
        keyword_scores = []
        for stats in analysis["keyword_stats"].values():
            if self.min_keyword_density <= stats["density"] <= self.max_keyword_density:
                keyword_scores.append(100)
            else:
                score = 100 - abs(stats["density"] - self.target_keyword_density) * 1000
                keyword_scores.append(max(0, min(100, score)))
        
        avg_keyword_score = sum(keyword_scores) / len(keyword_scores) if keyword_scores else 0
        
        # Оценка структуры
        structure_score = min(100, analysis["headings_count"] * 20 + analysis["paragraphs_count"] * 5)
        
        # Итоговый счет
        overall_score = (avg_keyword_score * 0.6 + structure_score * 0.4)
                return {
            "overall_score": round(overall_score, 1),
            "keyword_optimization": round(avg_keyword_score, 1),
            "structure_score": round(structure_score, 1),
            "readability_score": round(analysis["readability_score"], 1),
            "total_words": analysis["total_words"],
            "keyword_stats": analysis["keyword_stats"],
            "recommendations": await self._generate_recommendations(analysis, keywords)
        }
    
    async def _generate_recommendations(self, analysis: Dict, keywords: List[str]) -> List[str]:
        """Сгенерировать рекомендации по улучшению"""
        
        recommendations = []
        
        # Проверяем ключевые слова
        underused = [
            kw for kw, stats in analysis["keyword_stats"].items()
            if stats["density"] < self.min_keyword_density
        ]
        
        overused = [
            kw for kw, stats in analysis["keyword_stats"].items()
            if stats["density"] > self.max_keyword_density
        ]
        
        if underused:
            recommendations.append(
                f"Добавьте ключевые слова: {", ".join(underused)}"
            )
        
        if overused:
            recommendations.append(
                f"Уменьшите использование: {", ".join(overused)}"
            )
        
        # Проверяем структуру
        if analysis["headings_count"] < 3:
            recommendations.append("Добавьте больше заголовков (H2, H3)")
        
        if analysis["paragraphs_count"] < 5:
            recommendations.append("Разбейте текст на больше абзацев")
        
        # Проверяем читаемость
        if analysis["readability_score"] < 50:
            recommendations.append("Упростите текст: используйте более короткие предложения")
        
        if not recommendations:
            recommendations.append("Контент хорошо оптимизирован для SEO!")
                return recommendations
