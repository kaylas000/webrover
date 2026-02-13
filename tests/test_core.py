"""
Тесты для ядра системы
"""

import pytest
import asyncio
from src.core.gpu_manager import GPUManager
from src.core.task_queue import TaskQueue, TaskPriority


class TestGPUManager:
    """Тесты для GPU Manager"""
    
    def test_gpu_manager_initialization(self):
        """Тест инициализации GPU Manager"""
        gpu_manager = GPUManager(max_vram_gb=24, reserved_vram_gb=2)
        
        assert gpu_manager.max_vram_gb == 24
        assert gpu_manager.reserved_vram_gb == 2
        assert gpu_manager.available_vram_gb == 22
    
    def test_gpu_memory_usage(self):
        """Тест получения использования видеопамяти"""
        gpu_manager = GPUManager()
        used_vram, total_vram = gpu_manager.get_gpu_memory_usage()
        
        # Проверяем, что значения неотрицательные
        assert used_vram >= 0
        assert total_vram >= 0


class TestTaskQueue:
    """Тесты для Task Queue"""
    
    @pytest.mark.asyncio
    async def test_task_queue_initialization(self):
        """Тест инициализации Task Queue"""
        task_queue = TaskQueue(max_concurrent_tasks=3)
        
        assert task_queue.max_concurrent_tasks == 3
        assert len(task_queue.queue) == 0
    
    @pytest.mark.asyncio
    async def test_add_task(self):
        """Тест добавления задачи"""
        task_queue = TaskQueue()
        
        await task_queue.add_task(
            task_id="test_task_1",
            task_type="content",
            priority=TaskPriority.HIGH,
            complexity=0.5,
            payload={"description": "Test task"}
        )
        
        assert len(task_queue.queue) == 1
        assert task_queue.queue[0].id == "test_task_1"
        assert task_queue.queue[0].type == "content"
        assert task_queue.queue[0].priority == TaskPriority.HIGH
