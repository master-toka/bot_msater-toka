import asyncio
import logging
import ssl
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, Update
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import BOT_TOKEN, WEBHOOK_DOMAIN, WEBHOOK_PATH, WEB_SERVER_HOST, WEB_SERVER_PORT, SSL_CERT, SSL_KEY
from database import init_db
from handlers import client, installer, admin

logging.basicConfig(level=logging.INFO)

# URL для вебхука
WEBHOOK_URL = f"{WEBHOOK_DOMAIN}{WEBHOOK_PATH}"

async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    # Устанавливаем вебхук
    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True,  # Пропустить старые обновления
        max_connections=40,  # Максимальное количество одновременных соединений
        allowed_updates=["message", "callback_query"]  # Только нужные типы обновлений
    )
    print(f"✅ Webhook установлен на {WEBHOOK_URL}")
    
    # Устанавливаем команды бота
    await bot.set_my_commands([
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="help", description="❓ Помощь"),
        BotCommand(command="new_request", description="📝 Создать заявку"),
        BotCommand(command="my_requests", description="📋 Мои заявки"),
        BotCommand(command="admin", description="👑 Админ панель"),
    ])
    
    # Инициализация базы данных
    await init_db()
    print("✅ База данных инициализирована")

async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    # Удаляем вебхук
    await bot.delete_webhook()
    print("❌ Webhook удален")

async def main():
    """Основная функция"""
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
    
    # Регистрируем функции запуска и остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Создаем aiohttp приложение
    app = web.Application()
    
    # Настраиваем обработчик вебхуков
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    
    # Регистрируем путь для вебхуков
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # Настраиваем приложение
    setup_application(app, dp, bot=bot)
    
    # Настройка SSL (если используется)
    ssl_context = None
    if SSL_CERT and SSL_KEY:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(SSL_CERT, SSL_KEY)
    
    print(f"✅ Бот запущен в режиме webhook на порту {WEB_SERVER_PORT}")
    print(f"🌐 Webhook URL: {WEBHOOK_URL}")
    
    # Запускаем веб-сервер
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT, ssl_context=ssl_context)
    await site.start()
    
    # Держим приложение запущенным
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
