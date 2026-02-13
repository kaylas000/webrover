"""
Text Translator - переводчик текста
"""

import asyncio
import json
import re
from typing import Dict, Optional, List
from loguru import logger

from ..core.model_router import ModelRouter


class TextTranslator:
    """Переводчик текста"""
    
    def __init__(self, model_router: ModelRouter):
        self.model_router = model_router
        
        # Поддерживаемые языки
        self.supported_languages = {
            "en": "английский",
            "ru": "русский",
            "es": "испанский",
            "fr": "французский",
            "de": "немецкий",
            "it": "итальянский",
            "pt": "португальский",
            "zh": "китайский",
            "ja": "японский",
            "ko": "корейский",
            "ar": "арабский",
            "tr": "турецкий"
        }
        
        logger.info("Text Translator initialized")
    
    async def translate(
        self,
        text: str,
        target_lang: str = "en",
        source_lang: Optional[str] = None,
        preserve_formatting: bool = True
    ) -> str:
        """
        Перевести текст
        
        Args:
            text: Текст для перевода
            target_lang: Целевой язык (код)            source_lang: Исходный язык (код, опционально)
            preserve_formatting: Сохранять форматирование
        
        Returns:
            Переведенный текст
        """
        
        logger.info(f"Translating to {target_lang}")
        
        if target_lang not in self.supported_languages:
            logger.error(f"Unsupported target language: {target_lang}")
            return text
        
        try:
            # Определяем модель для перевода
            model_type, model_name = self.model_router.select_model(
                task_type="content",
                complexity=0.4
            )
            
            # Создаем промпт для перевода
            lang_name = self.supported_languages[target_lang]
            
            if source_lang and source_lang in self.supported_languages:
                source_lang_name = self.supported_languages[source_lang]
                prompt = f"""
                    Переведи следующий текст с {source_lang_name} на {lang_name}.
                    
                    Текст:
                    {text}
                    
                    Требования:
                    1. Сохрани смысл и стиль оригинала
                    2. Используй естественные формулировки
                    3. Сохрани форматирование (если применимо)
                    4. Не добавляй комментарии
                    
                    Напиши только перевод.
                    """
            else:
                prompt = f"""
                    Переведи следующий текст на {lang_name}.
                    
                    Текст:
                    {text}
                    
                    Требования:
                    1. Сохрани смысл и стиль оригинала
                    2. Используй естественные формулировки
                    3. Сохрани форматирование (если применимо)                    4. Не добавляй комментарии
                    
                    Напиши только перевод.
                    """
            
            # Переводим
            if model_type == "cloud":
                # Используем облачную модель
                translation = await self._translate_with_cloud(prompt, model_name)
            else:
                # Используем локальную модель
                translation = await self._translate_with_local(prompt, model_name)
            
            # Восстанавливаем форматирование
            if preserve_formatting:
                translation = self._restore_formatting(text, translation)
            
            logger.success(f"Translation completed")
            return translation
            
        except Exception as e:
            logger.error(f"Error translating text: {e}")
            return text
    
    async def _translate_with_cloud(self, prompt: str, model_name: str) -> str:
        """Перевести с использованием облачной модели"""
        
        from anthropic import AsyncAnthropic
        import os
        
        client = AsyncAnthropic(api_key=os.getenv("CLAUDE_API_KEY"))
        
        response = await client.messages.create(
            model="claude-4.5-sonnet",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text.strip()
    
    async def _translate_with_local(self, prompt: str, model_name: str) -> str:
        """Перевести с использованием локальной модели"""
        
        # Используем Ollama для локального перевода
        import ollama
        
        response = ollama.generate(
            model=model_name,
            prompt=prompt
        )        
        return response["response"].strip()
    
    def _restore_formatting(self, original: str, translated: str) -> str:
        """Восстановить форматирование из оригинала"""
        
        # Сохраняем заголовки
        translated = re.sub(r"^# ", "# ", translated, flags=re.MULTILINE)
        
        # Сохраняем списки
        translated = re.sub(r"^[-*] ", r"- ", translated, flags=re.MULTILINE)
        
        # Сохраняем цифровые списки
        translated = re.sub(r"^\d+\.", r"1.", translated, flags=re.MULTILINE)
        
        # Сохраняем код (блоки в обратных кавычках)
        code_blocks = re.findall(r"`[^`]+`", original)
        for block in code_blocks:
            if block not in translated:
                translated += f"\n{block}"
        
        return translated
    
    async def batch_translate(
        self,
        texts: List[str],
        target_lang: str = "en",
        max_concurrent: int = 3
    ) -> List[str]:
        """
        Перевести несколько текстов параллельно
        
        Args:
            texts: Список текстов
            target_lang: Целевой язык
            max_concurrent: Максимум параллельных переводов
        
        Returns:
            Список переведенных текстов
        """
        
        logger.info(f"Batch translating {len(texts)} texts to {target_lang}")
        
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def translate_single(text):
            async with semaphore:
                return await self.translate(text, target_lang)
                # Создаем задачи
        tasks = [translate_single(text) for text in texts]
        
        # Выполняем параллельно
        results = await asyncio.gather(*tasks)
        
        logger.success(f"Batch translation completed")
        
        return results
    
    async def detect_language(self, text: str) -> Dict:
        """Определить язык текста"""
        
        model_type, model_name = self.model_router.select_model(
            task_type="content",
            complexity=0.2
        )
        
        prompt = f"""
        Определи язык следующего текста:
        
        {text[:200]}
        
        Ответь только кодом языка (например: ru, en, es, fr).
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
            
            lang_code = response.content[0].text.strip().lower()
            
            # Валидация
            if lang_code in self.supported_languages:
                return {
                    "detected": True,
                    "language_code": lang_code,
                    "language_name": self.supported_languages[lang_code]
                }
        
        # Резервный вариант - эвристика
        # Проверяем наличие кириллицы        if re.search(r"[а-яА-Я]", text):
            return {"detected": True, "language_code": "ru", "language_name": "русский"}
        
        # Проверяем наличие латиницы
        if re.search(r"[a-zA-Z]", text):
            return {"detected": True, "language_code": "en", "language_name": "английский"}
        
        return {"detected": False, "language_code": "unknown"}
    
    async def translate_document(self, document: Dict, target_lang: str) -> Dict:
        """
        Перевести документ с сохранением структуры
        
        Args:
            document: Словарь с полями для перевода
            target_lang: Целевой язык
        
        Returns:
            Переведенный документ
        """
        
        logger.info(f"Translating document to {target_lang}")
        
        translated_doc = {}
        
        # Переводим каждое поле
        for key, value in document.items():
            if isinstance(value, str) and len(value) > 0:
                translated_doc[key] = await self.translate(value, target_lang)
            elif isinstance(value, list):
                translated_doc[key] = await self.batch_translate(value, target_lang)
            else:
                translated_doc[key] = value
        
        return translated_doc
