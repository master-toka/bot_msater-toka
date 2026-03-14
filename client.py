from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InputMediaPhoto
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session, User, Request, District, GroupMessage
from keyboards.inline import districts_keyboard, get_geo_choice_keyboard, get_confirm_address_keyboard
from config import GROUP_ID
from utils.geocoder import reverse_geocode

router = Router()

class RequestForm(StatesGroup):
    description = State()
    photos = State()
    address_choice = State()
    manual_address = State()
    location = State()
    phone = State()
    district = State()

# Функции для отображения меню
async def show_client_menu(message: Message):
    """Показать меню заказчика"""
    await message.answer(
        "👤 <b>Меню заказчика</b>\n\n"
        "Доступные команды:\n"
        "📝 /new_request - Создать новую заявку\n"
        "📋 /my_requests - Мои заявки\n"
        "❓ /help - Помощь",
        parse_mode="HTML"
    )

async def show_installer_menu(message: Message):
    """Показать меню монтажника"""
    await message.answer(
        "🔧 <b>Меню монтажника</b>\n\n"
        "Доступные команды:\n"
        "📋 /my_requests - Мои заявки в работе\n"
        "📊 /stats - Моя статистика\n"
        "❓ /help - Помощь",
        parse_mode="HTML"
    )

async def show_admin_menu(message: Message):
    """Показать меню администратора"""
    await message.answer(
        "👑 <b>Панель администратора</b>\n\n"
        "Доступные команды:\n"
        "📊 /admin - Статистика\n"
        "📋 /all_requests - Все заявки\n"
        "👥 /users - Пользователи",
        parse_mode="HTML"
    )

def get_role_keyboard():
    """Клавиатура выбора роли"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = [
        [InlineKeyboardButton(text="👤 Я заказчик", callback_data="role_client")],
        [InlineKeyboardButton(text="🔧 Я монтажник", callback_data="role_installer")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Новый пользователь - предлагаем выбрать роль
            await message.answer(
                "👋 Добро пожаловать в бот для заказа монтажных работ!\n\n"
                "Выберите вашу роль:",
                reply_markup=get_role_keyboard()
            )
        else:
            # Существующий пользователь - показываем соответствующее меню
            if user.is_admin:
                await show_admin_menu(message)
            elif user.role == 'client':
                await show_client_menu(message)
            elif user.role == 'installer':
                await show_installer_menu(message)

@router.callback_query(F.data.startswith("role_"))
async def process_role(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора роли при регистрации"""
    role = callback.data.split("_")[1]
    
    async with async_session() as session:
        # Проверяем, может это админ
        from config import ADMIN_ID
        is_admin = (callback.from_user.id == ADMIN_ID)
        
        user = User(
            telegram_id=callback.from_user.id,
            role=role,
            name=callback.from_user.full_name,
            username=callback.from_user.username,
            is_admin=is_admin
        )
        session.add(user)
        await session.commit()
    
    await callback.message.edit_text(
        f"✅ Вы зарегистрированы как {'заказчик' if role == 'client' else 'монтажник'}!\n"
        "Используйте /start для входа в меню."
    )
    await callback.answer()

@router.message(Command("new_request"))
async def cmd_new_request(message: Message, state: FSMContext):
    """Создание новой заявки"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user or user.role != 'client':
            await message.answer("❌ Эта команда доступна только заказчикам.")
            return
    
    await message.answer("📝 Опишите, что нужно сделать:")
    await state.set_state(RequestForm.description)

# ... остальной код client.py (process_description, process_photo и т.д.) ...
