from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from database import async_session, User, Request, District, Refusal
from config import ADMIN_ID
from keyboards.inline import get_admin_keyboard

router = Router()

# Фильтр для админа
async def is_admin(message: Message) -> bool:
    return message.from_user.id == ADMIN_ID

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not await is_admin(message):
        await message.answer("❌ Доступ запрещён")
        return
    
    from keyboards.inline import get_admin_keyboard
    await message.answer(
        "👑 <b>Панель администратора</b>\n\n"
        "Выберите раздел:",
        reply_markup=get_admin_keyboard()
    )

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    async with async_session() as session:
        # Общая статистика
        total = await session.scalar(select(func.count(Request.id)))
        new = await session.scalar(
            select(func.count(Request.id)).where(Request.status == 'new')
        )
        in_progress = await session.scalar(
            select(func.count(Request.id)).where(Request.status == 'in_progress')
        )
        completed = await session.scalar(
            select(func.count(Request.id)).where(Request.status == 'completed')
        )
        
        # Статистика по отказам
        refusals = await session.scalar(select(func.count(Refusal.id)))
        
        # Количество монтажников
        installers = await session.scalar(
            select(func.count(User.id)).where(User.role == 'installer')
        )
        
        text = (
            f"📊 <b>Общая статистика</b>\n\n"
            f"📌 Всего заявок: {total}\n"
            f"🆕 Новых: {new}\n"
            f"🔨 В работе: {in_progress}\n"
            f"✅ Завершено: {completed}\n"
            f"❌ Отказов: {refusals}\n"
            f"👷 Монтажников: {installers}\n"
        )
    
    await callback.message.edit_text(text)
    await callback.answer()

@router.callback_query(F.data == "admin_districts")
async def admin_districts(callback: CallbackQuery):
    async with async_session() as session:
        districts = await session.execute(select(District))
        districts = districts.scalars().all()
        
        text = "🏘 <b>Статистика по районам</b>\n\n"
        
        for district in districts:
            total = await session.scalar(
                select(func.count(Request.id)).where(Request.district_id == district.id)
            )
            completed = await session.scalar(
                select(func.count(Request.id)).where(
                    and_(Request.district_id == district.id, Request.status == 'completed')
                )
            )
            text += f"• {district.name}: всего {total}, выполнено {completed}\n"
    
    await callback.message.edit_text(text)
    await callback.answer()

@router.callback_query(F.data == "admin_installers")
async def admin_installers(callback: CallbackQuery):
    async with async_session() as session:
        installers = await session.execute(
            select(User).where(User.role == 'installer')
        )
        installers = installers.scalars().all()
        
        text = "👷 <b>Рейтинг монтажников</b>\n\n"
        
        for installer in installers:
            completed = await session.scalar(
                select(func.count(Request.id)).where(
                    and_(Request.installer_id == installer.id, Request.status == 'completed')
                )
            )
            refusals = await session.scalar(
                select(func.count(Refusal.id)).where(Refusal.installer_id == installer.id)
            )
            text += (
                f"• @{installer.username or installer.name}\n"
                f"  ✅ Выполнено: {completed}\n"
                f"  ❌ Отказов: {refusals}\n\n"
            )
    
    await callback.message.edit_text(text)
    await callback.answer()
