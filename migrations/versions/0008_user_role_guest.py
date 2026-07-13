"""Расширить CHECK на users.role третьей ролью 'guest' (RBAC).

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-10

Что делает миграция:
    upgrade:
        Роль хранится как varchar(16) с CHECK-констрейнтом (НЕ PG-enum), поэтому
        трогаем ТОЛЬКО ограничение, тип колонки не меняем. В миграции 0007
        констрейнт создан ЯВНО с именем `ck_users_role` (а не дефолтным
        `users_role_check`), поэтому дропаем именно его и пересоздаём с
        расширенным списком: role IN ('admin','user','guest').
    downgrade:
        Сначала безопасно перегоняем все guest-строки в 'user' (иначе новый
        суженный CHECK не пройдёт валидацию существующих строк и откат упадёт),
        затем возвращаем прежний CHECK role IN ('admin','user').

`server_default 'user'` для колонки не трогаем. Bootstrap-админ (0007) не трогаем.
Написана вручную (как и предыдущие ревизии — в окружении нет сети для autogenerate).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# Идентификаторы ревизии, используемые Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Имя CHECK-констрейнта — как задано явно в миграции 0007 (не дефолтное).
_CONSTRAINT = "ck_users_role"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "users", type_="check")
    op.create_check_constraint(
        _CONSTRAINT,
        "users",
        "role IN ('admin', 'user', 'guest')",
    )


def downgrade() -> None:
    # Безопасный откат: иначе суженный CHECK упадёт на существующих guest-строках.
    op.execute("UPDATE users SET role = 'user' WHERE role = 'guest'")
    op.drop_constraint(_CONSTRAINT, "users", type_="check")
    op.create_check_constraint(
        _CONSTRAINT,
        "users",
        "role IN ('admin', 'user')",
    )
