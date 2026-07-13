"""models.py — ORM-модель типа экрана (таблица screen_types).

Владелец таблицы screen_types — этот модуль. Модуль screens ссылается на неё по
внешнему ключу (screens.screen_type_id → screen_types.id).

Связь односторонняя: у ScreenModel есть relationship screen_type (для отдачи
развёрнутого объекта в ответе), а обратной коллекции screens у ScreenTypeModel
нет — числом ссылок управляет репозиторий типов через COUNT-запрос при удалении.
Так этот модуль не импортирует ScreenModel и цикла импорта не возникает.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class ScreenTypeModel(Base):
    """Таблица типов экрана (управляемый справочник)."""

    __tablename__ = "screen_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Отображаемое имя: обязательное, уникальное (регистрозависимый барьер БД;
    # регистронезависимую проверку дублирует репозиторий).
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    # Машинный код: необязательный; уникальный, если задан (в Postgres несколько
    # NULL допускаются одним UNIQUE-индексом).
    code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
