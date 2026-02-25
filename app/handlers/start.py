import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.console import Console
from app.keyboards.main import welcome_kb, city_select_kb, location_select_kb, console_select_kb
from app.models.city import City
from app.models.location import Location

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


@router.callback_query(F.data.startswith("city:"))
async def select_city(callback: CallbackQuery, db: AsyncSession):
    city_id = int(callback.data.split(":")[1])
    stmt = (
        select(Location)
        .where(Location.city_id == city_id, Location.is_active.is_(True))
    )
    result = await db.execute(stmt)
    locations = result.scalars().all()

    if not locations:
        await callback.answer("В этом городе пока нет точек", show_alert=True)
        return

    items = [(loc.id, loc.address) for loc in locations]
    await callback.message.edit_text(
        "📍 Выберите адрес",
        reply_markup=location_select_kb(items, city_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("location:"))
async def select_location(callback: CallbackQuery, db: AsyncSession):
    location_id = int(callback.data.split(":")[1])
    stmt = select(Location).where(Location.id == location_id)
    result = await db.execute(stmt)
    location = result.scalars().first()
    if not location:
        await callback.answer("Локация не найдена", show_alert=True)
        return

    consoles = [c for c in location.consoles if c.is_active]
    if not consoles:
        await callback.answer("Нет доступных консолей", show_alert=True)
        return

    status_labels = {"FREE": "свободна", "BUSY": "занята", "OFFLINE": "офлайн"}
    items = [
        (c.code, c.name, status_labels.get(c.status.value, c.status.value))
        for c in consoles
    ]
    await callback.message.edit_text(
        f"📍 {location.address}, подъезд {location.entrance}\nВыберите консоль 🎮",
        reply_markup=console_select_kb(items, location_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("console:"))
async def select_console(callback: CallbackQuery, db: AsyncSession):
    console_code = callback.data.split(":")[1]
    stmt = select(Console).where(Console.code == console_code, Console.is_active.is_(True))
    result = await db.execute(stmt)
    console = result.scalars().first()
    if not console:
        await callback.answer("Консоль не найдена", show_alert=True)
        return

    location = console.location
    city_name = location.city.name if location.city else ""
    text = (
        f"🎮 Вы выбрали **{console.name}**\n"
        f"📍 {city_name}, {location.address}, подъезд {location.entrance}\n\n"
        f"Выберите, как хотите играть 👇"
    )
    await callback.message.edit_text(text, reply_markup=welcome_kb(console.code), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "back_cities")
async def back_to_cities(callback: CallbackQuery, db: AsyncSession):
    stmt = select(City).where(City.is_active.is_(True))
    result = await db.execute(stmt)
    cities = [(c.id, c.name) for c in result.scalars().all()]
    await callback.message.edit_text(
        "🎮 Выберите город 👇",
        reply_markup=city_select_kb(cities),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("back_location:"))
async def back_to_location(callback: CallbackQuery, db: AsyncSession):
    location_id = int(callback.data.split(":")[1])
    location = await db.get(Location, location_id)
    if not location:
        await callback.answer("Локация не найдена", show_alert=True)
        return

    stmt = (
        select(Location)
        .where(Location.city_id == location.city_id, Location.is_active.is_(True))
    )
    result = await db.execute(stmt)
    locations = result.scalars().all()
    items = [(loc.id, loc.address) for loc in locations]
    await callback.message.edit_text(
        "📍 Выберите адрес",
        reply_markup=location_select_kb(items, location.city_id),
    )
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
