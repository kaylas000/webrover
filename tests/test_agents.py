"""
Тесты для агентов
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from src.agents.ceo_agent import CEOAgent, Mission
from src.core.model_router import ModelRouter
from src.core.task_queue import TaskQueue


class TestCEOAgent:
    """Тесты для CEO Agent"""
    
    @pytest.fixture
    def mock_model_router(self):
        """Мок Model Router"""
        model_router = Mock(spec=ModelRouter)
        return model_router
    
    @pytest.fixture
    def mock_task_queue(self):
        """Мок Task Queue"""
        task_queue = AsyncMock(spec=TaskQueue)
        return task_queue
    
    @pytest.mark.asyncio
    async def test_ceo_agent_initialization(self, mock_model_router, mock_task_queue):
        """Тест инициализации CEO Agent"""
        ceo_agent = CEOAgent(mock_model_router, mock_task_queue)
        
        assert ceo_agent.model_router == mock_model_router
        assert ceo_agent.task_queue == mock_task_queue
        assert len(ceo_agent.missions) == 0
    
    @pytest.mark.asyncio
    async def test_receive_mission(self, mock_model_router, mock_task_queue):
        """Тест получения миссии"""
        ceo_agent = CEOAgent(mock_model_router, mock_task_queue)
        
        # Мокаем анализ миссии
        ceo_agent._analyze_mission = AsyncMock(return_value={
            "tasks": [{"id": "task_1", "type": "content", "description": "Test", "complexity": 0.5, "priority": "medium"}]
        })
        
        mission_id = await ceo_agent.receive_mission("Test mission")
        
        assert mission_id is not None
        assert len(ceo_agent.missions) == 1
        assert mission_id in ceo_agent.missions
