import os
from dotenv import load_dotenv
from pathlib import Path

# Загружаем .env
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# Получаем переменные
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID_STR = os.getenv("GROUP_ID")
ADMIN_ID_STR = os.getenv("ADMIN_ID")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///montazh_bot.db")
GEOCODER_API_KEY = os.getenv("GEOCODER_API_KEY")

# Настройки webhook
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN", "https://example.com")  # Ваш домен
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")  # Путь для вебхука
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "my-secret-key")  # Секретный ключ для безопасности

# Настройки веб-сервера
WEB_SERVER_HOST = os.getenv("WEB_SERVER_HOST", "0.0.0.0")  # Слушаем все интерфейсы
WEB_SERVER_PORT = int(os.getenv("WEB_SERVER_PORT", "8080"))  # Порт

# SSL сертификаты (если используете свой сертификат, а не прокси)
SSL_CERT = os.getenv("SSL_CERT", None)  # Путь к SSL сертификату
SSL_KEY = os.getenv("SSL_KEY", None)  # Путь к ключу SSL

# Список районов
DISTRICTS = [
    "Советский",
    "Железнодорожный", 
    "Октябрьский",
    "Иволгинский",
    "Тарбагатайский",
    "Заиграевский"
]

# Проверяем и преобразуем
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

if not GROUP_ID_STR:
    raise ValueError("❌ GROUP_ID не найден в .env файле!")

if not ADMIN_ID_STR:
    raise ValueError("❌ ADMIN_ID не найден в .env файле!")

try:
    GROUP_ID = int(GROUP_ID_STR)
    ADMIN_ID = int(ADMIN_ID_STR)
except ValueError as e:
    raise ValueError(f"❌ Ошибка преобразования ID: {e}")

print("✅ Конфигурация загружена успешно!")
print(f"🌐 Webhook будет доступен по адресу: {WEBHOOK_DOMAIN}{WEBHOOK_PATH}")
