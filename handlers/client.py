from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
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

def get_location_keyboard():
    """Клавиатура для отправки геолокации"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Отправить геолокацию", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

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
    
    # Сбрасываем состояние на всякий случай
    await state.clear()
    
    await message.answer("📝 Опишите, что нужно сделать:")
    await state.set_state(RequestForm.description)
    print(f"Установлено состояние: description для пользователя {message.from_user.id}")

@router.message(RequestForm.description)
async def process_description(message: Message, state: FSMContext):
    """Обработка описания заявки"""
    print(f"Обработка описания от {message.from_user.id}: {message.text}")
    
    # Сохраняем описание
    await state.update_data(description=message.text)
    
    # Переходим к следующему шагу
    await message.answer(
        "📸 Теперь отправьте фотографию (можно несколько).\n"
        "Когда закончите, отправьте /done"
    )
    await state.set_state(RequestForm.photos)
    await state.update_data(photos=[])
    
    print(f"Переключено состояние на: photos")

@router.message(RequestForm.photos, F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Обработка фотографий"""
    data = await state.get_data()
    photos = data.get('photos', [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"✅ Фото добавлено. Всего: {len(photos)}. Отправьте ещё или /done")

@router.message(RequestForm.photos, Command("done"))
async def photos_done(message: Message, state: FSMContext):
    """Завершение загрузки фотографий"""
    data = await state.get_data()
    if not data.get('photos'):
        await message.answer("❌ Нужно отправить хотя бы одно фото!")
        return
    
    await message.answer(
        "📍 Выберите способ указания адреса:",
        reply_markup=get_geo_choice_keyboard()
    )
    await state.set_state(RequestForm.address_choice)

@router.callback_query(F.data == "send_geo")
async def address_choice_geo(callback: CallbackQuery, state: FSMContext):
    """Выбор отправки геолокации"""
    await callback.message.delete()
    await callback.message.answer(
        "📍 Отправьте вашу геолокацию, нажав на кнопку ниже:",
        reply_markup=get_location_keyboard()
    )
    await state.set_state(RequestForm.location)
    await callback.answer()

@router.callback_query(F.data == "manual_address")
async def address_choice_manual(callback: CallbackQuery, state: FSMContext):
    """Выбор ручного ввода адреса"""
    await callback.message.delete()
    await callback.message.answer(
        "✍️ Введите адрес текстом:"
    )
    await state.set_state(RequestForm.manual_address)
    await callback.answer()

@router.message(RequestForm.location, F.location)
async def process_location(message: Message, state: FSMContext):
    """Обработка полученной геолокации"""
    latitude = message.location.latitude
    longitude = message.location.longitude
    
    await state.update_data(
        latitude=latitude,
        longitude=longitude
    )
    
    processing_msg = await message.answer("🔄 Получаем адрес по координатам...")
    
    address = await reverse_geocode(latitude, longitude)
    
    await processing_msg.delete()
    
    if address:
        await state.update_data(
            address=address,
            location_address=address
        )
        
        await message.answer(
            f"📍 Найден адрес:\n<code>{address}</code>\n\n"
            f"Всё верно?",
            reply_markup=get_confirm_address_keyboard()
        )
    else:
        await message.answer(
            "❌ Не удалось определить адрес по координатам.\n"
            "Пожалуйста, введите адрес вручную:"
        )
        await state.set_state(RequestForm.manual_address)

@router.callback_query(F.data == "confirm_address")
async def confirm_address(callback: CallbackQuery, state: FSMContext):
    """Подтверждение адреса"""
    await callback.message.delete()
    await callback.message.answer(
        "✅ Адрес подтвержден.\n"
        "📞 Теперь введите номер телефона для связи:"
    )
    await state.set_state(RequestForm.phone)
    await callback.answer()

@router.callback_query(F.data == "edit_address")
async def edit_address(callback: CallbackQuery, state: FSMContext):
    """Редактирование адреса"""
    await callback.message.delete()
    await callback.message.answer(
        "✍️ Введите правильный адрес текстом:"
    )
    await state.set_state(RequestForm.manual_address)
    await callback.answer()

@router.message(RequestForm.manual_address)
async def process_manual_address(message: Message, state: FSMContext):
    """Обработка ручного ввода адреса"""
    await state.update_data(address=message.text)
    await message.answer("📞 Введите ваш номер телефона для связи:")
    await state.set_state(RequestForm.phone)

@router.message(RequestForm.phone)
async def process_phone(message: Message, state: FSMContext):
    """Обработка номера телефона"""
    phone = message.text
    await state.update_data(phone=phone)
    
    await message.answer(
        "🏘 Выберите район:",
        reply_markup=await districts_keyboard()
    )
    await state.set_state(RequestForm.district)

@router.callback_query(RequestForm.district, F.data.startswith("district_"))
async def process_district(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора района и создание заявки"""
    district_id = int(callback.data.split("_")[1])
    data = await state.get_data()
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one()
        
        request = Request(
            client_id=user.id,
            description=data['description'],
            photo_file_id=','.join(data['photos']),
            address=data.get('address') or data.get('location_address'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            location_address=data.get('location_address'),
            contact_phone=data['phone'],
            district_id=district_id
        )
        session.add(request)
        await session.flush()
        
        from handlers.installer import send_request_to_group
        await send_request_to_group(callback.bot, request, session)
        
        await session.commit()
    
    await callback.message.edit_text(
        f"✅ Заявка №{request.id} создана и отправлена монтажникам!\n"
        "Мы уведомим вас, когда её возьмут в работу."
    )
    await state.clear()
    await callback.answer()
