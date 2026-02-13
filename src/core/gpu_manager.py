"""
GPU Manager - управление видеопамятью и загрузкой моделей
"""

import torch
import subprocess
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger
import time
import asyncio
from asyncio import Lock


@dataclass
class ModelInfo:
    """Информация о модели"""
    name: str
    vram_gb: float
    quantization: str
    priority: int
    loaded: bool = False
    load_time: Optional[float] = None


class GPUManager:
    """Менеджер управления видеопамятью"""
    
    def __init__(self, max_vram_gb: int = 24, reserved_vram_gb: int = 2):
        self.max_vram_gb = max_vram_gb
        self.reserved_vram_gb = reserved_vram_gb
        self.available_vram_gb = max_vram_gb - reserved_vram_gb
        
        self.loaded_models: Dict[str, ModelInfo] = {}
        self.model_queue: List[str] = []
        self._lock = Lock()
        
        logger.info(f"GPU Manager initialized")
        logger.info(f"Total VRAM: {max_vram_gb} GB")
        logger.info(f"Available VRAM: {self.available_vram_gb} GB")
    
    def get_gpu_memory_usage(self) -> Tuple[float, float]:
        """Получить использование видеопамяти"""
        try:
            if torch.cuda.is_available():
                total = torch.cuda.get_device_properties(0).total_memory / 1e9
                allocated = torch.cuda.memory_allocated(0) / 1e9
                cached = torch.cuda.memory_reserved(0) / 1e9
                used = allocated + cached
                return used, total            else:
                return 0.0, self.max_vram_gb
        except Exception as e:
            logger.error(f"Error getting GPU memory: {e}")
            return 0.0, self.max_vram_gb
    
    def check_vram_availability(self, required_vram_gb: float) -> bool:
        """Проверить доступность видеопамяти"""
        used_vram, _ = self.get_gpu_memory_usage()
        available = self.available_vram_gb - used_vram
        return available >= required_vram_gb
    
    async def load_model(self, model_name: str, model_config: Dict, timeout: int = 600) -> bool:
        """Загрузить модель в память"""
        async with self._lock:
            try:
                required_vram = model_config.get("vram_gb", 0)
                
                if not self.check_vram_availability(required_vram):
                    logger.warning(f"Not enough VRAM to load {model_name}")
                    return False
                
                model_full_name = f"{model_config["name"]}:{model_config.get("quantization", "latest")}"
                logger.info(f"Loading model: {model_full_name}")
                
                process = await asyncio.wait_for(
                    asyncio.create_subprocess_exec(
                        "ollama", "pull", model_full_name,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    ),
                    timeout=timeout
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                
                if process.returncode != 0:
                    logger.error(f"Failed to load model {model_name}")
                    return False
                
                model_info = ModelInfo(
                    name=model_name,
                    vram_gb=required_vram,
                    quantization=model_config.get("quantization", "latest"),
                    priority=model_config.get("priority", 1),
                    loaded=True,
                    load_time=time.time()                )
                
                self.loaded_models[model_name] = model_info
                logger.success(f"Model {model_name} loaded successfully")
                return True
                
            except Exception as e:
                logger.error(f"Error loading model {model_name}: {e}")
                return False
    
    async def unload_model(self, model_name: str) -> bool:
        """Выгрузить модель из памяти"""
        async with self._lock:
            try:
                if model_name not in self.loaded_models:
                    return False
                
                logger.info(f"Unloading model: {model_name}")
                
                process = await asyncio.create_subprocess_exec(
                    "ollama", "rm", self.loaded_models[model_name].name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    logger.error(f"Failed to unload model {model_name}")
                    return False
                
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                del self.loaded_models[model_name]
                logger.success(f"Model {model_name} unloaded successfully")
                return True
                
            except Exception as e:
                logger.error(f"Error unloading model {model_name}: {e}")
                return False
    
    def get_status(self) -> Dict:
        """Получить статус менеджера"""
        used_vram, total_vram = self.get_gpu_memory_usage()
        
        return {
            "total_vram_gb": self.max_vram_gb,
            "used_vram_gb": used_vram,
            "available_vram_gb": self.available_vram_gb - used_vram,            "loaded_models": [
                {
                    "name": info.name,
                    "vram_gb": info.vram_gb,
                    "priority": info.priority,
                    "load_time": info.load_time
                }
                for info in self.loaded_models.values()
            ],
            "model_count": len(self.loaded_models)
        }
