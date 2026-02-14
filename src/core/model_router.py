"""
ИИ-Корпорация 2.0 — Model Router
Интеллектуальный маршрутизатор: выбирает оптимальную модель для задачи
"""
import time
from dataclasses import dataclass
from typing import Optional

import aiohttp
from loguru import logger

from src.core.config import settings, ModelTier
from src.core.gpu_manager import GPUManager


@dataclass
class ModelResponse:
    text: str
    model_used: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float
    from_cache: bool = False


@dataclass
class RoutingDecision:
    tier: ModelTier
    model_name: str
    reason: str


class ModelRouter:
    """Маршрутизатор моделей с fallback и учётом стоимости"""

    CLOUD_PRICING: dict[str, tuple[float, float]] = {
        "claude-3-5-sonnet-20241022": (0.003, 0.015),
        "claude-3-haiku-20240307": (0.00025, 0.00125),
        "gpt-4o": (0.005, 0.015),
        "gpt-4o-mini": (0.00015, 0.0006),
    }

    def __init__(self, gpu_manager: GPUManager):
        self.gpu = gpu_manager
        self._request_count = 0
        self._total_cost = 0.0

    def _classify_complexity(
        self, prompt: str, task_type: str = "general"
    ) -> str:
        """Классификация сложности задачи"""
        prompt_lower = prompt.lower()
        length = len(prompt)

        complex_indicators = [
            "проанализируй", "сравни", "разработай архитектуру",
            "напиши production", "оптимизируй", "рефакторинг",
            "стратегия", "бизнес-план", "многоуровневый",
        ]
        simple_indicators = [
            "переведи", "исправь ошибку", "форматируй",
            "кратко", "summary", "простой", "список",
        ]

        complex_score = sum(
            1 for ind in complex_indicators if ind in prompt_lower
        )
        simple_score = sum(
            1 for ind in simple_indicators if ind in prompt_lower
        )

        if complex_score >= 2 or length > 3000 or task_type == "architecture":
            return "complex"
        elif simple_score >= 2 or length < 200 or task_type == "translation":
            return "simple"
        else:
            return "medium"

    def _tier_from_model(self, model: str) -> ModelTier:
        """Определение уровня модели по имени"""
        if "claude" in model:
            return ModelTier.CLOUD_CLAUDE
        elif "gpt" in model:
            return ModelTier.CLOUD_OPENAI
        elif "32b" in model:
            return ModelTier.LOCAL_LARGE
        elif "14b" in model or "13b" in model:
            return ModelTier.LOCAL_MEDIUM
        else:
            return ModelTier.LOCAL_SMALL

    async def _best_model_for_tier(self, tier: ModelTier) -> str:
        """Лучшая модель для уровня"""
        tier_models = {
            ModelTier.LOCAL_SMALL: "qwen2.5:7b",
            ModelTier.LOCAL_MEDIUM: "qwen2.5:14b",
            ModelTier.LOCAL_LARGE: "qwen2.5:32b",
            ModelTier.CLOUD_CLAUDE: "claude-3-5-sonnet-20241022",
            ModelTier.CLOUD_OPENAI: "gpt-4o",
        }
        return tier_models.get(tier, "qwen2.5:14b")

    async def route(
        self,
        prompt: str,
        task_type: str = "general",
        force_tier: Optional[ModelTier] = None,
        force_model: Optional[str] = None,
    ) -> RoutingDecision:
        """Выбор оптимальной модели для задачи"""
        if force_model:
            return RoutingDecision(
                tier=self._tier_from_model(force_model),
                model_name=force_model,
                reason="Forced by user",
            )

        if force_tier:
            model = await self._best_model_for_tier(force_tier)
            return RoutingDecision(
                tier=force_tier,
                model_name=model,
                reason=f"Forced tier: {force_tier.value}",
            )

        complexity = self._classify_complexity(prompt, task_type)
        model = await self.gpu.get_recommendation(complexity)

        return RoutingDecision(
            tier=self._tier_from_model(model),
            model_name=model,
            reason=f"Auto-routed: complexity={complexity}",
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        task_type: str = "general",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        force_model: Optional[str] = None,
    ) -> ModelResponse:
        """Генерация ответа с автоматическим выбором модели"""
        start_time = time.time()
        self._request_count += 1

        decision = await self.route(
            prompt, task_type, force_model=force_model
        )
        logger.info(f"Routing: {decision.model_name} ({decision.reason})")

        try:
            if decision.tier in (
                ModelTier.CLOUD_CLAUDE, ModelTier.CLOUD_OPENAI
            ):
                response = await self._generate_cloud(
                    decision.model_name, prompt, system_prompt,
                    max_tokens, temperature,
                )
            else:
                response = await self._generate_local(
                    decision.model_name, prompt, system_prompt,
                    max_tokens, temperature,
                )

            response.latency_ms = (time.time() - start_time) * 1000
            self._total_cost += response.cost_usd

            logger.info(
                f"Generated: {response.tokens_out} tokens, "
                f"{response.latency_ms:.0f}ms, "
                f"${response.cost_usd:.4f}"
            )
            return response

        except Exception as e:
            logger.error(
                f"Generation failed with {decision.model_name}: {e}"
            )
            return await self._fallback_generate(
                prompt, system_prompt, decision,
                max_tokens, temperature,
            )

    async def _generate_local(
        self,
        model: str,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> ModelResponse:
        """Генерация через Ollama"""
        loaded = await self.gpu.ensure_model_loaded(model)
        if not loaded:
            raise RuntimeError(f"Failed to load model {model}")

        async with aiohttp.ClientSession() as session:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            }
            if system_prompt:
                payload["system"] = system_prompt

            async with session.post(
                f"{settings.ollama_base_url}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(
                    total=settings.task_timeout_seconds
                ),
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise RuntimeError(f"Ollama error: {error}")

                data = await resp.json()
                return ModelResponse(
                    text=data.get("response", ""),
                    model_used=model,
                    tokens_in=data.get("prompt_eval_count", 0),
                    tokens_out=data.get("eval_count", 0),
                    latency_ms=0,
                    cost_usd=0.0,
                )

    async def _generate_cloud(
        self,
        model: str,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> ModelResponse:
        """Генерация через облачные API"""
        if "claude" in model:
            return await self._generate_anthropic(
                model, prompt, system_prompt, max_tokens, temperature,
            )
        elif "gpt" in model:
            return await self._generate_openai(
                model, prompt, system_prompt, max_tokens, temperature,
            )
        else:
            raise ValueError(f"Unknown cloud model: {model}")

    async def _generate_anthropic(
        self,
        model: str,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> ModelResponse:
        """Генерация через Anthropic Claude"""
        if not settings.anthropic_api_key:
            raise RuntimeError("Anthropic API key not configured")

        async with aiohttp.ClientSession() as session:
            headers = {
                "x-api-key": settings.anthropic_api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            }
            payload = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_prompt:
                payload["system"] = system_prompt

            async with session.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise RuntimeError(f"Anthropic error: {data}")

                text = data["content"][0]["text"]
                tokens_in = data["usage"]["input_tokens"]
                tokens_out = data["usage"]["output_tokens"]

                pricing = self.CLOUD_PRICING.get(
                    model, (0.003, 0.015)
                )
                cost = (
                    (tokens_in / 1000 * pricing[0])
                    + (tokens_out / 1000 * pricing[1])
                )

                return ModelResponse(
                    text=text,
                    model_used=model,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    latency_ms=0,
                    cost_usd=cost,
                )

    async def _generate_openai(
        self,
        model: str,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> ModelResponse:
        """Генерация через OpenAI"""
        if not settings.openai_api_key:
            raise RuntimeError("OpenAI API key not configured")

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            }
            messages = []
            if system_prompt:
                messages.append({
                    "role": "system", "content": system_prompt
                })
            messages.append({"role": "user", "content": prompt})

            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise RuntimeError(f"OpenAI error: {data}")

                text = data["choices"][0]["message"]["content"]
                tokens_in = data["usage"]["prompt_tokens"]
                tokens_out = data["usage"]["completion_tokens"]

                pricing = self.CLOUD_PRICING.get(
                    model, (0.005, 0.015)
                )
                cost = (
                    (tokens_in / 1000 * pricing[0])
                    + (tokens_out / 1000 * pricing[1])
                )

                return ModelResponse(
                    text=text,
                    model_used=model,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    latency_ms=0,
                    cost_usd=cost,
                )

    async def _fallback_generate(
        self,
        prompt: str,
        system_prompt: str,
        failed_decision: RoutingDecision,
        max_tokens: int,
        temperature: float,
    ) -> ModelResponse:
        """Fallback при ошибке основной модели"""
        fallback_chain = [
            "qwen2.5:7b",
            "claude-3-haiku-20240307",
            "gpt-4o-mini",
        ]

        for fallback_model in fallback_chain:
            if fallback_model == failed_decision.model_name:
                continue
            try:
                logger.warning(f"Trying fallback: {fallback_model}")
                tier = self._tier_from_model(fallback_model)
                if tier in (
                    ModelTier.CLOUD_CLAUDE, ModelTier.CLOUD_OPENAI
                ):
                    return await self._generate_cloud(
                        fallback_model, prompt, system_prompt,
                        max_tokens, temperature,
                    )
                else:
                    return await self._generate_local(
                        fallback_model, prompt, system_prompt,
                        max_tokens, temperature,
                    )
            except Exception as e:
                logger.error(f"Fallback {fallback_model} also failed: {e}")
                continue

        raise RuntimeError("All models failed")

    def get_stats(self) -> dict:
        """Статистика использования"""
        return {
            "total_requests": self._request_count,
            "total_cost_usd": round(self._total_cost, 4),
            "gpu_status": "available",
        }
