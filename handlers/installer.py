from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext  # Этого импорта не хватает
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from aiogram.types import InputMediaPhoto

from database import async_session, User, Request, Refusal, GroupMessage, District
from keyboards.inline import get_complete_keyboard, get_installer_requests_keyboard

router = Router()

async def send_request_to_group(bot, request: Request, session: AsyncSession):
    """Отправка заявки в группу монтажников"""
    from config import GROUP_ID
    from keyboards.inline import get_request_action_keyboard
    
    # Получаем название района
    district = await session.get(District, request.district_id)
    
    # Формируем текст заявки
    text = (
        f"🔔 <b>Новая заявка №{request.id}</b>\n\n"
        f"👤 Клиент: {request.client.name}\n"
        f"📞 Телефон: {request.contact_phone}\n"
        f"📍 Район: {district.name}\n"
        f"🏠 Адрес: {request.address or 'Не указан'}\n"
        f"📝 Описание: {request.description}\n\n"
        f"Статус: 🆕 Новая"
    )
    
    # Отправляем сообщение с фото
    if request.photo_file_id:
        photo_ids = request.photo_file_id.split(',')
        if len(photo_ids) > 1:
            media_group = []
            for i, photo_id in enumerate(photo_ids):
                if i == 0:
                    media_group.append(
                        InputMediaPhoto(
                            media=photo_id,
                            caption=text
                        )
                    )
                else:
                    media_group.append(InputMediaPhoto(media=photo_id))
            
            messages = await bot.send_media_group(
                chat_id=GROUP_ID,
                media=media_group
            )
            main_message_id = messages[0].message_id
        else:
            msg = await bot.send_photo(
                chat_id=GROUP_ID,
                photo=photo_ids[0],
                caption=text,
                reply_markup=get_request_action_keyboard(request.id)
            )
            main_message_id = msg.message_id
    else:
        msg = await bot.send_message(
            chat_id=GROUP_ID,
            text=text,
            reply_markup=get_request_action_keyboard(request.id)
        )
        main_message_id = msg.message_id
    
    # Если есть координаты, отправляем их отдельно
    if request.latitude and request.longitude:
        await bot.send_location(
            chat_id=GROUP_ID,
            latitude=request.latitude,
            longitude=request.longitude,
            reply_to_message_id=main_message_id
        )
    
    # Сохраняем информацию о сообщении в группе
    group_msg = GroupMessage(
        request_id=request.id,
        group_chat_id=GROUP_ID,
        message_id=main_message_id
    )
    session.add(group_msg)

@router.callback_query(F.data.startswith("take_"))
async def take_request(callback: CallbackQuery):
    request_id = int(callback.data.split("_")[1])
    
    async with async_session() as session:
        # Получаем заявку
        result = await session.execute(
            select(Request).where(Request.id == request_id)
        )
        request = result.scalar_one_or_none()
        
        if not request or request.status != 'new':
            await callback.answer("❌ Заявка уже недоступна", show_alert=True)
            return
        
        # Получаем монтажника
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        installer = result.scalar_one_or_none()
        
        if not installer or installer.role != 'installer':
            await callback.answer("❌ Вы не монтажник", show_alert=True)
            return
        
        # Назначаем монтажника
        request.status = 'in_progress'
        request.installer_id = installer.id
        request.assigned_at = datetime.now()
        
        # Обновляем сообщение в группе
        await callback.message.edit_caption(
            caption=f"{callback.message.caption}\n\n🔨 Взял: @{installer.username or installer.name}",
            reply_markup=None
        )
        
        # Уведомляем заказчика
        await callback.bot.send_message(
            chat_id=request.client.telegram_id,
            text=(
                f"🔔 <b>Заявка №{request.id} взята в работу!</b>\n\n"
                f"Монтажник: @{installer.username or installer.name}\n"
                f"Свяжитесь с ним для уточнения деталей."
            )
        )
        
        # Отправляем детали монтажнику в ЛС
        await send_request_details_to_installer(callback.bot, installer.telegram_id, request)
        
        await session.commit()
    
    await callback.answer("✅ Заявка взята в работу!")

@router.callback_query(F.data.startswith("refuse_"))
async def refuse_request(callback: CallbackQuery, state: FSMContext):
    request_id = int(callback.data.split("_")[1])
    
    await state.update_data(refuse_request_id=request_id)
    await callback.message.answer(
        "❓ Укажите причину отказа (отправьте текстовое сообщение):"
    )
    await state.set_state("waiting_refuse_reason")
    await callback.answer()

@router.message(F.state == "waiting_refuse_reason")
async def process_refuse_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    request_id = data['refuse_request_id']
    reason = message.text
    
    async with async_session() as session:
        # Получаем монтажника
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        installer = result.scalar_one()
        
        # Сохраняем отказ
        refusal = Refusal(
            request_id=request_id,
            installer_id=installer.id,
            reason=reason
        )
        session.add(refusal)
        
        # Обновляем сообщение в группе (опционально)
        result = await session.execute(
            select(GroupMessage).where(GroupMessage.request_id == request_id)
        )
        group_msg = result.scalar_one_or_none()
        
        if group_msg:
            await message.bot.edit_message_caption(
                chat_id=group_msg.group_chat_id,
                message_id=group_msg.message_id,
                caption=f"{group_msg.caption}\n\n⚠️ Отказ от @{installer.username}: {reason}"
            )
        
        await session.commit()
    
    await message.answer("✅ Отказ зарегистрирован")
    await state.clear()

@router.message(Command("my_requests"))
async def my_requests(message: Message):
    async with async_session() as session:
        # Получаем монтажника
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        installer = result.scalar_one_or_none()
        
        if not installer or installer.role != 'installer':
            await message.answer("❌ Эта команда доступна только монтажникам")
            return
        
        # Получаем активные заявки
        result = await session.execute(
            select(Request).where(
                Request.installer_id == installer.id,
                Request.status == 'in_progress'
            )
        )
        requests = result.scalars().all()
        
        if not requests:
            await message.answer("📭 У вас нет активных заявок")
            return
        
        await message.answer(
            "📋 Ваши заявки в работе:",
            reply_markup=get_installer_requests_keyboard(requests)
        )

async def send_request_details_to_installer(bot, installer_id: int, request: Request):
    """Отправка деталей заявки монтажнику в ЛС"""
    # Получаем район
    async with async_session() as session:
        district = await session.get(District, request.district_id)
    
    text = (
        f"🔨 <b>Заявка №{request.id} (в работе)</b>\n\n"
        f"📝 Описание: {request.description}\n"
        f"📍 Район: {district.name}\n"
        f"🏠 Адрес: {request.address}\n"
        f"📞 Телефон: {request.contact_phone}\n"
    )
    
    # Создаем клавиатуру с действиями
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🗺 Открыть на карте",
                url=f"https://yandex.ru/maps/?pt={request.longitude},{request.latitude}&z=17&l=map"
            ) if request.latitude and request.longitude else None,
            InlineKeyboardButton(
                text="📞 Позвонить",
                url=f"tel:{request.contact_phone}"
            )
        ].filter(None),
        [InlineKeyboardButton(text="✅ Завершить заявку", callback_data=f"complete_{request.id}")]
    ])
    
    # Отправляем фото если есть
    if request.photo_file_id:
        photo_ids = request.photo_file_id.split(',')
        await bot.send_photo(
            chat_id=installer_id,
            photo=photo_ids[0],
            caption=text,
            reply_markup=keyboard
        )
        for photo_id in photo_ids[1:]:
            await bot.send_photo(chat_id=installer_id, photo=photo_id)
    else:
        await bot.send_message(
            chat_id=installer_id,
            text=text,
            reply_markup=keyboard
        )
