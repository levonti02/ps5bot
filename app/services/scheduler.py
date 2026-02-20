import datetime
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, and_

from app.config import settings
from app.database import async_session
from app.models.console import Console, ConsoleStatus
from app.models.session import Session, SessionStatus
from app.services import shelly

logger = logging.getLogger(__name__)
tz = ZoneInfo(settings.TIMEZONE)

_bot = None  # set at startup


def set_bot(bot):
    global _bot
    _bot = bot


async def _notify(telegram_id: int, text: str):
    if _bot:
        try:
            await _bot.send_message(telegram_id, text)
        except Exception as exc:
            logger.warning("Failed to notify %s: %s", telegram_id, exc)


async def check_sessions():
    """Periodic job: handle HOLD expiry, notifications, session end, NO_SHOW."""
    now = datetime.datetime.now(tz)
    async with async_session() as db:
        # --- 1. Expire HOLD sessions ---
        stmt = select(Session).where(
            and_(
                Session.status == SessionStatus.HOLD,
                Session.hold_until <= now,
            )
        )
        result = await db.execute(stmt)
        for s in result.scalars().all():
            s.status = SessionStatus.CANCELLED
            logger.info("Session %s HOLD expired -> CANCELLED", s.id)

        # --- 2. NO_SHOW: CONFIRMED bookings past activation window ---
        activation_deadline = now - datetime.timedelta(
            minutes=settings.ACTIVATION_WINDOW_MINUTES,
        )
        stmt = select(Session).where(
            and_(
                Session.status == SessionStatus.CONFIRMED,
                Session.session_type == "BOOKING",
                Session.slot_start <= activation_deadline,
            )
        )
        result = await db.execute(stmt)
        for s in result.scalars().all():
            s.status = SessionStatus.NO_SHOW
            user = await db.get(s.__class__.__mapper__.relationships["user"].mapper.class_, s.user_id)
            if user:
                await _notify(
                    user.telegram_id,
                    "⛔ Бронь не была активирована\nСлот освобождён.",
                )
            logger.info("Session %s -> NO_SHOW", s.id)

        # --- 3. End ACTIVE sessions past slot_end ---
        stmt = select(Session).where(
            and_(
                Session.status == SessionStatus.ACTIVE,
                Session.slot_end <= now,
            )
        )
        result = await db.execute(stmt)
        for s in result.scalars().all():
            console = await db.get(Console, s.console_id)
            if console:
                ok = await shelly.turn_off(console.shelly_ip)
                if not ok:
                    # notify admin
                    for admin_id in settings.ADMIN_IDS:
                        await _notify(
                            admin_id,
                            f"⚠️ Не удалось выключить розетку консоли {console.name} "
                            f"(IP: {console.shelly_ip})",
                        )
                console.status = ConsoleStatus.FREE
            s.status = SessionStatus.COMPLETED
            user = await db.get(s.__class__.__mapper__.relationships["user"].mapper.class_, s.user_id)
            if user:
                await _notify(
                    user.telegram_id,
                    "⛔ Время вышло\nСпасибо за игру! Будем рады видеть вас снова 🎮",
                )
            logger.info("Session %s ACTIVE -> COMPLETED", s.id)

        # --- 4. Notifications for upcoming sessions ---
        for minutes_before, text in [
            (15, "🎮 Игра начнётся через 15 минут"),
            (10, "⏳ До окончания игры осталось 10 минут"),
            (1, "⏳ Осталась 1 минута"),
        ]:
            # Upcoming CONFIRMED bookings — remind before start
            if minutes_before == 15:
                target = now + datetime.timedelta(minutes=15)
                window_start = target - datetime.timedelta(seconds=30)
                window_end = target + datetime.timedelta(seconds=30)
                stmt = select(Session).where(
                    and_(
                        Session.status == SessionStatus.CONFIRMED,
                        Session.slot_start >= window_start,
                        Session.slot_start <= window_end,
                    )
                )
                result = await db.execute(stmt)
                for s in result.scalars().all():
                    from app.models.user import User
                    user = await db.get(User, s.user_id)
                    if user:
                        await _notify(
                            user.telegram_id,
                            f"{text}\nВы сможете активировать сессию по кнопке ниже.",
                        )

            # Running ACTIVE sessions — remind before end
            if minutes_before in (10, 1):
                target = now + datetime.timedelta(minutes=minutes_before)
                window_start = target - datetime.timedelta(seconds=30)
                window_end = target + datetime.timedelta(seconds=30)
                stmt = select(Session).where(
                    and_(
                        Session.status == SessionStatus.ACTIVE,
                        Session.slot_end >= window_start,
                        Session.slot_end <= window_end,
                    )
                )
                result = await db.execute(stmt)
                for s in result.scalars().all():
                    from app.models.user import User
                    user = await db.get(User, s.user_id)
                    if user:
                        await _notify(user.telegram_id, text)

        await db.commit()


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(check_sessions, "interval", seconds=30)
    return scheduler
