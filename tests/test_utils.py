"""
Тесты для утилит
"""

import pytest
from src.utils.validators import TextValidator, URLValidator, ValidationError


class TestTextValidator:
    """Тесты для TextValidator"""
    
    def test_valid_text(self):
        """Тест валидного текста"""
        text = "Это тестовый текст с цифрами 123 и знаками препинания."
        result = TextValidator.validate_text(text)
        assert result == text
    
    def test_text_too_short(self):
        """Тест слишком короткого текста"""
        with pytest.raises(ValidationError):
            TextValidator.validate_text("Hi", min_length=10)
    
    def test_text_too_long(self):
        """Тест слишком длинного текста"""
        long_text = "a" * 10001
        with pytest.raises(ValidationError):
            TextValidator.validate_text(long_text, max_length=10000)
    
    def test_sanitize_text(self):
        """Тест санитизации текста"""
        dirty_text = "Test<script>alert(1)</script>text; rm -rf /"
        sanitized = TextValidator.sanitize_text(dirty_text)
        
        # Проверяем, что опасные символы удалены
        assert "<script>" not in sanitized
        assert "; rm -rf /" not in sanitized


class TestURLValidator:
    """Тесты для URLValidator"""
    
    def test_valid_url(self):
        """Тест валидного URL"""
        url = "https://example.com/path?query=1"
        result = URLValidator.validate_url(url)
        assert result == url
    
    def test_invalid_url_scheme(self):
        """Тест невалидной схемы URL"""
        with pytest.raises(ValidationError):
            URLValidator.validate_url("javascript:alert(1)")
    
    def test_invalid_url_format(self):
        """Тест невалидного формата URL"""
        with pytest.raises(ValidationError):
            URLValidator.validate_url("not-a-url")
