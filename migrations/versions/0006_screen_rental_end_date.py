"""Поле screens.rental_end_date — авто-архивация по истечению аренды (FR-4.4).

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-10

Что делает миграция (зеркалит ScreenModel.rental_end_date):
    upgrade:
        1. ADD COLUMN screens.rental_end_date DATE NULL (последний день аренды
           включительно; NULL — бессрочная аренда, экран не истекает). Безопасный
           бэкфилл: у всех существующих строк остаётся NULL, поэтому авто-архивация
           никого не тронет, пока дату не проставят вручную.
        2. (Опционально, но полезно) частичный индекс под предикат sweep:
           WHERE status = 'active' — bulk-UPDATE ищет только активные с истёкшей датой.
    downgrade:
        обратные шаги — снять индекс и колонку (данные уходят вместе со столбцом).

Написана вручную (в окружении нет сети для autogenerate), как и предыдущие ревизии.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Идентификаторы ревизии, используемые Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Новая колонка — nullable, без бэкфилла (NULL = бессрочная аренда).
    op.add_column(
        "screens",
        sa.Column("rental_end_date", sa.Date(), nullable=True),
    )

    # 2. Частичный индекс под sweep: ускоряет bulk-UPDATE активных с истёкшей датой.
    #    При low-load не критичен, но дёшев — оставляем.
    op.create_index(
        "ix_screens_active_expiry",
        "screens",
        ["rental_end_date"],
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("ix_screens_active_expiry", table_name="screens")
    op.drop_column("screens", "rental_end_date")
