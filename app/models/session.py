import datetime
import enum
from typing import Optional

from sqlalchemy import (
    ForeignKey,
    Integer,
    Enum,
    DateTime,
    Index,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SessionStatus(str, enum.Enum):
    HOLD = "HOLD"            # slot reserved, waiting for payment (10 min)
    CONFIRMED = "CONFIRMED"  # paid, waiting for activation
    ACTIVE = "ACTIVE"        # session is running, power ON
    COMPLETED = "COMPLETED"  # finished normally
    NO_SHOW = "NO_SHOW"      # user didn't activate within window
    CANCELLED = "CANCELLED"  # cancelled by user or timeout


class SessionType(str, enum.Enum):
    INSTANT = "INSTANT"      # "play now"
    BOOKING = "BOOKING"      # advance booking


class Session(Base):
    __tablename__ = "sessions"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    console_id: Mapped[int] = mapped_column(
        ForeignKey("consoles.id", ondelete="CASCADE"), nullable=False,
    )
    session_type: Mapped[SessionType] = mapped_column(
        Enum(SessionType), nullable=False,
    )
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), default=SessionStatus.HOLD, nullable=False,
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)  # in kopecks (rub * 100)

    slot_start: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    slot_end: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    activated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
    )
    hold_until: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
    )

    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="sessions",
    )
    console: Mapped["Console"] = relationship(  # noqa: F821
        back_populates="sessions",
    )
    transaction: Mapped[Optional["Transaction"]] = relationship(  # noqa: F821
        back_populates="session",
        uselist=False,
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_sessions_console_slot",
            "console_id",
            "slot_start",
            "slot_end",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Session #{self.id} console={self.console_id} "
            f"{self.slot_start}–{self.slot_end} [{self.status.value}]>"
        )
