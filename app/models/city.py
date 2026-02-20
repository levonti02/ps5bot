from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class City(Base):
    __tablename__ = "cities"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    locations: Mapped[list["Location"]] = relationship(  # noqa: F821
        back_populates="city",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<City {self.name}>"
