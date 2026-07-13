"""models.py — ORM-модель пользователя (таблица users).

Владелец таблицы users — этот модуль. Уникальность логина — регистронезависимая:
барьер БД — функциональный UNIQUE-индекс по lower(username) (заводится миграцией
0007), а репозиторий дублирует проверку через func.lower. Роль хранится строкой
(значение UserRole) с CHECK-ограничением на уровне БД (см. миграцию).

Пароль хранится ТОЛЬКО хешем (password_hash); наружу (в схемах ответа) он никогда
не отдаётся.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class UserModel(Base):
    """Таблица пользователей системы (учётки с ролью для RBAC, NFR-8)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Логин: непустой. Уникальность регистронезависима — обеспечивается
    # функциональным UNIQUE-индексом ux_users_username_lower (в миграции 0007),
    # поэтому column-level unique здесь НЕ ставим.
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Роль строкой ("admin"|"user"); CHECK-ограничение и server_default — в миграции.
    role: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'user'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
