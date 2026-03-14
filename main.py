import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand  # Добавлен этот импорт

from config import BOT_TOKEN, ADMIN_ID
from database import init_db, async_session
from handlers import client, installer, admin

logging.basicConfig(level=logging.INFO)

async def main():
    # Инициализация бота и диспетчера
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    
    # Подключаем роутеры
    dp.include_router(client.router)
    dp.include_router(installer.router)
    dp.include_router(admin.router)
    
    # Инициализация базы данных
    await init_db()
    
    # Устанавливаем команды бота (исправлено!)
    await bot.set_my_commands([
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="help", description="❓ Помощь"),
        BotCommand(command="new_request", description="📝 Создать заявку"),
        BotCommand(command="my_requests", description="📋 Мои заявки"),
        BotCommand(command="admin", description="👑 Админ панель"),
    ])
    
    # Запуск поллинга
    try:
        print("✅ Бот запущен и готов к работе!")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
