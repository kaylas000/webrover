# 🤖 ИИ-Корпорация 2.0

**Автономная многоагентная система на базе AI** — автоматизирует до 70% рутинных задач команды из 5-7 специалистов.

## 🚀 Возможности

### Контент
- ✍️ Генерация SEO-статей (до 10 000 слов)
- 🌐 Перевод на 12 языков
- 📝 Суммаризация текстов
- 🔍 SEO-оптимизация

### Разработка
- 💻 Генерация production-ready кода (9 языков)
- 🧪 Unit-тесты (pytest, Jest)
- 👀 Code review с оценкой
- 📚 Автоматическая документация

### Координация
- 🎯 CEO-агент разбивает миссии на подзадачи
- ⚡ Параллельное выполнение до 3 задач
- 🔄 Автоматический retry при ошибках
- 📊 Отчёты о выполнении

## 📋 Требования

- GPU: NVIDIA RTX 4090 (24 ГБ VRAM)
- RAM: 64 ГБ
- Storage: 1 ТБ SSD
- OS: Ubuntu 22.04/24.04
- Python: 3.11+

## 🛠 Установка

```bash
git clone https://github.com/kaylas000/webrover.git
cd webrover
cp .env.example .env
make install
make pull-models
```

## 🚀 Запуск

```bash
# Локально
python src/main.py

# Docker
make docker-up
```

## 📱 Telegram Bot

1. Создайте бота через @BotFather
2. Укажите токен в .env
3. Напишите /start

## 🌐 API

- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health

## 📚 Документация

Полная документация в [docs/README.md](docs/README.md)

## 📝 Лицензия

MIT License
