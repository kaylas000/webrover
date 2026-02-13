"""
Валидаторы для входных данных
"""

import re
from typing import List, Optional
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Исключение для ошибок валидации"""
    pass


class ArticleRequestValidator(BaseModel):
    """Валидатор для запроса на генерацию статьи"""
    
    topic: str = Field(..., min_length=1, max_length=500)
    keywords: List[str] = Field(..., min_items=1, max_items=20)
    target_length: int = Field(2000, ge=100, le=10000)
    language: str = Field("ru", pattern="^(ru|en|es|fr|de|it|pt|zh|ja|ko|ar|tr)$")
    style: str = Field("professional", pattern="^(professional|casual|technical|academic)$")
    
    @validator("topic")
    def validate_topic(cls, v):
        if len(v.strip()) < 3:
            raise ValidationError("Topic must be at least 3 characters")
        if len(v) > 500:
            raise ValidationError("Topic too long (max 500 characters)")
        return v.strip()
    
    @validator("keywords", each_item=True)
    def validate_keywords(cls, v):
        if len(v.strip()) < 2:
            raise ValidationError("Keywords must be at least 2 characters")
        if len(v) > 50:
            raise ValidationError("Keyword too long (max 50 characters)")
        return v.strip()
    
    @validator("language")
    def validate_language(cls, v):
        supported = ["ru", "en", "es", "fr", "de", "it", "pt", "zh", "ja", "ko", "ar", "tr"]
        if v not in supported:
            raise ValidationError(f"Language "{v}" not supported. Use: {", ".join(supported)}")
        return v

class CodeRequestValidator(BaseModel):
    """Валидатор для запроса на генерацию кода"""
    
    specification: str = Field(..., min_length=10, max_length=2000)
    language: str = Field("python", pattern="^(python|javascript|typescript|java|go|rust|cpp|csharp|php)$")
    framework: Optional[str] = Field(None, max_length=100)
    include_tests: bool = Field(True)
    
    @validator("specification")
    def validate_specification(cls, v):
        if len(v.strip()) < 10:
            raise ValidationError("Specification must be at least 10 characters")
        if len(v) > 2000:
            raise ValidationError("Specification too long (max 2000 characters)")
        return v.strip()
    
    @validator("language")
    def validate_language(cls, v):
        supported = ["python", "javascript", "typescript", "java", "go", "rust", "cpp", "csharp", "php"]
        if v not in supported:
            raise ValidationError(f"Language "{v}" not supported")
        return v


class MissionRequestValidator(BaseModel):
    """Валидатор для запроса на создание миссии"""
    
    description: str = Field(..., min_length=5, max_length=1000)
    priority: str = Field("medium", pattern="^(low|medium|high|critical)$")
    user_id: Optional[str] = Field(None, max_length=100)
    
    @validator("description")
    def validate_description(cls, v):
        if len(v.strip()) < 5:
            raise ValidationError("Description must be at least 5 characters")
        if len(v) > 1000:
            raise ValidationError("Description too long (max 1000 characters)")
        
        # Проверка на потенциально опасные символы
        if re.search(r"[;|&$><`]", v):
            raise ValidationError("Description contains forbidden characters")
        
        return v.strip()
    
    @validator("priority")
    def validate_priority(cls, v):
        priorities = ["low", "medium", "high", "critical"]
        if v not in priorities:
            raise ValidationError(f"Priority must be one of: {", ".join(priorities)}")
        return v

class URLValidator:
    """Валидатор для URL"""
    
    @staticmethod
    def validate_url(url: str, max_length: int = 2000) -> str:
        """
        Валидация и санитизация URL
        
        Args:
            url: URL для валидации
            max_length: Максимальная длина URL
        
        Returns:
            Валидированный URL
        
        Raises:
            ValidationError: Если URL невалиден
        """
        if not url or not isinstance(url, str):
            raise ValidationError("URL must be a non-empty string")
        
        # Ограничиваем длину
        if len(url) > max_length:
            raise ValidationError(f"URL too long (max {max_length} characters)")
        
        # Удаляем пробелы
        url = url.strip()
        
        # Проверяем формат URL
        url_pattern = re.compile(
            r"^https?://"  # http:// или https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # домен
            r"localhost|"  # localhost
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # или IP
            r"(?::\d+)?"  # порт (опционально)
            r"(?:/?|[/?]\S+)$", re.IGNORECASE
        )
        
        if not url_pattern.match(url):
            raise ValidationError("Invalid URL format")
        
        # Проверяем на потенциально опасные схемы
        forbidden_schemes = ["javascript:", "data:", "vbscript:", "file:"]
        if any(url.lower().startswith(scheme) for scheme in forbidden_schemes):
            raise ValidationError("Forbidden URL scheme")
        
        return url
        @staticmethod
    def validate_urls(urls: List[str], max_urls: int = 50) -> List[str]:
        """
        Валидация списка URL
        
        Args:
            urls: Список URL
            max_urls: Максимальное количество URL
        
        Returns:
            Список валидированных URL
        
        Raises:
            ValidationError: Если URL невалидны
        """
        if not isinstance(urls, list):
            raise ValidationError("URLs must be a list")
        
        if len(urls) > max_urls:
            raise ValidationError(f"Too many URLs (max {max_urls})")
        
        validated_urls = []
        for url in urls:
            validated_urls.append(URLValidator.validate_url(url))
        
        return validated_urls


class TextValidator:
    """Валидатор для текста"""
    
    @staticmethod
    def validate_text(
        text: str,
        min_length: int = 1,
        max_length: int = 10000,
        allow_empty: bool = False
    ) -> str:
        """
        Валидация текста
        
        Args:
            text: Текст для валидации
            min_length: Минимальная длина
            max_length: Максимальная длина
            allow_empty: Разрешить пустой текст
        
        Returns:
            Валидированный текст
                Raises:
            ValidationError: Если текст невалиден
        """
        if not isinstance(text, str):
            raise ValidationError("Text must be a string")
        
        if not allow_empty and not text.strip():
            raise ValidationError("Text cannot be empty")
        
        if len(text) < min_length:
            raise ValidationError(f"Text too short (min {min_length} characters)")
        
        if len(text) > max_length:
            raise ValidationError(f"Text too long (max {max_length} characters)")
        
        # Проверка на потенциально опасные символы
        # Разрешаем только печатные символы
        if not all(c.isprintable() or c in "\n\r\t" for c in text):
            raise ValidationError("Text contains non-printable characters")
        
        return text
    
    @staticmethod
    def sanitize_text(text: str, max_length: int = 10000) -> str:
        """
        Санитизация текста (удаление потенциально опасных символов)
        
        Args:
            text: Текст для санитизации
            max_length: Максимальная длина
        
        Returns:
            Санитизированный текст
        """
        # Ограничиваем длину
        text = text[:max_length]
        
        # Удаляем потенциально опасные символы
        # Разрешаем буквы, цифры, пробелы и базовые знаки препинания
        sanitized = "".join(
            c for c in text
            if c.isalnum() or c.isspace() or c in ".,!?-_:;()[]{}""=@#$%&*+/"
        )
        
        return sanitized.strip()


# Функции для удобства использования
def validate_article_request(**kwargs) -> ArticleRequestValidator:
    """Валидация запроса на генерацию статьи"""    try:
        return ArticleRequestValidator(**kwargs)
    except Exception as e:
        logger.error(f"Article request validation failed: {e}")
        raise ValidationError(f"Invalid article request: {e}")


def validate_code_request(**kwargs) -> CodeRequestValidator:
    """Валидация запроса на генерацию кода"""
    try:
        return CodeRequestValidator(**kwargs)
    except Exception as e:
        logger.error(f"Code request validation failed: {e}")
        raise ValidationError(f"Invalid code request: {e}")


def validate_mission_request(**kwargs) -> MissionRequestValidator:
    """Валидация запроса на создание миссии"""
    try:
        return MissionRequestValidator(**kwargs)
    except Exception as e:
        logger.error(f"Mission request validation failed: {e}")
        raise ValidationError(f"Invalid mission request: {e}")
