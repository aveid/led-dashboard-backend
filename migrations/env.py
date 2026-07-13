"""env.py — окружение Alembic для генерации и применения миграций.

За что отвечает:
    • берёт строку подключения к БД из настроек приложения (.env);
    • подключает метаданные всех ORM-моделей, чтобы autogenerate видел таблицы;
    • пропускает служебные таблицы PostGIS (например, spatial_ref_sys), которые
      создаёт само расширение, а не наше приложение.

Команды:
    alembic revision --autogenerate -m "init"   # сгенерировать миграцию
    alembic upgrade head                          # применить миграции
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from config.database import Base
from config.settings import get_settings

# Импортируем модули моделей, чтобы они зарегистрировались в Base.metadata.
# Порядок неважен для метаданных, но landlords/campaigns не зависят от screens,
# а screens ссылается на их таблицы по имени (ForeignKey строкой) — цикла импорта нет.
import features.campaigns.infrastructure.models  # noqa: F401
import features.cities.infrastructure.models  # noqa: F401
import features.landlords.infrastructure.models  # noqa: F401
import features.screen_types.infrastructure.models  # noqa: F401
import features.screens.infrastructure.models  # noqa: F401
import features.users.infrastructure.models  # noqa: F401

config = context.config

# Строку подключения берём из настроек приложения (единый источник).
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные, по которым Alembic сравнивает состояние БД и моделей.
target_metadata = Base.metadata

# Служебные таблицы PostGIS, которые не нужно включать в миграции.
_POSTGIS_TABLES = {"spatial_ref_sys"}


def include_object(obj, name, type_, reflected, compare_to):  # type: ignore[no-untyped-def]
    """Исключает служебные таблицы PostGIS из автогенерации миграций."""
    if type_ == "table" and name in _POSTGIS_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    """Генерация SQL без подключения к БД (режим offline)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Применение миграций с подключением к БД (обычный режим)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
