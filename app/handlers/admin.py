import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.console import Console, ConsoleStatus
from app.models.session import Session, SessionStatus
from app.services import shelly

router = Router()
logger = logging.getLogger(__name__)


def _is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.ADMIN_IDS


@router.message(Command("admin"))
async def admin_menu(message: Message):
    if not _is_admin(message.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Активные сессии", callback_data="adm:sessions")],
        [InlineKeyboardButton(text="🎮 Список консолей", callback_data="adm:consoles")],
    ])
    await message.answer("🔧 Админ-панель", reply_markup=kb)


@router.callback_query(F.data == "adm:sessions")
async def admin_sessions(callback: CallbackQuery, db: AsyncSession):
    if not _is_admin(callback.from_user.id):
        return
    stmt = select(Session).where(
        Session.status.in_((SessionStatus.HOLD, SessionStatus.CONFIRMED, SessionStatus.ACTIVE)),
    ).order_by(Session.slot_start)
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    if not sessions:
        await callback.message.edit_text("Нет активных сессий.")
        await callback.answer()
        return

    lines = ["📋 **Активные сессии:**\n"]
    for s in sessions:
        lines.append(
            f"• #{s.id} | консоль {s.console_id} | "
            f"{s.slot_start.strftime('%d.%m %H:%M')}–{s.slot_end.strftime('%H:%M')} | "
            f"[{s.status.value}]"
        )
    await callback.message.edit_text("\n".join(lines), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "adm:consoles")
async def admin_consoles(callback: CallbackQuery, db: AsyncSession):
    if not _is_admin(callback.from_user.id):
        return
    stmt = select(Console).where(Console.is_active.is_(True))
    result = await db.execute(stmt)
    consoles = result.scalars().all()

    rows = []
    for c in consoles:
        rows.append([
            InlineKeyboardButton(
                text=f"{c.name} [{c.status.value}]",
                callback_data=f"adm:console:{c.id}",
            )
        ])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await callback.message.edit_text("🎮 Консоли:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:console:"))
async def admin_console_actions(callback: CallbackQuery, db: AsyncSession):
    if not _is_admin(callback.from_user.id):
        return
    console_id = int(callback.data.split(":")[2])
    console = await db.get(Console, console_id)
    if not console:
        await callback.answer("Не найдена", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔌 Включить", callback_data=f"adm:on:{console_id}")],
        [InlineKeyboardButton(text="⏹ Выключить", callback_data=f"adm:off:{console_id}")],
        [InlineKeyboardButton(text="🚫 OFFLINE", callback_data=f"adm:offline:{console_id}")],
        [InlineKeyboardButton(text="✅ FREE", callback_data=f"adm:free:{console_id}")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="adm:consoles")],
    ])
    await callback.message.edit_text(
        f"🎮 {console.name}\nСтатус: {console.status.value}\nIP: {console.shelly_ip}",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:on:"))
async def admin_turn_on(callback: CallbackQuery, db: AsyncSession):
    if not _is_admin(callback.from_user.id):
        return
    console_id = int(callback.data.split(":")[2])
    console = await db.get(Console, console_id)
    ok = await shelly.turn_on(console.shelly_ip)
    if ok:
        console.status = ConsoleStatus.BUSY
        await db.commit()
        await callback.answer("✅ Включена")
    else:
        await callback.answer("❌ Ошибка включения", show_alert=True)


@router.callback_query(F.data.startswith("adm:off:"))
async def admin_turn_off(callback: CallbackQuery, db: AsyncSession):
    if not _is_admin(callback.from_user.id):
        return
    console_id = int(callback.data.split(":")[2])
    console = await db.get(Console, console_id)
    ok = await shelly.turn_off(console.shelly_ip)
    if ok:
        console.status = ConsoleStatus.FREE
        await db.commit()
        await callback.answer("✅ Выключена")
    else:
        await callback.answer("❌ Ошибка выключения", show_alert=True)


@router.callback_query(F.data.startswith("adm:offline:"))
async def admin_set_offline(callback: CallbackQuery, db: AsyncSession):
    if not _is_admin(callback.from_user.id):
        return
    console_id = int(callback.data.split(":")[2])
    console = await db.get(Console, console_id)
    console.status = ConsoleStatus.OFFLINE
    await db.commit()
    await callback.answer("🚫 Установлен OFFLINE")


@router.callback_query(F.data.startswith("adm:free:"))
async def admin_set_free(callback: CallbackQuery, db: AsyncSession):
    if not _is_admin(callback.from_user.id):
        return
    console_id = int(callback.data.split(":")[2])
    console = await db.get(Console, console_id)
    console.status = ConsoleStatus.FREE
    await db.commit()
    await callback.answer("✅ Установлен FREE")
