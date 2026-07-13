"""Вложения экрана: переход с file_url на object_key + метаданные файла.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-06

Что делает миграция (зеркалит новую AttachmentModel, см.
features/screens/infrastructure/models.py):
    1. ADD COLUMN object_key, original_filename, content_type, size_bytes (пока NULL).
    2. Бэкфилл существующих строк: object_key = file_url (как есть), остальные —
       безопасные заглушки (пустое имя, generic MIME, размер 0). Реальные значения
       появятся при следующих загрузках; старые ссылки file_url всё равно уже не
       используются (перешли на объектное хранилище/presign).
    3. SET NOT NULL на новые колонки + UNIQUE-индекс на object_key.
    4. DROP COLUMN file_url.

downgrade() возвращает file_url (наполняя его из object_key) и снимает новые колонки.

Написана вручную (в окружении нет сети для autogenerate), как и предыдущие ревизии.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Идентификаторы ревизии, используемые Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Новые колонки — сначала nullable, чтобы наполнить существующие строки.
    op.add_column("attachments", sa.Column("object_key", sa.String(length=512), nullable=True))
    op.add_column(
        "attachments", sa.Column("original_filename", sa.String(length=255), nullable=True)
    )
    op.add_column("attachments", sa.Column("content_type", sa.String(length=128), nullable=True))
    op.add_column("attachments", sa.Column("size_bytes", sa.BigInteger(), nullable=True))

    # 2. Бэкфилл: старую ссылку кладём в object_key как есть, метаданные — заглушки.
    op.execute(
        """
        UPDATE attachments
        SET object_key = file_url,
            original_filename = '',
            content_type = 'application/octet-stream',
            size_bytes = 0
        WHERE object_key IS NULL
        """
    )

    # 3. Теперь колонки обязательны; object_key уникален.
    op.alter_column("attachments", "object_key", existing_type=sa.String(length=512), nullable=False)
    op.alter_column(
        "attachments", "original_filename", existing_type=sa.String(length=255), nullable=False
    )
    op.alter_column(
        "attachments", "content_type", existing_type=sa.String(length=128), nullable=False
    )
    op.alter_column("attachments", "size_bytes", existing_type=sa.BigInteger(), nullable=False)
    op.create_index(
        "uq_attachments_object_key", "attachments", ["object_key"], unique=True
    )

    # 4. Старую колонку file_url удаляем.
    op.drop_column("attachments", "file_url")


def downgrade() -> None:
    # Возвращаем file_url и наполняем его из object_key.
    op.add_column("attachments", sa.Column("file_url", sa.String(length=500), nullable=True))
    op.execute("UPDATE attachments SET file_url = object_key WHERE file_url IS NULL")
    op.alter_column("attachments", "file_url", existing_type=sa.String(length=500), nullable=False)

    # Снимаем новые колонки и уникальный индекс.
    op.drop_index("uq_attachments_object_key", table_name="attachments")
    op.drop_column("attachments", "size_bytes")
    op.drop_column("attachments", "content_type")
    op.drop_column("attachments", "original_filename")
    op.drop_column("attachments", "object_key")
