"""Начальная схема БД: landlords, campaigns, contacts, screens, rental_contracts,
attachments, screen_campaigns.

Revision ID: 0001
Revises:
Create Date: 2026-07-03

Написана вручную (зеркалирует features/*/infrastructure/models.py), т.к. в среде
разработки не было сети/БД для запуска `alembic revision --autogenerate`. Порядок
создания таблиц учитывает внешние ключи: сначала независимые справочники
(landlords, campaigns, contacts), затем screens, затем то, что ссылается на screens
(rental_contracts, attachments, screen_campaigns).

Перед применением на БД должно быть включено расширение PostGIS — эта миграция
включает его сама (CREATE EXTENSION IF NOT EXISTS postgis).
"""

from __future__ import annotations

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

# Идентификаторы ревизии, используемые Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostGIS нужен для геометрической колонки screens.location.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # --- Независимые справочники (без внешних ключей на другие наши таблицы) ---
    op.create_table(
        "landlords",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("contact_person", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Экраны (центральная таблица; ссылается на landlords и contacts) ---
    op.create_table(
        "screens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("district", sa.String(length=120), nullable=False),
        sa.Column("street", sa.String(length=255), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("landlord_id", sa.Uuid(), nullable=True),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["landlord_id"], ["landlords.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Пространственный индекс (GIST) — без него запросы по координатам будут
    # делать полный перебор таблицы. geoalchemy2 не создаёт его автоматически
    # при management=False (используемом здесь), поэтому добавляем явно.
    op.execute("CREATE INDEX ix_screens_location ON screens USING GIST (location)")
    # Индексы под частые фильтры (FR-5): по арендодателю, статусу, городу.
    op.create_index("ix_screens_landlord_id", "screens", ["landlord_id"])
    op.create_index("ix_screens_status", "screens", ["status"])
    op.create_index("ix_screens_city", "screens", ["city"])

    # --- Договоры аренды — история (Q3), ссылаются на screens ---
    op.create_table(
        "rental_contracts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("screen_id", sa.Uuid(), nullable=False),
        sa.Column("rent_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["screen_id"], ["screens.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rental_contracts_screen_id", "rental_contracts", ["screen_id"])
    # Индекс под фильтр «договор заканчивается до даты» (FR-5.5) и сводку «скоро
    # заканчиваются» (FR-9.5).
    op.create_index("ix_rental_contracts_end_date", "rental_contracts", ["end_date"])

    # --- Вложения (фото/договоры/документы), ссылаются на screens ---
    op.create_table(
        "attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("screen_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("file_url", sa.String(length=500), nullable=False),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["screen_id"], ["screens.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attachments_screen_id", "attachments", ["screen_id"])

    # --- Таблица-связка «экран ↔ кампания» (M2M, задел на несколько — Q4) ---
    op.create_table(
        "screen_campaigns",
        sa.Column("screen_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["screen_id"], ["screens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("screen_id", "campaign_id"),
    )


def downgrade() -> None:
    # Удаляем в обратном порядке создания (сначала то, что ссылается на другие).
    op.drop_table("screen_campaigns")
    op.drop_index("ix_attachments_screen_id", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("ix_rental_contracts_end_date", table_name="rental_contracts")
    op.drop_index("ix_rental_contracts_screen_id", table_name="rental_contracts")
    op.drop_table("rental_contracts")
    op.drop_index("ix_screens_city", table_name="screens")
    op.drop_index("ix_screens_status", table_name="screens")
    op.drop_index("ix_screens_landlord_id", table_name="screens")
    op.execute("DROP INDEX IF EXISTS ix_screens_location")
    op.drop_table("screens")
    op.drop_table("contacts")
    op.drop_table("campaigns")
    op.drop_table("landlords")
    # Расширение postgis не удаляем — им могут пользоваться другие схемы/объекты.
