"""
ИИ-Корпорация 2.0 — Telegram Bot
Основной интерфейс управления через Telegram
"""
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger

from src.core.config import settings
from src.agents.ceo_agent import CEOAgent


class TelegramInterface:
    """Telegram бот для управления ИИ-Корпорацией"""

    def __init__(self, ceo: CEOAgent):
        self.bot = Bot(token=settings.telegram_bot_token)
        self.dp = Dispatcher()
        self.ceo = ceo
        self._active_missions: dict[int, str] = {}
        self._setup_handlers()

    def _setup_handlers(self):
        """Регистрация обработчиков команд"""

        @self.dp.message(Command("start"))
        async def cmd_start(message: types.Message):
            await message.answer(
                "🤖 **ИИ-Корпорация 2.0**\n\n"
                "Я — ваша AI-команда. Отправьте мне задачу:\n\n"
                "📝 Просто напишите что нужно сделать\n"
                "📊 /status — статус системы\n"
                "📋 /missions — активные миссии\n"
                "❓ /help — справка\n\n"
                "Примеры:\n"
                "• \"Напиши статью про нейросети на 2000 слов\"\n"
                "• \"Создай REST API на Python для todo-приложения\"\n"
                "• \"Переведи текст на английский: ...\"",
                parse_mode=ParseMode.MARKDOWN,
            )

        @self.dp.message(Command("status"))
        async def cmd_status(message: types.Message):
            if not self._is_admin(message.from_user.id):
                await message.answer("⛔ Доступ только для администратора")
                return

            gpu_status = await self.ceo.router.gpu.get_status()
            queue_stats = self.ceo.task_queue.get_stats()
            router_stats = self.ceo.router.get_stats()

            text = (
                f"📊 **Статус системы**\n\n"
                f"🖥 **GPU:**\n"
                f"  VRAM: {gpu_status.used_vram_gb:.1f}/{gpu_status.total_vram_gb:.1f} GB\n"
                f"  Температура: {gpu_status.temperature}°C\n"
                f"  Загрузка: {gpu_status.utilization}%\n"
                f"  Модели: {', '.join(gpu_status.loaded_models) or 'нет'}\n\n"
                f"📋 **Очередь:**\n"
                f"  Активных: {queue_stats['active_tasks']}\n"
                f"  В очереди: {queue_stats['pending_tasks']}\n"
                f"  Выполнено: {queue_stats['total_completed']}\n"
                f"  Ошибок: {queue_stats['total_failed']}\n\n"
                f"💰 **Расходы:** ${router_stats['total_cost_usd']:.4f}\n"
                f"📨 **Запросов:** {router_stats['total_requests']}"
            )
            await message.answer(text, parse_mode=ParseMode.MARKDOWN)

        @self.dp.message(Command("missions"))
        async def cmd_missions(message: types.Message):
            tasks = self.ceo.task_queue.get_all_tasks()
            if not tasks:
                await message.answer("📋 Нет активных миссий")
                return

            text = "📋 **Миссии:**\n\n"
            status_emoji = {
                "pending": "⏳", "running": "🔄", "completed": "✅",
                "failed": "❌", "retrying": "🔁",
            }
            for t in tasks[-10:]:
                emoji = status_emoji.get(t["status"], "❓")
                duration = f" ({t['duration']:.0f}s)" if t.get("duration") else ""
                text += f"{emoji} `{t['id']}` {t['name'][:40]}{duration}\n"

            await message.answer(text, parse_mode=ParseMode.MARKDOWN)

        @self.dp.message(Command("help"))
        async def cmd_help(message: types.Message):
            await message.answer(
                "❓ **Справка**\n\n"
                "**Контент:**\n"
                "• \"Напиши статью про [тема]\"\n"
                "• \"Переведи на [язык]: [текст]\"\n"
                "• \"Суммаризуй: [текст]\"\n\n"
                "**Код:**\n"
                "• \"Напиши [язык] код для [задача]\"\n"
                "• \"Проведи code review: [код]\"\n"
                "• \"Напиши тесты для: [код]\"\n\n"
                "**Команды:**\n"
                "/status — статус системы\n"
                "/missions — список миссий",
                parse_mode=ParseMode.MARKDOWN,
            )

        @self.dp.message(F.text)
        async def handle_message(message: types.Message):
            """Обработка произвольных сообщений как миссий"""
            if not self._is_admin(message.from_user.id):
                await message.answer("⛔ Доступ только для администратора")
                return

            user_text = message.text.strip()
            if len(user_text) < 10:
                await message.answer("📝 Задача слишком короткая (минимум 10 символов)")
                return

            builder = InlineKeyboardBuilder()
            builder.button(text="✅ Запустить", callback_data="confirm_mission")
            builder.button(text="❌ Отменить", callback_data="cancel_mission")

            self._active_missions[message.from_user.id] = user_text

            await message.answer(
                f"🎯 **Новая миссия:**\n\n{user_text[:500]}\n\nЗапустить?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=builder.as_markup(),
            )

        @self.dp.callback_query(F.data == "confirm_mission")
        async def confirm_mission(callback: types.CallbackQuery):
            user_id = callback.from_user.id
            mission_text = self._active_missions.pop(user_id, None)

            if not mission_text:
                await callback.answer("Миссия не найдена")
                return

            await callback.answer("🚀 Миссия запущена!")
            await callback.message.edit_text(
                f"🚀 **Миссия запущена!**\n\n{mission_text[:300]}...\n\n⏳ Ожидайте результатов...",
                parse_mode=ParseMode.MARKDOWN,
            )

            async def progress_callback(update_text: str):
                try:
                    await self.bot.send_message(user_id, update_text, parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    logger.error(f"Progress callback error: {e}")

            async def run_mission():
                return await self.ceo.execute(mission_text, callback=progress_callback)

            from src.core.config import Priority
            task_id = await self.ceo.task_queue.submit(
                name=f"Mission: {mission_text[:50]}",
                handler=run_mission,
                priority=Priority.HIGH,
                callback=lambda task: self._send_result(user_id, task),
            )

            await self.bot.send_message(user_id, f"📋 ID: `{task_id}`", parse_mode=ParseMode.MARKDOWN)

        @self.dp.callback_query(F.data == "cancel_mission")
        async def cancel_mission(callback: types.CallbackQuery):
            self._active_missions.pop(callback.from_user.id, None)
            await callback.answer("Миссия отменена")
            await callback.message.edit_text("❌ Миссия отменена")

    async def _send_result(self, user_id: int, task):
        """Отправка результата миссии"""
        try:
            if task.status.value == "completed" and task.result:
                result = task.result
                if result.success:
                    report = result.data.get("report", "Миссия выполнена")
                    cost = result.data.get("total_cost", 0)
                    text = (
                        f"✅ **Миссия выполнена!**\n\n{report[:3000]}\n\n"
                        f"💰 Стоимость: ${cost:.4f}\n⏱ Время: {task.duration:.0f}с"
                    )
                else:
                    text = f"❌ **Ошибка:**\n\n{result.error}"
            else:
                text = f"❌ **Не выполнена:**\n\n{task.error or 'Unknown error'}"

            if len(text) > 4096:
                chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
                for chunk in chunks:
                    await self.bot.send_message(user_id, chunk, parse_mode=ParseMode.MARKDOWN)
            else:
                await self.bot.send_message(user_id, text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Failed to send result: {e}")

    def _is_admin(self, user_id: int) -> bool:
        return user_id == settings.telegram_admin_id

    async def start(self):
        """Запуск бота"""
        logger.info("Starting Telegram bot...")
        await self.dp.start_polling(self.bot)

    async def stop(self):
        """Остановка бота"""
        await self.bot.session.close()
