"""Справочник типов экрана + поля screens.size / screens.screen_type_id.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-08

Что делает миграция (строго в порядке из инструкции Архитектора §3.3, зеркалит
features/screen_types/infrastructure/models.py и изменения ScreenModel):
    1. CREATE TABLE screen_types (id, name unique, code unique-nullable, created_at,
       updated_at).
    2. Сид 4 базовых типов (идемпотентно, upsert по code) — ДО backfill: тип
       «Вертикальный» (code='vertical') обязан существовать.
    3. ALTER screens ADD COLUMN size NULL, screen_type_id NULL + индекс на FK.
    4. Backfill старых строк: size = '', screen_type_id = id типа 'vertical'.
    5. Guard: если после backfill остались screen_type_id IS NULL — прерываемся с
       явной ошибкой (не оставляем «висящие» экраны).
    6. ALTER COLUMN: size → NOT NULL DEFAULT '', screen_type_id → NOT NULL + FK
       ON DELETE RESTRICT.

downgrade() выполняет обратные шаги: снимает FK/индекс/колонки screens и удаляет
таблицу screen_types. Ограничение NOT NULL снимается вместе с колонками; backfill
откатывать не требуется (данные уходят вместе со столбцами).

Написана вручную (в окружении нет сети для `alembic revision --autogenerate`),
как и предыдущие ревизии.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Идентификаторы ревизии, используемые Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Базовые типы экрана — стартовый справочник (name, code). Порядок вставки не важен.
_SEED_TYPES = [
    {"name": "Вертикальный", "code": "vertical"},
    {"name": "Горизонтальный", "code": "horizontal"},
    {"name": "Квадратный", "code": "square"},
    {"name": "Остановка", "code": "stop"},
]


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Таблица типов экрана. name — уникальный индекс; code — уникальный (nullable:
    #    в Postgres несколько NULL допускаются одним UNIQUE-индексом).
    op.create_table(
        "screen_types",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_screen_types_name", "screen_types", ["name"], unique=True)
    op.create_index("uq_screen_types_code", "screen_types", ["code"], unique=True)

    # 2. Сид базовых типов ДО backfill (идемпотентно: upsert по code).
    bind.execute(
        sa.text(
            "INSERT INTO screen_types (name, code) VALUES (:name, :code) "
            "ON CONFLICT (code) DO NOTHING"
        ),
        _SEED_TYPES,
    )

    # 3. Новые колонки экрана — сначала NULL, чтобы наполнить существующие строки.
    op.add_column("screens", sa.Column("size", sa.String(length=100), nullable=True))
    op.add_column("screens", sa.Column("screen_type_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_screens_screen_type_id", "screens", ["screen_type_id"])

    # 4. Backfill: пустой размер и перевод всех старых экранов на «Вертикальный».
    op.execute("UPDATE screens SET size = '' WHERE size IS NULL")
    op.execute(
        "UPDATE screens SET screen_type_id = "
        "(SELECT id FROM screen_types WHERE code = 'vertical') "
        "WHERE screen_type_id IS NULL"
    )

    # 5. Guard: не должно остаться экранов без типа (иначе NOT NULL ниже упадёт).
    orphans = bind.execute(
        sa.text("SELECT count(*) FROM screens WHERE screen_type_id IS NULL")
    ).scalar_one()
    if orphans:
        raise RuntimeError(
            f"Миграция 0005 прервана: у {orphans} экран(ов) не проставлен screen_type_id "
            "(не найден базовый тип 'vertical'?). Проверьте сиды и повторите."
        )

    # 6. Ограничения: size NOT NULL с DEFAULT '', screen_type_id NOT NULL + FK RESTRICT.
    op.alter_column(
        "screens", "size", existing_type=sa.String(length=100),
        nullable=False, server_default="",
    )
    op.alter_column(
        "screens", "screen_type_id", existing_type=sa.BigInteger(), nullable=False
    )
    op.create_foreign_key(
        "fk_screens_screen_type",
        "screens",
        "screen_types",
        ["screen_type_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # Снимаем связь screens → screen_types и новые колонки.
    op.drop_constraint("fk_screens_screen_type", "screens", type_="foreignkey")
    op.drop_index("ix_screens_screen_type_id", table_name="screens")
    op.drop_column("screens", "screen_type_id")
    op.drop_column("screens", "size")

    # Удаляем справочник типов.
    op.drop_index("uq_screen_types_code", table_name="screen_types")
    op.drop_index("ix_screen_types_name", table_name="screen_types")
    op.drop_table("screen_types")
