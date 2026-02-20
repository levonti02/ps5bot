"""FastAPI app for receiving YooKassa webhooks."""
import json
import logging

from fastapi import FastAPI, Request, Response

from app.config import settings
from app.database import async_session
from app.services.payment import handle_payment_webhook
from app.models.session import Session, SessionStatus
from app.models.console import Console, ConsoleStatus
from app.services import shelly

logger = logging.getLogger(__name__)

webhook_app = FastAPI()

_bot = None


def set_bot(bot):
    global _bot
    _bot = bot


@webhook_app.post(settings.YOOKASSA_WEBHOOK_PATH)
async def yookassa_webhook(request: Request):
    """Handle YooKassa payment notification."""
    body = await request.json()
    logger.info("YooKassa webhook: %s", json.dumps(body, ensure_ascii=False)[:500])

    event = body.get("event")
    obj = body.get("object", {})
    payment_id = obj.get("id")
    status = obj.get("status")

    if not payment_id or not status:
        return Response(status_code=200)

    async with async_session() as db:
        txn = await handle_payment_webhook(db, payment_id, status)
        if not txn:
            return Response(status_code=200)

        # If payment succeeded — start session (for instant) or confirm booking
        if txn.status.value == "PAID":
            session = await db.get(Session, txn.session_id)
            if session and session.session_type.value == "INSTANT":
                # Instant play — activate immediately
                session.status = SessionStatus.ACTIVE
                console = await db.get(Console, session.console_id)
                if console:
                    ok = await shelly.turn_on(console.shelly_ip)
                    if ok:
                        console.status = ConsoleStatus.BUSY
                    else:
                        for admin_id in settings.ADMIN_IDS:
                            if _bot:
                                try:
                                    await _bot.send_message(
                                        admin_id,
                                        f"⚠️ Не удалось включить розетку {console.name}",
                                    )
                                except Exception:
                                    pass
                await db.commit()

                # Notify user
                if _bot:
                    from app.models.user import User
                    user = await db.get(User, session.user_id)
                    if user:
                        from app.keyboards.main import session_active_kb
                        try:
                            await _bot.send_message(
                                user.telegram_id,
                                f"✅ Оплата получена\n🎮 Игра начинается!\n"
                                f"⏱ Окончание: {session.slot_end.strftime('%H:%M')}\n\n"
                                f"Приятной игры 🎮",
                                reply_markup=session_active_kb(),
                            )
                        except Exception as exc:
                            logger.warning("Failed to notify user: %s", exc)

            elif session and session.session_type.value == "BOOKING":
                # Booking — confirm, user activates later
                if _bot:
                    from app.models.user import User
                    user = await db.get(User, session.user_id)
                    console = await db.get(Console, session.console_id)
                    if user and console:
                        from app.keyboards.main import booking_confirmed_kb
                        try:
                            await _bot.send_message(
                                user.telegram_id,
                                f"✅ Бронь подтверждена\n"
                                f"🎮 {console.name}\n"
                                f"📅 {session.slot_start.strftime('%d.%m.%Y')}\n"
                                f"⏰ {session.slot_start.strftime('%H:%M')}–"
                                f"{session.slot_end.strftime('%H:%M')}\n\n"
                                f"Мы напомним вам перед началом 🔔",
                                reply_markup=booking_confirmed_kb(session.id, console.code),
                            )
                        except Exception as exc:
                            logger.warning("Failed to notify user: %s", exc)

    return Response(status_code=200)
