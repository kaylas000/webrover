"""
Content Parser - парсер веб-страниц и текста
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
from typing import Dict, Optional
from loguru import logger
import html2text


class ContentParser:
    """Парсер контента с веб-страниц"""
    
    def __init__(self):
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True
        self.html_converter.body_width = 0
        
        logger.info("Content Parser initialized")
    
    async def parse_url(self, url: str, timeout: int = 30) -> Optional[str]:
        """
        Спарсить контент с веб-страницы
        
        Args:
            url: URL страницы
            timeout: Таймаут в секундах
        
        Returns:
            Очищенный текст или None
        """
        
        logger.info(f"Parsing URL: {url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    if response.status != 200:
                        logger.error(f"HTTP {response.status} for {url}")
                        return None
                    
                    html = await response.text()
                    
                    # Очищаем HTML
                    text = self._clean_html(html, url)
                                        logger.success(f"Successfully parsed {url}")
                    return text
                    
        except asyncio.TimeoutError:
            logger.error(f"Timeout parsing {url}")
            return None
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
            return None
    
    def _clean_html(self, html: str, url: str) -> str:
        """Очистить HTML и извлечь текст"""
        
        # Используем BeautifulSoup для очистки
        soup = BeautifulSoup(html, "html.parser")
        
        # Удаляем скрипты, стили, навигацию
        for element in soup(["script", "style", "nav", "header", "footer", "iframe", "noscript"]):
            element.decompose()
        
        # Удаляем рекламу и боковые панели
        for element in soup.find_all(class_=re.compile(r"advertisement|sidebar|widget|related|comments")):
            element.decompose()
        
        # Удаляем скрытые элементы
        for element in soup.find_all(style=re.compile(r"display:\s*none")):
            element.decompose()
        
        # Пытаемся найти основной контент
        main_content = None
        
        # Ищем по тегам article, main, или контейнерам с контентом
        candidates = soup.find_all(["article", "main"]) + \
                    soup.find_all(class_=re.compile(r"article|post|content|entry|main")) + \
                    soup.find_all(id=re.compile(r"article|post|content|main"))
        
        if candidates:
            # Выбираем самый большой кандидат
            main_content = max(candidates, key=lambda x: len(x.get_text()))
        else:
            # Если не нашли, используем весь контент
            main_content = soup
        
        # Конвертируем в чистый текст
        text = self.html_converter.handle(str(main_content))
        
        # Дополнительная очистка
        text = self._post_process(text)
        
        return text.strip()    
    def _post_process(self, text: str) -> str:
        """Пост-обработка текста"""
        
        # Удаляем множественные переносы строк
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        
        # Удаляем множественные пробелы
        text = re.sub(r" {2,}", " ", text)
        
        # Удаляем URL в тексте (оставляем только ссылки в скобках)
        text = re.sub(r"https?://[^\s)]+", "", text)
        
        # Удаляем лишние символы
        text = re.sub(r"[^\S\n]+$", "", text, flags=re.MULTILINE)
        
        # Ограничиваем длину (максимум 10000 символов)
        if len(text) > 10000:
            text = text[:10000] + "\n\n[... текст обрезан из-за ограничения длины ...]"
        
        return text
