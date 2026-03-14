from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database import async_session, District

def get_geo_choice_keyboard():
    """Клавиатура выбора способа указания адреса"""
    buttons = [
        [InlineKeyboardButton(text="📍 Отправить геолокацию", callback_data="send_geo")],
        [InlineKeyboardButton(text="✍️ Ввести адрес вручную", callback_data="manual_address")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_confirm_address_keyboard():
    """Клавиатура подтверждения адреса"""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Да, верно", callback_data="confirm_address"),
            InlineKeyboardButton(text="✍️ Ввести вручную", callback_data="edit_address")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def districts_keyboard():
    """Клавиатура выбора района (асинхронная)"""
    async with async_session() as session:
        result = await session.execute(select(District).order_by(District.name))
        districts = result.scalars().all()
    
    buttons = []
    row = []
    for i, district in enumerate(districts):
        row.append(
            InlineKeyboardButton(
                text=district.name,
                callback_data=f"district_{district.id}"
            )
        )
        if (i + 1) % 2 == 0:  # по 2 кнопки в ряд
            buttons.append(row)
            row = []
    if row:  # добавляем оставшиеся кнопки
        buttons.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_request_action_keyboard(request_id: int):
    """Клавиатура для заявки в группе (Взять/Отказаться)"""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Взять", callback_data=f"take_{request_id}"),
            InlineKeyboardButton(text="❌ Отказаться", callback_data=f"refuse_{request_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_installer_requests_keyboard(requests):
    """Клавиатура со списком заявок монтажника"""
    buttons = []
    for req in requests:
        # Обрезаем адрес до 30 символов
        address_short = req.address[:30] + "..." if len(req.address) > 30 else req.address
        buttons.append([
            InlineKeyboardButton(
                text=f"📋 Заявка №{req.id} - {address_short}",
                callback_data=f"view_{req.id}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_complete_keyboard(request_id: int):
    """Клавиатура для завершения заявки"""
    buttons = [
        [InlineKeyboardButton(text="✅ Подтвердить завершение", callback_data=f"complete_{request_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_list")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_keyboard():
    """Клавиатура для админ-панели"""
    buttons = [
        [InlineKeyboardButton(text="📊 Общая статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🏘 По районам", callback_data="admin_districts")],
        [InlineKeyboardButton(text="👷 По монтажникам", callback_data="admin_installers")],
        [InlineKeyboardButton(text="📅 За период", callback_data="admin_period")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_keyboard():
    """Клавиатура с кнопкой 'Назад'"""
    buttons = [
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
