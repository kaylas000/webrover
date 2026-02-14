"""
ИИ-Корпорация 2.0 — API Gateway
RESTful API для интеграции и управления
"""
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from loguru import logger

from src.core.config import settings, Priority
from src.agents.ceo_agent import CEOAgent


# === Pydantic Models ===

class MissionRequest(BaseModel):
    instruction: str = Field(..., min_length=10, max_length=10000)
    priority: str = Field(default="medium", pattern="^(critical|high|medium|low)$")


class ContentRequest(BaseModel):
    instruction: str = Field(..., min_length=10)
    action: str = Field(default="write_article")
    word_count: int = Field(default=2000, ge=100, le=10000)
    language: str = Field(default="ru")


class CodeRequest(BaseModel):
    instruction: str = Field(..., min_length=10)
    action: str = Field(default="generate_code")
    language: str = Field(default="python")
    framework: Optional[str] = None


class MissionResponse(BaseModel):
    task_id: str
    status: str
    message: str


# === Rate Limiting ===

class RateLimiter:
    def __init__(self, max_requests: int = 50, window: int = 60):
        self.max_requests = max_requests
        self.window = window
        self._requests: dict[str, list[float]] = {}

    def check(self, client_ip: str) -> bool:
        now = time.time()
        if client_ip not in self._requests:
            self._requests[client_ip] = []

        self._requests[client_ip] = [
            t for t in self._requests[client_ip]
            if now - t < self.window
        ]

        if len(self._requests[client_ip]) >= self.max_requests:
            return False

        self._requests[client_ip].append(now)
        return True


# === API ===

def create_api(ceo: CEOAgent) -> FastAPI:
    app = FastAPI(
        title="ИИ-Корпорация 2.0 API",
        description="AI-powered automation platform",
        version="2.0.0",
    )

    rate_limiter = RateLimiter(settings.rate_limit_per_minute)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security headers
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        client_ip = request.client.host
        if not rate_limiter.check(client_ip):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

    @app.get("/")
    async def root():
        return {"name": "ИИ-Корпорация 2.0", "version": "2.0.0", "status": "running"}

    @app.get("/health")
    async def health():
        return {"status": "healthy", "timestamp": time.time()}

    @app.get("/status")
    async def system_status():
        gpu = await ceo.router.gpu.get_status()
        queue = ceo.task_queue.get_stats()
        router = ceo.router.get_stats()

        return {
            "gpu": {
                "vram_used_gb": gpu.used_vram_gb,
                "vram_total_gb": gpu.total_vram_gb,
                "temperature": gpu.temperature,
                "utilization": gpu.utilization,
                "loaded_models": gpu.loaded_models,
            },
            "queue": queue,
            "router": router,
        }

    @app.post("/mission", response_model=MissionResponse)
    async def create_mission(req: MissionRequest):
        """Создание новой миссии"""
        priority_map = {
            "critical": Priority.CRITICAL,
            "high": Priority.HIGH,
            "medium": Priority.MEDIUM,
            "low": Priority.LOW,
        }
        priority = priority_map.get(req.priority, Priority.MEDIUM)

        task_id = await ceo.task_queue.submit(
            name=f"Mission: {req.instruction[:50]}",
            handler=ceo.execute,
            req.instruction,
            priority=priority,
        )

        return MissionResponse(
            task_id=task_id,
            status="pending",
            message="Mission submitted successfully",
        )

    @app.get("/mission/{task_id}")
    async def get_mission(task_id: str):
        """Получение статуса миссии"""
        task = ceo.task_queue.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Mission not found")

        result_data = None
        if task.result and hasattr(task.result, 'data'):
            result_data = task.result.data

        return {**task.to_dict(), "result": result_data}

    @app.post("/content")
    async def generate_content(req: ContentRequest):
        """Прямая генерация контента"""
        content_agent = ceo.agents.get("content_agent")
        if not content_agent:
            raise HTTPException(status_code=503, detail="Content agent not available")

        result = await content_agent.execute(
            instruction=req.instruction,
            action=req.action,
            word_count=req.word_count,
        )

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)

        return {
            "success": True,
            "data": result.data,
            "model_used": result.model_used,
            "tokens_used": result.tokens_used,
            "cost_usd": result.cost_usd,
        }

    @app.post("/code")
    async def generate_code(req: CodeRequest):
        """Прямая генерация кода"""
        devops_agent = ceo.agents.get("devops_agent")
        if not devops_agent:
            raise HTTPException(status_code=503, detail="DevOps agent not available")

        result = await devops_agent.execute(
            instruction=req.instruction,
            action=req.action,
            language=req.language,
            framework=req.framework,
        )

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)

        return {
            "success": True,
            "data": result.data,
            "model_used": result.model_used,
            "tokens_used": result.tokens_used,
            "cost_usd": result.cost_usd,
        }

    @app.get("/tasks")
    async def list_tasks():
        """Список всех задач"""
        return ceo.task_queue.get_all_tasks()

    return app
