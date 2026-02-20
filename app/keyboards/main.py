import datetime
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.config import settings

tz = ZoneInfo(settings.TIMEZONE)


def welcome_kb(console_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶ Играть сейчас", callback_data=f"play_now:{console_code}")],
        [InlineKeyboardButton(text="📅 Забронировать заранее", callback_data=f"book:{console_code}")],
        [InlineKeyboardButton(text="ℹ Правила и помощь", callback_data="rules")],
    ])


def city_select_kb(cities: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=name, callback_data=f"city:{cid}")] for cid, name in cities]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tariff_kb(console_code: str, prefix: str = "tariff") -> InlineKeyboardMarkup:
    tariffs = settings.tariffs
    labels = {30: "🕐 30 минут", 60: "🕐 60 минут", 90: "🕐 90 минут", 120: "🕐 120 минут"}
    rows = []
    for dur, price_kop in tariffs.items():
        price_rub = price_kop // 100
        rows.append([
            InlineKeyboardButton(
                text=f"{labels[dur]} — {price_rub} ₽",
                callback_data=f"{prefix}:{console_code}:{dur}",
            )
        ])
    rows.append([InlineKeyboardButton(text="◀ Назад", callback_data=f"back_welcome:{console_code}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_order_kb(session_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить через СБП", callback_data=f"pay:{session_id}")],
        [InlineKeyboardButton(text="🔄 Изменить тариф", callback_data=f"change_tariff:{session_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_session:{session_id}")],
    ])


def payment_kb(confirmation_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Перейти к оплате", url=confirmation_url)],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")],
    ])


def session_active_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆘 Проблема / помощь", callback_data="help")],
        [InlineKeyboardButton(text="ℹ Правила", callback_data="rules")],
    ])


def after_game_kb(console_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶ Сыграть ещё", callback_data=f"play_now:{console_code}")],
        [InlineKeyboardButton(text="📅 Забронировать заранее", callback_data=f"book:{console_code}")],
    ])


def booking_date_kb(console_code: str) -> InlineKeyboardMarkup:
    today = datetime.date.today()
    rows = [
        [InlineKeyboardButton(text="Сегодня", callback_data=f"bdate:{console_code}:{today.isoformat()}")],
        [InlineKeyboardButton(
            text="Завтра",
            callback_data=f"bdate:{console_code}:{(today + datetime.timedelta(days=1)).isoformat()}",
        )],
    ]
    # next 7 days
    for d in range(2, min(settings.BOOKING_HORIZON_DAYS, 9)):
        dt = today + datetime.timedelta(days=d)
        rows.append([InlineKeyboardButton(
            text=dt.strftime("%d.%m (%a)"),
            callback_data=f"bdate:{console_code}:{dt.isoformat()}",
        )])
    rows.append([InlineKeyboardButton(text="◀ Назад", callback_data=f"back_welcome:{console_code}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def time_slots_kb(console_code: str, date_str: str, slots: list[datetime.datetime]) -> InlineKeyboardMarkup:
    rows = []
    for slot in slots[:12]:  # limit buttons
        t = slot.strftime("%H:%M")
        rows.append([InlineKeyboardButton(
            text=t,
            callback_data=f"btime:{console_code}:{date_str}:{t}",
        )])
    rows.append([InlineKeyboardButton(text="◀ Назад", callback_data=f"book:{console_code}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def activate_session_kb(session_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶ Активировать сессию", callback_data=f"activate:{session_id}")],
    ])


def help_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Не включился экран", callback_data="issue:screen")],
        [InlineKeyboardButton(text="❌ Пропала игра / зависло", callback_data="issue:freeze")],
        [InlineKeyboardButton(text="❌ Другое", callback_data="issue:other")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="back_session")],
    ])


def booking_confirmed_kb(session_id: int, console_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить бронь", callback_data=f"cancel_session:{session_id}")],
        [InlineKeyboardButton(text="ℹ Правила", callback_data="rules")],
        [InlineKeyboardButton(text="◀ В меню", callback_data=f"back_welcome:{console_code}")],
    ])
