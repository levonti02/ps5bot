import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.config import settings
from app.keyboards.main import help_kb

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    text = (
        "🆘 Возникла проблема?\n"
        "Опишите, что случилось, и мы поможем."
    )
    await callback.message.edit_text(text, reply_markup=help_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("issue:"))
async def report_issue(callback: CallbackQuery):
    issue_type = callback.data.split(":")[1]
    labels = {"screen": "Не включился экран", "freeze": "Зависло", "other": "Другое"}
    label = labels.get(issue_type, issue_type)

    # Notify all admins
    for admin_id in settings.ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"🚨 Обращение от @{callback.from_user.username or callback.from_user.id}\n"
                f"Проблема: {label}",
            )
        except Exception:
            pass

    await callback.message.edit_text(
        "✅ Сообщение отправлено администратору.\nМы скоро свяжемся с вами."
    )
    await callback.answer()
