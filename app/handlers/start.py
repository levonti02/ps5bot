import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.console import Console
from app.keyboards.main import welcome_kb, city_select_kb
from app.models.city import City

router = Router()
logger = logging.getLogger(__name__)


async def _get_or_create_user(db: AsyncSession, message: Message) -> User:
    tg = message.from_user
    stmt = select(User).where(User.telegram_id == tg.id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        user = User(
            telegram_id=tg.id,
            username=tg.username,
            first_name=tg.first_name,
            last_name=tg.last_name,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


@router.message(CommandStart(deep_link=True))
async def cmd_start_deeplink(message: Message, command: CommandObject, db: AsyncSession):
    """Handle /start ps_<console_code> (QR deep-link)."""
    user = await _get_or_create_user(db, message)
    payload = command.args  # e.g. "ps_001"

    stmt = select(Console).where(Console.code == payload, Console.is_active.is_(True))
    result = await db.execute(stmt)
    console = result.scalars().first()

    if not console:
        await message.answer("❌ Консоль не найдена. Попробуйте отсканировать QR-код ещё раз.")
        return

    location = console.location
    city_name = location.city.name if location.city else ""
    text = (
        f"🎮 Добро пожаловать!\n"
        f"Вы на игровой станции **{console.name}**\n"
        f"📍 {city_name}, {location.address}, подъезд {location.entrance}\n\n"
        f"Выберите, как хотите играть 👇"
    )
    await message.answer(text, reply_markup=welcome_kb(console.code), parse_mode="Markdown")


@router.message(CommandStart())
async def cmd_start(message: Message, db: AsyncSession):
    """Handle /start without parameters — city selection."""
    user = await _get_or_create_user(db, message)
    stmt = select(City).where(City.is_active.is_(True))
    result = await db.execute(stmt)
    cities = [(c.id, c.name) for c in result.scalars().all()]

    if not cities:
        await message.answer("Пока нет доступных городов. Попробуйте позже.")
        return

    await message.answer(
        "🎮 Добро пожаловать в игровой сервис\nВыберите город, чтобы продолжить 👇",
        reply_markup=city_select_kb(cities),
    )


@router.callback_query(F.data == "rules")
async def show_rules(callback: CallbackQuery):
    text = (
        "ℹ **Правила использования**\n\n"
        "• Игра запускается автоматически после оплаты\n"
        "• Время фиксированное\n"
        "• Возвраты — по обращению\n"
        "• Бережно относитесь к оборудованию\n\n"
        "Спасибо 🙏"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("back_welcome:"))
async def back_to_welcome(callback: CallbackQuery, db: AsyncSession):
    console_code = callback.data.split(":")[1]
    stmt = select(Console).where(Console.code == console_code)
    result = await db.execute(stmt)
    console = result.scalars().first()
    if not console:
        await callback.answer("Консоль не найдена", show_alert=True)
        return

    location = console.location
    city_name = location.city.name if location.city else ""
    text = (
        f"🎮 Добро пожаловать!\n"
        f"Вы на игровой станции **{console.name}**\n"
        f"📍 {city_name}, {location.address}, подъезд {location.entrance}\n\n"
        f"Выберите, как хотите играть 👇"
    )
    await callback.message.edit_text(text, reply_markup=welcome_kb(console.code), parse_mode="Markdown")
    await callback.answer()
