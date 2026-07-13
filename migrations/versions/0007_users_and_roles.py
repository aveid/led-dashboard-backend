"""Таблица users + роли (RBAC, NFR-8) и bootstrap-админ.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-10

Что делает миграция:
    upgrade:
        1. CREATE TABLE users (id, username, password_hash, role, is_active,
           created_at). role — varchar(16) с CHECK IN ('admin','user'),
           server_default 'user'; is_active BOOLEAN server_default true.
        2. Функциональный UNIQUE-индекс ux_users_username_lower по lower(username):
           регистронезависимая уникальность логина (барьер БД под проверкой в репо).
        3. Bootstrap-админ (идемпотентный upsert из настроек INITIAL_ADMIN_*):
           если пользователя с таким логином нет — создаём с role='admin'; если
           есть — промоутим до admin+active. Гарантирует ≥1 администратора сразу
           после миграции, иначе раздел «Пользователи» оказался бы заблокирован
           (все прежние учётки без роли получили бы 'user'). Здесь это единственный
           путь сида (зафиксировано в BACKEND_CONTEXT.md).
    downgrade:
        DROP TABLE users (индекс и CHECK уходят вместе с таблицей).

Пароль bootstrap-админа хешируется тем же bcrypt-хешером, что и при логине
(config.security.hash_password) — второй хешер не заводим. Написана вручную (в
окружении нет сети для autogenerate), как и предыдущие ревизии.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from config.security import hash_password
from config.settings import get_settings

# Идентификаторы ревизии, используемые Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Таблица пользователей. role — строкой с CHECK-барьером; пароль только хешем.
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), server_default=sa.text("'user'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("role IN ('admin', 'user')", name="ck_users_role"),
    )

    # 2. Регистронезависимая уникальность логина (барьер БД под проверкой в репозитории).
    op.create_index(
        "ux_users_username_lower",
        "users",
        [sa.text("lower(username)")],
        unique=True,
    )

    # 3. Bootstrap-админ: идемпотентный upsert из настроек (без него — лок-аут раздела).
    settings = get_settings()
    username = settings.initial_admin_username.strip()
    password_hash = hash_password(settings.initial_admin_password)
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT id FROM users WHERE lower(username) = lower(:u)"),
        {"u": username},
    ).first()
    if existing is None:
        bind.execute(
            sa.text(
                "INSERT INTO users (username, password_hash, role, is_active) "
                "VALUES (:u, :h, 'admin', true)"
            ),
            {"u": username, "h": password_hash},
        )
    else:
        bind.execute(
            sa.text("UPDATE users SET role = 'admin', is_active = true WHERE id = :id"),
            {"id": existing.id},
        )


def downgrade() -> None:
    # Индекс и CHECK-ограничение удаляются вместе с таблицей.
    op.drop_table("users")
