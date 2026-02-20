import enum

from sqlalchemy import ForeignKey, String, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ConsoleStatus(str, enum.Enum):
    FREE = "FREE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


class Console(Base):
    __tablename__ = "consoles"

    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "PS1"
    code: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True,
    )  # unique code for QR deep-link, e.g. "ps_001"
    status: Mapped[ConsoleStatus] = mapped_column(
        Enum(ConsoleStatus), default=ConsoleStatus.FREE, nullable=False,
    )
    shelly_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    location: Mapped["Location"] = relationship(  # noqa: F821
        back_populates="consoles",
    )
    sessions: Mapped[list["Session"]] = relationship(  # noqa: F821
        back_populates="console",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Console {self.name} [{self.status.value}]>"
