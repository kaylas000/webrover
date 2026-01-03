#!/bin/bash

# Останавливать выполнение при ошибках
set -e

echo "---------------------------------------------------"
echo "🛠 Начинаем полную установку WebRover для разработки"
echo "---------------------------------------------------"

# 1. Проверка необходимых системных утилит
for tool in git python3 curl; do
    if ! command -v $tool &> /dev/null; then
        echo "❌ Ошибка: $tool не установлен. Установите его и попробуйте снова."
        exit 1
    fi
done

# 2. Клонирование исходного кода (если еще нет)
if [ ! -d "core" ]; then
    echo "📂 Клонирование исходного кода WebRover в папку /core..."
    git clone https://github.com/hrithikkoduri/WebRover.git temp_webrover
    mv temp_webrover/backend core
    rm -rf temp_webrover
fi

cd core

# 3. Установка Poetry (изолированный менеджер пакетов)
if ! command -v poetry &> /dev/null; then
    echo "📦 Установка Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi

# 4. Конфигурация Poetry (создание venv внутри проекта для удобства IDE)
poetry config virtualenvs.in-project true

# 5. Установка зависимостей (включая группы для разработки и тестов)
echo "🛠 Установка библиотек и инструментов разработки..."
# Добавляем pytest и black принудительно для будущего расширения
poetry add --group dev pytest pytest-asyncio black isort mypy

# Основная установка
poetry install

# 6. Установка headless-браузеров Playwright
echo "🌐 Загрузка браузеров для Playwright (необходимо для работы агента)..."
poetry run playwright install chromium --with-deps

# 7. Подготовка инфраструктуры для тестирования
echo "🧪 Создание папки для тестов..."
mkdir -p tests
if [ ! -f "tests/test_basic.py" ]; then
    cat <<EOF > tests/test_basic.py
import pytest

def test_environment():
    """Базовый тест проверки окружения"""
    assert True

@pytest.mark.asyncio
async def test_agent_import():
    """Проверка импорта основного модуля"""
    try:
        from main import WebRover
        assert True
    except ImportError:
        pytest.fail("Не удалось импортировать WebRover")
EOF
fi

# 8. Настройка переменных окружения
if [ ! -f ".env" ]; then
    echo "📝 Создание файла .env..."
    echo "OPENAI_API_KEY=your_key_here" > .env
    echo "DATABASE_URL=sqlite:///./test.db" >> .env
    echo ".env создан. НЕ ЗАБУДЬТЕ ДОБАВИТЬ СВОЙ OPENAI_API_KEY!"
fi

echo "---------------------------------------------------"
echo "✅ Установка успешно завершена!"
echo "---------------------------------------------------"
echo "Как работать с программой:"
echo "1. Активировать окружение:    source .venv/bin/activate (или poetry shell)"
echo "2. Запустить тесты:           poetry run pytest"
echo "3. Запустить проект:          poetry run python main.py"
echo "4. Проверить стиль кода:      poetry run black ."
echo "---------------------------------------------------"
