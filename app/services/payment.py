import uuid
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.session import Session, SessionStatus
from app.models.transaction import Transaction, PaymentStatus

logger = logging.getLogger(__name__)


def _configure_yookassa():
    """Lazy-configure YooKassa SDK (only when not in mock mode)."""
    from yookassa import Configuration
    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY


async def create_payment(db: AsyncSession, session: Session) -> Transaction:
    """Create a payment. In mock mode — instant PAID without YooKassa."""
    idempotency_key = str(uuid.uuid4())
    amount_rub = session.price / 100

    if settings.PAYMENT_MOCK:
        # --- MOCK: no real payment, instant success ---
        txn = Transaction(
            session_id=session.id,
            user_id=session.user_id,
            amount=session.price,
            yookassa_payment_id=f"mock_{idempotency_key}",
            status=PaymentStatus.PAID,
            confirmation_url=None,
        )
        session.status = SessionStatus.CONFIRMED
        db.add(txn)
        await db.commit()
        await db.refresh(txn)
        await db.refresh(session)
        logger.info("MOCK payment created for session %s", session.id)
        return txn

    # --- REAL YooKassa ---
    _configure_yookassa()
    from yookassa import Payment

    payment = Payment.create(
        {
            "amount": {
                "value": f"{amount_rub:.2f}",
                "currency": "RUB",
            },
            "confirmation": {
                "type": "redirect",
                "return_url": settings.YOOKASSA_RETURN_URL,
            },
            "capture": True,
            "description": (
                f"Игровая сессия {session.duration_minutes} мин "
                f"(консоль #{session.console_id})"
            ),
            "metadata": {
                "session_id": session.id,
                "user_id": session.user_id,
            },
            "payment_method_data": {
                "type": "sbp",
            },
        },
        idempotency_key,
    )

    txn = Transaction(
        session_id=session.id,
        user_id=session.user_id,
        amount=session.price,
        yookassa_payment_id=payment.id,
        status=PaymentStatus.WAITING,
        confirmation_url=payment.confirmation.confirmation_url,
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)

    logger.info("Created payment %s for session %s", payment.id, session.id)
    return txn


async def handle_payment_webhook(
    db: AsyncSession,
    yookassa_payment_id: str,
    yookassa_status: str,
) -> Transaction | None:
    """Process YooKassa webhook notification. Returns updated Transaction."""
    from sqlalchemy import select

    stmt = select(Transaction).where(
        Transaction.yookassa_payment_id == yookassa_payment_id,
    )
    result = await db.execute(stmt)
    txn = result.scalars().first()
    if not txn:
        logger.warning("Transaction not found for payment %s", yookassa_payment_id)
        return None

    session = await db.get(Session, txn.session_id)

    if yookassa_status == "succeeded":
        txn.status = PaymentStatus.PAID
        if session:
            session.status = SessionStatus.CONFIRMED
    elif yookassa_status in ("canceled", "cancelled"):
        txn.status = PaymentStatus.FAILED
        if session:
            session.status = SessionStatus.CANCELLED
    else:
        logger.info("Unhandled YooKassa status: %s", yookassa_status)
        return txn

    await db.commit()
    await db.refresh(txn)
    logger.info(
        "Payment %s status -> %s, session %s -> %s",
        yookassa_payment_id,
        txn.status.value,
        session.id if session else "?",
        session.status.value if session else "?",
    )
    return txn
