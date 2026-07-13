"""Удаление колонок district/street из таблицы screens (FR-3.3).

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-08

Что делает миграция (зеркалит новую ScreenModel, см.
features/screens/infrastructure/models.py):
    Убирает текстовый адрес экрана (район/улица) — расположение экрана теперь
    задаётся только точкой на карте (PostGIS-колонка location, POINT 4326).
    Меняется через новый эндпоинт PATCH /api/screens/{id}/location.

⚠️ Данные district/street будут ПОТЕРЯНЫ (destructive). Если бизнес попросит
сохранить — заархивировать значения до применения ревизии.

downgrade() возвращает колонки в исходном виде (NOT NULL, server_default '' —
чтобы существующие строки прошли ограничение NOT NULL). Геометрия не трогается,
поэтому маркеры не «переезжают».

Написана вручную (в окружении нет сети для autogenerate), как и предыдущие ревизии.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Идентификаторы ревизии, используемые Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Порядок обратный созданию (сначала street, потом district) — не обязателен,
    # но симметричен downgrade и исходной ревизии 0001.
    op.drop_column("screens", "street")
    op.drop_column("screens", "district")


def downgrade() -> None:
    # Возвращаем колонки как в 0001: NOT NULL с пустым значением по умолчанию,
    # чтобы существующие строки удовлетворяли ограничению NOT NULL.
    op.add_column(
        "screens",
        sa.Column(
            "district",
            sa.String(length=120),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "screens",
        sa.Column(
            "street",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
    )
    # Снимаем server_default: в исходной схеме значение по умолчанию задаётся на
    # уровне приложения (ORM default=""), а не на уровне БД.
    op.alter_column("screens", "district", server_default=None)
    op.alter_column("screens", "street", server_default=None)
