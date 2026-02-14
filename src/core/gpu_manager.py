"""
ИИ-Корпорация 2.0 — GPU Manager
Интеллектуальное управление видеопамятью и моделями
"""
import asyncio
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
from loguru import logger

from src.core.config import settings


@dataclass
class LoadedModel:
    name: str
    vram_usage_gb: float
    last_used: float
    request_count: int = 0


@dataclass
class GPUStatus:
    total_vram_gb: float
    used_vram_gb: float
    free_vram_gb: float
    temperature: int
    utilization: int
    loaded_models: list[str] = field(default_factory=list)


class GPUManager:
    """Менеджер GPU с автоматической загрузкой/выгрузкой моделей"""

    MODEL_VRAM_MAP: dict[str, float] = {
        "qwen2.5:7b": 4.5,
        "qwen2.5:14b": 9.0,
        "qwen2.5:32b": 18.0,
        "llama3.1:8b": 5.0,
        "codellama:13b": 8.5,
        "mistral:7b": 4.5,
        "nomic-embed-text": 0.5,
    }

    def __init__(self):
        self._loaded_models: dict[str, LoadedModel] = {}
        self._lock = asyncio.Lock()
        self._total_vram = settings.gpu_total_vram_gb
        self._reserved = settings.gpu_reserved_vram_gb
        self._available = self._total_vram - self._reserved

    async def get_status(self) -> GPUStatus:
        """Получение текущего статуса GPU через nvidia-smi"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi",
                "--query-gpu=memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu",
                "--format=csv,noheader,nounits",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.warning(f"nvidia-smi failed: {stderr.decode()}")
                return self._fallback_status()

            values = stdout.decode().strip().split(", ")
            return GPUStatus(
                total_vram_gb=float(values[0]) / 1024,
                used_vram_gb=float(values[1]) / 1024,
                free_vram_gb=float(values[2]) / 1024,
                temperature=int(values[3]),
                utilization=int(values[4]),
                loaded_models=list(self._loaded_models.keys()),
            )
        except FileNotFoundError:
            logger.warning("nvidia-smi not found, using fallback")
            return self._fallback_status()

    def _fallback_status(self) -> GPUStatus:
        """Статус без nvidia-smi (для разработки / Termux)"""
        used = sum(m.vram_usage_gb for m in self._loaded_models.values())
        return GPUStatus(
            total_vram_gb=self._total_vram,
            used_vram_gb=used + self._reserved,
            free_vram_gb=self._total_vram - used - self._reserved,
            temperature=0,
            utilization=0,
            loaded_models=list(self._loaded_models.keys()),
        )

    def _used_vram(self) -> float:
        return sum(m.vram_usage_gb for m in self._loaded_models.values())

    def _free_vram(self) -> float:
        return self._available - self._used_vram()

    async def ensure_model_loaded(self, model_name: str) -> bool:
        """Гарантирует что модель загружена в VRAM"""
        async with self._lock:
            # Модель уже загружена
            if model_name in self._loaded_models:
                self._loaded_models[model_name].last_used = time.time()
                self._loaded_models[model_name].request_count += 1
                logger.debug(f"Model {model_name} already loaded")
                return True

            required_vram = self.MODEL_VRAM_MAP.get(model_name, 8.0)

            # Проверяем влезет ли модель вообще
            if required_vram > self._available:
                logger.error(
                    f"Model {model_name} requires {required_vram}GB "
                    f"but only {self._available}GB available total"
                )
                return False

            # Освобождаем память если нужно
            while self._free_vram() < required_vram:
                evicted = await self._evict_least_used()
                if not evicted:
                    logger.error("Cannot free enough VRAM")
                    return False

            # Загружаем модель
            success = await self._load_model_ollama(model_name)
            if success:
                self._loaded_models[model_name] = LoadedModel(
                    name=model_name,
                    vram_usage_gb=required_vram,
                    last_used=time.time(),
                    request_count=1,
                )
                logger.info(
                    f"Loaded {model_name} "
                    f"({required_vram}GB, "
                    f"free: {self._free_vram():.1f}GB)"
                )
            return success

    async def _evict_least_used(self) -> bool:
        """Выгружает наименее используемую модель"""
        if not self._loaded_models:
            return False

        least_used = min(
            self._loaded_models.values(),
            key=lambda m: (m.request_count, m.last_used),
        )

        logger.info(
            f"Evicting model {least_used.name} "
            f"to free {least_used.vram_usage_gb}GB"
        )

        await self._unload_model_ollama(least_used.name)
        del self._loaded_models[least_used.name]
        return True

    async def _load_model_ollama(self, model_name: str) -> bool:
        """Загрузка модели через Ollama"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": "hi",
                        "stream": False,
                    },
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as resp:
                    if resp.status == 200:
                        return True
                    else:
                        error = await resp.text()
                        logger.error(f"Failed to load {model_name}: {error}")
                        return False
        except Exception as e:
            logger.error(f"Error loading model {model_name}: {e}")
            return False

    async def _unload_model_ollama(self, model_name: str) -> None:
        """Выгрузка модели из VRAM"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": "",
                        "keep_alive": 0,
                    },
                ) as resp:
                    pass
        except Exception as e:
            logger.warning(f"Error unloading {model_name}: {e}")

    async def get_recommendation(self, task_complexity: str) -> str:
        """Рекомендация модели на основе сложности и ресурсов"""
        free = self._free_vram()

        recommendations = {
            "simple": [
                ("qwen2.5:7b", 4.5),
                ("mistral:7b", 4.5),
            ],
            "medium": [
                ("qwen2.5:14b", 9.0),
                ("codellama:13b", 8.5),
            ],
            "complex": [
                ("qwen2.5:32b", 18.0),
            ],
        }

        candidates = recommendations.get(
            task_complexity, recommendations["medium"]
        )

        # Предпочитаем уже загруженную модель
        for model, vram in candidates:
            if model in self._loaded_models:
                return model

        # Иначе — ту что влезет
        for model, vram in candidates:
            if vram <= free:
                return model

        # Если локальные не помещаются — облако
        if settings.anthropic_api_key:
            return "claude-3-5-sonnet-20241022"
        if settings.openai_api_key:
            return "gpt-4o"

        # Последний вариант — выгрузить и загрузить
        return candidates[0][0]
