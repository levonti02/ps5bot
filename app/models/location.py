from sqlalchemy import ForeignKey, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Location(Base):
    __tablename__ = "locations"

    city_id: Mapped[int] = mapped_column(
        ForeignKey("cities.id", ondelete="CASCADE"), nullable=False,
    )
    address: Mapped[str] = mapped_column(String(256), nullable=False)
    entrance: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(String(512), default="")
    is_active: Mapped[bool] = mapped_column(default=True)

    city: Mapped["City"] = relationship(  # noqa: F821
        back_populates="locations",
    )
    consoles: Mapped[list["Console"]] = relationship(  # noqa: F821
        back_populates="location",
        lazy="selectin",
    )

    @property
    def full_address(self) -> str:
        return f"{self.city.name}, {self.address}, подъезд {self.entrance}"

    def __repr__(self) -> str:
        return f"<Location {self.address}, подъезд {self.entrance}>"
