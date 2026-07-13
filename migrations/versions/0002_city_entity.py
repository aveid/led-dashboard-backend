"""Промотирование города в сущность: таблица cities + screens.city_id (FK).

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-04

Что делает миграция (строго в порядке из задания Архитектора):
    1. CREATE TABLE cities (id, name unique, is_active, created_at).
    2. Сид известных областных центров (7 городов).
    3. ALTER screens ADD COLUMN city_id INTEGER NULL.
    4. Заполнить связь: screens.city_id = cities.id по совпадению названий.
    5. Guard: любой оставшийся город (которого нет в сиде) — INSERT в cities и
       повторный UPDATE. После этого city_id не должен содержать NULL, иначе
       миграция падает с явной ошибкой (не оставляем «висящие» экраны).
    6. ALTER COLUMN city_id SET NOT NULL + внешний ключ ON DELETE RESTRICT + индекс.
    7. ALTER TABLE screens DROP COLUMN city (со старым индексом ix_screens_city).

downgrade() выполняет обратные шаги без потери связей: возвращает строковую
колонку city, заполняет её из cities.name, снимает FK/индекс/city_id и удаляет
таблицу cities.

Написана вручную (в окружении нет сети для `alembic revision --autogenerate`),
зеркалирует features/cities/infrastructure/models.py и изменения ScreenModel.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Идентификаторы ревизии, используемые Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Областные центры Кыргызстана — стартовый справочник (Domain Core Dictionary).
_SEED_CITIES = [
    "Бишкек",
    "Ош",
    "Джалал-Абад",
    "Каракол",
    "Нарын",
    "Талас",
    "Баткен",
]


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Таблица городов. name — уникальный индекс (unique+index, как в модели).
    op.create_table(
        "cities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cities_name", "cities", ["name"], unique=True)

    # 2. Сид известных городов (id — автоинкремент, created_at — now() по умолчанию).
    bind.execute(
        sa.text("INSERT INTO cities (name, is_active) VALUES (:name, true)"),
        [{"name": name} for name in _SEED_CITIES],
    )

    # 3. Новая колонка-ссылка на город (пока NULL — заполним ниже).
    op.add_column("screens", sa.Column("city_id", sa.Integer(), nullable=True))

    # 4. Связываем экраны с городами по совпадению названия.
    op.execute("UPDATE screens s SET city_id = c.id FROM cities c WHERE s.city = c.name")

    # 5. Guard: города, встречающиеся у экранов, но отсутствующие в сиде, — заводим
    #    и повторно связываем. Затем проверяем, что не осталось экранов без города.
    op.execute(
        """
        INSERT INTO cities (name, is_active)
        SELECT DISTINCT s.city, true
        FROM screens s
        WHERE s.city IS NOT NULL AND btrim(s.city) <> ''
          AND NOT EXISTS (SELECT 1 FROM cities c WHERE c.name = s.city)
        """
    )
    op.execute(
        "UPDATE screens s SET city_id = c.id "
        "FROM cities c WHERE s.city = c.name AND s.city_id IS NULL"
    )
    orphans = bind.execute(
        sa.text("SELECT count(*) FROM screens WHERE city_id IS NULL")
    ).scalar_one()
    if orphans:
        raise RuntimeError(
            f"Миграция 0002 прервана: у {orphans} экран(ов) не удалось определить city_id "
            "(пустое или отсутствующее название города). Исправьте данные и повторите."
        )

    # 6. Теперь связь обязательна: NOT NULL + внешний ключ (RESTRICT) + индекс.
    op.alter_column("screens", "city_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "fk_screens_city", "screens", "cities", ["city_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_screens_city_id", "screens", ["city_id"])

    # 7. Старую строковую колонку city и её индекс удаляем.
    op.drop_index("ix_screens_city", table_name="screens")
    op.drop_column("screens", "city")


def downgrade() -> None:
    # Возвращаем строковую колонку city и наполняем её из справочника.
    op.add_column("screens", sa.Column("city", sa.String(length=120), nullable=True))
    op.execute("UPDATE screens s SET city = c.name FROM cities c WHERE s.city_id = c.id")
    op.alter_column("screens", "city", existing_type=sa.String(length=120), nullable=False)
    op.create_index("ix_screens_city", "screens", ["city"])

    # Снимаем связь на cities.
    op.drop_index("ix_screens_city_id", table_name="screens")
    op.drop_constraint("fk_screens_city", "screens", type_="foreignkey")
    op.drop_column("screens", "city_id")

    # Удаляем таблицу городов.
    op.drop_index("ix_cities_name", table_name="cities")
    op.drop_table("cities")
