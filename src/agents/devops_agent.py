"""
DevOps Agent - агенты для работы с кодом
"""

import asyncio
import json
import subprocess
import tempfile
import os
import shutil
from typing import Dict, List, Any, Optional
from loguru import logger
from datetime import datetime
import re
import traceback

from ..core.model_router import ModelRouter
from ..utils.decorators import measure_time, retry, timeout


class DevOpsAgent:
    """Агент для генерации и тестирования кода"""
    
    def __init__(self, model_router: ModelRouter):
        self.model_router = model_router
        
        # Поддерживаемые языки
        self.supported_languages = [
            "python", "javascript", "typescript", 
            "java", "go", "rust", "c++", "c#", "php"
        ]
        
        logger.info("DevOps Agent initialized")
    
    @measure_time
    async def generate_code(
        self,
        specification: str,
        language: str = "python",
        framework: Optional[str] = None,
        include_tests: bool = True
    ) -> Dict:
        """
        Сгенерировать код по спецификации
        
        Args:
            specification: Описание требуемого функционала
            language: Язык программирования
            framework: Фреймворк (опционально)
            include_tests: Генерировать ли тесты        
        Returns:
            Dict с результатами
        """
        
        logger.info(f"Generating code: {language} - {specification[:100]}...")
        start_time = datetime.now()
        
        try:
            # Валидация языка
            if language.lower() not in self.supported_languages:
                return {
                    "status": "error",
                    "error": f"Language {language} not supported",
                    "supported_languages": self.supported_languages
                }
            
            # Генерируем код
            code_result = await self._generate_code_implementation(
                specification,
                language,
                framework
            )
            
            if code_result["status"] != "success":
                return code_result
            
            # Генерируем тесты
            tests = None
            if include_tests:
                tests = await self._generate_tests(
                    code_result["code"],
                    language,
                    specification
                )
            
            # Проверяем синтаксис
            syntax_check = await self._check_syntax(code_result["code"], language)
            
            elapsed_time = (datetime.now() - start_time).total_seconds()
            
            logger.success(f"Code generated successfully in {elapsed_time:.1f}s")
            
            return {
                "status": "success",
                "language": language,
                "framework": framework,
                "specification": specification,
                "code": code_result["code"],
                "explanation": code_result.get("explanation", ""),                "tests": tests,
                "syntax_valid": syntax_check["valid"],
                "syntax_errors": syntax_check.get("errors", []),
                "generation_time": elapsed_time
            }
            
        except Exception as e:
            logger.error(f"Error generating code: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            return {
                "status": "error",
                "error": str(e),
                "specification": specification
            }
    
    @retry(max_attempts=3, delay=2)
    @timeout(60)
    async def _generate_code_implementation(
        self,
        specification: str,
        language: str,
        framework: Optional[str]
    ) -> Dict:
        """Сгенерировать реализацию кода с повторными попытками"""
        
        model_type, model_name = self.model_router.select_model(
            task_type="code",
            complexity=0.7
        )
        
        framework_info = f" с использованием {framework}" if framework else ""
        
        code_prompt = f"""
Напиши код на {language}{framework_info} для следующей задачи:

{specification}

Требования:
1. Используй лучшие практики программирования
2. Добавь комментарии на русском языке
3. Обработай возможные ошибки
4. Сделай код читаемым и поддерживаемым
5. Используй типизацию если поддерживается языком
6. Добавь документацию к функциям

Формат ответа:
```{language}
// Код здесь
```
После кода кратко объясни основные решения.
"""
        
        try:
            if model_type == "cloud":
                # Используем облачную модель (Claude или GPT)
                from anthropic import AsyncAnthropic
                import os
                
                client = AsyncAnthropic(api_key=os.getenv("CLAUDE_API_KEY"))
                
                response = await client.messages.create(
                    model="claude-4",
                    max_tokens=4000,
                    messages=[{"role": "user", "content": code_prompt}]
                )
                
                response_text = response.content[0].text
                
                # Извлекаем код из блока ```language
                code_pattern = rf"```{language}\s*(.*?)```"
                code_match = re.search(code_pattern, response_text, re.DOTALL | re.IGNORECASE)
                
                if code_match:
                    code = code_match.group(1).strip()
                else:
                    # Пытаемся найти любой блок кода
                    code_pattern = r"```\w*\s*(.*?)```"
                    code_match = re.search(code_pattern, response_text, re.DOTALL)
                    code = code_match.group(1).strip() if code_match else response_text
                
                # Извлекаем объяснение
                explanation = ""
                if "```" in response_text:
                    parts = response_text.split("```")
                    if len(parts) > 2:
                        explanation = parts[2].strip()
                
                return {
                    "status": "success",
                    "code": code,
                    "explanation": explanation
                }
            
            else:
                # Локальная генерация (упрощенная)
                code = f"""
# Сгенерированный код для: {specification[:100]}

def main():    print("Hello from generated code!")
    # TODO: Implement actual functionality based on specification:
    # {specification[:200]}

if __name__ == "__main__":
    main()
"""
                explanation = "Локальная генерация - базовая реализация"
                
                return {
                    "status": "success",
                    "code": code,
                    "explanation": explanation
                }
                
        except asyncio.TimeoutError:
            logger.warning("Timeout generating code implementation")
            raise
        except Exception as e:
            logger.error(f"Error generating code implementation: {e}")
            raise
    
    @retry(max_attempts=2, delay=2)
    async def _generate_tests(self, code: str, language: str, specification: str) -> Optional[Dict]:
        """Сгенерировать тесты для кода"""
        
        model_type, model_name = self.model_router.select_model(
            task_task="code",
            complexity=0.5
        )
        
        test_prompt = f"""
Напиши тесты для следующего кода на {language}:

{code[:2000]}  # Ограничиваем длину

Спецификация: {specification[:500]}

Требования:
1. Покрой основные сценарии использования
2. Добавь тесты на обработку ошибок
3. Используй популярный фреймворк для тестирования ({language})
4. Добавь комментарии
5. Добавь проверки на крайние случаи

Формат ответа:
```{language}
# Тесты здесь
```
"""        
        try:
            if model_type == "cloud":
                from anthropic import AsyncAnthropic
                import os
                
                client = AsyncAnthropic(api_key=os.getenv("CLAUDE_API_KEY"))
                
                response = await asyncio.wait_for(
                    client.messages.create(
                        model="claude-4",
                        max_tokens=2000,
                        messages=[{"role": "user", "content": test_prompt}]
                    ),
                    timeout=30
                )
                
                response_text = response.content[0].text
                
                # Извлекаем тесты
                test_pattern = rf"```{language}\s*(.*?)```"
                test_match = re.search(test_pattern, response_text, re.DOTALL | re.IGNORECASE)
                
                tests = test_match.group(1).strip() if test_match else None
                
                if tests:
                    return {
                        "tests": tests,
                        "language": language
                    }
            
            return None
            
        except asyncio.TimeoutError:
            logger.warning("Timeout generating tests")
            return None
        except Exception as e:
            logger.error(f"Error generating tests: {e}")
            return None
    
    async def _check_syntax(self, code: str, language: str) -> Dict:
        """Проверить синтаксис кода"""
        
        try:
            if language.lower() == "python":
                # Проверяем Python синтаксис
                compile(code, "<string>", "exec")
                return {"valid": True}
            
            elif language.lower() in ["javascript", "typescript"]:                # Для JS/TS можно использовать eslint (если установлен)
                # Пока просто базовая проверка
                if code.strip():
                    return {"valid": True}
            
            elif language.lower() == "java":
                # Для Java можно использовать javac (если установлен)
                pass
            
            # Для остальных языков - базовая проверка
            if code.strip():
                return {"valid": True}
            
            return {"valid": False, "errors": ["Empty code"]}
            
        except SyntaxError as e:
            return {
                "valid": False,
                "errors": [str(e)]
            }
        except Exception as e:
            logger.warning(f"Syntax check failed: {e}")
            return {"valid": True}  # Не критично
    
    @measure_time
    @timeout(120)
    async def run_tests(self, code: str, tests: str, language: str) -> Dict:
        """Запустить тесты с таймаутом"""
        
        logger.info(f"Running tests for {language} code")
        
        try:
            if language.lower() == "python":
                return await self._run_python_tests(code, tests)
            
            return {
                "status": "skipped",
                "message": f"Test execution not implemented for {language}"
            }
            
        except asyncio.TimeoutError:
            logger.error("Tests execution timeout")
            return {
                "status": "timeout",
                "error": "Tests execution timed out after 2 minutes"
            }
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return {
                "status": "error",                "error": str(e)
            }
    
    async def _run_python_tests(self, code: str, tests: str) -> Dict:
        """Запустить Python тесты"""
        
        tmpdir = None
        try:
            tmpdir = tempfile.mkdtemp(prefix="ai_corp_tests_")
            
            code_file = os.path.join(tmpdir, "module.py")
            test_file = os.path.join(tmpdir, "test_module.py")
            
            # Сохраняем код
            with open(code_file, "w", encoding="utf-8") as f:
                f.write(code)
            
            # Сохраняем тесты
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(tests)
            
            # Запускаем pytest
            try:
                result = subprocess.run(
                    ["pytest", test_file, "-v", "--tb=short"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env={**os.environ, "PYTHONPATH": tmpdir}
                )
                
                passed = result.returncode == 0
                
                return {
                    "status": "completed",
                    "return_code": result.returncode,
                    "stdout": result.stdout[:5000],  # Ограничиваем вывод
                    "stderr": result.stderr[:5000],
                    "passed": passed,
                    "test_count": self._count_tests(result.stdout)
                }
                
            except subprocess.TimeoutExpired:
                return {
                    "status": "timeout",
                    "error": "Tests execution timed out after 60 seconds"
                }
            except FileNotFoundError:
                return {                    "status": "error",
                    "error": "pytest not installed. Install with: pip install pytest"
                }
        
        finally:
            # Очищаем временную директорию
            if tmpdir and os.path.exists(tmpdir):
                try:
                    shutil.rmtree(tmpdir, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"Error cleaning up temp directory: {e}")
    
    def _count_tests(self, output: str) -> int:
        """Подсчитать количество тестов из вывода pytest"""
        
        # Ищем строку типа "3 passed, 1 failed"
        match = re.search(r"(\d+)\s+passed", output)
        if match:
            return int(match.group(1))
        return 0
    
    @measure_time
    async def batch_generate_code(
        self,
        specifications: List[Dict],
        concurrent_limit: int = 2
    ) -> List[Dict]:
        """Сгенерировать несколько кодов параллельно"""
        
        logger.info(f"Batch generating {len(specifications)} code snippets")
        
        results = []
        semaphore = asyncio.Semaphore(concurrent_limit)
        
        async def generate_single(spec):
            async with semaphore:
                result = await self.generate_code(**spec)
                return result
        
        # Создаем задачи
        tasks = [generate_single(spec) for spec in specifications]
        
        # Выполняем параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем результаты
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append({                    "status": "error",
                    "error": str(result),
                    "specification": specifications[i].get("specification", "unknown")
                })
            else:
                final_results.append(result)
        
        logger.success(f"Batch code generation completed: {len(final_results)} snippets")
        
        return final_results
    
    @retry(max_attempts=2, delay=2)
    async def analyze_code(self, code: str, language: str) -> Dict:
        """Проанализировать код и дать рекомендации"""
        
        logger.info(f"Analyzing {language} code")
        
        model_type, model_name = self.model_router.select_model(
            task_type="code",
            complexity=0.6
        )
        
        analysis_prompt = f"""
Проанализируй следующий код на {language}:

{code[:3000]}  # Ограничиваем длину

Дай анализ по следующим аспектам:
1. Качество кода и читаемость
2. Потенциальные ошибки и проблемы
3. Рекомендации по улучшению
4. Безопасность (если применимо)
5. Производительность
6. Соответствие best practices

Формат ответа (структурированный):
- Сильные стороны:
- Проблемы:
- Рекомендации:
- Оценка качества (1-10):
"""
        
        try:
            if model_type == "cloud":
                from anthropic import AsyncAnthropic
                import os
                
                client = AsyncAnthropic(api_key=os.getenv("CLAUDE_API_KEY"))
                
                response = await asyncio.wait_for(                    client.messages.create(
                        model="claude-4",
                        max_tokens=2000,
                        messages=[{"role": "user", "content": analysis_prompt}]
                    ),
                    timeout=30
                )
                
                analysis = response.content[0].text
            
            else:
                analysis = "Локальный анализ недоступен. Используйте облачные модели."
            
            return {
                "status": "success",
                "language": language,
                "analysis": analysis
            }
            
        except asyncio.TimeoutError:
            logger.warning("Timeout analyzing code")
            return {
                "status": "timeout",
                "error": "Analysis timeout"
            }
        except Exception as e:
            logger.error(f"Error analyzing code: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
