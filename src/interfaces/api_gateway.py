"""
API Gateway - FastAPI сервер для ИИ-Корпорации
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from loguru import logger
import uvicorn
import asyncio

from ..agents.ceo_agent import CEOAgent
from ..agents.content_agent import ContentAgent
from ..agents.devops_agent import DevOpsAgent
from ..core.task_queue import TaskQueue
from ..core.model_router import ModelRouter


# Модели данных
class MissionRequest(BaseModel):
    """Запрос на создание миссии"""
    description: str = Field(..., description="Описание миссии")
    priority: str = Field("medium", description="Приоритет: low, medium, high, critical")
    user_id: Optional[str] = Field(None, description="ID пользователя")


class MissionResponse(BaseModel):
    """Ответ с информацией о миссии"""
    mission_id: str
    status: str
    description: str
    estimated_time: Optional[float] = None


class ArticleRequest(BaseModel):
    """Запрос на генерацию статьи"""
    topic: str
    keywords: List[str]
    target_length: int = 2000
    language: str = "ru"
    style: str = "professional"


class CodeRequest(BaseModel):
    """Запрос на генерацию кода"""
    specification: str
    language: str = "python"
    framework: Optional[str] = None
    include_tests: bool = True

class StatusResponse(BaseModel):
    """Ответ со статусом системы"""
    status: str
    queue: Dict[str, Any]
    gpu: Dict[str, Any]
    loaded_models: List[str]


class APIGateway:
    """API Gateway для ИИ-Корпорации"""
    
    def __init__(
        self,
        ceo_agent: Optional[CEOAgent] = None,
        content_agent: Optional[ContentAgent] = None,
        devops_agent: Optional[DevOpsAgent] = None,
        task_queue: Optional[TaskQueue] = None,
        model_router: Optional[ModelRouter] = None
    ):
        self.app = FastAPI(
            title="AI Corporation API",
            description="API для управления ИИ-Корпорацией",
            version="2.0.0"
        )
        
        self.ceo_agent = ceo_agent
        self.content_agent = content_agent
        self.devops_agent = devops_agent
        self.task_queue = task_queue
        self.model_router = model_router
        
        # Настраиваем CORS
        self._setup_cors()
        
        # Регистрируем маршруты
        self._register_routes()
        
        logger.info("API Gateway initialized")
    
    def _setup_cors(self):
        """Настройка CORS"""
        
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # В продакшене указать конкретные домены
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],        )
    
    def _register_routes(self):
        """Регистрация маршрутов API"""
        
        @self.app.get("/")
        async def root():
            """Корневой эндпоинт"""
            return {
                "name": "AI Corporation API",
                "version": "2.0.0",
                "status": "running"
            }
        
        @self.app.get("/health")
        async def health_check():
            """Проверка здоровья системы"""
            return {
                "status": "healthy",
                "timestamp": asyncio.get_event_loop().time()
            }
        
        @self.app.get("/status", response_model=StatusResponse)
        async def get_status():
            """Получить статус системы"""
            return await self._get_system_status()
        
        @self.app.post("/missions", response_model=MissionResponse)
        async def create_mission(
            request: MissionRequest,
            background_tasks: BackgroundTasks
        ):
            """Создать новую миссию"""
            return await self._create_mission(request)
        
        @self.app.get("/missions/{mission_id}")
        async def get_mission(mission_id: str):
            """Получить информацию о миссии"""
            return await self._get_mission(mission_id)
        
        @self.app.get("/missions")
        async def list_missions():
            """Список всех миссий"""
            return await self._list_missions()
        
        @self.app.post("/content/articles")
        async def generate_article(request: ArticleRequest):
            """Сгенерировать статью"""
            return await self._generate_article(request)
                @self.app.post("/code/generate")
        async def generate_code(request: CodeRequest):
            """Сгенерировать код"""
            return await self._generate_code(request)
        
        @self.app.get("/models")
        async def list_models():
            """Список доступных моделей"""
            return await self._list_models()
    
    async def _get_system_status(self) -> StatusResponse:
        """Получить статус системы"""
        
        queue_status = {}
        gpu_status = {}
        loaded_models = []
        
        if self.task_queue:
            queue_status = self.task_queue.get_queue_status()
        
        if self.model_router and hasattr(self.model_router, "gpu_manager"):
            gpu_info = self.model_router.gpu_manager.get_status()
            gpu_status = {
                "total_vram_gb": gpu_info["total_vram_gb"],
                "used_vram_gb": gpu_info["used_vram_gb"],
                "available_vram_gb": gpu_info["available_vram_gb"]
            }
            loaded_models = [m["name"] for m in gpu_info["loaded_models"]]
        
        return StatusResponse(
            status="operational",
            queue=queue_status,
            gpu=gpu_status,
            loaded_models=loaded_models
        )
    
    async def _create_mission(self, request: MissionRequest) -> MissionResponse:
        """Создать новую миссию"""
        
        if not self.ceo_agent:
            raise HTTPException(status_code=503, detail="CEO agent not available")
        
        try:
            mission_id = await self.ceo_agent.receive_mission(
                description=request.description,
                user_id=request.user_id
            )
            
            return MissionResponse(
                mission_id=mission_id,                status="accepted",
                description=request.description,
                estimated_time=3600.0  # 1 час по умолчанию
            )
            
        except Exception as e:
            logger.error(f"Error creating mission: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _get_mission(self, mission_id: str):
        """Получить информацию о миссии"""
        
        if not self.ceo_agent:
            raise HTTPException(status_code=503, detail="CEO agent not available")
        
        mission_info = self.ceo_agent.get_mission_status(mission_id)
        
        if not mission_info:
            raise HTTPException(status_code=404, detail="Mission not found")
        
        return mission_info
    
    async def _list_missions(self):
        """Список всех миссий"""
        
        if not self.ceo_agent:
            raise HTTPException(status_code=503, detail="CEO agent not available")
        
        return self.ceo_agent.get_all_missions()
    
    async def _generate_article(self, request: ArticleRequest):
        """Сгенерировать статью"""
        
        if not self.content_agent:
            raise HTTPException(status_code=503, detail="Content agent not available")
        
        try:
            result = await self.content_agent.generate_article(
                topic=request.topic,
                keywords=request.keywords,
                target_length=request.target_length,
                language=request.language,
                style=request.style
            )
            
            if result["status"] == "error":
                raise HTTPException(status_code=500, detail=result["error"])
            
            return result
                    except Exception as e:
            logger.error(f"Error generating article: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _generate_code(self, request: CodeRequest):
        """Сгенерировать код"""
        
        if not self.devops_agent:
            raise HTTPException(status_code=503, detail="DevOps agent not available")
        
        try:
            result = await self.devops_agent.generate_code(
                specification=request.specification,
                language=request.language,
                framework=request.framework,
                include_tests=request.include_tests
            )
            
            if result["status"] == "error":
                raise HTTPException(status_code=500, detail=result["error"])
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating code: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _list_models(self):
        """Список доступных моделей"""
        
        if not self.model_router:
            raise HTTPException(status_code=503, detail="Model router not available")
        
        available_models = self.model_router.get_available_models()
        
        return {
            "loaded": available_models.get("local_loaded", []),
            "available": available_models.get("local_available", []),
            "cloud": available_models.get("cloud_available", [])
        }
    
    def get_app(self) -> FastAPI:
        """Получить FastAPI приложение"""
        return self.app
    
    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Запустить сервер"""
        
        logger.info(f"Starting API Gateway on {host}:{port}")
                uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )
