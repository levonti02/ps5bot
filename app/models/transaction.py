import enum
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PaymentStatus(str, enum.Enum):
    NEW = "NEW"
    WAITING = "WAITING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUND = "REFUND"


class Transaction(Base):
    __tablename__ = "transactions"

    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # kopecks
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    yookassa_payment_id: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, index=True,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.NEW, nullable=False,
    )
    confirmation_url: Mapped[Optional[str]] = mapped_column(String(512))

    session: Mapped["Session"] = relationship(  # noqa: F821
        back_populates="transaction",
    )
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="transactions",
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction #{self.id} yookassa={self.yookassa_payment_id} "
            f"[{self.status.value}]>"
        )
