"""
Model Router - интеллектуальный выбор моделей
"""

import yaml
from typing import Dict, Optional, Tuple
from loguru import logger
from .gpu_manager import GPUManager


class ModelRouter:
    """Роутер для выбора оптимальных моделей"""
    
    def __init__(self, config_path: str = "configs/models.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        
        gpu_config = self.config.get("gpu", {})
        self.gpu_manager = GPUManager(
            max_vram_gb=gpu_config.get("max_vram_gb", 24),
            reserved_vram_gb=gpu_config.get("reserved_vram_gb", 2)
        )
        
        logger.info("Model Router initialized")
    
    def _load_config(self) -> Dict:
        """Загрузить конфигурацию"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except:
            return {
                "gpu": {"max_vram_gb": 24, "reserved_vram_gb": 2},
                "models": {}
            }
    
    def select_model(self, task_type: str, complexity: float = 0.5) -> Tuple[str, str]:
        """Выбрать оптимальную модель"""
        # В реальной реализации здесь будет логика выбора
        return "cloud", "claude-4.5-sonnet"
