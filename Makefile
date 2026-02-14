.PHONY: help install run test docker-up docker-down status

help: ## Показать справку
@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Установить зависимости
pip install -r requirements.txt
@echo "✅ Зависимости установлены"

setup: ## Полная настройка (установка + модели)
$(MAKE) install
@echo "⚠️ Установите Ollama вручную: curl -fsSL https://ollama.com/install.sh | sh"
@echo "⚠️ Затем: ollama pull qwen2.5:14b && ollama pull qwen2.5:7b"
cp .env.example .env
@echo "✅ Setup завершён. Отредактируйте .env"

run: ## Запустить приложение
python src/main.py

test: ## Запустить тесты
pytest tests/ -v --cov=src --cov-report=html

docker-up: ## Запустить все сервисы через Docker
docker compose up -d --build
@echo "✅ Сервисы запущены"

docker-down: ## Остановить все сервисы
docker compose down
@echo "🛑 Сервисы остановлены"

docker-logs: ## Смотреть логи
docker compose logs -f ai-corp

status: ## Проверить статус системы
@curl -s http://localhost:8000/health | python -m json.tool || echo "❌ API недоступен"

pull-models: ## Скачать модели Ollama
ollama pull qwen2.5:7b
ollama pull qwen2.5:14b
@echo "✅ Модели загружены"

clean: ## Очистить временные файлы
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete
rm -rf .pytest_cache htmlcov .coverage
@echo "🧹 Очищено"
