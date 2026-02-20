import datetime
from typing import Optional

from sqlalchemy import BigInteger, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True,
    )
    username: Mapped[Optional[str]] = mapped_column(String(64))
    first_name: Mapped[Optional[str]] = mapped_column(String(128))
    last_name: Mapped[Optional[str]] = mapped_column(String(128))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    last_activity: Mapped[Optional[datetime.datetime]] = mapped_column()

    sessions: Mapped[list["Session"]] = relationship(  # noqa: F821
        back_populates="user",
        lazy="selectin",
    )
    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        back_populates="user",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User {self.telegram_id} @{self.username}>"
