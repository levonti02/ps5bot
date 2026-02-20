import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.console import Console, ConsoleStatus
from app.models.user import User
from app.services.booking import create_instant_session, get_next_free_time
from app.services.payment import create_payment
from app.keyboards.main import (
    tariff_kb,
    confirm_order_kb,
    payment_kb,
    session_active_kb,
)

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("play_now:"))
async def play_now(callback: CallbackQuery, db: AsyncSession):
    console_code = callback.data.split(":")[1]
    stmt = select(Console).where(Console.code == console_code, Console.is_active.is_(True))
    result = await db.execute(stmt)
    console = result.scalars().first()

    if not console:
        await callback.answer("Консоль не найдена", show_alert=True)
        return

    if console.status == ConsoleStatus.FREE:
        await callback.message.edit_text(
            "✅ Станция сейчас свободна\nВыберите длительность игры 🎮",
            reply_markup=tariff_kb(console_code, prefix="tariff_instant"),
        )
    else:
        free_at = await get_next_free_time(db, console.id)
        free_text = f"Освободится в {free_at.strftime('%H:%M')}" if free_at else "Время неизвестно"
        from app.keyboards.main import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Забронировать на позже", callback_data=f"book:{console_code}")],
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"back_welcome:{console_code}")],
        ])
        await callback.message.edit_text(f"⏳ Сейчас станция занята\n{free_text}", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("tariff_instant:"))
async def select_tariff_instant(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split(":")
    console_code, duration = parts[1], int(parts[2])
    price = settings.tariffs.get(duration)
    if not price:
        await callback.answer("Неверный тариф", show_alert=True)
        return

    stmt = select(Console).where(Console.code == console_code)
    result = await db.execute(stmt)
    console = result.scalars().first()
    if not console:
        await callback.answer("Консоль не найдена", show_alert=True)
        return

    stmt_user = select(User).where(User.telegram_id == callback.from_user.id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalars().first()

    session = await create_instant_session(db, user.id, console.id, duration, price)
    if not session:
        await callback.message.edit_text(
            "❌ Слот уже занят. Попробуйте другое время.",
        )
        await callback.answer()
        return

    location = console.location
    city_name = location.city.name if location.city else ""
    price_rub = price // 100
    text = (
        f"📋 Подтверждение\n\n"
        f"📍 {city_name}, {location.address}\n"
        f"🚪 Подъезд {location.entrance}\n"
        f"🎮 {console.name}\n"
        f"⏱ Длительность: {duration} минут\n"
        f"💰 Стоимость: {price_rub} ₽"
    )
    await callback.message.edit_text(text, reply_markup=confirm_order_kb(session.id))
    await callback.answer()


@router.callback_query(F.data.startswith("pay:"))
async def pay_session(callback: CallbackQuery, db: AsyncSession):
    session_id = int(callback.data.split(":")[1])
    from app.models.session import Session
    session = await db.get(Session, session_id)
    if not session:
        await callback.answer("Сессия не найдена", show_alert=True)
        return

    txn = await create_payment(db, session)
    text = (
        "💳 Оплата через СБП\n"
        "Нажмите кнопку ниже и завершите оплату.\n"
        "После подтверждения игра запустится автоматически."
    )
    await callback.message.edit_text(text, reply_markup=payment_kb(txn.confirmation_url))
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_session:"))
async def cancel_session(callback: CallbackQuery, db: AsyncSession):
    session_id = int(callback.data.split(":")[1])
    from app.models.session import Session, SessionStatus
    session = await db.get(Session, session_id)
    if session and session.status in (SessionStatus.HOLD, SessionStatus.CONFIRMED):
        session.status = SessionStatus.CANCELLED
        await db.commit()
    await callback.message.edit_text("❌ Сессия отменена.")
    await callback.answer()
