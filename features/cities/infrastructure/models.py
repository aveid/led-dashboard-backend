"""models.py — ORM-модель города (таблица cities).

Владелец таблицы cities — этот модуль. Модуль screens ссылается на неё по
внешнему ключу (screens.city_id → cities.id) и держит обратную связь city.

Двунаправленная связь City.screens ↔ Screen.city настроена через back_populates.
Класс ScreenModel здесь НЕ импортируется в рантайме (это создало бы цикл, ведь
screens.models импортирует CityModel) — на него ссылаемся строкой "ScreenModel",
которую SQLAlchemy разрешает по общему реестру моделей во время конфигурации
мапперов. Для проверки типов класс подтягивается только под TYPE_CHECKING.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import Base

if TYPE_CHECKING:
    from features.screens.infrastructure.models import ScreenModel


class CityModel(Base):
    """Таблица городов (справочник областных центров)."""

    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    # Экраны этого города (обратная сторона Screen.city).
    screens: Mapped[list["ScreenModel"]] = relationship(back_populates="city")
