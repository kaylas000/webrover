"""
Telegram Bot - интерфейс управления ИИ-Корпорацией
"""

import asyncio
import logging
from typing import Dict, Optional, Callable
from loguru import logger
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import json

from ..agents.ceo_agent import CEOAgent
from ..core.task_queue import TaskQueue


class TelegramBot:
    """Telegram бот для управления ИИ-Корпорацией"""
    
    def __init__(
        self,
        token: str,
        ceo_agent: Optional[CEOAgent] = None,
        task_queue: Optional[TaskQueue] = None
    ):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        
        self.ceo_agent = ceo_agent
        self.task_queue = task_queue
        
        # Администраторы бота
        self.admins: list = []
        
        # Регистрируем обработчики
        self._register_handlers()
        
        logger.info("Telegram Bot initialized")
    
    def _register_handlers(self):
        """Регистрация обработчиков команд"""
        
        @self.dp.message(Command("start"))
        async def cmd_start(message: types.Message):
            """Обработчик команды /start"""
            await self._handle_start(message)
        
        @self.dp.message(Command("status"))        async def cmd_status(message: types.Message):
            """Обработчик команды /status"""
            await self._handle_status(message)
        
        @self.dp.message(Command("missions"))
        async def cmd_missions(message: types.Message):
            """Обработчик команды /missions"""
            await self._handle_missions(message)
        
        @self.dp.message(Command("help"))
        async def cmd_help(message: types.Message):
            """Обработчик команды /help"""
            await self._handle_help(message)
        
        @self.dp.callback_query(lambda c: c.data.startswith("approve_"))
        async def handle_approve(callback_query: types.CallbackQuery):
            """Обработчик подтверждения задач"""
            await self._handle_approve(callback_query)
        
        @self.dp.callback_query(lambda c: c.data.startswith("reject_"))
        async def handle_reject(callback_query: types.CallbackQuery):
            """Обработчик отклонения задач"""
            await self._handle_reject(callback_query)
        
        @self.dp.message()
        async def handle_text(message: types.Message):
            """Обработчик текстовых сообщений"""
            await self._handle_text(message)
    
    async def _handle_start(self, message: types.Message):
        """Обработчик команды /start"""
        
        welcome_text = """
🤖 Добро пожаловать в ИИ-Корпорацию!

Я - ваш личный ассистент для управления автоматизированной командой ИИ-агентов.

📋 Доступные команды:
• /start - Начать работу
• /status - Статус системы
• /missions - Список миссий
• /help - Помощь

💬 Просто напишите задачу, и я передам её команде!
        
Примеры задач:
• "Создай 5 статей про криптовалюты"
• "Обнови кликер-игру, добавь систему достижений"
• "Сделай баннеры и посты для соцсетей"
        """        
        await message.answer(welcome_text)
    
    async def _handle_status(self, message: types.Message):
        """Обработчик команды /status"""
        
        if not self.ceo_agent or not self.task_queue:
            await message.answer("⚠️ Система не инициализирована")
            return
        
        # Получаем статус
        queue_status = self.task_queue.get_queue_status()
        
        status_text = f"""
📊 Статус ИИ-Корпорации

Очередь задач:
• Всего задач: {queue_status["total_tasks"]}
• В ожидании: {queue_status["pending_tasks"]}
• В работе: {queue_status["running_tasks"]}
• Максимум одновременно: {queue_status["max_concurrent"]}

Загруженные модели:
"""
        
        # Добавляем информацию о моделях
        if self.ceo_agent and hasattr(self.ceo_agent.model_router, "gpu_manager"):
            gpu_status = self.ceo_agent.model_router.gpu_manager.get_status()
            status_text += f"\nВидеопамять:"
            status_text += f"\n• Использовано: {gpu_status["used_vram_gb"]:.1f} ГБ"
            status_text += f"\n• Доступно: {gpu_status["available_vram_gb"]:.1f} ГБ"
            status_text += f"\n• Загружено моделей: {gpu_status["model_count"]}"
        
        await message.answer(status_text)
    
    async def _handle_missions(self, message: types.Message):
        """Обработчик команды /missions"""
        
        if not self.ceo_agent:
            await message.answer("⚠️ CEO агент не инициализирован")
            return
        
        missions = self.ceo_agent.get_all_missions()
        
        if not missions:
            await message.answer("📭 Нет активных миссий")
            return
        
        missions_text = "📋 Список миссий:\n\n"
                for mission in missions[-10:]:  # Последние 10 миссий
            status_emoji = {
                "pending": "⏳",
                "running": "🚀",
                "completed": "✅",
                "failed": "❌"
            }.get(mission["status"], "❓")
            
            missions_text += f"{status_emoji} {mission["id"]}\n"
            missions_text += f"   Описание: {mission["description"][:50]}...\n"
            missions_text += f"   Статус: {mission["status"]}\n\n"
        
        await message.answer(missions_text)
    
    async def _handle_help(self, message: types.Message):
        """Обработчик команды /help"""
        
        help_text = """
📖 Помощь по ИИ-Корпорации

🎯 Как работать с ботом:

1. Просто напишите задачу на русском языке
   Пример: "Создай статью про блокчейн"

2. Укажите параметры через запятые
   Пример: "5 статей, криптовалюты, 2000 слов"

3. Используйте команды:
   • /status - проверить статус системы
   • /missions - список миссий
   • /help - эта справка

💡 Типы задач:
• Контент: статьи, посты, переводы
• Код: программы, скрипты, функции
• Дизайн: баннеры, изображения
• Маркетинг: посты, аналитика

⚡ Система автоматически:
• Разобьет задачу на подзадачи
• Распределит между агентами
• Отправит на утверждение при необходимости
• Отправит результат

❓ Вопросы? Напишите "помощь" или "примеры"
        """
        
        await message.answer(help_text)
        async def _handle_text(self, message: types.Message):
        """Обработчик текстовых сообщений"""
        
        user_text = message.text.strip()
        
        # Проверяем служебные команды
        if user_text.lower() in ["помощь", "help"]:
            await self._handle_help(message)
            return
        
        if user_text.lower() in ["статус", "status"]:
            await self._handle_status(message)
            return
        
        if user_text.lower() in ["миссии", "missions"]:
            await self._handle_missions(message)
            return
        
        if user_text.lower() in ["примеры", "examples"]:
            await self._handle_examples(message)
            return
        
        # Обрабатываем как новую миссию
        await self._handle_new_mission(message, user_text)
    
    async def _handle_examples(self, message: types.Message):
        """Показать примеры задач"""
        
        examples_text = """
📝 Примеры задач для ИИ-Корпорации:

📋 Контент:
• "Напиши статью про искусственный интеллект, 1500 слов"
• "Создай 5 постов для Телеграм о криптовалютах"
• "Переведи этот текст на английский"

💻 Код:
• "Напиши функцию на Python для генерации паролей"
• "Создай React компонент для формы регистрации"
• "Напиши скрипт для парсинга веб-сайта"

🎨 Дизайн:
• "Создай баннер 1200x600 для статьи о технологиях"
• "Сделай обложку для поста в соцсетях"

🎮 Игры:
• "Добавь в кликер систему достижений"
• "Создай новую механику для блокчейн-игры"

📊 Аналитика:• "Проанализируй статистику за неделю"
• "Сделай отчет по эффективности постов"

Просто напишите задачу, и я передам её команде! 🚀
        """
        
        await message.answer(examples_text)
    
    async def _handle_new_mission(self, message: types.Message, description: str):
        """Обработать новую миссию"""
        
        if not self.ceo_agent:
            await message.answer("⚠️ CEO агент не инициализирован")
            return
        
        # Отправляем сообщение о принятии задачи
        processing_msg = await message.answer("🚀 Принимаю задачу, анализирую...")
        
        try:
            # Передаем задачу CEO агенту
            mission_id = await self.ceo_agent.receive_mission(
                description=description,
                user_id=str(message.from_user.id)
            )
            
            # Отправляем подтверждение
            await processing_msg.edit_text(
                f"✅ Задача принята!\n"
                f"📋 ID миссии: {mission_id}\n"
                f"📝 Описание: {description}\n\n"
                f"Я начну выполнение и сообщу о результатах."
            )
            
            # Отправляем кнопки для отслеживания
            keyboard = InlineKeyboardBuilder()
            keyboard.add(InlineKeyboardButton(
                text="Проверить статус",
                callback_data=f"check_{mission_id}"
            ))
            
            await message.answer(
                "Хотите отслеживать выполнение?",
                reply_markup=keyboard.as_markup()
            )
            
        except Exception as e:
            logger.error(f"Error handling mission: {e}")
            await processing_msg.edit_text(
                f"❌ Ошибка при обработке задачи:\n{str(e)}"
            )    
    async def _handle_approve(self, callback_query: types.CallbackQuery):
        """Обработчик подтверждения"""
        
        task_id = callback_query.data.replace("approve_", "")
        
        await callback_query.answer("✅ Задача подтверждена!")
        
        # Здесь можно добавить логику подтверждения задачи
        logger.info(f"Task {task_id} approved by user")
        
        await callback_query.message.edit_text(
            f"✅ Задача {task_id} подтверждена и продолжит выполнение."
        )
    
    async def _handle_reject(self, callback_query: types.CallbackQuery):
        """Обработчик отклонения"""
        
        task_id = callback_query.data.replace("reject_", "")
        
        await callback_query.answer("❌ Задача отклонена")
        
        # Здесь можно добавить логику отклонения задачи
        logger.info(f"Task {task_id} rejected by user")
        
        await callback_query.message.edit_text(
            f"❌ Задача {task_id} отклонена. Пожалуйста, укажите причину или отправьте исправленную версию."
        )
    
    async def send_notification(
        self,
        user_id: str,
        message: str,
        keyboard: Optional[InlineKeyboardMarkup] = None
    ):
        """Отправить уведомление пользователю"""
        
        try:
            if keyboard:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    reply_markup=keyboard
                )
            else:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=message
                )
        except Exception as e:            logger.error(f"Error sending notification to {user_id}: {e}")
    
    async def send_mission_complete(
        self,
        user_id: str,
        mission_id: str,
        report: Dict
    ):
        """Отправить отчет о завершении миссии"""
        
        report_text = f"""
🎉 Миссия {mission_id} завершена!

📊 Отчет:
• Всего задач: {report.get("total_tasks", 0)}
• Успешно: {report.get("completed_tasks", 0)}
• Ошибок: {report.get("failed_tasks", 0)}
• Успешность: {report.get("success_rate", "0%")}

🕐 Время выполнения: {report.get("completed_at", "N/A")}

Результаты готовы к просмотру!
        """
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(
            text="Посмотреть результаты",
            callback_data=f"results_{mission_id}"
        ))
        
        await self.send_notification(
            user_id,
            report_text,
            keyboard.as_markup()
        )
    
    async def run(self):
        """Запустить бота"""
        
        logger.info("Starting Telegram Bot...")
        
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Error running Telegram Bot: {e}")
            raise
    
    async def stop(self):
        """Остановить бота"""        
        logger.info("Stopping Telegram Bot...")
        await self.bot.session.close()
