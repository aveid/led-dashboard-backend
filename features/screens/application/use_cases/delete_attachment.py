"""delete_attachment.py — сценарий «Удалить вложение экрана» (FR-3.12/3.13).

За что отвечает: удаляет и объект из хранилища, и строку вложения в БД. Проверяет,
что вложение действительно принадлежит указанному экрану (иначе 404) — так нельзя
удалить чужое вложение, зная только его id.

Порядок шагов:
    1. Загрузить экран (иначе 404).
    2. Найти вложение среди его attachments; нет ИЛИ чужой screen_id — 404.
    3. Удалить строку вложения из БД (repo.delete_attachment) — БД источник правды.
    4. Best-effort удалить объект из хранилища (storage.delete): ошибку логируем,
       но ответ не роняем (осиротевший объект в MinIO безвреден — presigned-ссылки
       на него уже нет).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from core.application.storage import FileStorage
from core.application.use_case import UseCase
from core.domain.exceptions import NotFoundError
from features.screens.domain.repositories import ScreenRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeleteAttachmentInput:
    """Входные данные сценария удаления вложения: экран и вложение."""

    screen_id: UUID
    attachment_id: UUID


class DeleteAttachmentUseCase(UseCase[DeleteAttachmentInput, None]):
    """Удаляет вложение экрана из хранилища и из БД."""

    def __init__(self, repository: ScreenRepository, storage: FileStorage) -> None:
        """Внедряем репозиторий и хранилище через конструктор (DIP)."""
        self._repository = repository
        self._storage = storage

    def execute(self, data: DeleteAttachmentInput) -> None:
        """Проверить принадлежность вложения экрану, удалить из БД и (best-effort) S3."""
        screen = self._repository.get_by_id(data.screen_id)

        # Ищем вложение ТОЛЬКО среди вложений этого экрана: так нельзя удалить чужое
        # вложение, зная лишь его id и подставив произвольный screen_id (→ 404).
        attachment = next(
            (a for a in screen.attachments if a.id == data.attachment_id), None
        )
        if attachment is None:
            raise NotFoundError(
                f"Вложение id={data.attachment_id} не найдено у экрана id={data.screen_id}."
            )

        # БД — источник правды: сначала удаляем строку (идемпотентно).
        self._repository.delete_attachment(data.attachment_id)

        # Затем best-effort убираем объект из хранилища. Ошибку S3 логируем, но не
        # роняем ответ: строка уже удалена, presigned-ссылки на объект больше нет,
        # осиротевший объект в бакете безвреден.
        try:
            self._storage.delete(attachment.object_key)
        except Exception:  # noqa: BLE001 — намеренно best-effort: любой сбой S3 не должен ломать удаление
            logger.warning(
                "Не удалось удалить объект '%s' из хранилища после удаления вложения "
                "id=%s (осиротевший объект безвреден).",
                attachment.object_key,
                data.attachment_id,
                exc_info=True,
            )
