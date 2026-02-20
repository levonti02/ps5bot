import datetime
import logging
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.console import Console
from app.models.user import User
from app.services.booking import get_free_slots, create_booking_session
from app.services.payment import create_payment
from app.keyboards.main import (
    booking_date_kb,
    time_slots_kb,
    tariff_kb,
    confirm_order_kb,
    payment_kb,
    booking_confirmed_kb,
)

router = Router()
logger = logging.getLogger(__name__)
tz = ZoneInfo(settings.TIMEZONE)


@router.callback_query(F.data.startswith("book:"))
async def booking_select_date(callback: CallbackQuery, db: AsyncSession):
    console_code = callback.data.split(":")[1]
    await callback.message.edit_text(
        "📅 Выберите дату игры",
        reply_markup=booking_date_kb(console_code),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("bdate:"))
async def booking_select_time(callback: CallbackQuery, db: AsyncSession):
    """User selected a date — show available time slots for 30-min sessions."""
    parts = callback.data.split(":")
    console_code, date_str = parts[1], parts[2]
    date = datetime.date.fromisoformat(date_str)

    stmt = select(Console).where(Console.code == console_code)
    result = await db.execute(stmt)
    console = result.scalars().first()
    if not console:
        await callback.answer("Консоль не найдена", show_alert=True)
        return

    # Show slots for minimum duration (30 min) — user picks duration next
    slots = await get_free_slots(db, console.id, date, 30)
    if not slots:
        await callback.message.edit_text(
            "😔 На эту дату нет свободных слотов.\nПопробуйте другой день.",
            reply_markup=booking_date_kb(console_code),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"⏰ Свободные слоты на {date.strftime('%d.%m.%Y')}\nВыберите время начала 👇",
        reply_markup=time_slots_kb(console_code, date_str, slots),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("btime:"))
async def booking_select_duration(callback: CallbackQuery, db: AsyncSession):
    """User selected start time — show tariff options."""
    parts = callback.data.split(":")
    console_code, date_str, time_str = parts[1], parts[2], parts[3]
    # Store selection in callback_data prefix for next step
    await callback.message.edit_text(
        f"🕐 Начало: {time_str}, {date_str}\nВыберите длительность 🎮",
        reply_markup=tariff_kb(console_code, prefix=f"tariff_book:{date_str}:{time_str}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tariff_book:"))
async def booking_confirm(callback: CallbackQuery, db: AsyncSession):
    """User selected duration — create HOLD and show confirmation."""
    # tariff_book:<date>:<time>:<console_code>:<duration>
    parts = callback.data.split(":")
    date_str, time_str, console_code, duration_str = parts[1], parts[2], parts[3], parts[4]
    duration = int(duration_str)
    price = settings.tariffs.get(duration)
    if not price:
        await callback.answer("Неверный тариф", show_alert=True)
        return

    date = datetime.date.fromisoformat(date_str)
    hour, minute = map(int, time_str.split("-") if "-" in time_str else time_str.split(":"))
    slot_start = datetime.datetime.combine(date, datetime.time(hour, minute), tzinfo=tz)

    stmt = select(Console).where(Console.code == console_code)
    result = await db.execute(stmt)
    console = result.scalars().first()

    stmt_user = select(User).where(User.telegram_id == callback.from_user.id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalars().first()

    session = await create_booking_session(
        db, user.id, console.id, slot_start, duration, price,
    )
    if not session:
        await callback.message.edit_text("❌ Этот слот уже занят. Выберите другое время.")
        await callback.answer()
        return

    slot_end = slot_start + datetime.timedelta(minutes=duration)
    price_rub = price // 100
    location = console.location
    city_name = location.city.name if location.city else ""
    text = (
        f"📋 Подтверждение брони\n\n"
        f"📍 {city_name}, {location.address}\n"
        f"🚪 Подъезд {location.entrance}\n"
        f"🎮 {console.name}\n"
        f"📅 {date.strftime('%d.%m.%Y')}\n"
        f"⏰ {slot_start.strftime('%H:%M')}–{slot_end.strftime('%H:%M')}\n"
        f"💰 {price_rub} ₽\n\n"
        f"⏳ Мы удерживаем слот 10 минут.\nЗавершите оплату, чтобы подтвердить бронь."
    )
    await callback.message.edit_text(text, reply_markup=confirm_order_kb(session.id))
    await callback.answer()


@router.callback_query(F.data.startswith("activate:"))
async def activate_booking(callback: CallbackQuery, db: AsyncSession):
    """Activate a confirmed booking."""
    session_id = int(callback.data.split(":")[1])
    from app.models.session import Session
    from app.services.booking import activate_session

    session = await db.get(Session, session_id)
    if not session:
        await callback.answer("Сессия не найдена", show_alert=True)
        return

    ok = await activate_session(db, session)
    if not ok:
        await callback.message.edit_text(
            "⛔ Активация недоступна.\nПопробуйте ближе ко времени начала.",
        )
        await callback.answer()
        return

    # Turn on console
    console = await db.get(Console, session.console_id)
    from app.services import shelly
    from app.models.console import ConsoleStatus
    power_ok = await shelly.turn_on(console.shelly_ip)
    if power_ok:
        console.status = ConsoleStatus.BUSY
        await db.commit()
    else:
        for admin_id in settings.ADMIN_IDS:
            try:
                await callback.bot.send_message(
                    admin_id,
                    f"⚠️ Не удалось включить розетку {console.name} ({console.shelly_ip})",
                )
            except Exception:
                pass

    from app.keyboards.main import session_active_kb
    await callback.message.edit_text(
        f"✅ Сессия запущена\n⏱ Окончание: {session.slot_end.strftime('%H:%M')}\n\nХорошей игры!",
        reply_markup=session_active_kb(),
    )
    await callback.answer()
