"""
Web Panel - веб-интерфейс для управления ИИ-Корпорацией
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import asyncio
from typing import Dict, Optional
from loguru import logger

from ..agents.ceo_agent import CEOAgent
from ..core.task_queue import TaskQueue
from ..core.model_router import ModelRouter


class WebPanel:
    """Веб-панель для управления ИИ-Корпорацией"""
    
    def __init__(
        self,
        ceo_agent: Optional[CEOAgent] = None,
        task_queue: Optional[TaskQueue] = None,
        model_router: Optional[ModelRouter] = None
    ):
        self.app = FastAPI(
            title="AI Corporation Web Panel",
            description="Веб-интерфейс для управления ИИ-Корпорацией"
        )
        
        self.ceo_agent = ceo_agent
        self.task_queue = task_queue
        self.model_router = model_router
        
        # Настройка шаблонов
        self.templates = Jinja2Templates(directory="web/templates")
        
        # Настройка статических файлов
        self.app.mount("/static", StaticFiles(directory="web/static"), name="static")
        
        # Регистрация маршрутов
        self._register_routes()
        
        logger.info("Web Panel initialized")
    
    def _register_routes(self):
        """Регистрация маршрутов веб-панели"""
        
        @self.app.get("/", response_class=HTMLResponse)        async def dashboard(request: Request):
            """Главная страница - дашборд"""
            return await self._render_dashboard(request)
        
        @self.app.get("/missions", response_class=HTMLResponse)
        async def missions_page(request: Request):
            """Страница миссий"""
            return await self._render_missions(request)
        
        @self.app.get("/models", response_class=HTMLResponse)
        async def models_page(request: Request):
            """Страница моделей"""
            return await self._render_models(request)
        
        @self.app.get("/status", response_class=HTMLResponse)
        async def status_page(request: Request):
            """Страница статуса системы"""
            return await self._render_status(request)
        
        @self.app.post("/api/mission")
        async def create_mission_api(request: Request):
            """API для создания миссии"""
            return await self._handle_mission_creation(request)
        
        @self.app.get("/api/status")
        async def get_system_status():
            """API для получения статуса системы"""
            return await self._get_system_status_api()
    
    async def _render_dashboard(self, request: Request):
        """Отрисовка главной страницы"""
        
        try:
            # Получаем статус системы
            system_status = await self._get_system_status_data()
            
            # Получаем последние миссии
            missions = []
            if self.ceo_agent:
                missions = self.ceo_agent.get_all_missions()[-5:]  # Последние 5 миссий
            
            return self.templates.TemplateResponse(
                "dashboard.html",
                {
                    "request": request,
                    "system_status": system_status,
                    "missions": missions,
                    "page_title": "AI Corporation - Dashboard"
                }
            )            
        except Exception as e:
            logger.error(f"Error rendering dashboard: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _render_missions(self, request: Request):
        """Отрисовка страницы миссий"""
        
        try:
            missions = []
            if self.ceo_agent:
                missions = self.ceo_agent.get_all_missions()
            
            return self.templates.TemplateResponse(
                "missions.html",
                {
                    "request": request,
                    "missions": missions,
                    "page_title": "AI Corporation - Missions"
                }
            )
            
        except Exception as e:
            logger.error(f"Error rendering missions page: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _render_models(self, request: Request):
        """Отрисовка страницы моделей"""
        
        try:
            models_info = {}
            if self.model_router:
                models_info = self.model_router.get_available_models()
            
            gpu_status = {}
            if self.model_router and hasattr(self.model_router, "gpu_manager"):
                gpu_status = self.model_router.gpu_manager.get_status()
            
            return self.templates.TemplateResponse(
                "models.html",
                {
                    "request": request,
                    "models_info": models_info,
                    "gpu_status": gpu_status,
                    "page_title": "AI Corporation - Models"
                }
            )
            
        except Exception as e:
            logger.error(f"Error rendering models page: {e}")            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _render_status(self, request: Request):
        """Отрисовка страницы статуса"""
        
        try:
            system_status = await self._get_system_status_data()
            
            return self.templates.TemplateResponse(
                "status.html",
                {
                    "request": request,
                    "system_status": system_status,
                    "page_title": "AI Corporation - Status"
                }
            )
            
        except Exception as e:
            logger.error(f"Error rendering status page: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _handle_mission_creation(self, request: Request):
        """Обработка создания миссии через API"""
        
        try:
            form_data = await request.form()
            description = form_data.get("description", "")
            priority = form_data.get("priority", "medium")
            user_id = form_data.get("user_id", "web_user")
            
            if not description:
                raise HTTPException(status_code=400, detail="Description is required")
            
            if not self.ceo_agent:
                raise HTTPException(status_code=503, detail="CEO agent not available")
            
            mission_id = await self.ceo_agent.receive_mission(
                description=str(description),
                user_id=str(user_id),
                priority=str(priority)
            )
            
            return {
                "success": True,
                "mission_id": mission_id,
                "message": "Mission created successfully"
            }
            
        except HTTPException:
            raise        except Exception as e:
            logger.error(f"Error creating mission: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _get_system_status_api(self):
        """Получить статус системы через API"""
        
        try:
            system_status = await self._get_system_status_data()
            return system_status
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _get_system_status_data(self) -> Dict:
        """Получить данные о статусе системы"""
        
        status_data = {
            "timestamp": asyncio.get_event_loop().time(),
            "queue": {},
            "gpu": {},
            "loaded_models": [],
            "missions_count": 0
        }
        
        # Статус очереди
        if self.task_queue:
            status_data["queue"] = self.task_queue.get_queue_status()
        
        # Статус GPU и моделей
        if self.model_router and hasattr(self.model_router, "gpu_manager"):
            gpu_info = self.model_router.gpu_manager.get_status()
            status_data["gpu"] = {
                "total_vram_gb": gpu_info["total_vram_gb"],
                "used_vram_gb": gpu_info["used_vram_gb"],
                "available_vram_gb": gpu_info["available_vram_gb"]
            }
            status_data["loaded_models"] = [m["name"] for m in gpu_info["loaded_models"]]
        
        # Количество миссий
        if self.ceo_agent:
            status_data["missions_count"] = len(self.ceo_agent.get_all_missions())
        
        return status_data
    
    def get_app(self) -> FastAPI:
        """Получить FastAPI приложение"""
        return self.app
        def run(self, host: str = "0.0.0.0", port: int = 8080):
        """Запустить веб-панель"""
        
        logger.info(f"Starting Web Panel on http://{host}:{port}")
        
        import uvicorn
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )
