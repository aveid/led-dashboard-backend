"""models.py — ORM-модель арендодателя (таблица landlords).

Владелец таблицы landlords — этот модуль. Модуль screens ссылается на неё по
внешнему ключу (по имени таблицы 'landlords.id'), не импортируя эту модель.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class LandlordModel(Base):
    """Таблица арендодателей (FR-8)."""

    __tablename__ = "landlords"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    contact_person: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
