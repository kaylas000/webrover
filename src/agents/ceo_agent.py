"""
CEO Agent - главный координатор ИИ-Корпорации
"""

import asyncio
import json
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
import traceback

from ..core.model_router import ModelRouter
from ..core.task_queue import TaskQueue


@dataclass
class Mission:
    """Миссия - комплексная задача"""
    id: str
    description: str
    tasks: List[Dict]
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    results: Dict = field(default_factory=dict)


class CEOAgent:
    """CEO-бот - координатор всей системы"""
    
    def __init__(self, model_router: ModelRouter, task_queue: TaskQueue):
        self.model_router = model_router
        self.task_queue = task_queue
        self.missions: Dict[str, Mission] = {}
        self._lock = asyncio.Lock()
        logger.info("CEO Agent initialized")
    
    async def receive_mission(self, description: str, user_id: Optional[str] = None) -> str:
        """Получить новую миссию"""
        async with self._lock:
            mission_id = f"mission_{uuid.uuid4().hex[:8]}"
            logger.info(f"Received new mission: {mission_id}")
            
            mission_plan = await self._analyze_mission(description)
            
            mission = Mission(
                id=mission_id,
                description=description,                tasks=mission_plan.get("tasks", [])
            )
            
            self.missions[mission_id] = mission
            asyncio.create_task(self._execute_mission(mission))
            
            return mission_id
    
    async def _analyze_mission(self, description: str) -> Dict:
        """Проанализировать миссию"""
        try:
            from anthropic import AsyncAnthropic
            import os
            
            client = AsyncAnthropic(api_key=os.getenv("CLAUDE_API_KEY"))
            
            prompt = f"""
Проанализируй миссию и создай план задач:

Миссия: {description}

Формат ответа (JSON):
{{
    "mission_summary": "Описание",
    "estimated_time_hours": 2.5,
    "tasks": [
        {{
            "id": "task_1",
            "type": "content",
            "description": "Задача",
            "complexity": 0.7,
            "priority": "high"
        }}
    ]
}}
"""
            
            response = await client.messages.create(
                model="claude-4.5-sonnet",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            import re
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            
            if json_match:
                return json.loads(json_match.group())
                    except Exception as e:
            logger.error(f"Error analyzing mission: {e}")
        
        # Fallback
        return {
            "mission_summary": description,
            "estimated_time_hours": 1.0,
            "tasks": [{
                "id": "task_1",
                "type": "content",
                "description": description,
                "complexity": 0.5,
                "priority": "medium"
            }]
        }
    
    async def _execute_mission(self, mission: Mission):
        """Выполнить миссию"""
        logger.info(f"Starting mission: {mission.id}")
        
        async with self._lock:
            mission.status = "running"
        
        try:
            for task_info in mission.tasks:
                task_id = f"{mission.id}_{task_info["id"]}"
                
                from ..core.task_queue import TaskPriority
                priority = {
                    "critical": TaskPriority.CRITICAL,
                    "high": TaskPriority.HIGH,
                    "medium": TaskPriority.MEDIUM,
                    "low": TaskPriority.LOW
                }.get(task_info.get("priority", "medium"), TaskPriority.MEDIUM)
                
                await self.task_queue.add_task(
                    task_id=task_id,
                    task_type=task_info["type"],
                    priority=priority,
                    complexity=task_info["complexity"],
                    payload={"description": task_info["description"], "mission_id": mission.id}
                )
            
            await self._wait_for_mission_completion(mission)
            logger.success(f"Mission {mission.id} completed!")
            
        except Exception as e:
            logger.error(f"Error executing mission: {e}")
    
    async def _wait_for_mission_completion(self, mission: Mission, timeout: int = 7200):        """Ожидать завершения миссии"""
        start_time = datetime.now()
        
        while True:
            async with self._lock:
                completed = sum(1 for r in mission.results.values() if r.get("status") == "completed")
                total = len(mission.tasks)
                
                if completed == total:
                    break
            
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                logger.error(f"Mission timeout")
                break
            
            await asyncio.sleep(5)
