"""
Декораторы для улучшения функциональности
"""

import asyncio
import time
import hashlib
from functools import wraps
from typing import Any, Callable, Optional
import logging

logger = logging.getLogger(__name__)


def measure_time(func: Callable) -> Callable:
    """
    Декоратор для измерения времени выполнения функции
    
    Пример использования:
        @measure_time
        async def my_function():
            pass
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.info(f"{func.__name__} completed in {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"{func.__name__} failed after {elapsed:.2f}s: {e}")
            raise
    
    return wrapper


def retry(max_attempts: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)) -> Callable:
    """
    Декоратор для повторных попыток при ошибках
    
    Args:
        max_attempts: Максимальное количество попыток
        delay: Начальная задержка между попытками (сек)
        exceptions: Какие исключения перехватывать
    
    Пример использования:
        @retry(max_attempts=3, delay=2)        async def unreliable_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        logger.error(f"{func.__name__} failed after {max_attempts} attempts: {e}")
                        raise
                    
                    # Экспоненциальная задержка
                    wait_time = delay * (2 ** attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}, "
                        f"retrying in {wait_time:.1f}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
            
            raise last_exception
        
        return wrapper
    
    return decorator


def cache_result(maxsize: int = 128, ttl: Optional[int] = None) -> Callable:
    """
    Декоратор для кэширования результатов функции
    
    Args:
        maxsize: Максимальный размер кэша
        ttl: Время жизни кэша в секундах (None = бесконечно)
    
    Пример использования:
        @cache_result(maxsize=100, ttl=3600)
        async def expensive_function(param):
            pass
    """
    cache = {}
    timestamps = {}
    
    def decorator(func: Callable) -> Callable:        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Создаем ключ кэша из аргументов
            cache_key = hashlib.md5(
                f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}".encode()
            ).hexdigest()
            
            # Проверяем TTL
            if ttl and cache_key in timestamps:
                if time.time() - timestamps[cache_key] > ttl:
                    logger.debug(f"Cache expired for {func.__name__}")
                    del cache[cache_key]
                    del timestamps[cache_key]
            
            # Возвращаем из кэша
            if cache_key in cache:
                logger.debug(f"Cache hit for {func.__name__}")
                return cache[cache_key]
            
            # Выполняем функцию и кэшируем результат
            result = await func(*args, **kwargs)
            cache[cache_key] = result
            timestamps[cache_key] = time.time()
            
            # Ограничиваем размер кэша
            if len(cache) > maxsize:
                # Удаляем самый старый элемент
                oldest_key = min(timestamps, key=timestamps.get)
                del cache[oldest_key]
                del timestamps[oldest_key]
            
            logger.debug(f"Cache miss for {func.__name__}, cached result")
            return result
        
        # Добавляем метод для очистки кэша
        def clear_cache():
            cache.clear()
            timestamps.clear()
            logger.info(f"Cache cleared for {func.__name__}")
        
        wrapper.clear_cache = clear_cache
        return wrapper
    
    return decorator


def sanitize_input(max_length: int = 1000, remove_special: bool = True) -> Callable:
    """
    Декоратор для санитизации входных данных
        Args:
        max_length: Максимальная длина строки
        remove_special: Удалять специальные символы
    
    Пример использования:
        @sanitize_input(max_length=500)
        async def process_text(text: str):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Санитизируем строковые аргументы
            sanitized_args = []
            for arg in args:
                if isinstance(arg, str):
                    sanitized = arg[:max_length]
                    if remove_special:
                        sanitized = "".join(
                            c for c in sanitized 
                            if c.isprintable() and c not in ";|&$><`"
                        )
                    sanitized_args.append(sanitized)
                else:
                    sanitized_args.append(arg)
            
            # Санитизируем строковые ключевые аргументы
            sanitized_kwargs = {}
            for key, value in kwargs.items():
                if isinstance(value, str):
                    sanitized = value[:max_length]
                    if remove_special:
                        sanitized = "".join(
                            c for c in sanitized 
                            if c.isprintable() and c not in ";|&$><`"
                        )
                    sanitized_kwargs[key] = sanitized
                else:
                    sanitized_kwargs[key] = value
            
            return await func(*sanitized_args, **sanitized_kwargs)
        
        return wrapper
    
    return decorator


def timeout(seconds: float) -> Callable:
    """
    Декоратор для установки таймаута на выполнение функции    
    Args:
        seconds: Таймаут в секундах
    
    Пример использования:
        @timeout(30)
        async def slow_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                logger.error(f"Timeout after {seconds}s for {func.__name__}")
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds}s")
        
        return wrapper
    
    return decorator
