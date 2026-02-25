import asyncio
import logging
import sys
import uvicorn

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from sqlalchemy import text

# Fix aiogram bug: prepare_value raises KeyError for 'link_preview' sentinel
_orig_prepare_value = BaseSession.prepare_value


def _safe_prepare_value(self, value, bot=None, files=None):
    try:
        return _orig_prepare_value(self, value, bot=bot, files=files)
    except KeyError:
        return None


BaseSession.prepare_value = _safe_prepare_value

from app.config import settings
from app.database import engine
from app.models import Base
from app.middlewares.db import DbSessionMiddleware
from app.handlers import start, play, booking, admin, help
from app.services.scheduler import create_scheduler, set_bot
from app.webhook import webhook_app, set_bot as set_webhook_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Create tables and start scheduler."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured")


async def main():
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Middleware
    dp.update.middleware(DbSessionMiddleware())

    # Routers
    dp.include_router(start.router)
    dp.include_router(play.router)
    dp.include_router(booking.router)
    dp.include_router(admin.router)
    dp.include_router(help.router)

    # Scheduler
    set_bot(bot)
    set_webhook_bot(bot)
    scheduler = create_scheduler()
    scheduler.start()

    # Create DB tables
    await on_startup(bot)

    # Run FastAPI webhook server in background
    config = uvicorn.Config(
        webhook_app,
        host="0.0.0.0",
        port=settings.FASTAPI_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    asyncio.create_task(server.serve())

    logger.info("Bot starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
